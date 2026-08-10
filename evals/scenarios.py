"""Scenario definitions + deterministic graders.

Every grade is computed from the final IncidentState, the on-disk transcript,
and real git/pytest state — never from LLM self-report. ``blackbox`` imports are
deferred so scenario *metadata* can be inspected before the process environment
(e.g. BLACKBOX_DISABLE_DATAHUB) is finalized by ``evals.run_one``.
"""

from __future__ import annotations

import dataclasses
import json
import re
from collections import Counter
from typing import Any, Callable

from . import harness
from .harness import Outcome

POSITIVE_REPORT = (
    "Revenue just jumped roughly 100x on the executive dashboard. Is this real?"
)
CONTROL_REPORT = (
    "Finance mentioned revenue felt slightly off this week. Can you check whether anything is wrong?"
)

# Correct answer fingerprints for the incident fixture (see pipeline/generate_sources.py:
# cloudpay_v2 rows report integer cents in raw_orders.amount; raw_fx_rates going stale
# is a deliberate distractor present in BOTH modes).
ROOT_CAUSE_URN_SUFFIX = "raw.raw_orders,PROD)"
ROOT_CAUSE_FIELD = "amount"
REPAIR_FILE = "pipeline/transforms/stg_orders.sql"
SEMANTIC_RE = re.compile(r"(cent|minor.?unit|100(x|×)|scal(e|ing)|unit)", re.IGNORECASE)

# The deliberately naive repair for bad_repair_rejected: blanket-divide EVERY
# amount by 100 (fixes the new cloudpay_v2 rows, corrupts all history).
NAIVE_OLD_LINE = "    CAST(amount AS DOUBLE) AS amount,"
NAIVE_NEW_LINE = "    CAST(amount AS DOUBLE) / 100.0 AS amount,"


@dataclasses.dataclass(frozen=True)
class Scenario:
    name: str
    mode: str  # fixture mode reset_environment() applies before the run
    requires_llm: bool
    requires_datahub: bool  # GMS must answer ping (agent tools + grading depend on it)
    runner: Callable[["Scenario"], Outcome]
    disable_datahub: bool = False  # run with BLACKBOX_DISABLE_DATAHUB=true (subprocess env)
    description: str = ""


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------
def _new_incident(report_text: str):
    from blackbox.models import IncidentState
    from blackbox.store import IncidentStore

    store = IncidentStore()
    state = IncidentState(report_text=report_text)
    store.save(state)
    return store, state


def _transcript_stats(incident_id: str) -> dict[str, int]:
    """Efficiency: model turns + tool calls from data/incidents/{id}.transcript.jsonl."""
    path = harness.INCIDENTS_DIR / f"{incident_id}.transcript.jsonl"
    turns = tool_calls = 0
    if path.exists():
        for line in path.read_text().splitlines():
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if "stop_reason" in entry:
                turns += 1
            elif "tool_result_for" in entry:
                tool_calls += 1
    return {"turns": turns, "tool_calls": tool_calls}


def _common_state_details(state) -> dict[str, Any]:
    return {
        "final_stage": state.stage.value,
        "final_summary": state.final_summary,
        "error": state.error,
        "n_evidence": len(state.evidence),
        "n_hypotheses": len(state.hypotheses),
    }


ACCEPTABLE_URN_SUFFIXES = (ROOT_CAUSE_URN_SUFFIX, "staging.stg_orders,PROD)")


def _root_cause_correct(rc) -> bool:
    """Correct = blames the order-amount unit defect. Both raw.raw_orders (origin)
    and staging.stg_orders (where normalization is missing / the repair lands) are
    defensible answers a staff engineer could give; `blamed_most_upstream` tracks
    which one was chosen."""
    return bool(
        rc
        and any(rc.asset_urn.endswith(s) for s in ACCEPTABLE_URN_SUFFIXES)
        and rc.field == ROOT_CAUSE_FIELD
    )


def _blamed_most_upstream(rc) -> bool:
    return bool(rc and rc.asset_urn.endswith(ROOT_CAUSE_URN_SUFFIX))


