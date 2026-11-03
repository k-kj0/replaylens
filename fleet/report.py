"""Render one self-contained HTML page (works on GitHub Pages)."""
from __future__ import annotations

from html import escape

from .store import ACCOUNT_WEEKLY_SQL, MODEL_SUMMARY_SQL

LANE_LABEL = {
    "person": "Assign a person",
    "program": "Run a program",
    "expansion": "Expansion",
    "none": "Healthy",
}

CSS = """
:root{--bg:#fff;--fg:#1a1a1a;--mut:#666;--line:#ddd;--card:#f6f6f6}
@media (prefers-color-scheme:dark){:root{--bg:#121212;--fg:#eee;--mut:#aaa;--line:#333;--card:#1c1c1c}}
body{font:15px/1.5 system-ui,sans-serif;background:var(--bg);color:var(--fg);max-width:980px;margin:0 auto;padding:24px 16px}
h1{margin:0 0 4px}h2{margin-top:32px}.mut{color:var(--mut)}
.cards{display:flex;gap:12px;flex-wrap:wrap}.card{background:var(--card);padding:12px 16px;border-radius:8px;min-width:130px}
.card b{display:block;font-size:22px}
.wrap{overflow-x:auto}table{border-collapse:collapse;width:100%}
th,td{padding:6px 10px;border-bottom:1px solid var(--line);text-align:left;white-space:nowrap}
td.wrapcell{white-space:normal;min-width:220px}
.person{color:#c62828;font-weight:600}.program{color:#b26a00;font-weight:600}.expansion{color:#2e7d32;font-weight:600}
.critical{color:#c62828;font-weight:600}.warning{color:#b26a00;font-weight:600}
pre{background:var(--card);padding:12px;border-radius:8px;overflow-x:auto;font-size:12px}
"""


def _money(x):
    return "n/a" if x is None else f"${x:.4f}"


def render(health, models, alerts, totals, latest_wk):
    e = escape
    out = [
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>",
        "<meta name='viewport' content='width=device-width,initial-scale=1'>",
        f"<title>ReplayLens Fleet</title><style>{CSS}</style></head><body>",
        "<h1>ReplayLens Fleet</h1>",
        "<p class='mut'>Account health, model economics and alerts from agent run logs. "
        f"Report week {e(str(latest_wk))}. Demo data is synthetic.</p>",
        "<div class='cards'>",
        f"<div class='card'><b>{totals['accounts']}</b>accounts</div>",
        f"<div class='card'><b>{totals['runs']}</b>runs</div>",
        f"<div class='card'><b>{totals['models']}</b>models</div>",
        f"<div class='card'><b>${totals['cost'] or 0:.2f}</b>total cost</div>",
        f"<div class='card'><b>{sum(1 for a in health if a['lane'] == 'person')}</b>need a person</div>",
        "</div>",
        "<h2>Which accounts get a person, which get a program</h2>",
        "<div class='wrap'><table><tr><th>Account</th><th>Health</th><th>Lane</th><th>Runs</th>"
        "<th>Usage trend</th><th>Why</th><th>Next step</th></tr>",
    ]
    for a in health:
        out.append(
            "<tr><td>{}</td><td>{}</td><td class='{}'>{}</td><td>{}</td><td>{:+.0%}</td>"
            "<td class='wrapcell'>{}</td><td class='wrapcell'>{}</td></tr>".format(
                e(a["account"]),
                a["score"],
                e(a["lane"]),
                e(LANE_LABEL[a["lane"]]),
                a["runs"],
                a["trend"],
                e(", ".join(a["reasons"]) or "nothing flagged"),
                e(a["action"]),
            )
        )
    out.append("</table></div>")
    out.append("<h2>Model economics</h2><p class='mut'>Cost per passing run is total spend divided by passed runs.</p>")
    out.append(
        "<div class='wrap'><table><tr><th>Model</th><th>Runs</th><th>Pass rate</th>"
        "<th>Cost per run</th><th>Cost per pass</th><th>Avg latency</th><th>p95 latency</th></tr>"
    )
    for m in models:
        out.append(
            f"<tr><td>{e(m['model'])}</td><td>{m['runs']}</td><td>{m['pass_rate']:.1%}</td>"
            f"<td>{_money(m['cost_per_run'])}</td><td>{_money(m['cost_per_pass'])}</td>"
            f"<td>{m['avg_latency']:.0f} ms</td><td>{m['p95_latency']:.0f} ms</td></tr>"
        )
    out.append("</table></div><h2>Alerts</h2>")
    if alerts:
        out.append("<ul>")
        for a in alerts:
            out.append(
                f"<li><span class='{e(a['level'])}'>{e(a['level'])}</span> "
                f"<b>{e(a['subject'])}</b>: {e(a['message'])}</li>"
            )
        out.append("</ul>")
    else:
        out.append("<p>No alerts.</p>")
    out.append("<h2>How it is computed</h2><p class='mut'>Plain SQL over SQLite, no dependencies.</p>")
    out.append(f"<pre>{e(ACCOUNT_WEEKLY_SQL.strip())}</pre><pre>{e(MODEL_SUMMARY_SQL.strip())}</pre>")
    out.append("</body></html>")
    return "".join(out)
