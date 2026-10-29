"""COMPARE: old recorded run vs new replayed run -> a verdict per run and for the whole batch."""
import difflib
import json

from .policy import policy_violations


def tool_names(run):
    return [c["name"] for c in run.get("tool_calls", [])]


def tool_args(run):
    return [(c["name"], json.dumps(c.get("arguments", {}), sort_keys=True))
            for c in run.get("tool_calls", [])]


def rule_violations(text, rules):
    """rules = {"must_not_contain": [...], "must_contain_any": [...]}  (case-insensitive)"""
    if not rules:
        return []
    low, bad = (text or "").lower(), []
    for phrase in rules.get("must_not_contain", []):
        if phrase.lower() in low:
            bad.append(f"contains forbidden phrase: {phrase!r}")
    wanted = rules.get("must_contain_any", [])
    if wanted and not any(p.lower() in low for p in wanted):
        bad.append(f"missing all of required phrases: {wanted}")
    return bad


def compare_run(old, new, rules=None, judge=None):
    reasons = []
    if new.get("error"):
        reasons.append(f"new run crashed: {new['error']}")
    if tool_names(old) != tool_names(new):
        reasons.append(f"different tools: {tool_names(old)} -> {tool_names(new)}")
    elif tool_args(old) != tool_args(new):
        reasons.append("same tools but different arguments")
    old_bad, new_bad = rule_violations(old.get("output"), rules), rule_violations(new.get("output"), rules)
    fresh_bad = [b for b in new_bad if b not in old_bad]
    reasons += [f"rule: {b}" for b in fresh_bad]
    old_pol, new_pol = policy_violations(old, rules), policy_violations(new, rules)
    reasons += [f"policy: {p}" for p in new_pol if p not in old_pol]
    sim = difflib.SequenceMatcher(None, old.get("output", ""), new.get("output", "")).ratio()
    verdict = None
    if judge and sim < 0.98:
        verdict = judge(old["input"], old.get("output", ""), new.get("output", ""))
        if verdict == "worse":
            reasons.append("LLM judge: new answer is worse")

    if reasons:
        status = "regression"
    elif verdict == "better":
        status = "improved"
    elif sim < 0.8:
        status = "changed"
    else:
        status = "same"
    return {"input": old["input"], "status": status, "reasons": reasons,
            "text_similarity": round(sim, 3), "judge": verdict,
            "old": old, "new": new}


def summarize(results, max_regressions=0):
    n = len(results)
    count = lambda s: sum(1 for r in results if r["status"] == s)
    old_cost = sum(r["old"].get("cost_usd", 0) for r in results)
    new_cost = sum(r["new"].get("cost_usd", 0) for r in results)
    old_lat = sum(r["old"].get("latency_ms", 0) for r in results) / max(n, 1)
    new_lat = sum(r["new"].get("latency_ms", 0) for r in results) / max(n, 1)
    pct = lambda a, b: round((b - a) / a * 100, 1) if a else 0.0
    regressions = count("regression")
    return {
        "total_runs": n, "same": count("same"), "changed": count("changed"),
        "improved": count("improved"), "regressions": regressions,
        "old_cost_usd": round(old_cost, 6), "new_cost_usd": round(new_cost, 6),
        "cost_change_pct": pct(old_cost, new_cost),
        "old_avg_latency_ms": round(old_lat), "new_avg_latency_ms": round(new_lat),
        "latency_change_pct": pct(old_lat, new_lat),
        "safe_to_ship": regressions <= max_regressions,
    }
