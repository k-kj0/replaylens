"""Import transcripts (one JSON per line: {"user":..., "agent":..., "tool_calls":[...]})
Usage: python -m replaylens.transcripts logs.jsonl runs.jsonl"""
import json
import sys

from .recorder import make_row


def convert(src, dst, model="imported", prompt_version="imported"):
    n = 0
    with open(src, encoding="utf-8") as f, open(dst, "a", encoding="utf-8") as out:
        for line in f:
            if not line.strip():
                continue
            t = json.loads(line)
            res = {"output": t.get("agent", ""), "tool_calls": t.get("tool_calls", []),
                   "tokens_in": t.get("tokens_in", 0), "tokens_out": t.get("tokens_out", 0)}
            row = make_row(t["user"], res, model, prompt_version,
                           int(t.get("latency_ms", 0)), 0.0, 0.0)
            out.write(json.dumps(row) + "\n")
            n += 1
    print(f"imported {n} rows into {dst}")


if __name__ == "__main__":
    convert(sys.argv[1], sys.argv[2])
