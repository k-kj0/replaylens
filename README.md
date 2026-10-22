# ReplayLens

**AI agent quality and regression testing — compare runs, track changes, and review release readiness.**

ReplayLens helps developers evaluate changes between versions of an AI agent or prompt by summarizing reported test outcomes, regressions, cost changes, and latency changes.

The project includes automated Python checks and a lightweight dashboard for reviewing a report.

**[View the Dashboard](https://k-kj0.github.io/replaylens/)** · **[View the Source Code](https://github.com/k-kj0/replaylens)**

---

## Overview

AI agent behavior can change when prompts, models, or application logic are updated. A change may improve one outcome while introducing a regression elsewhere.

ReplayLens is a small project focused on making those changes easier to review.

It presents report information such as:

- Total runs included in a report
- Reported regressions, unchanged runs, improvements, and other changes
- Previous and new prompt or version identifiers
- Reported cost and latency changes
- A JSON export of the displayed report summary

## Dashboard Preview

The dashboard displays a report snapshot with a high-level quality summary, a version comparison, performance changes, and a run breakdown.

It also explains when individual run records are unavailable rather than displaying fabricated examples.

**Important:** The published dashboard currently displays a static report snapshot. It does not automatically collect new runs, connect to a live AI agent, or update itself when a new report is generated.

## Example Report

The current dashboard snapshot contains the following reported results:

| Metric | Reported result |
|---|---:|
| Total runs | 30 |
| Regressions | 0 |
| Same | 30 |
| Improved | 0 |
| Changed | 0 |
| Cost change | −0.2% |
| Latency change | −0.2% |
| Reported outcome | SAFE TO SHIP |

**Compared versions**

- Previous: `good-model / v1.txt`
- New: `good-model / v3_polite.txt`

These values describe the supplied report snapshot, not a guarantee that every possible agent interaction is safe or correct.

## Features

### Report summary
Review the overall results without having to interpret every metric separately.

### Version comparison
See which previous and new prompt or version identifiers were compared.

### Regression visibility
Review the regression count and other reported outcome categories.

### Performance metrics
See reported changes in cost and latency.

### JSON export
Export the summary displayed on the dashboard for further inspection or use in another tool.

### Automated checks
Use GitHub Actions to run the project's Python checks and deploy the static dashboard.

## Project Structure

```text
replaylens/
├── .github/
│   └── workflows/
│       ├── replay.yml
│       └── static.yml
├── dashboard/
│   └── index.html
├── tests/
├── README.md
└── pyproject.toml
```

The `tests/` directory and `pyproject.toml` are shown as the expected locations for tests and Python project configuration. Check the repository before relying on these paths; adjust this tree if your actual files differ.

## Getting Started

### View the dashboard

Open the published dashboard:

https://k-kj0.github.io/replaylens/

### Get the source code

Clone the repository:

```bash
git clone https://github.com/k-kj0/replaylens.git
cd replaylens
```

### Run the Python checks

This project uses Python checks in GitHub Actions. The exact local commands depend on the dependencies and test configuration in the repository.

If the project uses `pytest` and the required dependencies are installed, run:

```bash
python -m pytest
```

If dependencies are declared in `pyproject.toml`, follow the installation instructions defined there before running the tests.

## Continuous Integration and Deployment

ReplayLens uses GitHub Actions for two workflows:

- **Python checks:** runs the configured automated checks.
- **Dashboard deployment:** publishes the static dashboard through GitHub Pages.

Both workflows have passed for the current dashboard update.

Workflow results are available in the [GitHub Actions tab](https://github.com/k-kj0/replaylens/actions).

## Current Limitations

ReplayLens is under development. The current published dashboard is a report-viewing prototype rather than a complete, live regression-testing service.

Currently:

- The dashboard displays one predefined report snapshot.
- Individual run records are not included in the displayed report.
- New test runs are not automatically collected by the dashboard.
- The report summary does not independently verify model quality or production safety.
- Automated checks validate only the behavior covered by the project's configured tests.

## Potential Next Steps

Possible future improvements include:

- Loading reports from generated JSON files.
- Displaying individual test-run details and before/after outputs.
- Adding filters for regression outcomes.
- Comparing multiple reports over time.
- Integrating report generation into an automated evaluation workflow.

These are potential improvements, not features currently claimed as implemented.

## Contributing

Contributions, bug reports, and suggestions are welcome.

1. Open an issue describing the proposed change or problem.
2. Keep changes focused and testable.
3. Run the relevant checks before submitting a pull request.

## License

A license has not been specified here. Add a `LICENSE` file and update this section once you choose a license for the project.

---

**ReplayLens** — making AI agent evaluation results easier to inspect and compare.
