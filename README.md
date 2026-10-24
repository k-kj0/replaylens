# ReplayLens

**Regression testing for AI agents.** Record agent runs, replay them against a changed prompt or model, and see exactly what changed: outputs, tool calls, rule violations, cost, and latency.

- **Live dashboard:** https://k-kj0.github.io/replaylens/
- **License:** MIT

## Why it exists

Changing a prompt or swapping a model can quietly break an agent. ReplayLens gives you a repeatable before/after comparison so you can review release readiness the same way you review code.

## What it does

- Records agent runs and the metadata needed to replay them.
- Replays recorded runs against a changed prompt or model.
- Flags changes to tool names or arguments, newly violated rules, and run errors.
- Summarizes regression counts, cost changes, and latency changes.
- Produces a standalone HTML report and supports a CI regression gate that can fail a build.
- Loads a generated JSON report into a static dashboard where you can filter runs by outcome, search run content, and export a summary.

## Dashboard

The published dashboard is a static, client-side report explorer. It does not run an agent and does not fetch new reports automatically.

1. Open the [ReplayLens dashboard](https://k-kj0.github.io/replaylens/).
2. Select **Load report JSON**.
3. Choose a ReplayLens JSON report that contains `summary` and `results` fields.
4. Filter runs by outcome, or search inputs, outputs, and regression reasons.
5. Use **Export summary JSON** to download a compact summary.

The file you select is processed locally in your browser. It is not uploaded to any server.

The bundled sample is illustrative data, not a guarantee of agent safety. A "SAFE TO SHIP" result only means the supplied report met its configured regression threshold.

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

Use the CLI help and the examples in `examples/` to record runs and replay them against a different prompt.

## Run the tests

```bash
python -m pip install -e ".[test]"
python -m pytest
```

Optional OpenAI integration:

```bash
python -m pip install -e ".[openai]"
```

## Continuous integration

ReplayLens includes a GitHub Action (`action.yml`) and a GitLab CI configuration (`.gitlab-ci.yml`) for running replay checks in a development workflow. Provide your run data, agent entry point, prompt, and optional rules, then enable the regression gate if you want a regression to fail the job.

## Repository layout

```
replaylens/
├── .github/workflows/   # CI, replay, and dashboard workflows
├── dashboard/index.html # Static report explorer
├── docs/                # Case studies and example reports
├── examples/            # Example agents, prompts, and rules
├── replaylens/          # Python package and CLI
├── tests/               # Automated tests
├── action.yml           # GitHub Action metadata
├── pyproject.toml
└── README.md
```

## Limitations

- The hosted dashboard starts with a bundled sample snapshot and does not update when a new report is generated.
- Individual runs appear only when the loaded report includes a `results` array with old and new run data.
- A regression check cannot prove an agent is universally safe or correct. Results depend on your test cases, rules, and comparison settings.
- The dashboard displays supplied report values. It does not validate model quality or reproduce the run.

## Contributing

1. Open an issue describing the problem or proposed change.
2. Keep pull requests focused and include tests where relevant.
3. Run the relevant checks before opening a pull request.

## License

MIT. See [LICENSE](LICENSE).
