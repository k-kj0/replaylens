"""Regression checks for VOICE agents (speech-to-text -> LLM -> text-to-speech).

A voice agent can get worse in ways a text agent cannot: it hears words wrong,
or it answers correctly but TOO SLOWLY, so the caller hears dead air.
This module compares two recordings of the same calls (old vs new) and tells
you which stage got slower, how much the transcript drifted, and whether it is
safe to ship.

Each line of a voice file is one turn of a call (JSON):
  {"call_id": "c1", "turn": 1,
   "user_transcript": "i want a refund",      # what the STT heard
   "agent_transcript": "Sure, one moment.",   # what the agent said back
   "stt_ms": 180, "llm_ms": 420, "tts_ms": 150,
   "first_audio_ms": 750,                      # optional: caller-heard delay
   "interrupted": false}                       # optional: caller talked over the agent

Usage:
  python -m replaylens.voice demo  out_dir
  python -m replaylens.voice compare old.jsonl new.jsonl [--budget-ms 800]
         [--max-wer 0.10] [--max-p95-increase 20] [--md voice_report.md]

Exit codes: 0 = SAFE, 1 = NOT SAFE, 2 = bad usage.
"""
import argparse
import difflib
import json
import math
import os
import random
import re
import sys

STAGES = ("stt_ms", "llm_ms", "tts_ms")


# ---------- loading ----------

def load_calls(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def total_ms(row):
    """Delay the caller hears. Use first_audio_ms if recorded, else add the stages."""
    if row.get("first_audio_ms"):
        return float(row["first_audio_ms"])
    return float(sum(row.get(s, 0) or 0 for s in STAGES))


def _key(row, i):
    return (str(row.get("call_id", "")), row.get("turn", i))


# ---------- small math helpers ----------

def percentile(values, pct):
    """Nearest-rank percentile; 0.0 for an empty list."""
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(1, math.ceil(pct / 100.0 * len(ordered)))
    return float(ordered[rank - 1])


def _words(text):
    return re.sub(r"[^a-z0-9' ]+", " ", (text or "").lower()).split()


def wer(reference, hypothesis):
    """Word error rate: word edits needed to turn reference into hypothesis, / reference length."""
    ref, hyp = _words(reference), _words(hypothesis)
    if not ref:
        return 0.0 if not hyp else 1.0
    prev = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        cur = [i]
        for j, h in enumerate(hyp, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (r != h)))
        prev = cur
    return prev[-1] / len(ref)


def pct_change(old, new):
    if old == 0:
        return 0.0 if new == 0 else float("inf")
    return 100.0 * (new - old) / old


# ---------- comparison ----------

def compare(old_rows, new_rows, budget_ms=800):
    old = {_key(r, i): r for i, r in enumerate(old_rows)}
    new = {_key(r, i): r for i, r in enumerate(new_rows)}
    keys = [k for k in old if k in new]
    if not keys:
        raise ValueError("no matching (call_id, turn) pairs between the two files")

    pairs = [(old[k], new[k]) for k in keys]
    stages = {}
    for name in STAGES + ("total",):
        get = total_ms if name == "total" else (lambda r, n=name: float(r.get(n, 0) or 0))
        o, n = [get(a) for a, _ in pairs], [get(b) for _, b in pairs]
        stages[name] = {"old_p50": percentile(o, 50), "new_p50": percentile(n, 50),
                        "old_p95": percentile(o, 95), "new_p95": percentile(n, 95)}

    wers = [wer(a.get("user_transcript"), b.get("user_transcript")) for a, b in pairs]
    sims = [difflib.SequenceMatcher(None, a.get("agent_transcript", ""),
                                    b.get("agent_transcript", "")).ratio() for a, b in pairs]
    n = len(pairs)
    rate = lambda xs: sum(xs) / n
    worst = sorted(((total_ms(b) - total_ms(a), k) for (a, b), k in zip(pairs, keys)),
                   reverse=True)[:5]
    return {
        "turns_compared": n,
        "turns_only_in_one_file": (len(old) - n) + (len(new) - n),
        "budget_ms": budget_ms,
        "stages": stages,
        "mean_wer": rate(wers),
        "turns_with_heard_differently": sum(w > 0 for w in wers),
        "mean_agent_similarity": rate(sims),
        "agent_reply_changed_a_lot": sum(s < 0.6 for s in sims),
        "over_budget_old": rate([total_ms(a) > budget_ms for a, _ in pairs]),
        "over_budget_new": rate([total_ms(b) > budget_ms for _, b in pairs]),
        "interrupt_old": rate([bool(a.get("interrupted")) for a, _ in pairs]),
        "interrupt_new": rate([bool(b.get("interrupted")) for _, b in pairs]),
        "slowest_regressions": [{"call_id": k[0], "turn": k[1], "added_ms": round(d)}
                                for d, k in worst if d > 0],
    }


def evaluate(result, max_wer=0.10, max_p95_increase=20.0, max_over_budget_increase=0.05,
             min_abs_ms=50.0):
    """Return a list of failure messages. Empty list = SAFE."""
    fails = []
    if result["mean_wer"] > max_wer:
        fails.append(f"transcripts drifted: mean WER {result['mean_wer']:.1%} > {max_wer:.1%}")
    t = result["stages"]["total"]
    change = pct_change(t["old_p95"], t["new_p95"])
    if change > max_p95_increase and (t["new_p95"] - t["old_p95"]) >= min_abs_ms:
        fails.append(f"p95 response delay {t['old_p95']:.0f}ms -> {t['new_p95']:.0f}ms "
                     f"(+{change:.0f}% > {max_p95_increase:.0f}%)")
    over = result["over_budget_new"] - result["over_budget_old"]
    if over > max_over_budget_increase:
        fails.append(f"turns slower than {result['budget_ms']}ms went "
                     f"{result['over_budget_old']:.0%} -> {result['over_budget_new']:.0%}")
    if result["interrupt_new"] - result["interrupt_old"] > 0.05:
        fails.append(f"callers talk over the agent more: "
                     f"{result['interrupt_old']:.0%} -> {result['interrupt_new']:.0%}")
    return fails


