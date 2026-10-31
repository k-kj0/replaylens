"""Benchmark speech-to-text models on phone-quality audio, then feed ReplayLens.

Voice agents are judged on how they sound on a phone call, not in a studio. This
module takes clean speech, degrades it the way a phone line does (300-3400 Hz band,
8 kHz sampling, mu-law companding as in G.711, optional background noise), runs an
ASR model and records word error rate, latency and real-time factor.

Each row is written in the ReplayLens voice format, so two runs can be compared
with `python -m replaylens.voice compare old.jsonl new.jsonl`, or pasted into the
Voice tab of dashboard/audit.html. Extra fields (reference, rtf, device, ...) are
ignored by the voice checker.

Usage (needs: pip install -e ".[asr]"):
  python -m replaylens.asr_bench run --model openai/whisper-tiny.en --limit 40 --out out/tiny-clean.jsonl
  python -m replaylens.asr_bench run --model openai/whisper-tiny.en --phone --snr 10 --out out/tiny-phone.jsonl
  python -m replaylens.asr_bench run --model openai/whisper-small.en --fp16 --audio-dir my_wavs --out out/small.jsonl
  python -m replaylens.asr_bench run --model openai/whisper-base.en --cpu --out out/base-fp32-cpu.jsonl
  python -m replaylens.asr_bench run --model openai/whisper-base.en --int8 --out out/base-int8-cpu.jsonl
  python -m replaylens.asr_bench report out/*.jsonl --md out/report.md

--audio-dir expects 16-bit PCM .wav files, each with a same-named .txt holding the reference text.
--int8 applies PyTorch dynamic int8 quantization to the linear layers and runs on CPU;
compare it with --cpu (fp32) to see the accuracy, speed and size trade-off.
Note: stt_ms is time spent transcribing a finished clip, not streaming latency.
"""
import argparse
import glob
import json
import os
import sys
import time
import wave

from .voice import percentile, wer

TARGET_SR = 16000


def _np():
    try:
        import numpy as np
    except ImportError:
        raise SystemExit("asr_bench needs numpy: pip install numpy (or pip install -e '.[asr]')")
    return np


# ---------- phone-line simulation ----------

def band_limit(x, sr, lo=300.0, hi=3400.0):
    """Keep only the telephone band (default 300-3400 Hz)."""
    np = _np()
    spec = np.fft.rfft(x)
    freqs = np.fft.rfftfreq(len(x), 1.0 / sr)
    spec[(freqs < lo) | (freqs > hi)] = 0
    return np.fft.irfft(spec, n=len(x))


def mulaw_roundtrip(x, mu=255):
    """Compress to 8-bit mu-law (G.711 style) and expand again."""
    np = _np()
    x = np.clip(x, -1.0, 1.0)
    y = np.sign(x) * np.log1p(mu * np.abs(x)) / np.log1p(mu)
    q = np.round((y + 1.0) / 2.0 * mu)
    y2 = q / mu * 2.0 - 1.0
    return np.sign(y2) * ((1.0 + mu) ** np.abs(y2) - 1.0) / mu


def add_noise(x, snr_db, seed=0):
    """Add white noise so the signal-to-noise ratio equals snr_db."""
    np = _np()
    power = float(np.mean(x ** 2))
    if power == 0:
        return x
    noise = np.random.default_rng(seed).standard_normal(len(x))
    noise *= (power / (10 ** (snr_db / 10.0)) / float(np.mean(noise ** 2))) ** 0.5
    return x + noise


def degrade(x, sr, phone=False, snr_db=None, seed=0):
    """Return a float32 copy of x as heard over a phone line and/or with noise."""
    np = _np()
    x = np.asarray(x, dtype=np.float64)
    if phone:
        x = band_limit(x, sr)
        n8 = int(len(x) * 8000 / sr)
        t_old, t_8k = np.arange(len(x)) / sr, np.arange(n8) / 8000.0
        x8 = mulaw_roundtrip(np.interp(t_8k, t_old, x))
        x = np.interp(t_old, t_8k, x8)
    if snr_db is not None:
        x = add_noise(x, snr_db, seed)
    return np.clip(x, -1.0, 1.0).astype(np.float32)


def condition_name(phone, snr_db):
    parts = (["phone"] if phone else []) + ([f"snr{snr_db:g}"] if snr_db is not None else [])
    return "+".join(parts) or "clean"


# ---------- data ----------

