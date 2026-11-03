"""Load agent run records into SQLite and answer analytics questions in plain SQL."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

ALIASES = {
    "account": ("account", "tenant", "customer"),
    "model": ("model",),
    "ts": ("ts", "timestamp", "created_at"),
    "passed": ("passed", "success", "ok"),
    "cost_usd": ("cost_usd", "cost"),
    "latency_ms": ("latency_ms", "latency"),
}

ACCOUNT_WEEKLY_SQL = """
WITH weekly AS (
    SELECT account,
           strftime('%Y-%W', ts)  AS wk,
           COUNT(*)               AS runs,
           AVG(passed)            AS pass_rate,
           SUM(cost_usd)          AS cost,
           AVG(latency_ms)        AS avg_latency
    FROM runs
    GROUP BY account, wk
), trended AS (
    SELECT *,
           LAG(runs)      OVER (PARTITION BY account ORDER BY wk) AS prev_runs,
           LAG(pass_rate) OVER (PARTITION BY account ORDER BY wk) AS prev_pass
    FROM weekly
)
SELECT * FROM trended ORDER BY account, wk
"""

MODEL_WEEKLY_SQL = """
WITH weekly AS (
    SELECT model,
           strftime('%Y-%W', ts) AS wk,
           COUNT(*)              AS runs,
           AVG(passed)           AS pass_rate
    FROM runs
    GROUP BY model, wk
)
SELECT *,
       LAG(pass_rate) OVER (PARTITION BY model ORDER BY wk) AS prev_pass
FROM weekly
ORDER BY model, wk
"""

MODEL_SUMMARY_SQL = """
SELECT model,
       COUNT(*)                                   AS runs,
       AVG(passed)                                AS pass_rate,
       AVG(cost_usd)                              AS cost_per_run,
       SUM(cost_usd) / NULLIF(SUM(passed), 0)     AS cost_per_pass,
       AVG(latency_ms)                            AS avg_latency
FROM runs
GROUP BY model
ORDER BY cost_per_pass
"""


def _pick(rec, names, default=None):
    for name in names:
        if name in rec and rec[name] is not None:
            return rec[name]
    return default


def _truthy(value) -> int:
    if isinstance(value, str):
        return 1 if value.strip().lower() in ("true", "1", "pass", "passed", "ok", "success") else 0
    return 1 if value else 0


def load_runs(path):
    """Read a JSONL file. Accepts a few common field names for each column."""
    runs = []
    text = Path(path).read_text(encoding="utf-8")
    for i, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        ts = _pick(rec, ALIASES["ts"])
        account = _pick(rec, ALIASES["account"])
        if ts is None or account is None:
            raise ValueError(f"line {i}: each run needs an account and a timestamp")
        runs.append(
            {
                "run_id": str(rec.get("run_id", i)),
                "account": str(account),
                "model": str(_pick(rec, ALIASES["model"], "unknown")),
                "ts": str(ts)[:19],
                "passed": _truthy(_pick(rec, ALIASES["passed"], False)),
                "cost_usd": float(_pick(rec, ALIASES["cost_usd"], 0.0)),
                "latency_ms": float(_pick(rec, ALIASES["latency_ms"], 0.0)),
            }
        )
    return runs


def p95(values):
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int(round(0.95 * (len(ordered) - 1)))))
    return ordered[index]


class RunStore:
    def __init__(self, runs):
        self.db = sqlite3.connect(":memory:")
        self.db.row_factory = sqlite3.Row
        self.db.execute(
            "CREATE TABLE runs (run_id TEXT, account TEXT, model TEXT, ts TEXT, "
            "passed INTEGER, cost_usd REAL, latency_ms REAL)"
        )
        self.db.executemany(
            "INSERT INTO runs VALUES (:run_id, :account, :model, :ts, :passed, :cost_usd, :latency_ms)",
            runs,
        )

    def _all(self, sql):
        return [dict(r) for r in self.db.execute(sql).fetchall()]

    def account_weekly(self):
        return self._all(ACCOUNT_WEEKLY_SQL)

    def model_weekly(self):
        return self._all(MODEL_WEEKLY_SQL)

    def model_summary(self):
        rows = self._all(MODEL_SUMMARY_SQL)
        for row in rows:
            lat = [r[0] for r in self.db.execute("SELECT latency_ms FROM runs WHERE model = ?", (row["model"],))]
            row["p95_latency"] = p95(lat)
        return rows

    def totals(self):
        row = self.db.execute(
            "SELECT COUNT(*) AS runs, COUNT(DISTINCT account) AS accounts, "
            "COUNT(DISTINCT model) AS models, SUM(cost_usd) AS cost FROM runs"
        ).fetchone()
        return dict(row)

    def latest_week(self):
        row = self.db.execute("SELECT MAX(strftime('%Y-%W', ts)) AS wk FROM runs").fetchone()
        return row["wk"]
