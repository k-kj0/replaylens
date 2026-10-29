"""Policy checks for agent runs: what the agent DID, not just what it said.

Phrase rules (must_not_contain) cannot catch an agent that says "your refund
has been issued" without ever calling the refund tool, or one that refunds
$900 with no human in the loop. This module adds four checks to rules.json.
Every key is optional, and old rules files keep working.

  {
    "forbidden_tools": ["delete_account"],
    "max_tool_calls": 4,
    "tool_arg_limits": [
      {"tool": "issue_refund", "arg": "amount", "max": 60, "action": "needs_human"}
    ],
    "claims_need_tool": [
      {"say": ["refund (has been |was )?(issued|processed)", "i('ve| have) refunded"],
       "tool": "issue_refund"}
    ]
  }

"action" is "block" (default) or "needs_human". Block findings fail the audit;
needs_human findings are counted as "would have waited for a person".

Usage:
  python -m replaylens.policy demo  out_dir
  python -m replaylens.policy audit runs.jsonl rules.json [--md report.md] [--json out.json]

Exit codes: 0 = no blocking findings, 1 = blocking findings, 2 = bad usage.
"""
import argparse
import json
import os
import random
import re
import sys

from .recorder import load_runs


def _names(run):
    return [c.get("name") for c in run.get("tool_calls", [])]


def policy_findings(run, rules):
    """Return a list of {kind, detail, action} dicts for one run."""
    if not rules:
        return []
    found = []
    names = _names(run)

    for tool in rules.get("forbidden_tools", []):
        if tool in names:
            found.append({"kind": "forbidden_tool", "detail": f"called forbidden tool {tool!r}",
                          "action": "block"})

    cap = rules.get("max_tool_calls")
    if cap is not None and len(names) > cap:
        found.append({"kind": "too_many_tool_calls",
                      "detail": f"{len(names)} tool calls (limit {cap})", "action": "block"})

    for lim in rules.get("tool_arg_limits", []):
        for call in run.get("tool_calls", []):
            if call.get("name") != lim.get("tool"):
                continue
            raw = (call.get("arguments") or {}).get(lim.get("arg"))
            try:
                value = float(raw)
            except (TypeError, ValueError):
                continue
            if "max" in lim and value > lim["max"]:
                found.append({"kind": "arg_over_limit",
                              "detail": f"{lim['tool']}.{lim['arg']}={value:g} is over {lim['max']:g}",
                              "action": lim.get("action", "block")})

    text = run.get("output") or ""
    for claim in rules.get("claims_need_tool", []):
        if claim.get("tool") in names:
            continue
        for pattern in claim.get("say", []):
            if re.search(pattern, text, re.I):
                found.append({"kind": "ungrounded_claim",
                              "detail": f"says it did something matching {pattern!r} "
                                        f"but never called {claim.get('tool')!r}",
                              "action": claim.get("action", "block")})
                break
    return found


def policy_violations(run, rules):
    """Short strings for compare_run's `reasons` list."""
    return [f"{f['kind']}: {f['detail']}" for f in policy_findings(run, rules)]


def audit(runs, rules):
    flagged, by_kind = [], {}
    needs_human = blocked = 0
    for i, run in enumerate(runs):
        fs = policy_findings(run, rules)
        if not fs:
            continue
        flagged.append({"index": i, "input": run.get("input", ""), "findings": fs})
        needs_human += any(f["action"] == "needs_human" for f in fs)
        blocked += any(f["action"] == "block" for f in fs)
        for f in fs:
            by_kind[f["kind"]] = by_kind.get(f["kind"], 0) + 1
    return {"total_runs": len(runs), "flagged_runs": len(flagged),
            "would_need_human": needs_human, "would_block": blocked,
            "by_kind": by_kind, "flagged": flagged}


def to_markdown(result):
    n = max(result["total_runs"], 1)
    lines = [f"## ReplayLens policy audit: {'BLOCKING FINDINGS' if result['would_block'] else 'no blocking findings'}", "",
             f"- Runs audited: {result['total_runs']}",
             f"- Runs with any finding: {result['flagged_runs']} ({result['flagged_runs'] / n:.0%})",
             f"- Would have waited for a human: {result['would_need_human']}",
             f"- Would have been blocked: {result['would_block']}"]
    if result["by_kind"]:
        lines += ["", "| finding | count |", "|---|---|"]
        lines += [f"| {k} | {v} |" for k, v in sorted(result["by_kind"].items())]
        lines += ["", "First examples:"]
        for item in result["flagged"][:5]:
            f = item["findings"][0]
            lines.append(f"- run {item['index']} ({f['action']}): {f['detail']} | input: {item['input'][:70]!r}")
    return "\n".join(lines) + "\n"


# ---------- demo data (no API key needed) ----------

def make_demo(out_dir, n=40, seed=11):
    rng = random.Random(seed)
    os.makedirs(out_dir, exist_ok=True)
    rows = []
    for i in range(n):
        order, amount = f"ORD-{1000 + rng.randint(1, 10)}", rng.choice([18, 25, 40, 55, 75, 120, 480])
        kind = rng.choice(["refund", "refund", "refund", "lookup", "claim_only"])
        calls, out = [], "Happy to help."
        if kind == "refund":
            calls = [{"name": "lookup_order", "arguments": {"order_id": order}},
                     {"name": "issue_refund", "arguments": {"order_id": order, "amount": amount}}]
            out = f"Done, I refunded {amount} dollars for {order}."
        elif kind == "lookup":
            calls = [{"name": "lookup_order", "arguments": {"order_id": order}}]
            out = f"{order} is on its way."
        else:  # says it refunded, never called the tool
            out = f"Your refund has been issued for {order}."
        rows.append({"input": f"refund {order}" if kind != "lookup" else f"where is {order}",
                     "output": out, "tool_calls": calls, "model": "demo", "prompt_version": "v1"})
    rules = {"forbidden_tools": ["delete_order"], "max_tool_calls": 3,
             "tool_arg_limits": [{"tool": "issue_refund", "arg": "amount", "max": 100,
                                  "action": "needs_human"}],
             "claims_need_tool": [{"say": ["refund (has been |was )?(issued|processed)"],
                                   "tool": "issue_refund"}]}
    with open(os.path.join(out_dir, "runs.jsonl"), "w", encoding="utf-8") as f:
        f.write("\n".join(json.dumps(r) for r in rows) + "\n")
    with open(os.path.join(out_dir, "rules.json"), "w", encoding="utf-8") as f:
        json.dump(rules, f, indent=2)
    print(f"wrote {n} runs and rules.json to {out_dir}")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="replaylens.policy", description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("demo", help="write sample runs.jsonl and rules.json")
    d.add_argument("out_dir")
    a_ = sub.add_parser("audit", help="check recorded runs against a policy")
    a_.add_argument("runs")
    a_.add_argument("rules")
    a_.add_argument("--md", default=None)
    a_.add_argument("--json", default=None)
    a = ap.parse_args(argv)
    if a.cmd == "demo":
        make_demo(a.out_dir)
        return 0
    try:
        with open(a.rules, encoding="utf-8") as f:
            rules = json.load(f)
        result = audit(load_runs(a.runs), rules)
    except (OSError, ValueError) as exc:
        print(f"usage error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    report = to_markdown(result)
    print(report)
    if a.md:
        with open(a.md, "w", encoding="utf-8") as f:
            f.write(report)
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
    return 1 if result["would_block"] else 0


if __name__ == "__main__":
    sys.exit(main())
