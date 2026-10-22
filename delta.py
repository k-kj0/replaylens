"""PREFIX-DELTA LOG: store each multi-turn row's input as (base row, new suffix).

Multi-turn rows repeat the whole conversation so far in "input", so raw storage
grows quadratically with conversation length. When a row's input extends an
earlier row's input, we keep only the new text plus a pointer to that row.
Encoding is lossless and deterministic: same rows in, same bytes out.
"""
import json


def encode_rows(rows):
    """Return rows where "input" may be {"base": index, "suffix": str}."""
    seen = []  # (row_index, input_text) in order
    out = []
    for i, row in enumerate(rows):
        text = row["input"]
        base = None
        for j, prev in reversed(seen):
            if len(prev) < len(text) and text.startswith(prev):
                base = j
                break
        new = dict(row)
        if base is not None:
            new["input"] = {"base": base, "suffix": text[len(rows[base]["input"]):]}
        out.append(new)
        seen.append((i, text))
    return out


def decode_rows(encoded):
    """Inverse of encode_rows. Raises ValueError on a bad pointer."""
    rows = []
    for i, row in enumerate(encoded):
        new = dict(row)
        inp = row["input"]
        if isinstance(inp, dict):
            base = inp["base"]
            if not (0 <= base < i):
                raise ValueError(f"row {i}: invalid base pointer {base}")
            new["input"] = rows[base]["input"] + inp["suffix"]
        rows.append(new)
    return rows


def save_delta(rows, path):
    with open(path, "w", encoding="utf-8") as f:
        for row in encode_rows(rows):
            f.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")


def load_delta(path):
    encoded = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                encoded.append(json.loads(line))
    return decode_rows(encoded)


def main(argv=None):
    import argparse
    import os
    from .recorder import load_runs

    ap = argparse.ArgumentParser(prog="replaylens.delta",
                                 description="Compress a runs.jsonl with prefix deltas and report the saving.")
    ap.add_argument("runs", help="input runs.jsonl")
    ap.add_argument("--out", default="runs.delta.jsonl", help="output file")
    args = ap.parse_args(argv)

    rows = load_runs(args.runs)
    save_delta(rows, args.out)
    assert load_delta(args.out) == rows, "round-trip mismatch"  # lossless check
    before, after = os.path.getsize(args.runs), os.path.getsize(args.out)
    pct = 100.0 * (before - after) / before if before else 0.0
    print(f"{len(rows)} rows: {before} -> {after} bytes ({pct:.1f}% smaller), round-trip OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
