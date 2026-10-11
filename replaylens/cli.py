"""Command line: replaylens replay | benchmark | report"""
import argparse
import importlib
import json
import os
import sys

from .compare import compare_run, summarize
from .recorder import load_runs
from .replayer import replay_runs
from .report import write_html


def load_agent(spec):
    sys.path.insert(0, os.getcwd())
    mod, _, fn = spec.partition(":")
    return getattr(importlib.import_module(mod), fn)


def cmd_replay(a):
    if a.mock:
        os.environ["REPLAYLENS_MOCK"] = "1"
    if a.base_url:
        os.environ["OPENAI_BASE_URL"] = a.base_url
    runs = load_runs(a.runs)
    agent = load_agent(a.agent)
    prompt = open(a.prompt, encoding="utf-8").read() if a.prompt else None
    if prompt is None:
        raise SystemExit("Please pass --prompt path/to/prompt.txt (the system prompt to test).")
    model = a.model or runs[0]["model"]
    rules = json.load(open(a.rules)) if a.rules else None

    judge = None
    if a.judge_model:
        from .judge import make_judge
        from openai import OpenAI
        judge = make_judge(OpenAI(), a.judge_model)

    print(f"Replaying {len(runs)} runs with model={model} ...")
    pairs = replay_runs(runs, agent, model, prompt, prompt_version=os.path.basename(a.prompt),
                        price_in=a.price_in, price_out=a.price_out, workers=a.workers)
    results = [compare_run(old, new, rules, judge) for old, new in pairs]
    summary = summarize(results, a.max_regressions)
    report = {"old_label": f"{runs[0]['model']} / {runs[0]['prompt_version']}",
              "new_label": f"{model} / {os.path.basename(a.prompt)}",
              "summary": summary, "results": results}
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    write_html(report, a.html)
    print_summary(summary, a)
    if a.fail_on_regression and not summary["safe_to_ship"]:
        sys.exit(1)


def cmd_benchmark(a):
    """Replay the SAME recorded runs on several models and print a comparison table."""
    if a.mock:
        os.environ["REPLAYLENS_MOCK"] = "1"
    if a.base_url:
        os.environ["OPENAI_BASE_URL"] = a.base_url
    runs = load_runs(a.runs)
    agent = load_agent(a.agent)
    prompt = open(a.prompt, encoding="utf-8").read()
    rules = json.load(open(a.rules)) if a.rules else None
    models = [m.strip() for m in a.models.split(",") if m.strip()]
    prices = [x.strip() for x in a.prices.split(",")] if a.prices else []
    rows = []
    for i, model in enumerate(models):
        p_in = p_out = None
        if i < len(prices) and ":" in prices[i]:
            p_in, p_out = (float(v) for v in prices[i].split(":"))
        print(f"Benchmarking {model} ...")
        pairs = replay_runs(runs, agent, model, prompt, prompt_version=os.path.basename(a.prompt),
                            price_in=p_in, price_out=p_out, workers=a.workers)
        results = [compare_run(o, n, rules) for o, n in pairs]
        s = summarize(results, a.max_regressions)
        rows.append({"model": model, **s})
    lines = ["| model | runs | same | regressions | cost change | latency change | verdict |",
             "|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['model']} | {r['total_runs']} | {r['same']} | {r['regressions']} | "
                     f"{r['cost_change_pct']:+}% | {r['latency_change_pct']:+}% | "
                     f"{'SAFE' if r['safe_to_ship'] else 'NOT SAFE'} |")
    table = "\n".join(lines)
    print("\n" + table)
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(table + "\n")
    print(f"\nWrote {a.out} (paste it into your README)")


def print_summary(s, a):
    print(f"\nOut of {s['total_runs']} past runs: {s['same']} same, {s['improved']} better, "
          f"{s['changed']} changed wording, {s['regressions']} REGRESSED")
    print(f"Cost {s['cost_change_pct']:+}%   Latency {s['latency_change_pct']:+}%")
    print("VERDICT:", "SAFE TO SHIP" if s["safe_to_ship"] else "NOT SAFE TO SHIP")
    print(f"Wrote {a.out} and {a.html}")


def cmd_report(a):
    report = json.load(open(a.report_json))
    write_html(report, a.html)
    print("Wrote", a.html)


def main(argv=None):
    p = argparse.ArgumentParser(prog="replaylens")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("replay", help="re-run recorded runs with a new prompt/model")
    r.add_argument("runs", help="runs.jsonl made by @record")
    r.add_argument("--agent", required=True, help="module:function, e.g. examples.refund_bot:run_agent")
    r.add_argument("--prompt", help="text file with the NEW system prompt")
    r.add_argument("--model", help="NEW model name (default: same as recorded)")
    r.add_argument("--base-url", help="any OpenAI-compatible endpoint (Together, Runpod, Groq, OpenRouter)")
    r.add_argument("--rules", help="JSON file with must_not_contain / must_contain_any")
    r.add_argument("--judge-model", help="optional LLM judge model (needs `pip install openai`)")
    r.add_argument("--price-in", type=float, default=None, help="$ per 1M input tokens of the NEW model (default: same as recorded)")
    r.add_argument("--price-out", type=float, default=None, help="$ per 1M output tokens of the NEW model (default: same as recorded)")
    r.add_argument("--workers", type=int, default=4)
    r.add_argument("--max-regressions", type=int, default=0)
    r.add_argument("--fail-on-regression", action="store_true", help="exit code 1 (for CI)")
    r.add_argument("--mock", action="store_true", help="use the built-in fake LLM (no API key)")
    r.add_argument("--out", default="report.json")
    r.add_argument("--html", default="report.html")
    r.set_defaults(fn=cmd_replay)

    b = sub.add_parser("benchmark", help="replay the same runs on several models and compare")
    b.add_argument("runs")
    b.add_argument("--agent", required=True)
    b.add_argument("--prompt", required=True)
    b.add_argument("--models", required=True, help="comma-separated model names")
    b.add_argument("--prices", help="comma-separated in:out $/1M tokens per model, e.g. 0.15:0.6,0.88:0.88")
    b.add_argument("--base-url")
    b.add_argument("--rules")
    b.add_argument("--workers", type=int, default=4)
    b.add_argument("--max-regressions", type=int, default=0)
    b.add_argument("--mock", action="store_true")
    b.add_argument("--out", default="benchmark.md")
    b.set_defaults(fn=cmd_benchmark)

    h = sub.add_parser("report", help="rebuild report.html from report.json")
    h.add_argument("report_json")
    h.add_argument("--html", default="report.html")
    h.set_defaults(fn=cmd_report)

    a = p.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
