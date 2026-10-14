"""Noise-aware comparison of agent tool-call behaviour.

Record each input several times per prompt/model (REPLAYLENS_FILE=base.jsonl),
then:
  python -m replaylens.noise stability base.jsonl
  python -m replaylens.noise compare base.jsonl cand.jsonl [--margin 0.10] [--fail]

Idea: an agent that disagrees with ITSELF on some inputs should not be blamed
for disagreeing with itself after a prompt change. We measure the baseline's
self-disagreement ("noise floor") and only call a change REAL if the candidate
exceeds it by --margin.
"""
import argparse
import sys
from collections import defaultdict

from ._compat import load_runs, normalize


def _seq(r):
    return tuple(tc.get("name", "?") if isinstance(tc, dict) else str(tc)
                 for tc in (r["tool_calls"] or []))


def _group(path):
    groups = defaultdict(list)
    for r in map(normalize, load_runs(path)):
        groups[r["input"]].append(_seq(r))
    return groups


def baseline_noise(groups):
    """Leave-one-out: how often does a baseline sample show a tool sequence
    that none of the OTHER baseline samples for that input showed?"""
    novel = total = 0
    for seqs in groups.values():
        if len(seqs) < 2:
            continue
        for i, s in enumerate(seqs):
            others = seqs[:i] + seqs[i + 1:]
            total += 1
            novel += s not in others
    return novel, total


def candidate_novelty(base, cand):
    novel = total = 0
    examples = []
    for q, cseqs in cand.items():
        if q not in base:
            continue
        known = set(base[q])
        for s in cseqs:
            total += 1
            if s not in known:
                novel += 1
                if len(examples) < 5:
                    examples.append((q, s, sorted(known)))
    return novel, total, examples


def stability(path):
    groups = _group(path)
    rows = []
    for q, seqs in groups.items():
        if len(seqs) < 2:
            continue
        top = max(set(seqs), key=seqs.count)
        rows.append((seqs.count(top) / len(seqs), len(seqs), len(set(seqs)), q))
    if not rows:
        print("No input appears twice. Record each input at least 3 times.")
        return
    rows.sort()
    mean = sum(r[0] for r in rows) / len(rows)
    print(f"inputs with repeats: {len(rows)}   mean agreement with most common "
          f"tool sequence: {mean:.0%}")
    print("least stable inputs:")
    for agree, n, distinct, q in rows[:5]:
        print(f"  {agree:.0%} agree over {n} runs, {distinct} distinct sequences: {q[:70]!r}")


def compare(base_path, cand_path, margin, fail):
    base, cand = _group(base_path), _group(cand_path)
    bn, bt = baseline_noise(base)
    cn, ct, examples = candidate_novelty(base, cand)
    if ct == 0:
        sys.exit("no overlapping inputs between the two files")
    cand_rate = cn / ct
    print(f"candidate samples compared: {ct}   new tool sequences: {cn} ({cand_rate:.0%})")
    if bt == 0:
        print("noise floor: UNKNOWN (record each baseline input at least 3 times)")
        print("VERDICT: INCONCLUSIVE")
        return 0
    base_rate = bn / bt
    print(f"baseline noise floor: {bn}/{bt} ({base_rate:.0%}) samples disagreed with their own siblings")
    real = cand_rate - base_rate > margin
    for q, s, known in examples:
        print(f"  e.g. {q[:50]!r}: candidate {list(s)} not in baseline {[list(k) for k in known]}")
    print(f"VERDICT: {'REAL CHANGE' if real else 'WITHIN NOISE'} "
          f"(excess {cand_rate - base_rate:+.0%}, margin {margin:.0%}, "
          f"n={ct}: small samples are weak evidence)")
    return 1 if (real and fail) else 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="replaylens.noise")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("stability"); s.add_argument("runs")
    c = sub.add_parser("compare"); c.add_argument("baseline"); c.add_argument("candidate")
    c.add_argument("--margin", type=float, default=0.10)
    c.add_argument("--fail", action="store_true", help="exit 1 on REAL CHANGE (for CI)")
    a = ap.parse_args(argv)
    if a.cmd == "stability":
        stability(a.runs)
        return 0
    return compare(a.baseline, a.candidate, a.margin, a.fail)


if __name__ == "__main__":
    sys.exit(main())
