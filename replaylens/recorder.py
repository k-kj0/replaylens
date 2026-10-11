"""RECORD: wrap your agent function with @record and every run is saved as one line in runs.jsonl."""
import functools
import json
import os
import time
from datetime import datetime, timezone

DEFAULT_FILE = os.environ.get("REPLAYLENS_FILE", "runs.jsonl")


def cost_usd(tokens_in, tokens_out, price_in, price_out):
    """Prices are dollars per 1 million tokens."""
    return round((tokens_in * price_in + tokens_out * price_out) / 1_000_000, 8)


def record(path=None, prompt_version="v1", price_in=0.0, price_out=0.0):
    """Decorator. Your agent must look like:

        def my_agent(user_input, *, model, system_prompt) -> dict

    and return {"output": str, "tool_calls": [{"name":..., "arguments": {...}}],
                "tokens_in": int, "tokens_out": int}
    """

    def wrap(fn):
        @functools.wraps(fn)
        def inner(user_input, *, model, system_prompt, **kw):
            start = time.perf_counter()
            error = None
            try:
                res = fn(user_input, model=model, system_prompt=system_prompt, **kw)
            except Exception as exc:  # a crash is also worth recording
                res = {"output": "", "tool_calls": [], "tokens_in": 0, "tokens_out": 0}
                error = f"{type(exc).__name__}: {exc}"
            latency_ms = int((time.perf_counter() - start) * 1000)
            row = make_row(user_input, res, model, prompt_version, latency_ms,
                           price_in, price_out, error)
            with open(path or DEFAULT_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(row) + "\n")
            return res

        return inner

    return wrap


def make_row(user_input, res, model, prompt_version, latency_ms, price_in, price_out, error=None):
    t_in, t_out = int(res.get("tokens_in", 0)), int(res.get("tokens_out", 0))
    return {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "input": user_input,
        "output": res.get("output", ""),
        "tool_calls": res.get("tool_calls", []),
        "model": model,
        "prompt_version": prompt_version,
        "latency_ms": latency_ms,
        "tokens_in": t_in,
        "tokens_out": t_out,
        "price_in": price_in,
        "price_out": price_out,
        "cost_usd": cost_usd(t_in, t_out, price_in, price_out),
        "error": error,
    }


def load_runs(path):
    runs = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                runs.append(json.loads(line))
    return runs
