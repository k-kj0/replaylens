"""Export runs.jsonl as OTLP/JSON-shaped traces.
Usage: python -m replaylens.otel runs.jsonl traces.json"""
import json, sys, time, uuid
from ._compat import load_runs, normalize

def _hex(n):
    return uuid.uuid4().hex[:n]

def _attr(k, v):
    if isinstance(v, bool):
        val = {"boolValue": v}
    elif isinstance(v, int):
        val = {"intValue": str(v)}
    elif isinstance(v, float):
        val = {"doubleValue": v}
    else:
        val = {"stringValue": str(v)}
    return {"key": k, "value": val}

def export(runs_path, out_path):
    spans, now = [], time.time_ns()
    for r in map(normalize, load_runs(runs_path)):
        trace, root = _hex(32), _hex(16)
        end = now + int(float(r["latency"] or 0) * 1e9)
        spans.append({
            "traceId": trace, "spanId": root, "name": "agent.run", "kind": 1,
            "startTimeUnixNano": str(now), "endTimeUnixNano": str(end),
            "attributes": [_attr("gen_ai.request.model", r["model"]),
                           _attr("replaylens.cost_usd", float(r["cost"] or 0)),
                           _attr("replaylens.run_id", r["id"] or "")],
        })
        for i, tc in enumerate(r["tool_calls"] or []):
            name = tc.get("name", "unknown") if isinstance(tc, dict) else str(tc)
            spans.append({
                "traceId": trace, "spanId": _hex(16), "parentSpanId": root,
                "name": f"tool.{name}", "kind": 1,
                "startTimeUnixNano": str(now), "endTimeUnixNano": str(end),
                "attributes": [_attr("tool.name", name), _attr("tool.index", i)],
            })
    doc = {"resourceSpans": [{
        "resource": {"attributes": [_attr("service.name", "replaylens")]},
        "scopeSpans": [{"scope": {"name": "replaylens"}, "spans": spans}]}]}
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2)
    print(f"wrote {len(spans)} spans to {out_path}")

if __name__ == "__main__":
    export(sys.argv[1], sys.argv[2])
