"""Make a large SYNTHETIC ReplayLens report for dashboard performance testing.

Usage:
    python scripts/make_big_report.py 5000

Writes big_report.json with N generated runs in the same shape the dashboard
loads (summary + results). The rows are generated test data, not real agent
runs. Describe it as a synthetic stress-test report on a resume.
"""
import json
import random
import sys

n = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
random.seed(42)

TOPICS = ["refund policy", "order tracking", "password reset", "insurance claim",
          "shipping delay", "invoice copy", "plan upgrade", "account closure"]
STATUSES = ["same"] * 70 + ["improved"] * 10 + ["changed"] * 15 + ["regression"] * 5


def run(topic, tone):
    return {
        "output": f"Here is the {tone} answer about {topic}. " * random.randint(3, 8),
        "tool_calls": [{"name": "lookup", "args": {"topic": topic, "id": random.randint(1000, 9999)}}],
        "error": None,
        "latency_ms": random.randint(300, 1800),
        "cost_usd": round(random.uniform(0.0005, 0.004), 5),
    }


results = []
for i in range(n):
    topic = random.choice(TOPICS)
    status = random.choice(STATUSES)
    results.append({
        "input": f"Customer question {i + 1}: help me with my {topic}",
        "status": status,
        "reasons": ["Required tool call missing in new run"] if status == "regression" else [],
        "old": run(topic, "previous"),
        "new": run(topic, "current"),
    })

count = {s: sum(1 for r in results if r["status"] == s) for s in ("same", "improved", "changed", "regression")}
old_lat = sum(r["old"]["latency_ms"] for r in results) / n
new_lat = sum(r["new"]["latency_ms"] for r in results) / n
old_cost = sum(r["old"]["cost_usd"] for r in results)
new_cost = sum(r["new"]["cost_usd"] for r in results)

report = {
    "old_label": "synthetic-model / v1.txt",
    "new_label": "synthetic-model / v2.txt",
    "summary": {
        "total_runs": n,
        "same": count["same"],
        "improved": count["improved"],
        "changed": count["changed"],
        "regressions": count["regression"],
        "cost_change_pct": round((new_cost - old_cost) / old_cost * 100, 1),
        "latency_change_pct": round((new_lat - old_lat) / old_lat * 100, 1),
        "new_avg_latency_ms": round(new_lat),
        "safe_to_ship": count["regression"] == 0,
    },
    "results": results,
}

with open("big_report.json", "w", encoding="utf-8") as f:
    json.dump(report, f)

print(f"Wrote big_report.json with {n} synthetic runs")
