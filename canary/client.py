"""Streaming client for OpenAI-compatible chat endpoints (standard library only)."""
from __future__ import annotations

import http.client
import json
import os
import socket
import time
from urllib.parse import urlparse


def _result(**kw):
    base = {"fail": None, "detail": None, "text": "", "e2e_ms": None, "ttft_ms": None, "ttv_ms": None}
    base.update(kw)
    return base


def _ensure_json_mention(messages):
    """Groq requires the word 'json' in messages whenever response_format=json_object is enabled."""
    has_json = any("json" in (m.get("content") or "").lower() for m in messages)
    if has_json:
        return messages
    updated = [dict(m) for m in messages]
    if updated and updated[0].get("role") == "system":
        updated[0]["content"] = updated[0]["content"].rstrip() + "\nRespond in valid JSON."
    else:
        updated.insert(0, {"role": "system", "content": "Respond in valid JSON."})
    return updated


def call_provider(provider, messages, timeout_s=20.0, max_tokens=256):
    """One request, no retries. fail is None or timeout, http_429, http_4xx, http_5xx, transport."""
    url = urlparse(provider["base_url"].rstrip("/") + "/chat/completions")
    cls = http.client.HTTPSConnection if url.scheme == "https" else http.client.HTTPConnection
    key = os.environ.get(provider.get("key_env", ""), "").strip()
    prepared_messages = _ensure_json_mention(messages)

    body = json.dumps({
        "model": provider["model"],
        "messages": prepared_messages,
        "temperature": 0,
        "top_p": 1,
        "presence_penalty": 0,
        "frequency_penalty": 0,
        "max_tokens": max_tokens,
        "stream": True,
        "response_format": {"type": "json_object"},
    })
    start = time.perf_counter()
    deadline = start + timeout_s
    conn = None
    try:
        conn = cls(url.hostname, url.port, timeout=timeout_s)
        conn.request("POST", url.path, body=body, headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + key,
            "User-Agent": "replaylens-canary/0.1",
        })
        resp = conn.getresponse()
        if resp.status != 200:
            err_body = resp.read().decode("utf-8", "replace")[:300]
            if resp.status == 429:
                return _result(fail="http_429", detail=f"429: {err_body}")
            code_type = "http_5xx" if resp.status >= 500 else "http_4xx"
            return _result(fail=code_type, detail=f"{resp.status}: {err_body}")

        text, ttft, ttv = [], None, None
        while True:
            remaining = deadline - time.perf_counter()
            if remaining <= 0:
                return _result(fail="timeout")
            conn.sock.settimeout(remaining)
            line = resp.readline()
            if not line:
                break
            line = line.decode("utf-8", "replace").strip()
            if not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if payload == "[DONE]":
                break
            try:
                delta = json.loads(payload)["choices"][0].get("delta") or {}
            except (ValueError, KeyError, IndexError, TypeError):
                continue
            content = delta.get("content") or ""
            thinking = delta.get("reasoning_content") or delta.get("reasoning") or ""
            now = (time.perf_counter() - start) * 1000
            if (content or thinking) and ttft is None:
                ttft = now
            if content and ttv is None:
                ttv = now
            text.append(content)
        return _result(text="".join(text), e2e_ms=(time.perf_counter() - start) * 1000,
                       ttft_ms=ttft, ttv_ms=ttv)
    except (socket.timeout, TimeoutError):
        return _result(fail="timeout")
    except (OSError, http.client.HTTPException) as exc:
        return _result(fail="transport", detail=str(exc)[:200])
    finally:
        if conn is not None:
            conn.close()
