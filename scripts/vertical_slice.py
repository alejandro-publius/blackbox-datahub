"""First end-to-end vertical slice, run directly against the engine (no UI):
broken KPI -> investigate -> root cause -> repair -> verify -> writeback.

Run: uv run python scripts/vertical_slice.py [--pause]
"""

import argparse
import json

from blackbox.agent.investigator import run_investigation, run_repair_phase
from blackbox.models import IncidentStage, IncidentState
from blackbox.store import IncidentStore


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pause", action="store_true", help="two-phase flow (like the demo UI)")
    ap.add_argument(
        "--report",
        default="Revenue just jumped roughly 100x on the executive dashboard. Is this real?",
    )
    args = ap.parse_args()

    store = IncidentStore()
    state = IncidentState(report_text=args.report)
    store.save(state)
    print("incident:", state.id, flush=True)

    final = run_investigation(state.id, store, pause_before_repair=args.pause)
    if args.pause and final.stage == IncidentStage.ROOT_CAUSE_CONFIRMED:
        print("phase 1 complete; authorizing repair phase", flush=True)
        final = run_repair_phase(state.id, store)

    print("\n=== FINAL ===")
    print("stage:", final.stage.value)
    if final.root_cause:
        print("root_cause.summary:", final.root_cause.summary)
        print("root_cause.asset:", final.root_cause.asset_urn)
        print("root_cause.field:", final.root_cause.field)
    print("patch:", final.patch.file if final.patch else None, final.patch.status if final.patch else "")
    if final.tests_after:
        print(f"tests_after: {final.tests_after.passed}/{final.tests_after.total}")
    if final.metric_before and final.metric_after:
        print(
            f"KPI: {final.metric_before.revenue:,.0f} ({final.metric_before.anomaly_ratio:.1f}x) -> "
            f"{final.metric_after.revenue:,.0f} ({final.metric_after.anomaly_ratio:.2f}x)"
        )
    print("git:", json.dumps(final.git_artifact.model_dump()) if final.git_artifact else None)
    print("writeback:", json.dumps(final.writeback.model_dump()) if final.writeback else None)
    print("hypotheses:", [(h.description[:60], h.status) for h in final.hypotheses])
    print("evidence count:", len(final.evidence), "by source:",
          {s: sum(1 for e in final.evidence if e.source == s) for s in {e.source for e in final.evidence}})
    print("error:", final.error)
    print("\nsummary:\n", (final.final_summary or "")[:2000])


if __name__ == "__main__":
    main()
