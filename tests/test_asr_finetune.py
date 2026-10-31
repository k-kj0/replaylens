import pytest

np = pytest.importorskip("numpy")

from replaylens import asr_finetune  # noqa: E402

SR = 16000


def _samples(n=5):
    t = np.arange(SR) / SR
    return [{"id": f"s{i}", "audio": (0.5 * np.sin(2 * np.pi * (300 + 40 * i) * t)).astype(np.float32),
             "sr": SR, "text": "hello world"} for i in range(n)]


def test_augment_keeps_ids_text_and_length_and_changes_audio():
    src = _samples()
    out = asr_finetune.augment_samples(src, seed=1)
    assert [s["id"] for s in out] == [s["id"] for s in src]
    assert all(o["text"] == "hello world" and len(o["audio"]) == len(s["audio"]) for o, s in zip(out, src))
    assert not np.array_equal(out[0]["audio"], src[0]["audio"])
    assert out[0]["audio"].dtype == np.float32


def test_augment_is_deterministic_and_does_not_touch_the_input():
    src = _samples(3)
    before = [s["audio"].copy() for s in src]
    a = asr_finetune.augment_samples(src, seed=7)
    b = asr_finetune.augment_samples(src, seed=7)
    assert all(np.array_equal(x["audio"], y["audio"]) for x, y in zip(a, b))
    assert all(np.array_equal(s["audio"], c) for s, c in zip(src, before))


def test_empty_training_folder_is_a_usage_error(tmp_path):
    assert asr_finetune.main(["--audio-dir", str(tmp_path), "--out", str(tmp_path / "m")]) == 2
