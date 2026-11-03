import json

from fleet.alerts import build_alerts, should_fail
from fleet.cli import main
from fleet.demo_data import generate
from fleet.health import build_health
from fleet.report import render
from fleet.store import RunStore, load_runs


def _store(tmp_path):
    path = tmp_path / "runs.jsonl"
    generate(path)
    return RunStore(load_runs(path))


def test_loader_accepts_alias_field_names(tmp_path):
    path = tmp_path / "x.jsonl"
    path.write_text(
        json.dumps({"tenant": "a", "timestamp": "2026-10-01T10:00:00Z", "success": "true", "cost": 0.5, "latency": 100})
        + "\n"
    )
    runs = load_runs(path)
    assert runs[0]["account"] == "a" and runs[0]["passed"] == 1 and runs[0]["cost_usd"] == 0.5


def test_declining_high_spend_account_needs_a_person(tmp_path):
    health = {a["account"]: a for a in build_health(_store(tmp_path))}
    assert health["northwind"]["lane"] == "person"


def test_quiet_account_is_flagged_and_healthy_growing_account_is_expansion(tmp_path):
    health = {a["account"]: a for a in build_health(_store(tmp_path))}
    assert health["umbrella"]["silent"] and health["umbrella"]["score"] < 60
    assert health["stark-labs"]["lane"] == "expansion"


def test_alerts_have_critical_and_can_fail_ci(tmp_path):
    store = _store(tmp_path)
    health = build_health(store)
    found = build_alerts(health, store.model_weekly(), store.latest_week())
    assert any(a["level"] == "critical" for a in found)
    assert should_fail(found, "critical") and not should_fail(found, "never")


def test_report_escapes_html_and_cli_writes_files(tmp_path):
    store = _store(tmp_path)
    health = build_health(store)
    health[0]["account"] = "<script>alert(1)</script>"
    html = render(health, store.model_summary(), [], store.totals(), store.latest_week())
    assert "<script>alert(1)" not in html
    runs = tmp_path / "r.jsonl"
    out = tmp_path / "out" / "index.html"
    assert main(["demo", "--out", str(runs)]) == 0
    assert main(["report", "--runs", str(runs), "--out", str(out)]) == 0
    assert out.exists()