# ---------------------------------------------------------------------------
# 1 & 5. positive_incident / positive_incident_repeat
# ---------------------------------------------------------------------------
def _grade_positive(state) -> Outcome:
    from blackbox.models import IncidentStage

    out = Outcome(incident_id=state.id)
    rc = state.root_cause

    out.checks["terminal_ok"] = state.stage in (
        IncidentStage.VERIFIED,
        IncidentStage.WRITEBACK_COMPLETE,
    )
    out.checks["root_cause_correct"] = _root_cause_correct(rc)
    out.metrics["blamed_most_upstream"] = _blamed_most_upstream(rc)
    sem_blob = f"{rc.summary} {rc.detail}" if rc else ""
    out.checks["semantic_identified"] = bool(rc and SEMANTIC_RE.search(sem_blob))
    out.checks["distractor_avoided"] = not (rc and "raw_fx_rates" in rc.asset_urn)

    # Bonus metric (not pass/fail): did the agent at least LOOK at the fx distractor?
    fx_texts = [f"{h.description} {h.target_urn}" for h in state.hypotheses]
    fx_texts += [f"{e.title} {e.detail}" for e in state.evidence]
    out.metrics["distractor_examined"] = any("fx" in s.lower() for s in fx_texts)

    patch = state.patch
    out.checks["repair_correct_file"] = bool(patch and patch.file == REPAIR_FILE)
    ta, ma = state.tests_after, state.metric_after
    out.checks["repair_verified"] = bool(
        ta and ta.failed == 0 and ta.total >= 30 and ma and 0.8 <= ma.anomaly_ratio <= 1.3
    )
    # A targeted fix must condition on the defective cohort's causal attribute
    # (the provider), not merely on dates or a bare CASE — date-scoped fixes are
    # numerically identical in this fixture but causally wrong. Diff reported
    # below for human review.
    added = "\n".join(l for l in (patch.diff.splitlines() if patch else []) if l.startswith("+"))
    out.checks["repair_targeted"] = bool(
        patch and ("cloudpay" in added.lower() or "payment_processor" in added.lower())
    )
    # The fixture is deterministic: the exact healthy values for the affected days
    # are in the committed baseline. A repair that merely lands inside the loose
    # KPI window (e.g. replacing amounts with a plausible constant) fails this.
    out.checks["repair_restores_baseline"] = _post_repair_matches_baseline()
    # The graded patch must be the ONLY change on disk (no earlier patch to a
    # different transform left behind by an iteration).
    out.checks["repair_single_file"] = _changed_transforms() in ([], [REPAIR_FILE])

    out.metrics["evidence_by_source"] = dict(Counter(e.source for e in state.evidence))
    has_datahub_lineage = any(e.source == "datahub" and e.kind == "lineage" for e in state.evidence)
    cited = [state.evidence_by_id(i) for i in (rc.evidence_ids if rc else [])]
    cited_quant = any(c and c.kind in ("profile", "baseline_comparison") for c in cited)
    out.checks["evidence_coverage"] = has_datahub_lineage and cited_quant

    wb = state.writeback
    out.checks["writeback_done"] = bool(wb and wb.status == "complete" and wb.incident_urn)

    out.metrics.update(_transcript_stats(state.id))
    out.details.update(_common_state_details(state))
    out.details["root_cause"] = rc.model_dump() if rc else None
    out.details["patch_diff"] = patch.diff if patch else None
    out.details["patch_reasoning"] = patch.reasoning if patch else None
    out.details["tests_after"] = ta.model_dump() if ta else None
    out.details["metric_after_anomaly_ratio"] = ma.anomaly_ratio if ma else None
    out.details["writeback"] = wb.model_dump() if wb else None
    out.notes.append(
        f"stage={state.stage.value}; turns={out.metrics['turns']}; tool_calls={out.metrics['tool_calls']}"
    )
    if state.error:
        out.notes.append(f"error: {state.error[:200]}")
    return out


def _post_repair_matches_baseline(tolerance: float = 0.01, days: int = 3) -> bool:
    """True iff post-repair daily revenue AND median AOV for the most recent days
    match the committed healthy baseline within `tolerance` (default 1%)."""
    try:
        from blackbox import warehouse

        comp = warehouse.compare_to_baseline(last_days=days)["comparisons"]
    except Exception:
        return False
    if len(comp) < days:
        return False
    for c in comp:
        for ratio_key in ("revenue_ratio", "aov_ratio"):
            r = c.get(ratio_key)
            if r is None or abs(r - 1.0) > tolerance:
                return False
    return True


def _changed_transforms() -> list[str]:
    import subprocess

    out = subprocess.run(
        ["git", "diff", "--name-only", "--", "pipeline/transforms/"],
        cwd=harness.REPO_ROOT, capture_output=True, text=True,
    )
    return [l.strip() for l in out.stdout.splitlines() if l.strip()]


def run_positive_incident(scenario: Scenario) -> Outcome:
    from blackbox.agent.investigator import run_investigation

    store, state = _new_incident(POSITIVE_REPORT)
    final = run_investigation(state.id, store, pause_before_repair=False)
    return _grade_positive(final)


