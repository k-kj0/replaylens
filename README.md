# ReplayLens

**A flight recorder + replay button for AI agents.**
Change a prompt or switch to a cheaper model, replay your real past conversations, and see exactly what behaves differently, especially which tools the agent now calls.

No account. No hosted service. One command, one verdict: **SAFE** or **NOT SAFE TO SHIP**.

---

## Why

Changing a prompt or swapping in a cheaper model can silently change which tools an agent calls or what it says to customers. Unit tests don't catch that, because the agent still "works". ReplayLens replays your real past conversations against the change and tells you exactly what behaves differently.

**Built for:** teams shipping agents (support, voice, finance, insurance, healthcare) who need a SAFE / NOT SAFE gate in CI before a prompt or model change goes out.

## See it in 30 seconds

| Example | Change tested | Result |
|---|---|---|
| Refund bot (single turn) | "Skip extra steps" prompt | NOT SAFE: 22 of 30 runs regress |
| Insurance claim intake (multi-turn) | "Skip verification, be confident" prompt | NOT SAFE: 18 of 28 turns regress |

The insurance run catches two kinds of damage at once: the agent stops looking up the policy before talking about coverage (a tool-call regression), and it starts telling customers things like "approved" (a compliance-rule violation).

![Insurance replay report](docs/insurance-report.png)

---

## Install

```bash
pip install git+https://github.com/k-kj0/replaylens@v0.1.0
```

## Quickstart (2 minutes, no API key)

```bash
git clone https://github.com/k-kj0/replaylens && cd replaylens
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -e .
python -m examples.refund_bot          # records 30 demo runs
python -m replaylens replay runs.jsonl --agent examples.refund_bot:run_agent \
  --prompt examples/prompts/p2_fast.txt --mock --rules examples/rules.json
# open report.html in your browser
```

## How it works

1. **Record:** add `@record` above your agent function. Every run is saved as one line in `runs.jsonl`.
2. **Replay:** change the prompt or model. One command re-asks every saved input.
3. **Compare:** you get a SAFE / NOT SAFE verdict, per-run tool-call diffs, and the cost and latency change.

Each replay writes `report.html`: filter by regressions / same / improved and see old and new answers side by side.

## Record your own agent

Your agent only needs to look like this:

```python
from replaylens.recorder import record

@record(path="runs.jsonl", prompt_version="v1")
def my_agent(user_input, *, model, system_prompt):
    ...
    return {
        "output": "text the customer sees",
        "tool_calls": [{"name": "lookup_order", "arguments": {"id": "ORD-1001"}}],
        "tokens_in": 120,
        "tokens_out": 45,
    }
```

Then replay with `--agent your_module:my_agent`.

---

## Multi-turn conversations (insurance claim example)

Real conversations go back and forth. ReplayLens handles this by recording **one row per customer turn**, where the row's input is the whole conversation so far. Replaying re-tests every turn in context.

The example in `examples/insurance_claims/` is a claim-intake agent that must:

- look up the policy before discussing coverage,
- never say "approved", "you are covered" or "guarantee",
- hand off to a human if anyone is injured.

```bash
python -m examples.insurance_claims.agent        # records 10 conversations (28 turns)

# Good prompt: expect SAFE
python -m replaylens replay runs_insurance.jsonl \
  --agent examples.insurance_claims.agent:run_agent \
  --prompt examples/insurance_claims/prompts/good.txt \
  --mock --rules examples/insurance_claims/rules.json

# Bad prompt: expect NOT SAFE
python -m replaylens replay runs_insurance.jsonl \
  --agent examples.insurance_claims.agent:run_agent \
  --prompt examples/insurance_claims/prompts/skip_checks.txt \
  --mock --rules examples/insurance_claims/rules.json \
  --html docs/insurance-report.html
```

The agent in this example is scripted, so it needs no API key. Swap in a real model for your own agent.

---

## Try 5 different prompts

The five prompt files live in `examples/prompts/`. Each tester picks one and changes only the file name.

