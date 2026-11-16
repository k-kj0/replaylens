"""Fetch the public Openbenchmarks microtasks at run time.

The dataset has no license recorded, so rows are never saved into this repo.
Only task ids, pass/fail flags and timings are stored.
"""
from __future__ import annotations

import hashlib
import json
import urllib.request

BASE = "https://huggingface.co/datasets/openbenchmarks/OB-Inference-Microtasks/resolve/main/"
FILES = ["contract-terms-extraction.jsonl", "meeting-notes-lookup.jsonl", "ticket-triage.jsonl"]


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "replaylens-canary/0.1"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def load_tasks(base=BASE, files=FILES):
    """Return (tasks, dataset_id). dataset_id changes if any file changes."""
    tasks, parts = [], []
    for name in files:
        raw = base.rstrip("/") + "/" + name
        data = _get(raw) if raw.startswith("http") else open(raw, "rb").read()
        parts.append("%s:%s" % (name, hashlib.sha256(data).hexdigest()))
        for line in data.decode("utf-8").splitlines():
            if line.strip():
                tasks.append(json.loads(line))
    tasks.sort(key=lambda t: str(t.get("id")))
    dataset_id = hashlib.sha256("\n".join(parts).encode()).hexdigest()[:12]
    return tasks, dataset_id


def describe(value, depth=0):
    """Shape of a value without dumping its content (for the inspect command)."""
    if isinstance(value, dict):
        pad = "  " * (depth + 1)
        inner = "\n".join("%s%s: %s" % (pad, k, describe(v, depth + 1)) for k, v in value.items())
        return "object\n" + inner
    if isinstance(value, list):
        return "list[%d]" % len(value)
    if isinstance(value, str):
        return "str(%d chars)" % len(value)
    return type(value).__name__ + " " + repr(value)[:20]
