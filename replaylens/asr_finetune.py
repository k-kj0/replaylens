"""Fine-tune a small Whisper model on phone-quality speech, then benchmark it.

Train data is clean read speech degraded like a phone call (300-3400 Hz, 8 kHz,
mu-law, random noise between 5 and 20 dB SNR), so the model adapts to what a
voice agent actually hears. After training, compare it with the original model
using the same benchmark:

  python -m replaylens.asr_finetune --model openai/whisper-tiny.en --train-clips 1200 --steps 400 --out out/whisper-tiny-phone
  python -m replaylens.asr_bench run --model openai/whisper-tiny.en --phone --snr 10 --out out/tiny-phone.jsonl
  python -m replaylens.asr_bench run --model out/whisper-tiny-phone --phone --snr 10 --out out/tiny-finetuned-phone.jsonl
  python -m replaylens.asr_bench report out/tiny-phone.jsonl out/tiny-finetuned-phone.jsonl

Needs a GPU for reasonable speed (free Colab T4) and: pip install -e ".[asr]".
English-only Whisper models (name ends in .en). Train clips come from LibriSpeech;
the benchmark's default clips come from a different split, so there is no overlap.
"""
import argparse
import random
import sys

from . import asr_bench


def load_train_samples(limit=1200):
    """Stream LibriSpeech clean train.100 clips (needs: pip install 'datasets<4' soundfile)."""
    np = asr_bench._np()
    from datasets import load_dataset
    ds = load_dataset("librispeech_asr", "clean", split="train.100", streaming=True)
    out = []
    for row in ds.take(limit):
        out.append({"id": str(row.get("id", len(out))), "audio": np.asarray(row["audio"]["array"], dtype=np.float32),
                    "sr": row["audio"]["sampling_rate"], "text": row["text"]})
    return out


def augment_samples(samples, seed=0, snr_range=(5.0, 20.0)):
    """Return copies of the samples degraded like a phone call, each with its own noise level."""
    rng = random.Random(seed)
    out = []
    for i, s in enumerate(samples):
        snr = rng.uniform(*snr_range)
        out.append({**s, "audio": asr_bench.degrade(s["audio"], s["sr"], phone=True, snr_db=snr, seed=seed + i)})
    return out


def train(model_name, samples, out_dir, steps=400, batch_size=16, lr=1e-5, seed=0):
    """Fine-tune and save the model and processor to out_dir."""
    from dataclasses import dataclass

    import torch
    from transformers import (Seq2SeqTrainer, Seq2SeqTrainingArguments, WhisperForConditionalGeneration,
                              WhisperProcessor)

    processor = WhisperProcessor.from_pretrained(model_name)
    model = WhisperForConditionalGeneration.from_pretrained(model_name)

    features = [{"input_features": processor.feature_extractor(s["audio"], sampling_rate=s["sr"]).input_features[0],
                 "labels": processor.tokenizer(s["text"].lower()).input_ids} for s in samples]

    @dataclass
    class Collator:
        start_token: int

        def __call__(self, batch):
            out = processor.feature_extractor.pad([{"input_features": b["input_features"]} for b in batch],
                                                  return_tensors="pt")
            lab = processor.tokenizer.pad([{"input_ids": b["labels"]} for b in batch], return_tensors="pt")
            labels = lab["input_ids"].masked_fill(lab.attention_mask.ne(1), -100)
            if (labels[:, 0] == self.start_token).all().cpu().item():
                labels = labels[:, 1:]
            out["labels"] = labels
            return out

    args = Seq2SeqTrainingArguments(
        output_dir=out_dir + "_trainer", per_device_train_batch_size=batch_size, learning_rate=lr,
        max_steps=steps, warmup_steps=max(1, min(50, steps // 10)), fp16=torch.cuda.is_available(),
        logging_steps=25, save_strategy="no", report_to="none", remove_unused_columns=False, seed=seed)
    trainer = Seq2SeqTrainer(model=model, args=args, train_dataset=features,
                             data_collator=Collator(model.config.decoder_start_token_id))
    trainer.train()
    model.save_pretrained(out_dir)
    processor.save_pretrained(out_dir)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="replaylens.asr_finetune", description=__doc__.split("\n")[0])
    ap.add_argument("--model", default="openai/whisper-tiny.en")
    ap.add_argument("--train-clips", type=int, default=1200)
    ap.add_argument("--steps", type=int, default=400)
    ap.add_argument("--batch-size", type=int, default=16)
    ap.add_argument("--lr", type=float, default=1e-5)
    ap.add_argument("--audio-dir", default=None, help="folder of .wav + .txt instead of streaming LibriSpeech")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    if not a.model.endswith(".en") and "/" in a.model and not a.model.startswith("."):
        print("note: this script is tested for English-only Whisper models (name ends in .en)", file=sys.stderr)
    samples = (list(asr_bench.load_audio_dir(a.audio_dir, a.train_clips)) if a.audio_dir
               else load_train_samples(a.train_clips))
    if not samples:
        print("usage error: no training clips found", file=sys.stderr)
        return 2
    print(f"training on {len(samples)} phone-degraded clips for {a.steps} steps")
    train(a.model, augment_samples(samples, a.seed), a.out, a.steps, a.batch_size, a.lr, a.seed)
    print(f"saved fine-tuned model to {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
