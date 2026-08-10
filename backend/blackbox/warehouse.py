"""Deterministic warehouse operations. All numbers shown in the UI or cited as
evidence come from here (or DataHub) — never from LLM text."""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import duckdb

from .config import REPO_ROOT, settings
from .models import DailyPoint, MetricSnapshot, TestFailure, TestReport

_READONLY_RE = re.compile(r"^\s*(select|with|describe|show|explain)\b", re.IGNORECASE)


def _connect() -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(settings.warehouse_path), read_only=True)


def run_sql(query: str, limit: int = 50) -> dict[str, Any]:
    """Read-only SQL against the demo warehouse."""
    if not _READONLY_RE.match(query):
        raise ValueError("only read-only queries (SELECT/WITH/DESCRIBE/SHOW/EXPLAIN) are allowed")
    if ";" in query.rstrip().rstrip(";"):
        raise ValueError("multiple statements are not allowed")
    with _connect() as con:
        rel = con.sql(query)
        cols = rel.columns
        rows = rel.fetchmany(limit)
    return {
        "columns": cols,
        "rows": [[_json_safe(v) for v in row] for row in rows],
        "row_count_returned": len(rows),
        "truncated_at": limit,
    }


def _json_safe(v: Any) -> Any:
    if isinstance(v, (int, float, str, bool)) or v is None:
        return v
    return str(v)


def profile_column(
    table: str, column: str, segment_by: str | None = None, last_days: int = 14
) -> dict[str, Any]:
    """Per-day stats for a numeric column, optionally segmented (e.g. by payment_processor).

    This is the primary evidence generator: it exposes distribution shifts without
    knowing anything about the specific incident.
    """
    _validate_ident(table)
    _validate_ident(column)
    ts_col = _pick_time_column(table)
    seg_expr = "'all'"
    if segment_by:
        _validate_ident(segment_by)
        seg_expr = segment_by
    q = f"""
        SELECT CAST({ts_col} AS DATE) AS day,
               {seg_expr} AS segment,
               COUNT(*) AS n,
               ROUND(AVG({column}), 4) AS mean,
               ROUND(MEDIAN({column}), 4) AS median,
               ROUND(MIN({column}), 4) AS min,
               ROUND(MAX({column}), 4) AS max,
               ROUND(AVG(CASE WHEN {column} IS NULL THEN 1 ELSE 0 END), 4) AS null_rate
        FROM {table}
        GROUP BY 1, 2
        ORDER BY 1 DESC, 2
    """
    with _connect() as con:
        max_day = con.sql(f"SELECT MAX(CAST({ts_col} AS DATE)) FROM {table}").fetchone()[0]
        rows = con.sql(q).fetchall()
    cutoff = None
    if max_day is not None:
        import datetime as _dt

        cutoff = max_day - _dt.timedelta(days=last_days - 1)
    out = []
    for day, seg, n, mean, median, mn, mx, null_rate in rows:
        if cutoff is not None and day < cutoff:
            continue
        out.append(
            {
                "day": str(day),
                "segment": seg,
                "n": n,
                "mean": mean,
                "median": median,
                "min": mn,
                "max": mx,
                "null_rate": null_rate,
            }
        )
    return {"table": table, "column": column, "segment_by": segment_by, "days": out}


def compare_to_baseline(last_days: int = 10) -> dict[str, Any]:
    """Compare current daily revenue/AOV against the committed healthy baselines."""
    baseline_path = settings.baselines_dir / "daily_revenue_baseline.json"
    baseline = {r["day"]: r for r in json.loads(baseline_path.read_text())}
    with _connect() as con:
        rows = con.sql(
            "SELECT CAST(day AS DATE) AS day, revenue_usd, order_count, aov_median_usd "
            "FROM marts.fct_revenue ORDER BY day DESC LIMIT ?",
            params=[last_days],
        ).fetchall()
    comparisons = []
    for day, revenue, n, aov in rows:
        b = baseline.get(str(day))
        comparisons.append(
            {
                "day": str(day),
                "revenue_usd": round(revenue, 2),
                "baseline_revenue_usd": round(b["revenue_usd"], 2) if b else None,
                "revenue_ratio": round(revenue / b["revenue_usd"], 3) if b and b["revenue_usd"] else None,
                "aov_median_usd": round(aov, 2),
                "baseline_aov_median_usd": round(b["aov_median_usd"], 2) if b else None,
                "aov_ratio": round(aov / b["aov_median_usd"], 3) if b and b["aov_median_usd"] else None,
                "order_count": n,
                "baseline_order_count": b["order_count"] if b else None,
            }
        )
    return {"comparisons": comparisons, "baseline_source": str(baseline_path.relative_to(REPO_ROOT))}


