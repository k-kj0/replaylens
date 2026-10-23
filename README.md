
# ReplayLens

**AI-agent quality and regression testing — compare runs, track changes, and review release readiness.**

ReplayLens records agent runs, replays them against a changed prompt or model, and compares outputs, tool calls, rule violations, cost, and latency.

- **Dashboard:** https://k-kj0.github.io/replaylens/
- **Source:** https://github.com/k-kj0/replaylens
- **License:** MIT

## What it does

- Records agent runs and relevant metadata.
- Compares previous and replayed runs.
- Flags changes to tool names or arguments, newly violated rules, and run errors.
- Summarizes reported regression counts, cost changes, and latency changes.
- Produces a standalone HTML report and supports a CI regression gate.
- Lets you load a generated JSON report into the static dashboard, filter individual runs by outcome, search run content, and export a summary.

## Dashboard

The published dashboard is a static, client-side report explorer. It does not run an agent or automatically fetch new reports.

1. Open the [ReplayLens dashboard](https://k-kj0.github.io/replaylens/).
2. Select **Load report JSON**.
3. Choose a ReplayLens JSON report containing `summary` and `results` fields.
4. Filter runs by outcome or search the input, output, and regression reasons.
5. Use **Export summary JSON** to download a compact summary.

The selected file is processed locally in your browser; it is not uploaded to a ReplayLens server by the dashboard.

The bundled sample is illustrative report data, not a guarantee of agent safety. A `SAFE TO SHIP` result means only that the supplied report's configured regression threshold was met.

## Quickstart

With Python installed:

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

Follow the CLI help and the example instructions to record runs and replay them against a different prompt.

## Run the tests

Install the test dependencies and run the suite:

```bash
python -m pip install -e ".[test]"
python -m pytest
```

Install the optional OpenAI integration only if you need it:

```bash
python -m pip install -e ".[openai]"
```

## Continuous integration

ReplayLens includes a GitHub Action and a GitLab CI configuration for running replay checks as part of a development workflow.

Configure a replay job with your run data, agent entry point, prompt, and optional rules. Enable the regression gate when you want a regression to fail the CI job.

See [`action.yml`](action.yml) and [`.gitlab-ci.yml`](.gitlab-ci.yml) for the available configuration.

## Repository layout

```text
replaylens/
├── .github/workflows/   # CI, replay, and static dashboard workflows
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

- The hosted dashboard starts with a bundled sample snapshot; it does not automatically update when a new report is generated.
- Individual runs appear only when the loaded report includes a `results` array with old/new run data.
- A regression check cannot prove that an AI agent is universally safe or correct. Results depend on the test cases, rules, and comparison settings used.
- The dashboard displays supplied report values; it does not independently validate model quality or reproduce the run.

## Contributing

1. Open an issue describing the problem or proposed change.
2. Keep pull requests focused and include tests where relevant.
3. Run the relevant checks before opening a pull request.

## License

This project is licensed under the MIT License. See [`LICENSE`](LICENSE).
