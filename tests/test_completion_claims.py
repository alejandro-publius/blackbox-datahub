"""A completion claim must match what actually happened.

Two places used to over-claim (issue #11, findings 5 and 6):

1. ``repair.verify_repair`` treated "no invariant failed" as "every invariant
   passed", so a suite of 32 skipped tests verified a repair. A skip checked
   nothing; only a suite where every collected test passed may verify.
2. ``writeback.resolve_incident`` returned ``complete`` even when the docs note
   and the tag on the root-cause dataset failed to write. Those are part of the
   promised record, so a failure in either must report ``partial``.

Offline: the warehouse and DataHub are replaced with stubs.
"""

import pytest

from blackbox import repair, warehouse
from blackbox.config import settings
from blackbox.datahub import writeback
from blackbox.models import IncidentState, MetricSnapshot, Writeback
# Aliased on import so pytest does not try to collect the pydantic model.
from blackbox.models import TestReport as InvariantReport

KPI_OK = MetricSnapshot(
    kpi_day="2026-08-09", revenue=27373.23, expected_revenue=29349.39,
    anomaly_ratio=0.9327, status="ok",
)
KPI_BAD = MetricSnapshot(
    kpi_day="2026-08-09", revenue=2737323.5, expected_revenue=29349.39,
    anomaly_ratio=93.27, status="anomalous",
)


# ------------------------------------------------------------- verify_repair


def _verified(monkeypatch, report: InvariantReport, kpi: MetricSnapshot = KPI_OK) -> bool:
    monkeypatch.setattr(warehouse, "rebuild_warehouse", lambda: {"ok": True})
    monkeypatch.setattr(warehouse, "run_invariants", lambda: report)
    monkeypatch.setattr(warehouse, "get_metric_snapshot", lambda: kpi)
    return repair.verify_repair()[2]


@pytest.mark.parametrize(
    "total, passed, failed, expected",
    [
        (32, 32, 0, True),    # the only verifying shape
        (32, 0, 0, False),    # every invariant skipped
        (32, 31, 0, False),   # one invariant skipped
        (32, 31, 1, False),   # one invariant failed
        (0, 0, 0, False),     # nothing collected
    ],
    ids=["all-passed", "all-skipped", "one-skipped", "one-failed", "none-collected"],
)
def test_verify_repair_requires_every_invariant_to_pass(monkeypatch, total, passed, failed, expected):
    report = InvariantReport(total=total, passed=passed, failed=failed)
    assert _verified(monkeypatch, report) is expected


def test_verify_repair_still_requires_the_kpi_back_in_range(monkeypatch):
    report = InvariantReport(total=32, passed=32, failed=0)
    assert _verified(monkeypatch, report, kpi=KPI_BAD) is False


# ---------------------------------------------------------- resolve_incident


class _FakeGraph:
    def __init__(self):
        self.queries: list[str] = []

    def execute_graphql(self, query, variables=None):
        self.queries.append(query)
        return {}


def _raise(exc):
    def _f(state):
        raise exc

    return _f


@pytest.fixture()
def datahub_stub(monkeypatch):
    graph = _FakeGraph()
    monkeypatch.setattr(settings, "blackbox_disable_datahub", False, raising=False)
    monkeypatch.setattr(writeback, "_graph", lambda: graph)
    monkeypatch.setattr(writeback, "_append_incident_note", lambda state: None)
    monkeypatch.setattr(writeback, "_tag_remediated", lambda state: None)
    return graph


def _state() -> IncidentState:
    state = IncidentState(report_text="Exec revenue KPI looks wrong.")
    state.writeback = Writeback(incident_urn="urn:li:incident:test", status="raised")
    state.tests_after = InvariantReport(total=32, passed=32, failed=0)
    state.metric_after = KPI_OK
    return state


def test_resolve_is_complete_only_when_every_write_lands(datahub_stub):
    wb = writeback.resolve_incident(_state())

    assert wb.status == "complete"
    assert any("updateIncidentStatus" in q for q in datahub_stub.queries)


def test_a_failed_docs_note_makes_the_writeback_partial(datahub_stub, monkeypatch):
    monkeypatch.setattr(writeback, "_append_incident_note", _raise(RuntimeError("docs outage")))

    wb = writeback.resolve_incident(_state())

    assert wb.status == "partial"
    assert "docs note FAILED" in wb.detail and "docs outage" in wb.detail
    assert "tagged blackbox-remediated" in wb.detail  # the write that worked is still reported


def test_a_failed_tag_makes_the_writeback_partial(datahub_stub, monkeypatch):
    monkeypatch.setattr(writeback, "_tag_remediated", _raise(RuntimeError("tag outage")))

    wb = writeback.resolve_incident(_state())

    assert wb.status == "partial"
    assert "tag FAILED" in wb.detail and "tag outage" in wb.detail
