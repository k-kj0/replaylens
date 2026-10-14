import json

def load_runs(path):
    runs = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                runs.append(json.loads(line))
    return runs

def _pick(run, *names, default=None):
    for n in names:
        if run.get(n) is not None:
            return run[n]
    return default

def normalize(run):
    """EDIT THE KEY NAMES HERE to match what recorder.py writes."""
    return {
        "id": _pick(run, "id", "run_id"),
        "input": _pick(run, "input", "question", "prompt", "user_message", default=""),
        "output": _pick(run, "output", "answer", "response", "final", default=""),
        "tool_calls": _pick(run, "tool_calls", "tools", "calls", default=[]),
        "model": _pick(run, "model", default="unknown"),
        "cost": _pick(run, "cost", "cost_usd", default=0.0),
        "latency": _pick(run, "latency", "latency_s", "duration", default=0.0),
    }
