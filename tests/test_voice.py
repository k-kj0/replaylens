import json

from replaylens import voice


def _row(call, turn, heard="i want a refund", said="ok", stt=100, llm=300, tts=100, intr=False):
    return {"call_id": call, "turn": turn, "user_transcript": heard, "agent_transcript": said,
            "stt_ms": stt, "llm_ms": llm, "tts_ms": tts, "interrupted": intr}


def _write(tmp_path, name, rows):
    p = tmp_path / name
    p.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    return str(p)


def test_wer_basics():
    assert voice.wer("i want a refund", "i want a refund") == 0.0
    assert voice.wer("i want a refund", "i want refund") == 0.25      # one word dropped
    assert voice.wer("", "") == 0.0
    assert voice.wer("", "hello") == 1.0


def test_total_ms_prefers_first_audio():
    assert voice.total_ms({"stt_ms": 1, "llm_ms": 2, "tts_ms": 3}) == 6
    assert voice.total_ms({"stt_ms": 1, "llm_ms": 2, "tts_ms": 3, "first_audio_ms": 50}) == 50


def test_identical_files_are_safe(tmp_path):
    rows = [_row("c1", i) for i in range(5)]
    old, new = _write(tmp_path, "o.jsonl", rows), _write(tmp_path, "n.jsonl", rows)
    assert voice.main(["compare", old, new]) == 0


def test_slow_tts_fails(tmp_path):
    old = _write(tmp_path, "o.jsonl", [_row("c1", i) for i in range(5)])
    new = _write(tmp_path, "n.jsonl", [_row("c1", i, tts=600) for i in range(5)])
    assert voice.main(["compare", old, new]) == 1


def test_stt_drift_fails(tmp_path):
    old = _write(tmp_path, "o.jsonl", [_row("c1", i) for i in range(4)])
    new = _write(tmp_path, "n.jsonl", [_row("c1", i, heard="i want a uh") for i in range(4)])
    assert voice.main(["compare", old, new]) == 1


def test_no_overlap_is_usage_error(tmp_path):
    old = _write(tmp_path, "o.jsonl", [_row("a", 0)])
    new = _write(tmp_path, "n.jsonl", [_row("b", 0)])
    assert voice.main(["compare", old, new]) == 2


def test_demo_runs_and_regresses(tmp_path):
    voice.main(["demo", str(tmp_path)])
    code = voice.main(["compare", str(tmp_path / "old.jsonl"), str(tmp_path / "new.jsonl"),
                       "--md", str(tmp_path / "r.md")])
    assert code == 1
    assert "NOT SAFE" in (tmp_path / "r.md").read_text()
