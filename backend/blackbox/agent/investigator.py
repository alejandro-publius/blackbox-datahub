"""The investigation loop: Claude drives strategy; deterministic tools produce facts;
the state machine + evidence gates keep it honest."""

from __future__ import annotations

import json
from typing import Any

from anthropic import Anthropic

from .. import repair, warehouse
from ..config import settings
from ..models import IncidentStage, IncidentState
from ..store import IncidentStore
from .prompts import SYSTEM_PROMPT
from .tools import TOOL_SCHEMAS, ToolExecutor

MAX_TURNS = 60
MAX_NUDGES = 2

TERMINAL_OK = {
    IncidentStage.WRITEBACK_COMPLETE,
    IncidentStage.VERIFIED,
    IncidentStage.NO_INCIDENT,
}


def run_investigation(
    incident_id: str, store: IncidentStore, pause_before_repair: bool = True
) -> IncidentState:
    """Phase 1: investigate up to a confirmed root cause (or NO_INCIDENT).
    With pause_before_repair=False it continues straight through repair+verify."""
    state = store.get(incident_id)
    if state is None:
        raise ValueError(f"unknown incident {incident_id}")

    executor = ToolExecutor(state, store, allow_repair=not pause_before_repair)

    # Pre-flight deterministic context (before/after story needs a 'before')
    try:
        state.metric_before = warehouse.get_metric_snapshot()
    except Exception as e:
        state.error = f"warehouse unavailable: {e}"
        state.stage = IncidentStage.FAILED
        store.save(state)
        return state
    state.tests_before = warehouse.run_invariants()
    store.save(state)

    if pause_before_repair:
        goal = (
            "Investigate until you either confirm the root cause (confirm_root_cause) or conclude "
            "there is no incident. Once confirm_root_cause is ACCEPTED, call finish(...) with your "
            "investigation report — the operator will authorize the repair phase separately."
        )
    else:
        goal = (
            "Investigate, confirm the root cause, repair it, and verify end-to-end. "
            "End with finish(...) only after verification (or declare no incident)."
        )
    messages: list[dict[str, Any]] = [
        {
            "role": "user",
            "content": (
                f"INCIDENT REPORT (from on-call): “{state.report_text}”\n\n"
                f"{goal}\n\nStart by locating the affected asset in DataHub and quantifying the symptom."
            ),
        }
    ]
    return _run_loop(state, store, executor, messages, phase="investigation")


def run_repair_phase(incident_id: str, store: IncidentStore) -> IncidentState:
    """Phase 2: operator-authorized repair for an incident with a confirmed root cause."""
    state = store.get(incident_id)
    if state is None:
        raise ValueError(f"unknown incident {incident_id}")
    if state.root_cause is None:
        raise ValueError("no confirmed root cause — cannot start repair phase")

    executor = ToolExecutor(state, store, allow_repair=True)
    rc = state.root_cause
    messages: list[dict[str, Any]] = [
        {
            "role": "user",
            "content": (
                "REPAIR PHASE AUTHORIZED by operator.\n\n"
                f"Confirmed root cause: {rc.summary}\nAsset: {rc.asset_urn}\nField: {rc.field}\n"
                f"Detail: {rc.detail}\n\n"
                f"Evidence already collected (ids): {[e.id for e in state.evidence][-20:]}\n\n"
                "Read the relevant transformation source, design the minimal principled fix, and use "
                "propose_repair. The system will rebuild the warehouse and run the full invariant "
                "suite. Iterate until verification passes, then call finish(...) with the resolution "
                "report."
            ),
        }
    ]
    return _run_loop(state, store, executor, messages, phase="repair")


def _run_loop(
    state: IncidentState,
    store: IncidentStore,
    executor: ToolExecutor,
    messages: list[dict[str, Any]],
    phase: str,
) -> IncidentState:
    transcript_path = store.root / f"{state.id}.transcript.jsonl"

    def log(entry: dict[str, Any]) -> None:
        with transcript_path.open("a") as f:
            f.write(json.dumps({"phase": phase, **entry}, default=str) + "\n")

    client = Anthropic(api_key=settings.anthropic_api_key, max_retries=8)

    nudges = 0
    try:
        for turn in range(MAX_TURNS):
            if executor.finished:
                break
            resp = client.messages.create(
                model=settings.anthropic_model,
                max_tokens=8192,
                system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
                tools=TOOL_SCHEMAS,
                messages=messages,
            )
            tool_uses = [b for b in resp.content if b.type == "tool_use"]
            log(
                {
                    "turn": turn,
                    "stop_reason": resp.stop_reason,
                    "text": " ".join(b.text for b in resp.content if b.type == "text")[:2000],
                    "tools": [{"name": t.name, "input_keys": sorted((t.input or {}).keys())} for t in tool_uses],
                    "usage": {"in": resp.usage.input_tokens, "out": resp.usage.output_tokens},
                }
            )
            messages.append({"role": "assistant", "content": resp.content})

            if not tool_uses:
                if executor.finished:
                    break
                nudges += 1
                if nudges > MAX_NUDGES:
                    break
                messages.append(
                    {
                        "role": "user",
                        "content": "Continue the investigation with tool calls. When fully done, call finish(...).",
                    }
                )
                continue

            results = []
            for tu in tool_uses:
                out = executor.dispatch(tu.name, dict(tu.input or {}))
                log({"turn": turn, "tool_result_for": tu.name, "result": out[:1500]})
                results.append({"type": "tool_result", "tool_use_id": tu.id, "content": out})
            messages.append({"role": "user", "content": results})
    except Exception as e:
        state.error = f"{type(e).__name__}: {e}"
        state.stage = IncidentStage.FAILED
        _cleanup_unverified_patch(state)
        store.save(state)
        log({"fatal": state.error})
        return state

    allowed = set(TERMINAL_OK)
    if not executor.allow_repair:
        # phase 1 with operator pause: a confirmed root cause is a successful stop
        allowed.add(IncidentStage.ROOT_CAUSE_CONFIRMED)
    if state.stage not in allowed and state.stage != IncidentStage.FAILED:
        state.error = state.error or f"{phase} phase ended without reaching a verified terminal state"
        state.stage = IncidentStage.FAILED
        _cleanup_unverified_patch(state)
    store.save(state)
    return state


def _cleanup_unverified_patch(state: IncidentState) -> None:
    if state.patch and state.patch.status in ("applied", "testing"):
        try:
            repair.revert_patch(state.patch)
            warehouse.rebuild_warehouse()
        except Exception:
            pass
