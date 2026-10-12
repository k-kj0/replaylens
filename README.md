# ReplayLens

**A flight recorder + replay button for AI agents.**
Change a prompt or switch to a cheaper model, replay your real past conversations,
and see exactly what behaves differently, especially which *tools* the agent now calls.

## Quickstart (2 minutes, no API key)

    pip install -e .
    python -m examples.refund_bot
    python -m replaylens replay runs.jsonl --agent examples.refund_bot:run_agent \
        --prompt examples/prompts/v2_fast.txt --mock --rules examples/rules.json
    # open report.html

## Why
Most teams test a prompt change on 5 examples by hand. ReplayLens re-runs *all* recorded runs
and compares tool calls and arguments, cost, latency, compliance rules, and (optionally) an LLM judge.

## Example result (demo refund bot, 30 recorded runs)

| change | regressions | cost | latency | verdict |
|---|---|---|---|---|
| polite prompt | 0 / 30 | +0.0% | ~0% | SAFE |
| "be fast, skip steps" prompt | 22 / 30 | -35% | -26% | NOT SAFE (skips order lookup) |
| cheaper model | 8 / 30 | -62.6% | -59.0% | NOT SAFE (wrong tool on status questions) |

## Works with any OpenAI-compatible endpoint

    export OPENAI_API_KEY=...
    python -m replaylens replay runs.jsonl --agent my_pkg.agent:run_agent --prompt new.txt \
        --model <model-name> --base-url <provider-url> --price-in <usd> --price-out <usd>

## Benchmark several models on the same runs

    python -m replaylens benchmark runs.jsonl --agent examples.refund_bot:run_agent \
        --prompt examples/prompts/v1.txt --models good-model,cheap-model --mock

## CI
GitHub: `.github/workflows/replay.yml`. GitLab: `.gitlab-ci.yml`.
`--fail-on-regression` makes the pull request or merge request fail.

## Honest limits (v0.1)
Single-turn conversations, sequential tool loop, text only (voice agents: replay transcripts).
The demo uses a built-in fake model; real-provider runs depend on your endpoint.
Similar projects exist (langgraph-replay, replayd, ProxyTrace). ReplayLens aims to be the
zero-setup, any-endpoint, tool-call-diff + compliance-rules option.
EOF

git rm -q poetry.lock
git add README.md
git commit -m "Full README, remove template lockfile"
git push origin main
