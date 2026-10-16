# ReplayLens

**A flight recorder + replay button for AI agents.** Change a prompt or switch to a cheaper model, replay your real past conversations,
and see exactly what behaves differently, especially which *tools* the agent now calls.

## Why

Changing a prompt or swapping in a cheaper model can silently change which tools an agent calls
or what it says to customers. Unit tests don't catch that. ReplayLens replays your real past
conversations against the change and tells you exactly what behaves differently, in one command,
with no account and no hosted service.

**Built for:** teams shipping agents (support, voice, finance, healthcare) who need a
SAFE / NOT SAFE gate in CI before a prompt or model change goes out.

## Install

```
pip install git+https://github.com/k-kj0/replaylens@v0.1.0
```

## Quickstart (2 minutes, no API key)

```
git clone https://github.com/k-kj0/replaylens && cd replaylens
python -m venv .venv && source .venv/bin/activate
pip install -e .
python -m examples.refund_bot          # records 30 demo runs
python -m replaylens replay runs.jsonl --agent examples.refund_bot:run_agent \
  --prompt examples/prompts/p2_fast.txt --mock --rules examples/rules.json
# open report.html in your browser
```

## How it works

1. **Record**: add `@record` above your agent function. Every run is saved to `runs.jsonl`.
2. **Replay**: change the prompt or model; one command re-asks every saved question.
3. **Compare**: you get a SAFE / NOT SAFE verdict, per-run tool-call diffs, and cost and latency change.

## Run the 5 different prompts (5 people, or one person 5 times)

The five prompt files live in `examples/prompts/`. Each tester picks one and changes only the file name.

| # | Prompt file        | What it does                                  | Expected on the built-in mock                                      |
|---|--------------------|-----------------------------------------------|--------------------------------------------------------------------|
| 1 | `p1_baseline.txt`  | Original prompt (control)                     | SAFE, 30 of 30 same                                                |
| 2 | `p2_fast.txt`      | "Skip extra steps", bot skips the order check | NOT SAFE, 22 of 30 regress                                         |
| 3 | `p3_polite.txt`    | Only the tone changes                         | SAFE, 30 of 30 same                                                |
| 4 | `p4_guarantee.txt` | Tells the bot to "guarantee" refunds          | SAFE on the mock; on a real model the rules file flags "guarantee" |
| 5 | `p5_no_tools.txt`  | "Never use tools"                             | NOT SAFE, 22 of 30 regress                                         |

One tester, one prompt:

```
python -m replaylens replay runs.jsonl --agent examples.refund_bot:run_agent \
  --prompt examples/prompts/p3_polite.txt --mock --rules examples/rules.json
```

All five in one go:

```
for p in p1_baseline p2_fast p3_polite p4_guarantee p5_no_tools; do
  echo "== $p"
  python -m replaylens replay runs.jsonl --agent examples.refund_bot:run_agent \
    --prompt examples/prompts/$p.txt --mock --rules examples/rules.json \
    --out /tmp/$p.json --html /tmp/$p.html | grep -E "Out of|VERDICT"
done
```

Each run writes `report.html`: filter by regressions / same / improved and see old and new answers side by side.

## Use a real model (any OpenAI-compatible endpoint)

```
pip install openai
export OPENAI_BASE_URL=https://api.groq.com/openai/v1   # or Together, Runpod, OpenRouter...
export OPENAI_API_KEY=your_key
PYTHONPATH=. python scripts/record_real.py MODEL_NAME     # records 10 real runs
python -m replaylens replay runs.jsonl --agent examples.refund_bot:run_agent \
  --prompt examples/prompts/p2_fast.txt --rules examples/rules.json
```

Tested on Groq (`openai/gpt-oss-120b`): the "skip the lookup" prompt was flagged as a regression
in 6 of 10 real runs. See `docs/real-run-report.html`. Never commit your `.env` file.

## Benchmark several models on the same runs

```
python -m replaylens benchmark runs.jsonl --agent examples.refund_bot:run_agent \
  --prompt examples/prompts/p1_baseline.txt --models good-model,cheap-model --mock
```

Prints a table (regressions, cost, latency per model) and writes `benchmark.md`.

## Use in CI

**GitHub Action** (one step, fails the pull request on regression):

```yaml
- uses: actions/checkout@v4
- uses: k-kj0/replaylens@v0.1.0
  with:
    runs: runs.jsonl
    agent: examples.refund_bot:run_agent
    prompt: examples/prompts/p1_baseline.txt
    rules: examples/rules.json
    mock: "true"
```

- **GitHub workflow example**: `.github/workflows/replay.yml`
- **GitLab**: `.gitlab-ci.yml`

`--fail-on-regression` makes the pull request or merge request fail when the agent regresses.

## Rules (compliance checks)

`examples/rules.json` lists phrases the agent must never say (or must say). A new violation counts as a regression.

## Honest limits (v0.1)

Single-turn conversations, sequential tool loop, text only (for voice agents, replay transcripts).
Latency numbers from free-tier APIs are noisy. Similar projects exist (langgraph-replay, replayd, ProxyTrace);
ReplayLens aims to be the zero-setup, any-endpoint tool with tool-call diffs and compliance rules.
