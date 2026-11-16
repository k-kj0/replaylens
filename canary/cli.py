from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .data import BASE, describe, load_tasks
from .drift import evaluate, latest_summary, replay_alarm_rate
from .runner import run_once, usable_providers
from .stats import min_discordant

RESULTS = "canary/data/results.jsonl"
PROVIDERS = "canary/providers.json"


def read_rows(path):
    p = Path(path)
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]


def markdown(rows, baseline_n, alpha):
    lines = ["# Canary check", ""]
    for s in latest_summary(rows):
        lines.append("- **%s** (%s): %d of %d tasks correct (95%% CI %.0f%% to %.0f%%), "
                     "median end to end %s ms, %d request failures, %d runs on this dataset version"
                     % (s["provider"], s["model"], s["ok"], s["n"], s["low"] * 100, s["high"] * 100,
                        "n/a" if s["p50_ms"] is None else "%.0f" % s["p50_ms"], s["failures"], s["runs"]))
    findings = evaluate(rows, baseline_n, alpha)
    lines += ["", "## Drift against the first %d runs" % baseline_n, ""]
    if not findings:
        lines.append("Still collecting the baseline. No comparison yet.")
    for f in findings:
        mark = "DRIFT" if f["flagged"] else "ok"
        lines.append("- [%s] %s, %s: %s (p = %.3f, Holm adjusted p = %.3f)"
                     % (mark, f["provider"], f["signal"], f["detail"], f["p"], f["p_adj"]))
    lines += ["", "With only %d tasks changing, McNemar cannot reach p < %.2f; at least %d tasks must change."
              % (min_discordant(alpha) - 1, alpha, min_discordant(alpha))]
    return "\n".join(lines) + "\n", findings


def main(argv=None):
    ap = argparse.ArgumentParser(prog="canary")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("inspect", help="print the shape of the first row of each dataset file")
    r = sub.add_parser("run", help="run every task against every provider and append results")
    r.add_argument("--providers", default=PROVIDERS)
    r.add_argument("--out", default=RESULTS)
    r.add_argument("--base", default=BASE, help="dataset base URL or local folder")
    r.add_argument("--timeout", type=float, default=20.0)
    c = sub.add_parser("check", help="compare the newest run to the baseline; exit code 2 on drift")
    c.add_argument("--results", default=RESULTS)
    c.add_argument("--out", default="canary/data/last_check.md")
    c.add_argument("--baseline-runs", type=int, default=7)
    c.add_argument("--alpha", type=float, default=0.05)
    a = sub.add_parser("aa", help="replay the detector over history and report the false alarm rate")
    a.add_argument("--results", default=RESULTS)
    a.add_argument("--baseline-runs", type=int, default=7)
    args = ap.parse_args(argv)

    if args.cmd == "inspect":
        tasks, dataset_id = load_tasks()
        print("dataset_id", dataset_id, "rows", len(tasks))
        seen = set()
        for t in tasks:
            kind = str(t.get("use_case"))
            if kind not in seen:
                seen.add(kind)
                print("\n== use_case %s ==\n%s" % (kind, describe(t)))
        return 0

    if args.cmd == "run":
        providers = usable_providers(json.loads(Path(args.providers).read_text(encoding="utf-8")))
        if not providers:
            print("no provider has an API key set", file=sys.stderr)
            return 1
        tasks, dataset_id = load_tasks(args.base)
        rows = run_once(tasks, providers, dataset_id, timeout_s=args.timeout)
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        with open(args.out, "a", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row, separators=(",", ":")) + "\n")
        for row in rows:
            k = sum(t["ok"] for t in row["tasks"])
            print("%s: %d of %d correct" % (row["provider"], k, len(row["tasks"])))
        return 0

    rows = read_rows(args.results)
    if not rows:
        print("no results yet")
        return 0

    if args.cmd == "check":
        text, findings = markdown(rows, args.baseline_runs, args.alpha)
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text, encoding="utf-8")
        print(text)
        return 2 if any(f["flagged"] for f in findings) else 0

    alarms, checks, low, high = replay_alarm_rate(rows, args.baseline_runs)
    print("A/A replay: %d alarms in %d checks (95%% CI for the false alarm rate %.1f%% to %.1f%%)"
          % (alarms, checks, low * 100, high * 100))
    return 0