def load_audio_dir(path, limit=None):
    """Yield samples from 16-bit PCM wavs with matching .txt reference files."""
    np = _np()
    for i, wav_path in enumerate(sorted(glob.glob(os.path.join(path, "*.wav")))):
        if limit is not None and i >= limit:
            break
        ref_path = os.path.splitext(wav_path)[0] + ".txt"
        if not os.path.exists(ref_path):
            continue
        with wave.open(wav_path, "rb") as w:
            if w.getsampwidth() != 2:
                raise ValueError(f"{wav_path}: only 16-bit PCM wav is supported")
            sr, ch = w.getframerate(), w.getnchannels()
            data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
        if ch > 1:
            data = data.reshape(-1, ch).mean(axis=1)
        if sr != TARGET_SR:
            t_old, t_new = np.arange(len(data)) / sr, np.arange(int(len(data) * TARGET_SR / sr)) / TARGET_SR
            data, sr = np.interp(t_new, t_old, data).astype(np.float32), TARGET_SR
        with open(ref_path, encoding="utf-8") as f:
            yield {"id": os.path.splitext(os.path.basename(wav_path))[0], "audio": data, "sr": sr,
                   "text": f.read().strip()}


def load_hf_samples(limit=40, dataset="hf-internal-testing/librispeech_asr_dummy",
                    config="clean", split="validation"):
    """Yield samples from a Hugging Face speech dataset (needs: pip install 'datasets<4')."""
    np = _np()
    from datasets import load_dataset
    ds = load_dataset(dataset, config, split=split)
    for i, row in enumerate(ds):
        if limit is not None and i >= limit:
            break
        yield {"id": str(row.get("id", i)), "audio": np.asarray(row["audio"]["array"], dtype=np.float32),
               "sr": row["audio"]["sampling_rate"], "text": row["text"]}


# ---------- model ----------

def _model_mb(model):
    """Size of the model's weights in MB (works for quantized models too)."""
    import io
    import torch
    buf = io.BytesIO()
    torch.save(model.state_dict(), buf)
    return round(buf.tell() / 1e6, 1)


def load_whisper(model_name, fp16=False, int8=False, cpu=False):
    """Return (transcribe(wave, sr) -> text, device_info). Needs torch + transformers.

    int8 = PyTorch dynamic quantization of the linear layers (CPU only).
    """
    import torch
    from transformers import pipeline
    cuda = torch.cuda.is_available() and not (cpu or int8)
    dtype = torch.float16 if (fp16 and cuda) else torch.float32
    pipe = pipeline("automatic-speech-recognition", model=model_name, device=0 if cuda else -1,
                    torch_dtype=dtype)
    if int8:
        pipe.model = torch.ao.quantization.quantize_dynamic(pipe.model, {torch.nn.Linear}, dtype=torch.qint8)

    def transcribe(wave_, sr):
        if cuda:
            torch.cuda.synchronize()
        text = pipe({"raw": wave_, "sampling_rate": sr}, chunk_length_s=30)["text"]
        if cuda:
            torch.cuda.synchronize()
        return text

    def peak_mb():
        return round(torch.cuda.max_memory_allocated() / 1e6) if cuda else None

    label = "int8-dynamic" if int8 else ("fp16" if dtype == torch.float16 else "fp32")
    info = {"device": torch.cuda.get_device_name(0) if cuda else "cpu", "dtype": label,
            "peak_mb": peak_mb, "model_mb": _model_mb(pipe.model)}
    return transcribe, info


# ---------- benchmark ----------

def run_bench(transcribe, samples, model_label, phone=False, snr_db=None, seed=0,
              device="cpu", dtype="fp32", peak_mb=None, warmup=True, model_mb=None):
    """Run one model on one condition. Returns rows in ReplayLens voice format."""
    samples = list(samples)
    condition = condition_name(phone, snr_db)
    if warmup and samples:  # first call pays one-off startup cost; keep it out of the timings
        transcribe(samples[0]["audio"], samples[0]["sr"])
    rows = []
    for i, s in enumerate(samples):
        wave_ = degrade(s["audio"], s["sr"], phone, snr_db, seed + i) if (phone or snr_db is not None) else s["audio"]
        start = time.perf_counter()
        heard = (transcribe(wave_, s["sr"]) or "").strip()
        ms = (time.perf_counter() - start) * 1000.0
        dur = len(wave_) / float(s["sr"])
        rows.append({"call_id": s["id"], "turn": 0, "user_transcript": heard, "agent_transcript": "",
                     "stt_ms": round(ms, 1), "llm_ms": 0, "tts_ms": 0,
                     "reference": s["text"], "wer": round(wer(s["text"], heard), 4),
                     "audio_s": round(dur, 2), "rtf": round(ms / 1000.0 / dur, 3) if dur else None,
                     "model": model_label, "condition": condition, "device": device, "dtype": dtype,
                     "peak_gpu_mb": peak_mb() if callable(peak_mb) else peak_mb,
                     "model_mb": model_mb})
    return rows


