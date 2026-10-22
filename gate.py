"""CI GATE: replay recorded runs against a new prompt/model and exit non-zero
if behaviour, latency or cost regressed beyond the limits you set.

Exit codes: 0 = SAFE, 1 = NOT SAFE, 2 = bad usage.
"""
import argparse
import importlib
import json
import math
import os
import sys

from .recorder import load_runs
from .replayer import replay_runs


def load_agent(spec):
    if ":" not in spec:
        raise ValueError("--agent must look like module:function")
    mod_name, fn_name = spec.split(":", 1)
    sys.path.insert(0, os.getcwd())
    return getattr(importlib.import_module(mod_name), fn_name)


def percentile(values, pct):
    """Nearest-rank percentile; 0.0 for an empty list."""
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(1, math.ceil(pct / 100.0 * len(ordered)))
    return float(ordered[rank - 1])


def tool_names(row):
    return sorted(c.get("name", "") for c in (row.get("tool_calls") or []))


def load_rules(path):
    if not path:
        return {"must_not_contain": [], "must_contain_any": []}
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return {"must_not_contain": [s.lower() for s in data.get("must_not_contain", [])],
            "must_contain_any": [s.lower() for s in data.get("must_contain_any", [])]}


def rule_violations(text, rules):
    low = (text or "").lower()
    found = [f"said '{p}'" for p in rules["must_not_contain"] if p in low]
    any_list = rules["must_contain_any"]
    if any_list and not any(p in low for p in any_list):
        found.append("missing required phrase")
    return found


def pct_change(old, new):
    if old == 0:
        return 0.0 if new == 0 else float("inf")
    return 100.0 * (new - old) / old


def evaluate(pairs, rules, max_regress_rate, max_p95_increase, max_cost_increase, min_abs_ms):
    regressions = []
    for old, new in pairs:
        reasons = []
        if new.get("error") and not old.get("error"):
            reasons.append(f"new error: {new['error']}")
        if tool_names(old) != tool_names(new):
            reasons.append(f"tools {tool_names(old)} -> {tool_names(new)}")
        fresh = [v for v in rule_violations(new.get("output"), rules)
                 if v not in rule_violations(old.get("output"), rules)]
        reasons.extend(fresh)
        if reasons:
            regressions.append({"input": str(old["input"])[-120:], "reasons": reasons})

    total = len(pairs)
    rate = len(regressions) / total if total else 0.0
    old_p95 = percentile([o.get("latency_ms", 0) for o, _ in pairs], 95)
    new_p95 = percentile([n.get("latency_ms", 0) for _, n in pairs], 95)
    p95_change = pct_change(old_p95, new_p95)
    old_cost = sum(o.get("cost_usd", 0.0) for o, _ in pairs)
    new_cost = sum(n.get("cost_usd", 0.0) for _, n in pairs)
    cost_change = pct_change(old_cost, new_cost)

    failures = []
    if rate > max_regress_rate:
        failures.append(f"{len(regressions)}/{total} runs regressed ({rate:.1%} > {max_regress_rate:.1%})")
    if p95_change > max_p95_increase and (new_p95 - old_p95) >= min_abs_ms:
        failures.append(f"p95 latency {old_p95:.0f}ms -> {new_p95:.0f}ms (+{p95_change:.1f}% > {max_p95_increase:.1f}%)")
    if cost_change > max_cost_increase:
        failures.append(f"cost +{cost_change:.1f}% > {max_cost_increase:.1f}%")

    return {"verdict": "NOT SAFE" if failures else "SAFE", "runs": total,
            "regressed": len(regressions), "regress_rate": rate,
            "p95_old_ms": old_p95, "p95_new_ms": new_p95, "p95_change_pct": p95_change,
            "cost_old": old_cost, "cost_new": new_cost, "cost_change_pct": cost_change,
            "failures": failures, "regressions": regressions}


def main(argv=None):
    ap = argparse.ArgumentParser(prog="replaylens.gate",
                                 description="Replay runs and fail (exit 1) if the change is not safe.")
    ap.add_argument("runs", help="recorded runs.jsonl")
    ap.add_argument("--agent", required=True, help="module:function")
    ap.add_argument("--prompt", required=True, help="path to the new system prompt file")
    ap.add_argument("--model", default="good-model", help="model name passed to the agent")
    ap.add_argument("--rules", default=None, help="optional rules.json")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--max-regress-rate", type=float, default=0.0,
                    help="allowed fraction of regressed runs, 0.0 to 1.0 (default 0.0)")
    ap.add_argument("--max-p95-increase", type=float, default=20.0,
                    help="allowed p95 latency increase in percent (default 20)")
    ap.add_argument("--max-cost-increase", type=float, default=20.0,
                    help="allowed total cost increase in percent (default 20)")
    ap.add_argument("--min-abs-ms", type=float, default=50.0,
                    help="ignore p95 increases smaller than this many ms (noise guard, default 50)")
    ap.add_argument("--out", default=None, help="write the full result as JSON")
    args = ap.parse_args(argv)

    try:
        runs = load_runs(args.runs)
        agent_fn = load_agent(args.agent)
        with open(args.prompt, encoding="utf-8") as f:
            prompt = f.read()
        rules = load_rules(args.rules)
    except (OSError, ValueError, ImportError, AttributeError, json.JSONDecodeError) as exc:
        print(f"usage error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    if not runs:
        print("usage error: no runs found in " + args.runs, file=sys.stderr)
        return 2

    pairs = replay_runs(runs, agent_fn, args.model, prompt, workers=args.workers)
    result = evaluate(pairs, rules, args.max_regress_rate, args.max_p95_increase,
                      args.max_cost_increase, args.min_abs_ms)

    print(f"Replayed {result['runs']} runs: {result['regressed']} regressed")
    print(f"p95 latency {result['p95_old_ms']:.0f}ms -> {result['p95_new_ms']:.0f}ms "
          f"({result['p95_change_pct']:+.1f}%), cost {result['cost_change_pct']:+.1f}%")
    for fail in result["failures"]:
        print("FAIL:", fail)
    print("VERDICT:", result["verdict"])
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
    return 1 if result["failures"] else 0


if __name__ == "__main__":
    sys.exit(main())
