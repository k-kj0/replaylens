# ReplayLens

**A flight recorder + replay button for AI agents.**
Change a prompt or switch to a cheaper model, replay your real past conversations,
and see exactly what behaves differently - especially which *tools* the agent now calls.

    pip install -e .
    python -m examples.refund_bot            # records 30 demo runs (no API key needed)
    python -m replaylens replay runs.jsonl --agent examples.refund_bot:run_agent \
        --prompt examples/prompts/v2_fast.txt --mock --rules examples/rules.json
    # open report.html

## Why
Most teams test a prompt change by trying 5 examples by hand. ReplayLens re-runs *all* recorded
runs and compares tool calls + arguments, cost, latency, compliance rules, and (optionally) an LLM judge.

## Works with any OpenAI-compatible endpoint
    export OPENAI_API_KEY=...
    python -m replaylens replay runs.jsonl --agent my_pkg.agent:run_agent --prompt new.txt \
        --model meta-llama/Llama-3.3-70B-Instruct-Turbo --base-url https://api.together.xyz/v1 \
        --price-in 0.88 --price-out 0.88

## Benchmark several models on the same recorded runs
    python -m replaylens benchmark runs.jsonl --agent examples.refund_bot:run_agent \
        --prompt examples/prompts/v1.txt --models good-model,cheap-model --mock
Prints a table (regressions, cost, latency per model) and writes `benchmark.md`.
Point `--base-url` at Together AI, Runpod (vLLM), Groq or OpenRouter to compare their models.

## Use in CI
GitLab: copy `.gitlab-ci.yml`. GitHub: see below.
See `.github/workflows/replay.yml` - `--fail-on-regression` makes the pull request fail.

## Honest limits (v0.1)
Single-turn conversations, sequential tool loop, text only (voice = replay transcripts).
Similar projects exist (langgraph-replay, replayd, ProxyTrace). ReplayLens aims to be the zero-setup,
any-endpoint, tool-call-diff + compliance-rules option.
