"""PYTHONPATH=. python scripts/bench_endpoints.py runs.jsonl \
     --base-url https://api.together.xyz/v1 --model MODEL --key-env TOGETHER_API_KEY"""
import argparse, os, statistics, sys, time
from openai import OpenAI
from replaylens._compat import load_runs, normalize

ap = argparse.ArgumentParser()
ap.add_argument("runs"); ap.add_argument("--base-url", required=True)
ap.add_argument("--model", required=True); ap.add_argument("--key-env", default="OPENAI_API_KEY")
ap.add_argument("--max-tokens", type=int, default=200); ap.add_argument("--limit", type=int, default=20)
a = ap.parse_args()

client = OpenAI(base_url=a.base_url, api_key=os.environ[a.key_env])
lat, tps, errors = [], [], 0
for r in list(map(normalize, load_runs(a.runs)))[: a.limit]:
    t0 = time.perf_counter()
    try:
        resp = client.chat.completions.create(
            model=a.model, max_tokens=a.max_tokens,
            messages=[{"role": "user", "content": r["input"]}])
    except Exception as e:
        errors += 1; print("error:", type(e).__name__, file=sys.stderr); continue
    dt = time.perf_counter() - t0
    lat.append(dt)
    toks = getattr(resp.usage, "completion_tokens", 0) or 0
    if toks: tps.append(toks / dt)

def pct(xs, p):
    xs = sorted(xs); return xs[min(len(xs) - 1, int(p * len(xs)))] if xs else float("nan")

print(f"| model | ok | err | p50 s | p95 s | median tok/s |")
print(f"| {a.model} | {len(lat)} | {errors} | {pct(lat,.5):.2f} | {pct(lat,.95):.2f} | "
      f"{statistics.median(tps) if tps else float('nan'):.1f} |")
