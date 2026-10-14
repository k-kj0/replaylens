import json

from replaylens import otel
from replaylens._compat import load_runs, normalize
from replaylens.evalset import cohen_kappa

ROW = {"ts": "2026-10-14T10:00:00+00:00", "input": "refund?", "output": "ok",
       "tool_calls": [{"name": "lookup_order", "arguments": {}},
                      {"name": "refund", "arguments": {}}],
       "model": "m", "prompt_version": "v1", "latency_ms": 1500,
       "tokens_in": 10, "tokens_out": 5, "cost_usd": 0.001, "error": None}


def _write(tmp_path):
    p = tmp_path / "runs.jsonl"
    p.write_text(json.dumps(ROW) + "\n")
    return p


def test_normalize_real_schema(tmp_path):
    r = normalize(load_runs(_write(tmp_path))[0])
    assert r["id"] == "0" and r["latency"] == 1.5 and r["cost"] == 0.001


def test_kappa():
    assert cohen_kappa(["ok", "ok", "bad", "bad"], ["ok", "ok", "bad", "bad"]) == 1.0
    assert cohen_kappa(["ok", "ok", "bad", "bad"], ["ok", "bad", "ok", "bad"]) == 0.0


def test_otel_spans(tmp_path):
    out = tmp_path / "t.json"
    otel.export(str(_write(tmp_path)), str(out))
    spans = json.loads(out.read_text())["resourceSpans"][0]["scopeSpans"][0]["spans"]
    assert len(spans) == 3   # 1 run + 2 tool calls
