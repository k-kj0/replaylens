import json
from replaylens import otel, evalset
from replaylens._compat import load_runs, normalize

ROW = {"ts": "2026-10-14T00:00:00+00:00", "input": "refund order 12", "output": "done",
       "tool_calls": [{"name": "lookup_order", "arguments": {"id": 12}},
                      {"name": "refund", "arguments": {"id": 12}}],
       "model": "m", "prompt_version": "v1", "latency_ms": 1500, "tokens_in": 10,
       "tokens_out": 5, "price_in": 0, "price_out": 0, "cost_usd": 0.0, "error": None}

def _write(tmp_path):
    p = tmp_path / "runs.jsonl"
    p.write_text(json.dumps(ROW) + "\n" + json.dumps(ROW) + "\n")
    return p

def test_normalize_units_and_ids(tmp_path):
    runs = load_runs(_write(tmp_path))
    assert [r["id"] for r in runs] == [0, 1]
    assert normalize(runs[0])["latency"] == 1.5

def test_otel_export(tmp_path):
    out = tmp_path / "t.json"
    otel.export(str(_write(tmp_path)), str(out))
    spans = json.loads(out.read_text())["resourceSpans"][0]["scopeSpans"][0]["spans"]
    assert len(spans) == 6          # 2 runs x (1 root + 2 tool spans)
    assert sum("parentSpanId" in s for s in spans) == 4

def test_kappa():
    assert evalset.cohen_kappa(["ok", "bad", "ok"], ["ok", "bad", "ok"]) == 1.0
    assert evalset.cohen_kappa(["ok", "ok", "bad", "bad"], ["ok", "bad", "ok", "bad"]) == 0.0