# ---------------------------------------------------------------------------
# 2. control_no_incident
# ---------------------------------------------------------------------------
def run_control_no_incident(scenario: Scenario) -> Outcome:
    from blackbox.agent.investigator import run_investigation
    from blackbox.models import IncidentStage

    store, state = _new_incident(CONTROL_REPORT)
    final = run_investigation(state.id, store, pause_before_repair=False)

    out = Outcome(incident_id=final.id)
    out.checks["stage_no_incident"] = final.stage == IncidentStage.NO_INCIDENT
    out.checks["no_patch"] = final.patch is None
    # Graded BEFORE the harness restores the environment.
    out.checks["transforms_unchanged"] = git_unchanged = harness.git_transforms_unchanged()
    out.checks["no_false_positive"] = final.root_cause is None

    out.metrics["false_positive"] = final.root_cause is not None
    out.metrics.update(_transcript_stats(final.id))
    out.details.update(_common_state_details(final))
    out.details["root_cause"] = final.root_cause.model_dump() if final.root_cause else None
    if not git_unchanged:
        out.notes.append("pipeline/transforms/ was modified during a healthy-mode control run")
    leftover = [p.name for p in harness.TRANSFORMS_DIR.glob("*.sql.orig")]
    if leftover:
        out.notes.append(f"leftover patch backups: {leftover}")
    out.notes.append(f"stage={final.stage.value}")
    if final.error:
        out.notes.append(f"error: {final.error[:200]}")
    return out


# ---------------------------------------------------------------------------
# 3. bad_repair_rejected — fully deterministic, no LLM, no DataHub
# ---------------------------------------------------------------------------
def run_bad_repair_rejected(scenario: Scenario) -> Outcome:
    """Prove the verification gate rejects a superficial fix: blanket-dividing
    every amount by 100 makes the LATEST KPI look right but corrupts all
    pre-cutover history — the historical-immutability invariants must catch it."""
    from blackbox import repair, warehouse

    out = Outcome()
    path = harness.TRANSFORMS_DIR / "stg_orders.sql"
    original = path.read_text()
    if NAIVE_OLD_LINE not in original:
        raise RuntimeError(
            f"fixture drift: expected line not found in stg_orders.sql: {NAIVE_OLD_LINE!r}"
        )
    new_content = original.replace(NAIVE_OLD_LINE, NAIVE_NEW_LINE)

    patch = repair.propose_patch(
        REPAIR_FILE,
        new_content,
        "EVAL FIXTURE: deliberately naive blanket /100 'fix' that ignores the "
        "cloudpay_v2 cutover and rescales all historical dollar amounts.",
    )
    report = snapshot = None
    verified_ok = None
    try:
        repair.apply_patch(patch, new_content)
        report, snapshot, verified_ok = repair.verify_repair()
    finally:
        revert_error = None
        try:
            repair.revert_patch(patch)
        except Exception as e:  # pragma: no cover — surfaced via checks below
            revert_error = f"revert failed: {e}"
        rebuild = warehouse.rebuild_warehouse()
        if revert_error:
            out.notes.append(revert_error)

    if report is None or verified_ok is None:
        raise RuntimeError("verify_repair did not complete")

    out.checks["bad_repair_rejected"] = verified_ok is False
    failing = [f.name for f in report.failures]
    # Actual invariant names (pipeline/invariants/test_invariants.py):
    # test_historical_immutability_aggregate matches 'immutab'; the spot-day
    # variants (test_historical_spot_day[...]) are reported alongside.
    immutability_hits = [
        n for n in failing if "immutab" in n.lower() or "baseline" in n.lower()
    ]
    historical_hits = [n for n in failing if "historical" in n.lower()]
    out.checks["immutability_caught"] = len(immutability_hits) > 0
    out.checks["environment_restored"] = (
        rebuild["ok"]
        and harness.git_transforms_unchanged()
        and not list(harness.TRANSFORMS_DIR.glob("*.sql.orig"))
    )

    out.metrics["tests_total"] = report.total
    out.metrics["tests_failed"] = report.failed
    out.metrics["kpi_anomaly_ratio_after_bad_patch"] = (
        round(snapshot.anomaly_ratio, 3) if snapshot else None
    )
    out.details["failing_tests"] = failing
    out.details["immutability_failures"] = immutability_hits
    out.details["historical_failures"] = historical_hits
    out.details["patch_diff"] = patch.diff
    out.notes.append(
        f"verify gate returned ok={verified_ok}; {report.failed}/{report.total} invariants failed; "
        f"immutability caught it ({len(historical_hits)} historical failures)"
    )
    return out


