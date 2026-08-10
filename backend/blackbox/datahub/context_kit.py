"""Embedded DataHub context transport, via the official Agent Context Kit.

BlackBox reads DataHub's context graph over two surfaces:

* the **MCP Server** (`mcp_bridge.py`) — the interoperable, agent-facing surface
  any MCP client can speak; and
* the **Agent Context Kit** (this module) — the native embedded Python path,
  no subprocess and no stdio hop.

They are transports, not independent sources of truth: both ultimately read the
same DataHub instance. We record which one produced each fact
(`EvidenceItem.transport`) so a reader can see the provenance of the evidence,
not so we can claim corroboration.

Everything here degrades gracefully — if the package is absent or the call
fails, callers fall back to MCP and then to GraphQL.

Cloud-gated tools in the kit (`ask_datahub_chat`, `get_datahub_chat`, document
search) are deliberately NOT used: this project targets DataHub OSS/Core only.
"""

from __future__ import annotations

import threading
from typing import Any

from ..config import settings

TRANSPORT = "datahub-agent-context"

_lock = threading.Lock()
_state: dict[str, Any] = {"ready": None, "error": None}


def available() -> bool:
    """True when the kit is importable and bound to our DataHub instance.

    Initialization happens once; failures are cached so a missing package or an
    unreachable GMS costs one attempt, not one per tool call.
    """
    if _state["ready"] is not None:
        return bool(_state["ready"])
    with _lock:
        if _state["ready"] is not None:
            return bool(_state["ready"])
        try:
            from datahub.sdk import DataHubClient
            from datahub_agent_context import set_client

            set_client(
                DataHubClient(
                    server=settings.datahub_gms_url,
                    token=settings.datahub_gms_token or None,
                )
            )
            _state["ready"] = True
        except Exception as e:  # package missing, bad token, GMS down
            _state["ready"] = False
            _state["error"] = f"{type(e).__name__}: {e}"
        return bool(_state["ready"])


def failure() -> str | None:
    return _state["error"]


def reset() -> None:
    """Forget cached readiness — used by tests and by demo reset."""
    with _lock:
        _state["ready"] = None
        _state["error"] = None


# --------------------------------------------------------------------- reads


def search(query: str, limit: int = 20) -> list[dict[str, Any]] | None:
    """Entity discovery through the embedded kit. None => caller should fall back."""
    if not available():
        return None
    try:
        from datahub_agent_context.mcp_tools import search as ack_search

        res = ack_search(query=query, num_results=limit)
        hits = (res or {}).get("searchResults") or []
        out = []
        for h in hits:
            ent = h.get("entity") or {}
            urn = ent.get("urn")
            if not urn:
                continue
            props = ent.get("properties") or {}
            out.append(
                {
                    "urn": urn,
                    "name": props.get("name") or _short_name(urn),
                    "platform": _platform_of(urn),
                    "description": props.get("description"),
                    "via": TRANSPORT,
                }
            )
        return out or None
    except Exception:
        return None


def schema_fields(urn: str) -> list[dict[str, Any]] | None:
    """Schema fields + documented meanings (the data contract) for a dataset."""
    if not available():
        return None
    try:
        from datahub_agent_context.mcp_tools import list_schema_fields

        res = list_schema_fields(urn=urn)
        fields = (res or {}).get("fields") or []
        return [
            {
                "field": f.get("fieldPath"),
                "type": f.get("nativeDataType"),
                "description": f.get("description"),
            }
            for f in fields
            if f.get("fieldPath")
        ] or None
    except Exception:
        return None


def lineage_hop(urn: str, upstream: bool = True) -> list[dict[str, Any]] | None:
    """One lineage hop. Returns neighbour datasets, or None to fall back."""
    if not available():
        return None
    try:
        from datahub_agent_context.mcp_tools import get_lineage

        res = get_lineage(urn=urn, upstream=upstream)
        block = (res or {}).get("upstreams" if upstream else "downstreams") or {}
        results = block.get("searchResults") or block.get("results") or []
        out = []
        for r in results:
            ent = r.get("entity") or r
            u = ent.get("urn")
            if not u or not u.startswith("urn:li:dataset:"):
                continue
            out.append({"urn": u, "name": _short_name(u), "platform": _platform_of(u)})
        return out or None
    except Exception:
        return None


# ------------------------------------------------------------------ helpers


def _short_name(urn: str) -> str:
    import re

    m = re.match(r"^urn:li:dataset:\(urn:li:dataPlatform:[^,]+,(?P<name>.+),[^,]+\)$", urn)
    return m.group("name") if m else urn


def _platform_of(urn: str) -> str:
    import re

    m = re.match(r"^urn:li:dataset:\(urn:li:dataPlatform:(?P<p>[^,]+),", urn)
    return m.group("p") if m else "unknown"
