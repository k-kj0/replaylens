"""Threshold alerts. Exit non-zero in CI when something critical shows up."""
from __future__ import annotations


def build_alerts(health, model_weekly, latest_wk):
    alerts = []
    for a in health:
        why = ", ".join(a["reasons"]) or "score below threshold"
        if a["score"] < 50:
            alerts.append({"level": "critical", "subject": a["account"], "message": f"health {a['score']}: {why}"})
        elif a["score"] < 70:
            alerts.append({"level": "warning", "subject": a["account"], "message": f"health {a['score']}: {why}"})
    for m in model_weekly:
        if m["wk"] != latest_wk or m["prev_pass"] is None:
            continue
        drop = m["prev_pass"] - m["pass_rate"]
        if drop > 0.20:
            level = "critical"
        elif drop > 0.10:
            level = "warning"
        else:
            continue
        alerts.append(
            {
                "level": level,
                "subject": m["model"],
                "message": f"model pass rate fell {drop:.0%} week over week",
            }
        )
    order = {"critical": 0, "warning": 1}
    alerts.sort(key=lambda a: (order[a["level"]], a["subject"]))
    return alerts


def should_fail(alerts, fail_on):
    if fail_on == "never":
        return False
    levels = {"critical": {"critical"}, "warning": {"critical", "warning"}}[fail_on]
    return any(a["level"] in levels for a in alerts)
