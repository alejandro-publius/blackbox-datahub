"""Reset BlackBox-written state in DataHub for the demo datasets.

Writeback is a feature (durable incident memory), but it must not contaminate
the next demo/eval run: a remediation note left on a dataset description would
hand the next investigation the answer key. Called by the API demo reset and by
the eval harness before every scenario.
"""

from __future__ import annotations

from .client import _graph
from .ingest import TABLES, dataset_urn

_UPDATE_DESCRIPTION = """
mutation updateDescription($input: DescriptionUpdateInput!) { updateDescription(input: $input) }
"""

_REMOVE_TAG = """
mutation removeTag($input: TagAssociationInput!) { removeTag(input: $input) }
"""

_ACTIVE_INCIDENTS = """
query activeIncidents($urn: String!) {
  dataset(urn: $urn) {
    incidents(state: ACTIVE, start: 0, count: 25) {
      incidents { urn title }
    }
  }
}
"""

_RESOLVE = """
mutation updateIncidentStatus($urn: String!, $input: IncidentStatusInput!) {
  updateIncidentStatus(urn: $urn, input: $input)
}
"""

INCIDENT_NOTE_MARKER = "Incident history (BlackBox"
REMEDIATED_TAG_URN = "urn:li:tag:blackbox-remediated"


def reset_blackbox_state(resolve_incidents: bool = True) -> dict:
    """Remove incident-history notes, remediation tags, and (optionally) resolve
    ACTIVE BlackBox incidents on all demo datasets. Idempotent."""
    graph = _graph()
    from .client import get_dataset

    notes_cleared = 0
    tags_removed = 0
    incidents_resolved = 0

    for table in TABLES:
        urn = dataset_urn(table)
        try:
            ds = get_dataset(urn)
        except Exception:
            continue  # not ingested yet — nothing to clean

        desc = ds.get("description") or ""
        if INCIDENT_NOTE_MARKER in desc:
            clean = desc.split("\n\n---\n\n### ⚠️ " + INCIDENT_NOTE_MARKER.split(" (")[0])[0]
            # robust fallback: cut at the marker if the exact separator changed
            idx = clean.find(INCIDENT_NOTE_MARKER)
            if idx != -1:
                clean = clean[:idx].rstrip("-#⚠️ \n")
            graph.execute_graphql(
                _UPDATE_DESCRIPTION,
                variables={"input": {"resourceUrn": urn, "description": clean.strip()}},
            )
            notes_cleared += 1

        if "blackbox-remediated" in (ds.get("tags") or []):
            try:
                graph.execute_graphql(
                    _REMOVE_TAG,
                    variables={"input": {"tagUrn": REMEDIATED_TAG_URN, "resourceUrn": urn}},
                )
                tags_removed += 1
            except Exception:
                pass

        if resolve_incidents:
            try:
                res = graph.execute_graphql(_ACTIVE_INCIDENTS, variables={"urn": urn})
                incs = (((res.get("dataset") or {}).get("incidents")) or {}).get("incidents") or []
                for inc in incs:
                    graph.execute_graphql(
                        _RESOLVE,
                        variables={
                            "urn": inc["urn"],
                            "input": {
                                "state": "RESOLVED",
                                "stage": "NO_ACTION_REQUIRED",
                                "message": "Superseded demo run — reset by BlackBox demo-reset.",
                            },
                        },
                    )
                    incidents_resolved += 1
            except Exception:
                pass

    return {
        "notes_cleared": notes_cleared,
        "tags_removed": tags_removed,
        "incidents_resolved": incidents_resolved,
    }


def contamination_report() -> list[str]:
    """Names of demo datasets whose descriptions still carry BlackBox incident
    notes — used by the eval harness as a hard precondition."""
    from .client import get_dataset

    dirty = []
    for table in TABLES:
        try:
            ds = get_dataset(dataset_urn(table))
        except Exception:
            continue
        if INCIDENT_NOTE_MARKER in (ds.get("description") or ""):
            dirty.append(table)
    return dirty
