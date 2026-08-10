"""Write-side DataHub integration: durable incident + remediation context.

Uses OSS-supported GraphQL mutations (raiseIncident / updateIncidentStatus /
updateDescription / addTags). After a BlackBox run, the DataHub UI shows a real
resolved incident on the affected assets with the root cause, evidence summary
and repair reference — institutional memory that outlives the demo."""

from __future__ import annotations

from ..models import IncidentState, Writeback
from .client import _graph

_RAISE = """
mutation raiseIncident($input: RaiseIncidentInput!) { raiseIncident(input: $input) }
"""

_UPDATE_STATUS = """
mutation updateIncidentStatus($urn: String!, $input: IncidentStatusInput!) {
  updateIncidentStatus(urn: $urn, input: $input)
}
"""

_ADD_TAGS = """
mutation addTags($input: AddTagsInput!) { addTags(input: $input) }
"""


def raise_incident(state: IncidentState) -> Writeback:
    """Raise a real ACTIVE incident in DataHub on the root-cause + affected assets."""
    from ..config import settings

    if settings.blackbox_disable_datahub:
        raise RuntimeError("DataHub is unavailable (metadata service unreachable)")
    rc = state.root_cause
    if rc is None:
        raise ValueError("no confirmed root cause")
    affected = [n.urn for n in state.nodes if n.status in ("affected", "root_cause")]
    resource_urns = list(dict.fromkeys([rc.asset_urn] + affected))
    description = (
        f"Reported symptom: {state.report_text}\n\n"
        f"Root cause: {rc.summary}\n\n{rc.detail}\n\n"
        f"Blamed field: {rc.field}\n"
        f"Evidence items collected: {len(state.evidence)} "
        f"(lineage + profiles + baseline comparisons; see BlackBox incident {state.id})."
    )
    res = _graph().execute_graphql(
        _RAISE,
        variables={
            "input": {
                "type": "OPERATIONAL",
                "title": f"[BlackBox] {rc.summary}"[:200],
                "description": description[:4500],
                "resourceUrns": resource_urns,
                "priority": "CRITICAL",
                "status": {
                    "state": "ACTIVE",
                    "stage": "INVESTIGATION",
                    "message": "Root cause confirmed by BlackBox with machine-checked evidence; repair in progress.",
                },
            }
        },
    )
    incident_urn = res.get("raiseIncident")
    return Writeback(
        incident_urn=incident_urn,
        status="raised",
        detail=f"ACTIVE incident raised in DataHub on {len(resource_urns)} asset(s)",
    )


def resolve_incident(state: IncidentState) -> Writeback:
    """Mark the DataHub incident RESOLVED/FIXED with the full remediation record,
    and leave durable context on the root-cause dataset."""
    from ..config import settings

    if settings.blackbox_disable_datahub:
        raise RuntimeError("DataHub is unavailable (metadata service unreachable)")
    wb = state.writeback
    if wb is None or not wb.incident_urn:
        wb = raise_incident(state)
        state.writeback = wb  # keep the urn even if a later step fails

    tests = state.tests_after
    metric = state.metric_after
    git = state.git_artifact
    message_parts = [
        f"Repair verified by BlackBox.",
        f"Patch: {state.patch.file}" if state.patch else None,
        f"Tests: {tests.passed}/{tests.total} passed" if tests else None,
        f"KPI restored: anomaly ratio {metric.anomaly_ratio:.2f}x (target ~1.0x)" if metric else None,
        f"Fix branch: {git.branch} @ {git.commit[:10]}" if git else None,
    ]
    message = " | ".join(p for p in message_parts if p)
    try:
        _graph().execute_graphql(
            _UPDATE_STATUS,
            variables={
                "urn": wb.incident_urn,
                "input": {"state": "RESOLVED", "stage": "FIXED", "message": message[:900]},
            },
        )
    except Exception as e:
        return Writeback(
            incident_urn=wb.incident_urn,
            status="partial",
            detail=f"incident raised but status update failed: {e}",
        )

    extras = []
    # institutional memory on the root-cause dataset (best-effort)
    try:
        _append_incident_note(state)
        extras.append("remediation note appended to dataset docs")
    except Exception as e:
        extras.append(f"docs note skipped ({type(e).__name__})")
    try:
        _tag_remediated(state)
        extras.append("tagged blackbox-remediated")
    except Exception as e:
        extras.append(f"tag skipped ({type(e).__name__})")

    return Writeback(
        incident_urn=wb.incident_urn,
        status="complete",
        detail=f"Incident RESOLVED (FIXED) in DataHub — {message}. " + "; ".join(extras),
    )


_UPDATE_DESCRIPTION = """
mutation updateDescription($input: DescriptionUpdateInput!) { updateDescription(input: $input) }
"""


def _append_incident_note(state: IncidentState) -> None:
    from .client import get_dataset

    rc = state.root_cause
    assert rc is not None
    current = get_dataset(rc.asset_urn)
    existing = current.get("description") or ""
    git = state.git_artifact
    note = (
        f"\n\n---\n\n### ⚠️ Incident history (BlackBox {state.id})\n\n"
        f"- **Root cause:** {rc.summary}\n"
        f"- **Field:** `{rc.field}`\n"
        f"- **Resolution:** patched `{state.patch.file if state.patch else 'n/a'}`"
        + (f" (branch `{git.branch}`, commit `{git.commit[:10]}`)" if git else "")
        + "\n"
        f"- **Verification:** {state.tests_after.passed}/{state.tests_after.total} invariants passed"
        if state.tests_after
        else ""
    )
    if f"BlackBox {state.id}" in existing:
        return
    _graph().execute_graphql(
        _UPDATE_DESCRIPTION,
        variables={"input": {"resourceUrn": rc.asset_urn, "description": (existing + note)[:9000]}},
    )


def _tag_remediated(state: IncidentState) -> None:
    import datahub.metadata.schema_classes as models
    from datahub.emitter.mcp import MetadataChangeProposalWrapper

    rc = state.root_cause
    assert rc is not None
    tag_urn = "urn:li:tag:blackbox-remediated"
    graph = _graph()
    graph.emit(
        MetadataChangeProposalWrapper(
            entityUrn=tag_urn,
            aspect=models.TagPropertiesClass(
                name="blackbox-remediated",
                description="Asset was involved in an incident remediated by BlackBox.",
            ),
        )
    )
    graph.execute_graphql(
        _ADD_TAGS,
        variables={"input": {"tagUrns": [tag_urn], "resourceUrn": rc.asset_urn}},
    )
