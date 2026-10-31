import json
import wave

import pytest

np = pytest.importorskip("numpy")

from replaylens import asr_bench, voice  # noqa: E402

SR = 16000


def _tone(freq, seconds=1.0, amp=0.5):
    t = np.arange(int(SR * seconds)) / SR
    return (amp * np.sin(2 * np.pi * freq * t)).astype(np.float32)


def _energy_above(x, hz):
    spec = np.abs(np.fft.rfft(x)) ** 2
    freqs = np.fft.rfftfreq(len(x), 1 / SR)
    return spec[freqs > hz].sum() / spec.sum()


def test_band_limit_removes_energy_outside_the_phone_band():
    mixed = _tone(1000) + _tone(6000)
    out = asr_bench.band_limit(mixed, SR)
    assert _energy_above(mixed, 4000) > 0.2
    assert _energy_above(out, 4000) < 0.01


def test_mulaw_roundtrip_is_close_and_bounded():
    x = _tone(440)
    y = asr_bench.mulaw_roundtrip(x)
    assert np.max(np.abs(y)) <= 1.0
    assert np.mean(np.abs(x - y)) < 0.01


def test_add_noise_hits_the_requested_snr():
    x = _tone(440)
    noisy = asr_bench.add_noise(x, 10, seed=1)
    snr = 10 * np.log10(np.mean(x ** 2) / np.mean((noisy - x) ** 2))
    assert abs(snr - 10) < 0.5


def test_degrade_is_deterministic_float32_and_clipped():
    x = _tone(440, amp=0.9)
    a = asr_bench.degrade(x, SR, phone=True, snr_db=5, seed=3)
    b = asr_bench.degrade(x, SR, phone=True, snr_db=5, seed=3)
    assert a.dtype == np.float32 and np.array_equal(a, b)
    assert np.max(np.abs(a)) <= 1.0 and len(a) == len(x)
    assert np.array_equal(asr_bench.degrade(x, SR), x)


def test_condition_names():
    assert asr_bench.condition_name(False, None) == "clean"
    assert asr_bench.condition_name(True, None) == "phone"
    assert asr_bench.condition_name(True, 10) == "phone+snr10"


def _samples(n=4):
    return [{"id": f"s{i}", "audio": _tone(300 + 50 * i), "sr": SR, "text": "hello world"} for i in range(n)]


def test_run_bench_rows_feed_the_voice_checker():
    good = lambda wave_, sr: "hello world"
    bad = lambda wave_, sr: "hello word"
    old = asr_bench.run_bench(good, _samples(), "good", warmup=False)
    new = asr_bench.run_bench(bad, _samples(), "bad", phone=True, snr_db=10, warmup=False)
    assert old[0]["wer"] == 0.0 and new[0]["wer"] == 0.5
    assert new[0]["condition"] == "phone+snr10" and new[0]["model"] == "bad"
    result = voice.compare(old, new)
    assert result["turns_compared"] == 4 and result["mean_wer"] == 0.5
    s = asr_bench.summarize(new)
    assert s["clips"] == 4 and s["mean_wer"] == 0.5
    assert "| bad | phone+snr10 |" in asr_bench.to_markdown([s])
    assert asr_bench.to_markdown([s]).splitlines()[0].endswith("| model MB |")


def test_model_size_is_carried_into_rows_and_summary():
    rows = asr_bench.run_bench(lambda w, sr: "hello world", _samples(2), "m", warmup=False, model_mb=151.2)
    assert rows[0]["model_mb"] == 151.2
    s = asr_bench.summarize(rows)
    assert s["model_mb"] == 151.2 and "151.2 |" in asr_bench.to_markdown([s])


def test_warmup_call_is_not_timed_as_a_row():
    calls = []
    asr_bench.run_bench(lambda w, sr: calls.append(1) or "x", _samples(3), "m")
    assert len(calls) == 4  # 1 warm-up + 3 clips


def test_audio_dir_loader_and_cli_report(tmp_path):
    pcm = (_tone(440) * 32767).astype("<i2").tobytes()
    with wave.open(str(tmp_path / "a.wav"), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm)
    (tmp_path / "a.txt").write_text("hello world")
    (tmp_path / "orphan.wav").write_bytes(b"")  # no .txt, must be skipped
    samples = list(asr_bench.load_audio_dir(str(tmp_path)))
    assert [s["id"] for s in samples] == ["a"] and samples[0]["text"] == "hello world"
    rows = asr_bench.run_bench(lambda w, sr: "hello world", samples, "m", warmup=False)
    path = tmp_path / "r.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in rows))
    assert asr_bench.main(["report", str(path)]) == 0
    assert asr_bench.main(["report", str(tmp_path / "missing.jsonl")]) == 2
