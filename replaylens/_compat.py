import json


def load_runs(path):
    runs = []
    with open(path, encoding="utf-8") as f:
        for i, line in enumerate(l for l in f if l.strip()):
            row = json.loads(line)
            row["id"] = i            # recorder.py writes no id, so use line number (int)
            runs.append(row)
    return runs


def normalize(run):
    """Matches the row format written by recorder.make_row()."""
    return {
        "id": str(run.get("id", "")),
        "ts": run.get("ts", ""),
        "input": run.get("input", ""),
        "output": run.get("output", ""),
        "tool_calls": run.get("tool_calls") or [],
        "model": run.get("model", "unknown"),
        "prompt_version": run.get("prompt_version", ""),
        "cost": float(run.get("cost_usd") or 0.0),
        "latency": float(run.get("latency_ms") or 0) / 1000.0,   # seconds
        "tokens_in": int(run.get("tokens_in") or 0),
        "tokens_out": int(run.get("tokens_out") or 0),
        "error": run.get("error"),
    }
