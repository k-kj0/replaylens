"""Judge calibration.
  python -m replaylens.evalset template runs.jsonl human.csv
  (fill the human_label column with ok/bad, then build judge.csv with columns id,label)
  python -m replaylens.evalset agree human.csv judge.csv"""
import csv, sys
from ._compat import load_runs, normalize

def cohen_kappa(a, b):
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    pe = sum((a.count(l) / n) * (b.count(l) / n) for l in set(a) | set(b))
    if pe == 1:
        return 1.0 if po == 1 else 0.0
    return (po - pe) / (1 - pe)

def template(runs_path, out_path):
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "input", "output", "human_label"])
        for i, r in enumerate(map(normalize, load_runs(runs_path))):
            w.writerow([r["id"] or i, r["input"], r["output"], ""])

def agree(human_path, judge_path):
    human = {r["id"]: r["human_label"] for r in csv.DictReader(open(human_path, encoding="utf-8")) if r["human_label"]}
    judge = {r["id"]: r["label"] for r in csv.DictReader(open(judge_path, encoding="utf-8"))}
    ids = [i for i in human if i in judge]
    if not ids:
        sys.exit("no overlapping ids")
    a, b = [human[i] for i in ids], [judge[i] for i in ids]
    acc = sum(x == y for x, y in zip(a, b)) / len(ids)
    print(f"n={len(ids)}  raw agreement={acc:.0%}  cohen_kappa={cohen_kappa(a, b):.2f}")

if __name__ == "__main__":
    cmd = sys.argv[1]
    template(*sys.argv[2:4]) if cmd == "template" else agree(*sys.argv[2:4])
