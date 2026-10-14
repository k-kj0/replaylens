import json

from replaylens import noise


def _file(tmp_path, name, rows):
    p = tmp_path / name
    p.write_text("\n".join(json.dumps({
        "ts": "2026-10-14T10:00:00+00:00", "input": q, "output": "x",
        "tool_calls": [{"name": t} for t in tools], "model": "m",
        "prompt_version": "v", "latency_ms": 1, "tokens_in": 1, "tokens_out": 1,
        "cost_usd": 0, "error": None}) for q, tools in rows))
    return str(p)


def test_stable_baseline_and_changed_candidate(tmp_path):
    base = _file(tmp_path, "b.jsonl", [("q1", ["lookup", "refund"])] * 3)
    cand = _file(tmp_path, "c.jsonl", [("q1", ["refund"])] * 3)
    assert noise.main(["compare", base, cand, "--fail"]) == 1


def test_noisy_baseline_absorbs_change(tmp_path):
    base = _file(tmp_path, "b.jsonl",
                 [("q1", ["a"]), ("q1", ["b"]), ("q1", ["a"]), ("q1", ["b"])])
    cand = _file(tmp_path, "c.jsonl", [("q1", ["a"]), ("q1", ["b"])])
    assert noise.main(["compare", base, cand, "--fail"]) == 0


def test_no_noise_estimate_is_inconclusive(tmp_path):
    base = _file(tmp_path, "b.jsonl", [("q1", ["a"])])
    cand = _file(tmp_path, "c.jsonl", [("q1", ["b"])])
    assert noise.main(["compare", base, cand, "--fail"]) == 0
