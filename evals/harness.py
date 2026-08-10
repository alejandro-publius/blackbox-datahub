"""Eval harness: environment reset, fail-fast preconditions, scenario execution.

Design notes
------------
* All ``blackbox`` imports are deferred into functions. ``blackbox.config.settings``
  is a module-level pydantic-settings singleton, so the process environment
  (e.g. BLACKBOX_DISABLE_DATAHUB) must be finalized *before* the first blackbox
  import. ``evals.run_one`` sets env vars, then imports this module's functions.
* The harness NEVER fakes a result: if a precondition fails, the scenario result
  is ``skipped: <reason>`` and nothing is executed or graded.
* Scenarios share the warehouse / transforms on disk, so they must run
  sequentially (the orchestrator enforces this).
"""

from __future__ import annotations

import dataclasses
import subprocess
import time
import traceback
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # avoid import cycles at runtime; scenarios imports harness
    from .scenarios import Scenario

REPO_ROOT = Path(__file__).resolve().parents[1]
TRANSFORMS_DIR = REPO_ROOT / "pipeline" / "transforms"
INCIDENTS_DIR = REPO_ROOT / "data" / "incidents"


# ---------------------------------------------------------------------------
# Result containers
# ---------------------------------------------------------------------------
@dataclasses.dataclass
class Outcome:
    """What a scenario runner reports back: graded checks + supporting context."""

    checks: dict[str, bool] = dataclasses.field(default_factory=dict)
    metrics: dict[str, Any] = dataclasses.field(default_factory=dict)
    notes: list[str] = dataclasses.field(default_factory=list)
    details: dict[str, Any] = dataclasses.field(default_factory=dict)
    incident_id: str | None = None


@dataclasses.dataclass
class ScenarioResult:
    scenario: str
    status: str  # "passed" | "failed" | "skipped: <reason>" | "error: <what>"
    checks: dict[str, bool]
    metrics: dict[str, Any]
    notes: list[str]
    details: dict[str, Any]
    incident_id: str | None
    wall_time_s: float

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


# ---------------------------------------------------------------------------
# Environment reset / restore
# ---------------------------------------------------------------------------
def _run(cmd: list[str], timeout: int = 600) -> subprocess.CompletedProcess:
    proc = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(
            f"{' '.join(cmd)} failed (rc={proc.returncode}): "
            f"{(proc.stderr or proc.stdout)[-800:]}"
        )
    return proc


def reset_environment(mode: str, clear_incidents: bool = True) -> None:
    """Bring the fixture to a known state: pristine transforms, fresh sources in
    the requested mode, rebuilt warehouse, (optionally) no incident records."""
    if mode not in ("incident", "healthy"):
        raise ValueError(f"unknown fixture mode {mode!r}")
    _run(["git", "checkout", "--", "pipeline/transforms/"])
    for p in TRANSFORMS_DIR.glob("*.sql.orig"):
        p.unlink()
    _run(["uv", "run", "python", "pipeline/generate_sources.py", "--mode", mode])
    _run(["uv", "run", "python", "pipeline/run.py"])
    if clear_incidents:
        # Dedicated store rooted at data/incidents (NOT the app's module singleton).
        from blackbox.store import IncidentStore

        IncidentStore().clear_all()
        for p in INCIDENTS_DIR.glob("inc_*.transcript.jsonl"):
            p.unlink()
        for p in INCIDENTS_DIR.glob("*.json.tmp"):
            p.unlink()

    # CONTAMINATION GUARD (adversarial-review finding C1): a previous run's
    # DataHub writeback (incident-history note on a dataset description) is the
    # answer key for the next run. Scrub BlackBox-written state and hard-fail if
    # any note survives — a contaminated run must never be graded.
    try:
        from blackbox.datahub import client as dh_client

        datahub_up = dh_client.ping()
    except Exception:
        datahub_up = False
    if datahub_up:
        from blackbox.datahub.reset import contamination_report, reset_blackbox_state

        reset_blackbox_state()
        dirty = contamination_report()
        if dirty:
            raise RuntimeError(
                f"DataHub contamination: BlackBox incident notes still present on {dirty}"
            )


def restore_environment() -> None:
    """Post-scenario restore: clean transforms, incident-mode sources, rebuilt
    warehouse. Incident records are kept for post-hoc debugging (the next
    scenario's reset clears them)."""
    reset_environment("incident", clear_incidents=False)


def git_transforms_unchanged() -> bool:
    rc = subprocess.run(
        ["git", "diff", "--quiet", "--", "pipeline/transforms/"], cwd=REPO_ROOT
    ).returncode
    return rc == 0


# ---------------------------------------------------------------------------
# Fail-fast preconditions
# ---------------------------------------------------------------------------
def check_preconditions(scenario: "Scenario") -> str | None:
    """Return a skip reason, or None if the scenario can run for real.

    The warehouse-buildable precondition is exercised by reset_environment()
    itself (generate + build); run_scenario turns a reset failure into a skip.
    """
    if scenario.requires_llm:
        from blackbox.config import settings  # reads .env + process env

        if not settings.anthropic_api_key:
            return "ANTHROPIC_API_KEY missing"
    if scenario.requires_datahub:
        from blackbox.config import settings
        from blackbox.datahub import client

        if not client.ping():
            return f"DataHub GMS unreachable at {settings.datahub_gms_url}"
    return None


# ---------------------------------------------------------------------------
# Scenario execution
# ---------------------------------------------------------------------------
def run_scenario(scenario: "Scenario") -> ScenarioResult:
    t0 = time.monotonic()

    def finish(status: str, outcome: Outcome) -> ScenarioResult:
        return ScenarioResult(
            scenario=scenario.name,
            status=status,
            checks=outcome.checks,
            metrics=outcome.metrics,
            notes=outcome.notes,
            details=outcome.details,
            incident_id=outcome.incident_id,
            wall_time_s=round(time.monotonic() - t0, 2),
        )

    reason = check_preconditions(scenario)
    if reason is not None:
        return finish(f"skipped: {reason}", Outcome(notes=[f"precondition failed: {reason}"]))

    try:
        reset_environment(scenario.mode)
    except Exception as e:
        return finish(f"skipped: warehouse not buildable: {e}", Outcome())

    outcome = Outcome()
    try:
        outcome = scenario.runner(scenario)
        if not outcome.checks:
            status = "error: scenario produced no checks"
        else:
            status = "passed" if all(outcome.checks.values()) else "failed"
    except Exception as e:
        outcome.details["traceback"] = traceback.format_exc()[-4000:]
        status = f"error: {type(e).__name__}: {e}"
    finally:
        try:
            restore_environment()
        except Exception as e:  # keep the graded result; flag the dirty env loudly
            outcome.notes.append(f"WARNING: post-run environment restore FAILED: {e}")
    return finish(status, outcome)
