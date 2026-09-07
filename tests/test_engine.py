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


URN_RAW = "urn:li:dataset:(urn:li:dataPlatform:duckdb,raw.raw_orders,PROD)"
URN_STG = "urn:li:dataset:(urn:li:dataPlatform:duckdb,staging.stg_orders,PROD)"
URN_FCT = "urn:li:dataset:(urn:li:dataPlatform:duckdb,marts.fct_revenue,PROD)"


def executor_with_lineage(state, store) -> ToolExecutor:
    ex = ToolExecutor(state, store)
    state.nodes = [
        LineageNode(urn=URN_RAW, name="raw.raw_orders", platform="duckdb", layer="source"),
        LineageNode(urn=URN_STG, name="staging.stg_orders", platform="duckdb", layer="staging"),
        LineageNode(urn=URN_FCT, name="marts.fct_revenue", platform="duckdb", layer="marts"),
    ]
    state.edges = [
        LineageEdge(source=URN_RAW, target=URN_STG),
        LineageEdge(source=URN_STG, target=URN_FCT),
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
        summary="units changed", asset_urn=URN_RAW, field="amount", detail="", evidence_ids=[]
    )
    assert "error" in out


def test_confirm_root_cause_rejects_without_quantitative(state, store):
    ex = executor_with_lineage(state, store)
    ev = add_evidence(state, "lineage", "datahub")
    out = ex.t_confirm_root_cause(
        summary="units changed", asset_urn=URN_RAW, field="amount", detail="", evidence_ids=[ev.id]
    )
    assert "error" in out and "quantitative" in out["error"]


def test_confirm_root_cause_rejects_without_datahub(state, store):
    ex = executor_with_lineage(state, store)
    ev = add_evidence(state, "profile", "warehouse", data={"column": "amount", "ratio": 100})
    out = ex.t_confirm_root_cause(
        summary="units changed", asset_urn=URN_RAW, field="amount", detail="", evidence_ids=[ev.id]
    )
    assert "error" in out and "DataHub" in out["error"]


def test_confirm_root_cause_rejects_when_field_not_in_evidence(state, store):
    ex = executor_with_lineage(state, store)
    e1 = add_evidence(state, "lineage", "datahub")
    e2 = add_evidence(state, "profile", "warehouse", data={"column": "usd_rate"})
    out = ex.t_confirm_root_cause(
        summary="units changed", asset_urn=URN_RAW, field="amount", detail="",
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
    e2 = add_evidence(state, "profile", "warehouse",
                      data={"table": "raw.raw_orders", "column": "amount", "median_ratio": 99.6})
    out = ex.t_confirm_root_cause(
        summary="raw_orders.amount switched dollars→cents", asset_urn=URN_RAW, field="amount",
        detail="cloudpay_v2 rows are 100x", evidence_ids=[e1.id, e2.id],
    )
    assert out.get("ok") is True
    assert state.stage == IncidentStage.ROOT_CAUSE_CONFIRMED
    assert state.node(URN_RAW).status == "root_cause"
    assert state.node(URN_STG).status == "affected"
    assert state.node(URN_FCT).status == "affected"


def test_confirm_root_cause_rejects_unknown_evidence_id(state, store):
    ex = executor_with_lineage(state, store)
    out = ex.t_confirm_root_cause(
        summary="units changed", asset_urn=URN_RAW, field="amount", detail="",
        evidence_ids=["ev_does_not_exist"],
    )
    assert "error" in out and "do not exist" in out["error"]


def test_confirm_root_cause_rejects_when_asset_not_in_evidence(state, store):
    # Field is mentioned, but nothing in the cited evidence names the blamed asset.
    ex = executor_with_lineage(state, store)
    e1 = add_evidence(state, "lineage", "datahub")
    e2 = add_evidence(
        state, "profile", "warehouse",
        data={"table": "staging.stg_orders", "column": "amount", "median_ratio": 99.6},
    )
    out = ex.t_confirm_root_cause(
        summary="units changed", asset_urn=URN_RAW, field="amount", detail="",
        evidence_ids=[e1.id, e2.id],
    )
    assert "error" in out and "raw.raw_orders" in out["error"]


def test_confirm_root_cause_rejects_contradictory_evidence(state, store):
    # Evidence that is topically on-point (right field, right asset) but whose own
    # numbers show nothing out of the ordinary must NOT confirm an incident — a
    # citation that reads as healthy cannot support a root-cause claim.
    ex = executor_with_lineage(state, store)
    e1 = add_evidence(state, "lineage", "datahub")
    e2 = add_evidence(
        state, "baseline_comparison", "warehouse",
        data={
            "table": "raw.raw_orders", "column": "amount",
            "comparisons": [{"day": "2026-08-09", "revenue_ratio": 1.02}],
        },
    )
    out = ex.t_confirm_root_cause(
        summary="units changed", asset_urn=URN_RAW, field="amount",
        detail="cloudpay_v2 rows are 100x", evidence_ids=[e1.id, e2.id],
    )
    assert "error" in out and "no anomaly" in out["error"]
    assert state.stage != IncidentStage.ROOT_CAUSE_CONFIRMED


def test_no_incident_requires_quantitative_evidence(state, store):
    ex = executor_with_lineage(state, store)
    e1 = add_evidence(state, "lineage", "datahub")
    out = ex.t_declare_no_incident(reasoning="all good", evidence_ids=[e1.id])
    assert "error" in out
    e2 = add_evidence(state, "baseline_comparison", "warehouse", data={"revenue_ratio": 1.0})
    out = ex.t_declare_no_incident(reasoning="all good", evidence_ids=[e2.id])
    assert out.get("ok") is True
    assert state.stage == IncidentStage.NO_INCIDENT


def test_no_incident_rejects_contradictory_evidence(state, store):
    # The cited evidence itself shows a 100x anomaly — citing it to declare
    # "no incident" is contradictory and must be refused, not accepted.
    ex = executor_with_lineage(state, store)
    e1 = add_evidence(
        state, "baseline_comparison", "warehouse",
        data={"comparisons": [{"day": "2026-08-09", "revenue_ratio": 100.0}]},
    )
    out = ex.t_declare_no_incident(reasoning="looks fine to me", evidence_ids=[e1.id])
    assert "error" in out and "anomalous" in out["error"]
    assert state.stage != IncidentStage.NO_INCIDENT


def test_no_incident_rejects_when_any_cited_evidence_is_anomalous(state, store):
    # Mixing one normal item with one anomalous item must still be refused —
    # partial support does not launder the contradictory citation.
    ex = executor_with_lineage(state, store)
    e_ok = add_evidence(state, "baseline_comparison", "warehouse", data={"revenue_ratio": 0.97})
    e_bad = add_evidence(state, "profile", "warehouse", data={"aov_ratio": 12.4})
    out = ex.t_declare_no_incident(reasoning="mostly fine", evidence_ids=[e_ok.id, e_bad.id])
    assert "error" in out


def test_hypothesis_elimination_requires_evidence(state, store):
    ex = executor_with_lineage(state, store)
    hyp = ex.t_record_hypothesis(description="fx staleness", target_urn=URN_FCT)
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
