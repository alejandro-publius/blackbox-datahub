"""Agent Context Kit adapter: transport tagging and graceful degradation.

These tests never touch the network. They pin the two properties that matter:
the embedded kit is optional (its absence must not break investigation), and
whichever transport answers is recorded honestly on the evidence.
"""

import pytest

from blackbox.datahub import client as dh
from blackbox.datahub import context_kit as ck


@pytest.fixture(autouse=True)
def _reset_kit_state():
    ck.reset()
    yield
    ck.reset()


# ------------------------------------------------------------ graceful degradation


def test_unavailable_kit_returns_none_not_raises(monkeypatch):
    """A missing/broken kit yields None so callers fall back — never an exception."""
    monkeypatch.setattr(ck, "available", lambda: False)
    assert ck.search("anything") is None
    assert ck.schema_fields("urn:li:dataset:(urn:li:dataPlatform:duckdb,x,PROD)") is None
    assert ck.lineage_hop("urn:li:dataset:(urn:li:dataPlatform:duckdb,x,PROD)") is None


def test_availability_failure_is_cached_and_reported(monkeypatch):
    """Initialization is attempted once, and the reason is retrievable."""
    calls = {"n": 0}

    def boom(*a, **k):
        calls["n"] += 1
        raise RuntimeError("gms unreachable")

    monkeypatch.setattr("datahub_agent_context.set_client", boom, raising=False)
    assert ck.available() is False
    assert ck.available() is False  # cached, not retried
    assert calls["n"] == 1
    assert "gms unreachable" in (ck.failure() or "")


def test_kit_errors_do_not_propagate(monkeypatch):
    """An exception inside a kit call degrades to None."""
    monkeypatch.setattr(ck, "available", lambda: True)
    import datahub_agent_context.mcp_tools as tools

    monkeypatch.setattr(tools, "search", lambda **kw: (_ for _ in ()).throw(RuntimeError("boom")))
    assert ck.search("q") is None


# ----------------------------------------------------------------- transport order


def test_search_prefers_mcp_then_ack_then_graphql(monkeypatch):
    """MCP answers first; the kit is the next embedded path; GraphQL is last."""
    from blackbox.datahub import mcp_bridge

    monkeypatch.setattr(type(mcp_bridge.bridge), "available", property(lambda self: False))

    ack_hits = [{"urn": "urn:li:dataset:(urn:li:dataPlatform:duckdb,a.b,PROD)",
                 "name": "a.b", "platform": "duckdb", "description": None,
                 "via": ck.TRANSPORT}]
    monkeypatch.setattr(ck, "search", lambda q, limit=20: ack_hits)

    def _no_graphql():
        raise AssertionError("GraphQL must not be reached when the kit answers")

    monkeypatch.setattr(dh, "_graph", _no_graphql)
    out = dh.search("revenue")
    assert out == ack_hits
    assert out[0]["via"] == "datahub-agent-context"


def test_lineage_falls_back_to_ack_when_mcp_is_down(monkeypatch):
    """A hop the MCP server cannot serve is served by the embedded kit, and the
    resulting graph reports that transport."""
    monkeypatch.setattr(dh, "_mcp_hop", lambda urn, direction: None)
    monkeypatch.setattr(
        dh, "_ack_hop",
        lambda urn, direction: (
            [{"urn": "urn:li:dataset:(urn:li:dataPlatform:duckdb,raw.o,PROD)",
              "name": "raw.o", "platform": "duckdb"}]
            if "marts" in urn else []
        ),
    )
    monkeypatch.setattr(dh, "_column_lineage_for", lambda urn: {})
    res = dh.lineage("urn:li:dataset:(urn:li:dataPlatform:duckdb,marts.m,PROD)", "UPSTREAM", 1)
    assert res["via"] == "datahub-agent-context"
    assert any(n["name"] == "raw.o" for n in res["nodes"])


# ------------------------------------------------------------------ honesty guard


def test_no_cloud_only_tools_are_referenced():
    """This project targets DataHub OSS/Core. The kit's Cloud-gated chat and
    document tools must never be wired in."""
    from pathlib import Path

    src = Path(ck.__file__).read_text()
    for cloud_only in ("ask_datahub_chat", "get_datahub_chat", "search_documents", "grep_documents"):
        assert f"import {cloud_only}" not in src
        assert f"{cloud_only}(" not in src
