"""Compare the newest run to a frozen baseline and decide if anything really changed."""
from __future__ import annotations

from collections import defaultdict
from statistics import median

from .stats import holm, mcnemar_exact, paired_bootstrap, wilson

LATENCY_MIN_RELATIVE = 0.25   # ignore latency shifts smaller than 25 percent
LATENCY_MIN_PAIRS = 10


def group(rows):
    """provider -> runs in time order, kept only for the newest dataset version."""
    by = defaultdict(list)
    for r in sorted(rows, key=lambda r: r["ts"]):
        by[r["provider"]].append(r)
    out = {}
    for name, runs in by.items():
        newest = runs[-1]["dataset_id"]
        out[name] = [r for r in runs if r["dataset_id"] == newest]
    return out


def _majority(runs, field):
    """Per task id: did the majority of baseline runs have field true? (ties count as false)"""
    votes = defaultdict(list)
    for r in runs:
        for t in r["tasks"]:
            votes[t["id"]].append(bool(t[field]) if field == "ok" else t["fail"] is not None)
    return {k: sum(v) * 2 > len(v) for k, v in votes.items()}


def _base_latency(runs):
    vals = defaultdict(list)
    for r in runs:
        for t in r["tasks"]:
            if t["e2e_ms"] is not None:
                vals[t["id"]].append(t["e2e_ms"])
    return {k: median(v) for k, v in vals.items()}


def tests_for(runs, baseline_n):
    """Raw tests for runs[-1] against runs[:baseline_n]. Returns [] while warming up."""
    if len(runs) <= baseline_n:
        return []
    base, cur = runs[:baseline_n], runs[-1]
    out = []
    for signal, field in (("accuracy", "ok"), ("failures", "fail")):
        ref = _majority(base, field)
        b = c = 0   # b: got worse, c: got better
        for t in cur["tasks"]:
            if t["id"] not in ref:
                continue
            now = bool(t["ok"]) if field == "ok" else t["fail"] is not None
            was = ref[t["id"]]
            if field == "ok":
                b += was and not now
                c += (not was) and now
            else:
                b += (not was) and now     # a new failure is worse
                c += was and not now
        changed = b + c
        out.append({"signal": signal, "p": mcnemar_exact(b, c), "worse": b, "better": c,
                    "changed": changed, "direction": "worse" if b > c else "better",
                    "practical": True,
                    "detail": "%d tasks got worse, %d got better" % (b, c)})
    lat = _base_latency(base)
    diffs, rel_base = [], []
    for t in cur["tasks"]:
        if t["e2e_ms"] is not None and t["id"] in lat:
            diffs.append(t["e2e_ms"] - lat[t["id"]])
            rel_base.append(lat[t["id"]])
    if len(diffs) >= LATENCY_MIN_PAIRS:
        point, low, high, p = paired_bootstrap(diffs)
        rel = point / median(rel_base) if median(rel_base) else 0.0
        out.append({"signal": "latency", "p": p, "worse": 0, "better": 0, "changed": len(diffs),
                    "direction": "worse" if point > 0 else "better",
                    "practical": abs(rel) >= LATENCY_MIN_RELATIVE,
                    "detail": "median end to end change %+.0f ms (%+.0f%%), 95%% CI %.0f to %.0f ms"
                              % (point, rel * 100, low, high)})
    return out


def evaluate(rows, baseline_n=7, alpha=0.05):
    """Findings for the latest run of every provider. Holm correction across all tests."""
    flat = []
    for name, runs in group(rows).items():
        for t in tests_for(runs, baseline_n):
            t = dict(t, provider=name, run_id=runs[-1]["run_id"])
            flat.append(t)
    adj = holm([t["p"] for t in flat]) if flat else []
    for t, a in zip(flat, adj):
        t["p_adj"] = a
        t["flagged"] = a < alpha and t["practical"]
    return flat


def replay_alarm_rate(rows, baseline_n=7, alpha=0.05):
    """A/A check: replay the detector over history and count alarms.

    Assumes the period after the baseline was quiet. Returns (alarms, checks, low, high).
    """
    alarms = checks = 0
    for name, runs in group(rows).items():
        for k in range(baseline_n + 1, len(runs) + 1):
            window = runs[:k]
            tests = tests_for(window, baseline_n)
            if not tests:
                continue
            adj = holm([t["p"] for t in tests])
            checks += 1
            alarms += any(a < alpha and t["practical"] for a, t in zip(adj, tests))
    low, high = wilson(alarms, checks)
    return alarms, checks, low, high


def latest_summary(rows):
    out = []
    for name, runs in group(rows).items():
        cur = runs[-1]
        n = len(cur["tasks"])
        k = sum(1 for t in cur["tasks"] if t["ok"])
        low, high = wilson(k, n)
        lat = sorted(t["e2e_ms"] for t in cur["tasks"] if t["e2e_ms"] is not None)
        p50 = lat[len(lat) // 2] if lat else None
        fails = sum(1 for t in cur["tasks"] if t["fail"])
        out.append({"provider": name, "model": cur["model"], "ok": k, "n": n, "low": low,
                    "high": high, "p50_ms": p50, "failures": fails, "runs": len(runs)})
    return out
