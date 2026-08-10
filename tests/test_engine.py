"""Unit tests for the incident engine's honesty gates: stage ordering, evidence-gated
root-cause confirmation, repair path safety, and read-only SQL enforcement."""

import pytest

from blackbox import repair, warehouse
from blackbox.agent.tools import ToolExecutor
from blackbox.models import (
    EvidenceItem,
    IncidentStage,
    IncidentState,
    LineageEdge,
    LineageNode,
)
from blackbox.store import IncidentStore


@pytest.fixture()
def store(tmp_path):
    return IncidentStore(root=tmp_path)


@pytest.fixture()
def state(store):
    s = IncidentState(report_text="Revenue jumped 100x?")
    store.save(s)
    return s


def executor_with_lineage(state, store) -> ToolExecutor:
    ex = ToolExecutor(state, store)
    state.nodes = [
        LineageNode(urn="urn:raw", name="raw.raw_orders", platform="duckdb", layer="source"),
        LineageNode(urn="urn:stg", name="staging.stg_orders", platform="duckdb", layer="staging"),
        LineageNode(urn="urn:fct", name="marts.fct_revenue", platform="duckdb", layer="marts"),
    ]
    state.edges = [
        LineageEdge(source="urn:raw", target="urn:stg"),
        LineageEdge(source="urn:stg", target="urn:fct"),
    ]
    return ex


def add_evidence(state, kind, source, data=None) -> EvidenceItem:
    ev = EvidenceItem(kind=kind, source=source, title=f"{kind} evidence", detail="", data=data)
    state.evidence.append(ev)
    return ev


# ---------------------------------------------------------------- state machine


def test_stage_order_forward_only(state):
    state.stage = IncidentStage.EVIDENCE_COLLECTION
    assert state.can_advance_to(IncidentStage.ROOT_CAUSE_CONFIRMED)
    assert not state.can_advance_to(IncidentStage.CONTEXT_DISCOVERY)
    assert state.can_advance_to(IncidentStage.FAILED)
    assert state.can_advance_to(IncidentStage.NO_INCIDENT)


def test_terminal_stages_are_sticky(state):
    state.stage = IncidentStage.NO_INCIDENT
    assert not state.can_advance_to(IncidentStage.REPAIR_GENERATED)


# ---------------------------------------------------------- root cause gating


def test_confirm_root_cause_rejects_without_evidence(state, store):
    ex = executor_with_lineage(state, store)
    out = ex.t_confirm_root_cause(
        summary="units changed", asset_urn="urn:raw", field="amount", detail="", evidence_ids=[]
    )
    assert "error" in out


def test_confirm_root_cause_rejects_without_quantitative(state, store):
    ex = executor_with_lineage(state, store)
    ev = add_evidence(state, "lineage", "datahub")
    out = ex.t_confirm_root_cause(
        summary="units changed", asset_urn="urn:raw", field="amount", detail="", evidence_ids=[ev.id]
    )
    assert "error" in out and "quantitative" in out["error"]


def test_confirm_root_cause_rejects_without_datahub(state, store):
    ex = executor_with_lineage(state, store)
    ev = add_evidence(state, "profile", "warehouse", data={"column": "amount", "ratio": 100})
    out = ex.t_confirm_root_cause(
        summary="units changed", asset_urn="urn:raw", field="amount", detail="", evidence_ids=[ev.id]
    )
    assert "error" in out and "DataHub" in out["error"]


def test_confirm_root_cause_rejects_when_field_not_in_evidence(state, store):
    ex = executor_with_lineage(state, store)
    e1 = add_evidence(state, "lineage", "datahub")
    e2 = add_evidence(state, "profile", "warehouse", data={"column": "usd_rate"})
    out = ex.t_confirm_root_cause(
        summary="units changed", asset_urn="urn:raw", field="amount", detail="",
        evidence_ids=[e1.id, e2.id],
    )
    assert "error" in out and "amount" in out["error"]


