# ReplayLens

**Regression testing, continuous drift monitoring, and release gates for AI agents and inference endpoints.** Record agent runs, replay them against a changed prompt or model, and track changes across outputs, tool calls, rule violations, cost, and latency.

- **Live dashboard:** https://k-kj0.github.io/replaylens/
- **License:** MIT

## Why it exists

Prompt changes, model swaps, or quiet upstream provider updates can cause silent regressions. ReplayLens offers repeatable before/after comparisons, statistical drift detection, and CI release gates to evaluate agent and endpoint readiness.

## What it does

- **Agent Replay & Regression Gate:** Records agent runs, replays them against modified prompts or models, and flags tool-call changes, rule violations, cost deltas, and latency regressions.
- **Inference Drift Canary (`canary/`):** Executes scheduled checks against `openbenchmarks/OB-Inference-Microtasks` (29 tasks) under strict controls (`temperature=0`, `top_p=1`, JSON mode, `max_tokens=256`, 20s timeout, zero retries, single concurrency), flagging drift via paired exact McNemar and bootstrap tests.
- **Voice Agent Regression (`replaylens.voice`):** Evaluates call recordings across STT, LLM, and TTS stage latencies, transcript word error rate (WER), latency budgets, and caller interruptions.
- **Fleet Economics & Health (`fleet/`):** Uses plain SQL over SQLite to analyze agent run logs, tracking per-model pass rates, p95 latency, cost per passing run, and week-over-week drop alerts.
- **Static Dashboard Explorer:** Loads generated JSON reports locally in the browser to filter outcomes, inspect diffs, and export summaries.

## Inference Drift Canary (New)

The `canary` module operates as a lightweight, automated early-warning system to detect provider or model drift and open a GitHub Issue when a full benchmark re-run is required.

### Protocol & Statistical Methods
- **Deterministic Runner:** Evaluates open-weight endpoints (such as Groq `llama-3.1-8b-instant` and Cerebras `llama3.1-8b`) with fixed parameters (`temperature=0`, `top_p=1`, `max_tokens=256`, `timeout=20s`, `retries=0`, `concurrency=1`), recording end-to-end latency, time-to-first-token (TTFT), and failure modes (`timeout`, `http_429`, `http_4xx`, `http_5xx`, `transport`).
- **Statistical Rigor:** Computes Wilson score confidence intervals, paired exact McNemar p-values, paired bootstrap intervals, and Holm-Bonferroni corrections across providers.
- **A/A False-Alarm Calibration:** Replays baseline runs against themselves to establish empirical false-alarm rates prior to drift alerting.

### Quick Canary Commands
```bash
python -m canary inspect     # Print dataset shape and protocol settings
python -m canary run         # Execute one live canary pass and append to canary/data/results.jsonl
python -m canary check       # Compare latest run against the 7-run baseline (exits 2 on drift)
python -m canary aa          # Run A/A false-alarm calibration across baseline runs
python -m pytest tests/test_canary.py -q
```

### Methodological Limitations (Canary)
- With 29 microtasks, a 90% pass rate yields a 95% Wilson confidence interval of approximately 74% to 96%, requiring at least 6 paired task outcomes to flip for an exact McNemar test to reach `p < 0.05`.
- Due to this statistical power floor, the canary functions strictly as a **drift trigger** for larger evaluations rather than a standalone provider leaderboard.

## Quickstart

Requires Python 3.

```bash
git clone https://github.com/k-kj0/replaylens.git
cd replaylens
python -m venv .venv
```

Activate the environment:

```bash
# macOS / Linux
source .venv/bin/activate

# Windows PowerShell
.venv\Scripts\Activate.ps1
```

Install the project and run the example:

```bash
python -m pip install -e .
python -m examples.refund_bot
python -m replaylens --help
```

## Run the tests

```bash
python -m pip install -e ".[test]"
python -m pytest
```

Optional OpenAI integration:

```bash
python -m pip install -e ".[openai]"
```

## Dashboard

The published dashboard is a static, client-side report explorer that does not execute agents or fetch new reports automatically.

1. Open the [ReplayLens dashboard](https://k-kj0.github.io/replaylens/).
2. Select **Load report JSON** and choose a ReplayLens JSON report containing `summary` and `results` fields.
3. Filter runs by outcome, or search inputs, outputs, and regression reasons.
4. Use **Export summary JSON** to download a compact summary.

Data is processed locally in your browser and is not uploaded to any server. Bundled samples are illustrative and do not guarantee agent safety.

## Continuous integration

ReplayLens includes GitHub Actions workflows (`.github/workflows/canary.yml`, `replay.yml`, `fleet-report.yml`) and a GitLab CI configuration (`.gitlab-ci.yml`). The Canary workflow runs every 3 hours on cron, appends results to `canary/data/results.jsonl`, checks for statistical drift against the baseline, and automatically opens a GitHub Issue when drift is detected.

## Repository layout

```text
replaylens/
├── .github/workflows/   # Scheduled canary, CI replay, fleet, and dashboard workflows
├── canary/              # OB-Inference-Microtasks drift canary, stats, and JSONL logs
├── dashboard/index.html # Static report explorer
├── docs/                # Case studies, fleet reports, and example outputs
├── examples/            # Example agents, prompts, and rules
├── fleet/               # SQLite-backed account health and model economics analyzer
├── replaylens/          # Core Python package, voice comparison, and CLI
├── tests/               # Automated unit and statistical tests
├── action.yml           # GitHub Action metadata
├── pyproject.toml
└── README.md
```

## Voice agents

`replaylens.voice` compares two recordings of the same calls to analyze speech-to-text accuracy, per-stage latency (STT, LLM, TTS), transcript drift (word error rate), latency budgets, and caller interruptions.

```bash
python -m replaylens.voice demo voice_demo          # sample calls, no API key or audio needed
python -m replaylens.voice compare voice_demo/old.jsonl voice_demo/new.jsonl --md voice_report.md
```

Exits with code 1 when the new setup is unsafe, making it suitable for pull request gates. Uses a single JSON line per turn (`call_id`, `turn`, `user_transcript`, `agent_transcript`, `stt_ms`, `llm_ms`, `tts_ms`, `first_audio_ms`, `interrupted`).

## ReplayLens Fleet

Converts agent run logs into account health insights, model economics, and alerts using plain SQL over SQLite.

- **Account routing:** Assigns health scores to route accounts to named owners, nudge programs, expansion, or no action.
- **Model economics:** Tracks cost per passing run, pass rate, and p95 latency per model.
- **Alerts:** Monitors week-over-week pass-rate drops and quiet accounts (`--fail-on critical` to gate CI).

```bash
python -m fleet demo
python -m fleet report --runs fleet/sample_runs.jsonl --out docs/fleet/index.html
python -m fleet alerts --runs your_runs.jsonl --fail-on critical
```

Live report: `docs/fleet/index.html` (synthetic demo data).

## Limitations

- The hosted dashboard starts with a bundled sample snapshot and does not update when new reports are generated.
- Individual runs appear only when the loaded report includes a `results` array with old and new run data.
- Regression checks cannot prove universal agent safety; results depend on test cases, rules, and comparison settings.
- The dashboard displays supplied report values without validating model quality or reproducing runs.

## Contributing

1. Open an issue describing the problem or proposed change.
2. Keep pull requests focused and include tests where relevant.
3. Run the relevant checks before opening a pull request.

## License

MIT. See `LICENSE`.
