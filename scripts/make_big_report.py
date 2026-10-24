"""Make a big ReplayLens report for performance testing.

Usage (run from the replaylens folder):
    python scripts/make_big_report.py 5000

It finds an existing report (a .json file with "summary" and "results"),
repeats its rows until there are N rows, and saves big_report.json.
"""
import glob
import json
import sys

n = int(sys.argv[1]) if len(sys.argv) > 1 else 5000

source = None
for path in glob.glob("**/*.json", recursive=True):
    if any(skip in path for skip in (".venv", "node_modules", ".git")):
        continue
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        continue
    if isinstance(data, dict) and "summary" in data and isinstance(data.get("results"), list) and data["results"]:
        source = path
        break

if source is None:
    sys.exit("No report with 'summary' and 'results' found. Put one report .json in this folder and retry.")

rows = data["results"]
big = [json.loads(json.dumps(rows[i % len(rows)])) for i in range(n)]
data["results"] = big

with open("big_report.json", "w", encoding="utf-8") as f:
    json.dump(data, f)

print(f"Used {source}: wrote big_report.json with {n} rows")