# ---------------------------------------------------------------------------
# 4. datahub_ablation
# ---------------------------------------------------------------------------
def run_datahub_ablation(scenario: Scenario) -> Outcome:
    """Same incident, but the agent's DataHub tools all error out AND the
    confirm gate's DataHub-citation requirements are relaxed (see tools.py) so
    the ablation measures information value, not gate wiring (a review found the
    earlier terminal-failure framing circular). Graded honestly:
      - run_executed: the agent actually took turns;
      - no_false_all_clear: it did not wrongly declare NO_INCIDENT;
    and REPORTED (not pass/fail): whether it still identified the right asset &
    field, whether writeback was possible, turns/tool-calls — compared against
    the DataHub-enabled arm in results."""
    from blackbox.config import settings

    if not settings.blackbox_disable_datahub:
        # Never grade a non-ablated run as an ablation. This means the env var
        # was not set before blackbox.config was imported (settings is a
        # module-level singleton) — run via `python -m evals.run_one datahub_ablation`.
        raise RuntimeError(
            "BLACKBOX_DISABLE_DATAHUB did not reach blackbox.config.settings; "
            "run this scenario through evals.run_one (subprocess isolation)"
        )

    from blackbox.agent.investigator import run_investigation
    from blackbox.models import IncidentStage

    store, state = _new_incident(POSITIVE_REPORT)
    final = run_investigation(state.id, store, pause_before_repair=False)

    out = Outcome(incident_id=final.id)
    rc = final.root_cause
    stats = _transcript_stats(final.id)
    # Guard: a run that crashed before the agent took a single turn (e.g. an API
    # error) proves nothing — never a pass.
    out.checks["run_executed"] = stats["turns"] > 0
    # An ablated agent that declares "no incident" on corrupted data is the
    # worst outcome — that IS a pass/fail matter.
    out.checks["no_false_all_clear"] = final.stage != IncidentStage.NO_INCIDENT
    reached_terminal = final.stage in (IncidentStage.VERIFIED, IncidentStage.WRITEBACK_COMPLETE)
    correct = _root_cause_correct(rc)

    out.metrics["ablated_final_stage"] = final.stage.value
    out.metrics["ablated_reached_terminal"] = reached_terminal
    out.metrics["ablated_root_cause_correct"] = correct
    out.metrics["ablated_writeback_possible"] = bool(
        final.writeback and final.writeback.status == "complete"
    )
    out.metrics["ablated_datahub_evidence_count"] = sum(
        1 for e in final.evidence if e.source == "datahub"
    )
    out.metrics.update(stats)
    out.details.update(_common_state_details(final))
    if final.error:
        out.notes.append(f"error: {final.error[:200]}")
    out.details["root_cause"] = rc.model_dump() if rc else None
    out.details["settings_blackbox_disable_datahub"] = settings.blackbox_disable_datahub
    out.notes.append(
        f"ablated run ended stage={final.stage.value}, "
        f"root_cause={'correct' if correct else ('present-but-wrong' if rc else 'none')}"
    )
    return out


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
SCENARIOS: dict[str, Scenario] = {
    s.name: s
    for s in [
        Scenario(
            name="positive_incident",
            mode="incident",
            requires_llm=True,
            requires_datahub=True,
            runner=run_positive_incident,
            description="Full autonomous loop on the cents-vs-dollars incident: correct root "
            "cause, targeted verified repair, DataHub writeback.",
        ),
        Scenario(
            name="control_no_incident",
            mode="healthy",
            requires_llm=True,
            requires_datahub=True,
            runner=run_control_no_incident,
            description="Healthy data + vague report: the agent must conclude NO_INCIDENT and "
            "touch nothing (false-positive control).",
        ),
        Scenario(
            name="bad_repair_rejected",
            mode="incident",
            requires_llm=False,
            requires_datahub=False,
            runner=run_bad_repair_rejected,
            description="Deterministic: a naive blanket /100 patch must be REJECTED by the "
            "verification gate via the historical-immutability invariants.",
        ),
        Scenario(
            name="datahub_ablation",
            mode="incident",
            requires_llm=True,
            requires_datahub=False,  # DataHub is deliberately disabled for this run
            disable_datahub=True,
            runner=run_datahub_ablation,
            description="Same incident with DataHub tools disabled: the agent must NOT reach a "
            "correct confirmed root cause (DataHub is load-bearing).",
        ),
        Scenario(
            name="positive_incident_repeat",
            mode="incident",
            requires_llm=True,
            requires_datahub=True,
            runner=run_positive_incident,
            description="positive_incident repeated N times (--trials) for consistency measurement.",
        ),
    ]
}
