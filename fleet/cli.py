from __future__ import annotations

import argparse
import json
from pathlib import Path

from .alerts import build_alerts, should_fail
from .demo_data import generate
from .health import build_health
from .report import render
from .store import RunStore, load_runs


def _load(path):
    store = RunStore(load_runs(path))
    health = build_health(store)
    alerts = build_alerts(health, store.model_weekly(), store.latest_week())
    return store, health, alerts


def main(argv=None):
    parser = argparse.ArgumentParser(prog="fleet")
    sub = parser.add_subparsers(dest="cmd", required=True)

    demo = sub.add_parser("demo", help="write synthetic run logs")
    demo.add_argument("--out", default="fleet/sample_runs.jsonl")

    report = sub.add_parser("report", help="write the HTML report")
    report.add_argument("--runs", default="fleet/sample_runs.jsonl")
    report.add_argument("--out", default="docs/fleet/index.html")

    alerts = sub.add_parser("alerts", help="print alerts, optionally fail CI")
    alerts.add_argument("--runs", default="fleet/sample_runs.jsonl")
    alerts.add_argument("--out", default=None, help="also write alerts as JSON")
    alerts.add_argument("--fail-on", choices=["never", "critical", "warning"], default="never")

    args = parser.parse_args(argv)

    if args.cmd == "demo":
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        n = generate(args.out)
        print(f"wrote {n} synthetic runs to {args.out}")
        return 0

    store, health, found = _load(args.runs)

    if args.cmd == "report":
        html = render(health, store.model_summary(), found, store.totals(), store.latest_week())
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(html, encoding="utf-8")
        print(f"wrote {args.out}")
        return 0

    for a in found:
        print(f"[{a['level']}] {a['subject']}: {a['message']}")
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(found, indent=2), encoding="utf-8")
    return 1 if should_fail(found, args.fail_on) else 0
