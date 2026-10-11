"""REPORT: turn report.json into ONE self-contained HTML file (no server, no signup).
Open it in a browser, attach it to a pull request, or host it on GitHub Pages."""
import json

TEMPLATE = """<!doctype html><html><head><meta charset="utf-8"><title>ReplayLens report</title>
<style>
body{font:15px/1.5 system-ui,sans-serif;max-width:1100px;margin:24px auto;padding:0 16px;color:#1d1d1f;background:#fff}
@media(prefers-color-scheme:dark){body{background:#16161a;color:#eee}.card,.run{border-color:#444!important}pre{background:#222!important}}
h1{margin:0 0 4px}.verdict{font-size:20px;font-weight:700;padding:10px 14px;border-radius:8px;display:inline-block;margin:8px 0}
.ok{background:#d9f5e0;color:#0a5c25}.bad{background:#fde0e0;color:#8a1010}
.cards{display:flex;flex-wrap:wrap;gap:10px;margin:12px 0}.card{border:1px solid #ddd;border-radius:8px;padding:10px 14px;min-width:130px}
.card b{display:block;font-size:22px}
.run{border:1px solid #ddd;border-radius:8px;margin:10px 0;padding:10px 14px}
.tag{font-size:12px;padding:2px 8px;border-radius:10px;margin-right:6px}
.regression{background:#fde0e0;color:#8a1010}.improved{background:#d9f5e0;color:#0a5c25}.changed{background:#fff2c9;color:#6b5000}.same{background:#e8e8e8;color:#444}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:12px}pre{white-space:pre-wrap;background:#f6f6f8;padding:8px;border-radius:6px;margin:4px 0}
select{padding:4px}
</style></head><body>
<h1>ReplayLens report</h1><div id="meta"></div><div id="verdict"></div><div class="cards" id="cards"></div>
<label>Show: <select id="f"><option value="all">all</option><option value="regression" selected>regressions</option>
<option value="improved">improved</option><option value="changed">changed</option><option value="same">same</option></select></label>
<div id="runs"></div>
<script>
const R = __DATA__;
const s = R.summary, $ = id => document.getElementById(id);
$("meta").textContent = `old: ${R.old_label}  ->  new: ${R.new_label}`;
$("verdict").innerHTML = `<div class="verdict ${s.safe_to_ship?'ok':'bad'}">${s.safe_to_ship?'SAFE TO SHIP':'NOT SAFE - regressions found'}</div>`;
const card=(k,v)=>`<div class="card">${k}<b>${v}</b></div>`;
$("cards").innerHTML = card("runs",s.total_runs)+card("same",s.same)+card("improved",s.improved)+card("changed",s.changed)+card("regressions",s.regressions)
 +card("cost change",s.cost_change_pct+"%")+card("latency change",s.latency_change_pct+"%");
const esc=t=>String(t).replace(/[&<>]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]));
const tools=r=>r.tool_calls.length?r.tool_calls.map(c=>c.name+"("+JSON.stringify(c.arguments)+")").join("\\n"):"(no tools)";
function draw(){const f=$("f").value;
 $("runs").innerHTML=R.results.filter(r=>f==="all"||r.status===f).map(r=>`<div class="run">
 <span class="tag ${r.status}">${r.status}</span><b>${esc(r.input)}</b>
 ${r.reasons.map(x=>`<div>- ${esc(x)}</div>`).join("")}
 <div class="cols"><div><small>OLD</small><pre>${esc(r.old.output)}</pre><pre>${esc(tools(r.old))}</pre></div>
 <div><small>NEW</small><pre>${esc(r.new.output)}</pre><pre>${esc(tools(r.new))}</pre></div></div></div>`).join("")||"<p>Nothing in this view.</p>";}
$("f").onchange=draw;draw();
</script></body></html>"""


def write_html(report, path):
    data = json.dumps(report).replace("</", "<\\/")
    with open(path, "w", encoding="utf-8") as f:
        f.write(TEMPLATE.replace("__DATA__", data))