def to_markdown(result, fails):
    lines = [f"## ReplayLens voice report: {'NOT SAFE' if fails else 'SAFE'}", "",
             f"Compared {result['turns_compared']} turns "
             f"(latency budget {result['budget_ms']}ms).", "",
             "| stage | p50 old | p50 new | p95 old | p95 new |", "|---|---|---|---|---|"]
    for name, s in result["stages"].items():
        lines.append(f"| {name} | {s['old_p50']:.0f} | {s['new_p50']:.0f} | "
                     f"{s['old_p95']:.0f} | {s['new_p95']:.0f} |")
    lines += ["",
              f"- Transcript drift (mean WER): **{result['mean_wer']:.1%}** "
              f"({result['turns_with_heard_differently']} turns heard differently)",
              f"- Agent replies that changed a lot: {result['agent_reply_changed_a_lot']}",
              f"- Turns over budget: {result['over_budget_old']:.0%} -> {result['over_budget_new']:.0%}",
              f"- Caller interruptions: {result['interrupt_old']:.0%} -> {result['interrupt_new']:.0%}"]
    if result["slowest_regressions"]:
        lines += ["", "Slowest new turns:"]
        lines += [f"- call {r['call_id']} turn {r['turn']}: +{r['added_ms']}ms"
                  for r in result["slowest_regressions"]]
    if fails:
        lines += ["", "**Why it failed:**"] + [f"- {f}" for f in fails]
    return "\n".join(lines) + "\n"


# ---------- demo data (no API key, no audio needed) ----------

UTTERANCES = [
    ("i want to cancel my subscription", "Sure, I can help you cancel that."),
    ("what is my account balance", "Your balance is forty two dollars."),
    ("please refund order one zero zero three", "I have started your refund."),
    ("can you speak to a human agent", "Transferring you to a person now."),
    ("my card was declined yesterday", "I am sorry, let me check that."),
]


def make_demo(out_dir, calls=10, turns=4, seed=7):
    """Write old.jsonl (baseline) and new.jsonl (a slower TTS + worse STT candidate)."""
    rng = random.Random(seed)
    os.makedirs(out_dir, exist_ok=True)
    old_rows, new_rows = [], []
    for c in range(calls):
        for t in range(turns):
            heard, said = rng.choice(UTTERANCES)
            stt, llm, tts = rng.randint(120, 220), rng.randint(280, 480), rng.randint(90, 180)
            old_rows.append({"call_id": f"c{c}", "turn": t, "user_transcript": heard,
                             "agent_transcript": said, "stt_ms": stt, "llm_ms": llm,
                             "tts_ms": tts, "interrupted": rng.random() < 0.05})
            words = heard.split()
            if rng.random() < 0.25 and len(words) > 3:      # candidate STT mishears a word
                words[rng.randrange(len(words))] = "uh"
            slow_tts = tts + rng.randint(180, 320)          # candidate TTS is slower
            new_rows.append({"call_id": f"c{c}", "turn": t, "user_transcript": " ".join(words),
                             "agent_transcript": said, "stt_ms": stt + rng.randint(-20, 20),
                             "llm_ms": llm + rng.randint(-30, 30), "tts_ms": slow_tts,
                             "interrupted": rng.random() < 0.12})
    for name, rows in (("old.jsonl", old_rows), ("new.jsonl", new_rows)):
        with open(os.path.join(out_dir, name), "w", encoding="utf-8") as f:
            f.write("\n".join(json.dumps(r) for r in rows) + "\n")
    print(f"wrote {len(old_rows)} turns each to {out_dir}/old.jsonl and {out_dir}/new.jsonl")


# ---------- command line ----------

def main(argv=None):
    ap = argparse.ArgumentParser(prog="replaylens.voice", description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("demo", help="write sample old.jsonl / new.jsonl")
    d.add_argument("out_dir")
    c = sub.add_parser("compare", help="compare two voice recordings")
    c.add_argument("old")
    c.add_argument("new")
    c.add_argument("--budget-ms", type=float, default=800, help="max comfortable reply delay")
    c.add_argument("--max-wer", type=float, default=0.10)
    c.add_argument("--max-p95-increase", type=float, default=20.0, help="percent")
    c.add_argument("--min-abs-ms", type=float, default=50.0, help="ignore smaller p95 changes")
    c.add_argument("--md", default=None, help="also write the report as markdown")
    c.add_argument("--json", default=None, help="also write the raw numbers as JSON")
    a = ap.parse_args(argv)

    if a.cmd == "demo":
        make_demo(a.out_dir)
        return 0
    try:
        result = compare(load_calls(a.old), load_calls(a.new), a.budget_ms)
    except (OSError, ValueError) as exc:
        print(f"usage error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    fails = evaluate(result, a.max_wer, a.max_p95_increase, min_abs_ms=a.min_abs_ms)
    report = to_markdown(result, fails)
    print(report)
    if a.md:
        with open(a.md, "w", encoding="utf-8") as f:
            f.write(report)
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump({"result": result, "failures": fails}, f, indent=2)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