def summarize(rows):
    if not rows:
        raise ValueError("no rows")
    ms = [r["stt_ms"] for r in rows]
    rtf = [r["rtf"] for r in rows if r.get("rtf") is not None]
    f = rows[0]
    return {"model": f["model"], "condition": f["condition"], "dtype": f.get("dtype", ""),
            "device": f.get("device", ""), "clips": len(rows),
            "mean_wer": sum(r["wer"] for r in rows) / len(rows),
            "p50_ms": percentile(ms, 50), "p95_ms": percentile(ms, 95),
            "mean_rtf": sum(rtf) / len(rtf) if rtf else 0.0, "peak_gpu_mb": f.get("peak_gpu_mb"),
            "model_mb": f.get("model_mb")}


def to_markdown(summaries):
    lines = ["| model | condition | dtype | device | clips | WER | p50 ms | p95 ms | RTF | peak GPU MB | model MB |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for s in summaries:
        lines.append(f"| {s['model']} | {s['condition']} | {s['dtype']} | {s['device']} | {s['clips']} | "
                     f"{s['mean_wer']:.1%} | {s['p50_ms']:.0f} | {s['p95_ms']:.0f} | {s['mean_rtf']:.3f} | "
                     f"{s['peak_gpu_mb'] if s['peak_gpu_mb'] is not None else '-'} | "
                     f"{s['model_mb'] if s['model_mb'] is not None else '-'} |")
    return "\n".join(lines) + "\n"


def _read_rows(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def main(argv=None):
    ap = argparse.ArgumentParser(prog="replaylens.asr_bench", description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="benchmark one model on one audio condition")
    r.add_argument("--model", required=True, help="Hugging Face ASR model, e.g. openai/whisper-tiny.en")
    r.add_argument("--limit", type=int, default=40)
    r.add_argument("--phone", action="store_true", help="simulate a phone line (300-3400 Hz, 8 kHz, mu-law)")
    r.add_argument("--snr", type=float, default=None, help="add white noise at this SNR in dB")
    r.add_argument("--fp16", action="store_true", help="half precision (GPU only)")
    r.add_argument("--int8", action="store_true", help="dynamic int8 quantization (runs on CPU)")
    r.add_argument("--cpu", action="store_true", help="force CPU, for a fair fp32 vs int8 comparison")
    r.add_argument("--audio-dir", default=None, help="folder of .wav + .txt instead of the Hugging Face demo set")
    r.add_argument("--seed", type=int, default=0)
    r.add_argument("--out", required=True)
    p = sub.add_parser("report", help="summarize one or more result files")
    p.add_argument("files", nargs="+")
    p.add_argument("--md", default=None)
    a = ap.parse_args(argv)

    if a.cmd == "report":
        try:
            files = [f for pat in a.files for f in (glob.glob(pat) or [pat])]
            table = to_markdown([summarize(_read_rows(f)) for f in sorted(files)])
        except (OSError, ValueError) as exc:
            print(f"usage error: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 2
        print(table)
        if a.md:
            with open(a.md, "w", encoding="utf-8") as f:
                f.write(table)
        return 0

    samples = load_audio_dir(a.audio_dir, a.limit) if a.audio_dir else load_hf_samples(a.limit)
    transcribe, info = load_whisper(a.model, a.fp16, a.int8, a.cpu)
    rows = run_bench(transcribe, samples, a.model, a.phone, a.snr, a.seed, info["device"], info["dtype"], info["peak_mb"],
                     model_mb=info["model_mb"])
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        f.write("\n".join(json.dumps(x) for x in rows) + "\n")
    s = summarize(rows)
    print(f"{s['model']} [{s['condition']}, {s['dtype']}, {s['device']}]: WER {s['mean_wer']:.1%}, "
          f"p95 {s['p95_ms']:.0f} ms, RTF {s['mean_rtf']:.3f}, model {s['model_mb']} MB, "
          f"{s['clips']} clips -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