def get_metric_snapshot() -> MetricSnapshot:
    raw = json.loads(settings.metric_snapshot_path.read_text())
    baseline_path = settings.baselines_dir / "daily_revenue_baseline.json"
    baseline = {}
    if baseline_path.exists():
        baseline = {r["day"]: r["revenue_usd"] for r in json.loads(baseline_path.read_text())}
    daily = [
        DailyPoint(day=d["day"], revenue_usd=d["revenue_usd"], baseline=baseline.get(d["day"]))
        for d in raw.get("daily", [])
    ]
    ratio = raw["anomaly_ratio"]
    return MetricSnapshot(
        kpi_day=raw["kpi_day"],
        revenue=raw["revenue"],
        expected_revenue=raw["expected_revenue"],
        anomaly_ratio=ratio,
        status="anomalous" if (ratio > 1.5 or ratio < 0.6) else "ok",
        daily=daily,
    )


def read_transform(name: str) -> dict[str, str]:
    """Read a transformation's SQL source (path-safe)."""
    fname = Path(name).name
    if not fname.endswith(".sql"):
        fname += ".sql"
    path = settings.transforms_dir / fname
    if not path.exists():
        available = sorted(p.name for p in settings.transforms_dir.glob("*.sql"))
        raise FileNotFoundError(f"unknown transform {fname!r}; available: {available}")
    return {"file": str(path.relative_to(REPO_ROOT)), "sql": path.read_text()}


def list_transforms() -> list[str]:
    return sorted(p.name for p in settings.transforms_dir.glob("*.sql"))


def rebuild_warehouse() -> dict[str, Any]:
    """Re-run the pipeline (transforms currently on disk) against the source CSVs."""
    proc = subprocess.run(
        ["uv", "run", "python", "pipeline/run.py"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=300,
    )
    return {"ok": proc.returncode == 0, "stdout": proc.stdout[-2000:], "stderr": proc.stderr[-2000:]}


def run_invariants() -> TestReport:
    """Run the pipeline invariant suite; parse structured results from junit xml."""
    with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as f:
        xml_path = f.name
    proc = subprocess.run(
        ["uv", "run", "pytest", "pipeline/invariants", "-q", f"--junitxml={xml_path}"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=600,
    )
    try:
        root = ET.parse(xml_path).getroot()
    except ET.ParseError:
        return TestReport(
            total=0, passed=0, failed=1,
            failures=[TestFailure(name="pytest", message=proc.stderr[-800:] or "junit parse error")],
        )
    suite = root if root.tag == "testsuite" else root.find("testsuite")
    total = int(suite.get("tests", 0))
    errors = int(suite.get("errors", 0))
    failed = int(suite.get("failures", 0)) + errors
    skipped = int(suite.get("skipped", 0))
    failures = []
    for case in suite.iter("testcase"):
        for bad in list(case.iter("failure")) + list(case.iter("error")):
            failures.append(
                TestFailure(
                    name=f"{case.get('classname', '')}::{case.get('name', '')}",
                    message=(bad.get("message") or "")[:400],
                )
            )
    return TestReport(total=total, passed=total - failed - skipped, failed=failed, failures=failures)


# -- helpers ------------------------------------------------------------------

_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*$")


def _validate_ident(ident: str) -> None:
    if not _IDENT_RE.match(ident):
        raise ValueError(f"invalid identifier: {ident!r}")


_TIME_COLUMNS = ["order_ts", "day", "date", "created_at", "rate_date"]


def _pick_time_column(table: str) -> str:
    with _connect() as con:
        cols = [r[0] for r in con.sql(f"DESCRIBE {table}").fetchall()]
    for c in _TIME_COLUMNS:
        if c in cols:
            return c
    raise ValueError(f"no known time column in {table}; columns={cols}")