| # | Prompt file | What it does | Expected on the built-in mock |
|---|---|---|---|
| 1 | `p1_baseline.txt` | Original prompt (control) | SAFE, 30 of 30 same |
| 2 | `p2_fast.txt` | "Skip extra steps": bot skips the order check | NOT SAFE, 22 of 30 regress |
| 3 | `p3_polite.txt` | Only the tone changes | SAFE, 30 of 30 same |
| 4 | `p4_guarantee.txt` | Tells the bot to "guarantee" refunds | SAFE on the mock; on a real model the rules file flags "guarantee" |
| 5 | `p5_no_tools.txt` | "Never use tools" | NOT SAFE, 22 of 30 regress |

All five in one go:

```bash
for p in p1_baseline p2_fast p3_polite p4_guarantee p5_no_tools; do
  echo "== $p"
  python -m replaylens replay runs.jsonl --agent examples.refund_bot:run_agent \
    --prompt examples/prompts/$p.txt --mock --rules examples/rules.json \
    --out /tmp/$p.json --html /tmp/$p.html | grep -E "Out of|VERDICT"
done
```

## Use a real model (any OpenAI-compatible endpoint)

```bash
pip install openai
export OPENAI_BASE_URL=https://api.groq.com/openai/v1   # or Together, Runpod, OpenRouter...
export OPENAI_API_KEY=your_key
PYTHONPATH=. python scripts/record_real.py MODEL_NAME     # records 10 real runs
python -m replaylens replay runs.jsonl --agent examples.refund_bot:run_agent \
  --prompt examples/prompts/p2_fast.txt --rules examples/rules.json
```

Tested on Groq (`openai/gpt-oss-120b`): the "skip the lookup" prompt was flagged as a regression in 6 of 10 real runs. See `docs/real-run-report.html`. Never commit your `.env` file.

## Benchmark several models on the same runs

```bash
python -m replaylens benchmark runs.jsonl --agent examples.refund_bot:run_agent \
  --prompt examples/prompts/p1_baseline.txt --models good-model,cheap-model --mock
```

Prints a table (regressions, cost, latency per model) and writes `benchmark.md`.

## Use in CI

GitHub Action (one step, fails the pull request on regression):

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

- GitHub workflow example: `.github/workflows/replay.yml`
- GitLab: `.gitlab-ci.yml`
- `--fail-on-regression` makes the pull request or merge request fail when the agent regresses.

## Rules (compliance checks)

A rules file lists phrases the agent must never say (or must say). A new violation counts as a regression.

```json
{
  "must_not_contain": ["approved", "you are covered", "guarantee"],
  "must_contain_any": []
}
```

Examples: `examples/rules.json` (refund bot) and `examples/insurance_claims/rules.json`.

## Case studies

Short write-ups of what ReplayLens catches:

- [Insurance claim intake agent](docs/case-study-insurance-claims.md)
- [Real-model run](docs/real-model-run.md)

## Project layout

```
replaylens/            the library (recorder, replayer, compare, report, judge, noise, otel...)
examples/              runnable demo agents, prompts and rules
  refund_bot.py        single-turn demo
  insurance_claims/    multi-turn demo
scripts/               helper scripts (record_real.py)
docs/                  reports and case studies
tests/                 test suite
action.yml             GitHub Action
.gitlab-ci.yml         GitLab CI template
```

## Honest limits (v0.1)

- **Multi-turn is turn-by-turn.** Each turn is replayed with the *recorded* history, so ReplayLens tests what your new prompt does next in the same situation. It does not re-simulate a whole conversation where the agent's new replies change what the customer would have said.
- The agent must follow the `record` format shown above (`output`, `tool_calls`, token counts).
- Text only. For voice agents, replay the transcripts.
- Latency numbers from free-tier APIs are noisy.
- The insurance example uses a scripted agent, so its numbers show how the tool behaves, not how a particular real model behaves.
- Similar projects exist (langgraph-replay, replayd, ProxyTrace). ReplayLens aims to be the zero-setup, any-endpoint tool with tool-call diffs and compliance rules.

## License

MIT