def test_confirm_root_cause_rejects_untraversed_asset(state, store):
    ex = executor_with_lineage(state, store)
    e1 = add_evidence(state, "lineage", "datahub")
    e2 = add_evidence(state, "profile", "warehouse", data={"column": "amount"})
    out = ex.t_confirm_root_cause(
        summary="units changed", asset_urn="urn:not-traversed", field="amount", detail="",
        evidence_ids=[e1.id, e2.id],
    )
    assert "error" in out


def test_confirm_root_cause_accepts_with_proper_evidence_and_marks_graph(state, store):
    ex = executor_with_lineage(state, store)
    state.stage = IncidentStage.EVIDENCE_COLLECTION
    e1 = add_evidence(state, "lineage", "datahub")
    e2 = add_evidence(state, "profile", "warehouse", data={"column": "amount", "median_ratio": 99.6})
    out = ex.t_confirm_root_cause(
        summary="raw_orders.amount switched dollars→cents", asset_urn="urn:raw", field="amount",
        detail="cloudpay_v2 rows are 100x", evidence_ids=[e1.id, e2.id],
    )
    assert out.get("ok") is True
    assert state.stage == IncidentStage.ROOT_CAUSE_CONFIRMED
    assert state.node("urn:raw").status == "root_cause"
    assert state.node("urn:stg").status == "affected"
    assert state.node("urn:fct").status == "affected"


def test_no_incident_requires_quantitative_evidence(state, store):
    ex = executor_with_lineage(state, store)
    e1 = add_evidence(state, "lineage", "datahub")
    out = ex.t_declare_no_incident(reasoning="all good", evidence_ids=[e1.id])
    assert "error" in out
    e2 = add_evidence(state, "baseline_comparison", "warehouse", data={"revenue_ratio": 1.0})
    out = ex.t_declare_no_incident(reasoning="all good", evidence_ids=[e2.id])
    assert out.get("ok") is True
    assert state.stage == IncidentStage.NO_INCIDENT


def test_hypothesis_elimination_requires_evidence(state, store):
    ex = executor_with_lineage(state, store)
    hyp = ex.t_record_hypothesis(description="fx staleness", target_urn="urn:fct")
    out = ex.t_update_hypothesis(hypothesis_id=hyp["hypothesis_id"], status="eliminated", confidence=0.1)
    assert "error" in out


# ------------------------------------------------------------- repair safety


def test_repair_restricted_to_transforms():
    with pytest.raises(ValueError):
        repair.propose_patch("backend/blackbox/api.py", "x", "nope")
    with pytest.raises((ValueError, FileNotFoundError)):
        repair.propose_patch("pipeline/transforms/../../Makefile", "x", "nope")


def test_propose_patch_produces_real_diff():
    current = warehouse.read_transform("stg_orders")["sql"]
    patched = current.replace("CAST(amount AS DOUBLE) AS amount", "CAST(amount AS DOUBLE) AS amount_x")
    p = repair.propose_patch("pipeline/transforms/stg_orders.sql", patched, "test")
    assert p.diff.startswith("--- a/pipeline/transforms/stg_orders.sql")
    assert "+" in p.diff and "-" in p.diff
    with pytest.raises(ValueError):
        repair.propose_patch("pipeline/transforms/stg_orders.sql", current, "identical")


# ------------------------------------------------------------ sql read-only


def test_run_sql_rejects_writes():
    with pytest.raises(ValueError):
        warehouse.run_sql("DROP TABLE staging.stg_orders")
    with pytest.raises(ValueError):
        warehouse.run_sql("SELECT 1; SELECT 2")
    assert warehouse.run_sql("SELECT 1 AS x")["rows"] == [[1]]


def test_run_sql_blocks_filesystem_exfiltration():
    # denylist layer
    with pytest.raises(ValueError):
        warehouse.run_sql("SELECT * FROM read_csv('/etc/hosts')")
    with pytest.raises(ValueError):
        warehouse.run_sql("SELECT * FROM read_text('.env')")
    # connection-hardening layer (bypass the regex with a novel function name):
    # any external-access attempt must fail at the DuckDB level too
    import duckdb as _duckdb

    with pytest.raises((_duckdb.Error, ValueError)):
        warehouse.run_sql("SELECT * FROM read_ndjson_objects('.env')")
