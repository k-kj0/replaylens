import json

def load_runs(path):
    """Same as recorder.load_runs, but gives rows without an id their line index."""
    runs = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                row = json.loads(line)
                row.setdefault("id", len(runs))
                runs.append(row)
    return runs

def normalize(run):
    return {
        "id": run.get("id"),
        "input": run.get("input", ""),
        "output": run.get("output", ""),
        "tool_calls": run.get("tool_calls") or [],
        "model": run.get("model", "unknown"),
        "cost": run.get("cost_usd", 0.0),
        "latency": (run.get("latency_ms") or 0) / 1000.0,   # seconds
        "tokens_in": run.get("tokens_in", 0),
        "tokens_out": run.get("tokens_out", 0),
        "error": run.get("error"),
    }
