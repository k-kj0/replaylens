"""Score each account and decide whether it needs a person or a program."""
from __future__ import annotations

PASS_FLOOR = 0.90
LATENCY_LIMIT_MS = 2000.0


def _latest_rows(rows, latest_wk):
    """One row per account for the latest week. Accounts that went quiet get a zero-run row."""
    by_account = {}
    for row in rows:
        by_account.setdefault(row["account"], []).append(row)
    out = []
    for account, history in sorted(by_account.items()):
        last = history[-1]
        typical_cost = sum(r["cost"] for r in history) / len(history)
        if last["wk"] == latest_wk:
            item = dict(last)
            item["silent"] = False
        else:
            item = {
                "account": account,
                "wk": latest_wk,
                "runs": 0,
                "pass_rate": None,
                "cost": 0.0,
                "avg_latency": 0.0,
                "prev_runs": last["runs"],
                "prev_pass": last["pass_rate"],
                "silent": True,
            }
        item["typical_cost"] = typical_cost
        out.append(item)
    return out


def score_account(a):
    score = 100.0
    reasons = []
    if a["silent"]:
        score -= 45
        reasons.append("no runs this week")
    else:
        if a["pass_rate"] < PASS_FLOOR:
            score -= min(40.0, (PASS_FLOOR - a["pass_rate"]) * 200)
            reasons.append(f"pass rate {a['pass_rate']:.0%}")
        if a["prev_pass"] is not None and a["prev_pass"] - a["pass_rate"] > 0.10:
            score -= 15
            reasons.append("pass rate fell more than 10 points")
        if a["avg_latency"] > LATENCY_LIMIT_MS:
            score -= 10
            reasons.append(f"slow runs ({a['avg_latency']:.0f} ms average)")
    prev = a["prev_runs"]
    trend = 0.0
    if prev:
        trend = (a["runs"] - prev) / prev
        if trend < -0.30 and not a["silent"]:
            score -= min(30.0, abs(trend) * 40)
            reasons.append(f"usage down {abs(trend):.0%} week over week")
    return max(0.0, round(score, 1)), reasons, trend


def recommend(score, trend, high_value):
    """The core question: which accounts get a person, which get a program."""
    if score < 60 and high_value:
        return "person", "Assign a named owner this week: call the team and review failing runs together."
    if score < 60:
        return "program", "Enroll in onboarding and office hours; send a targeted fix guide."
    if score < 80:
        return "program", "Send a nudge campaign: share the replay-and-compare workflow and best practices."
    if high_value and trend >= 0.20:
        return "expansion", "Healthy and growing: bring in the Account Executive to discuss expansion."
    return "none", "Healthy: no action needed. Keep monitoring."


def build_health(store):
    latest = store.latest_week()
    rows = _latest_rows(store.account_weekly(), latest)
    costs = sorted(r["typical_cost"] for r in rows)
    threshold = costs[int(0.75 * (len(costs) - 1))] if costs else 0.0
    out = []
    for a in rows:
        score, reasons, trend = score_account(a)
        high_value = a["typical_cost"] >= threshold and a["typical_cost"] > 0
        lane, action = recommend(score, trend, high_value)
        a.update(
            score=score,
            reasons=reasons,
            trend=trend,
            high_value=high_value,
            lane=lane,
            action=action,
        )
        out.append(a)
    out.sort(key=lambda r: (r["score"], r["account"]))
    return out
