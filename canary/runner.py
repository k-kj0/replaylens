"""Run every task against every provider, one request at a time."""
from __future__ import annotations

import os
import sys
import time

from .client import call_provider
from .grade import GraderShapeError, grade


def build_messages(task):
    prompt = task.get("prompt")
    if not (isinstance(prompt, dict) and "system" in prompt and "user" in prompt):
        raise GraderShapeError("prompt is not an object with system and user")
    return [{"role": "system", "content": prompt["system"]},
            {"role": "user", "content": prompt["user"]}]


def usable_providers(providers):
    ok = []
    for p in providers:
        if os.environ.get(p.get("key_env", "")):
            ok.append(p)
        else:
            print("skipping %s: environment variable %s is not set" % (p["name"], p.get("key_env")),
                  file=sys.stderr)
    return ok


def run_once(tasks, providers, dataset_id, call=call_provider, timeout_s=20.0):
    """Paired rounds: for each task every provider is called once, launch order rotates."""
    run_id = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    per = {p["name"]: [] for p in providers}
    n = len(providers)
    for i, task in enumerate(tasks):
        messages = build_messages(task)
        for p in providers[i % n:] + providers[:i % n]:
            r = call(p, messages, timeout_s)
            ok, why = False, r["fail"] or "unknown"
            if r["fail"] is None:
                ok, why = grade(task, r["text"])
            per[p["name"]].append({
                "id": task.get("id"), "ok": bool(ok), "fail": r["fail"], "why": why,
                "e2e_ms": None if r["fail"] else r["e2e_ms"],
                "ttft_ms": None if r["fail"] else r["ttft_ms"],
                "ttv_ms": None if r["fail"] else r["ttv_ms"],
            })
    return [{
        "run_id": run_id, "ts": ts, "provider": p["name"], "model": p["model"],
        "dataset_id": dataset_id,
        "protocol": {"temperature": 0, "top_p": 1, "max_tokens": 256, "timeout_s": timeout_s,
                     "retries": 0, "concurrency": 1, "json_mode": True, "stream": True},
        "tasks": per[p["name"]],
    } for p in providers]
