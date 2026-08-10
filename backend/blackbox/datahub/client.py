"""Read-side DataHub client used by the investigator's tools.

All lineage/metadata facts shown in the product come from these calls against a
real self-hosted DataHub OSS instance (GraphQL on GMS :8080 + aspect reads for
column-level lineage). Nothing here is fabricated.
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Any

import httpx

from ..config import settings


@lru_cache(maxsize=1)
def _graph():
    from datahub.ingestion.graph.client import DataHubGraph, DatahubClientConfig

    return DataHubGraph(
        DatahubClientConfig(
            server=settings.datahub_gms_url,
            token=settings.datahub_gms_token or None,
        )
    )


def ping() -> bool:
    try:
        r = httpx.get(f"{settings.datahub_gms_url}/health", timeout=5)
        return r.status_code == 200
    except Exception:
        return False


# --------------------------------------------------------------------- search

_SEARCH_QUERY = """
query search($q: String!) {
  searchAcrossEntities(input: {types: [DATASET], query: $q, start: 0, count: 20,
                               searchFlags: {skipAggregates: true, skipHighlighting: true}}) {
    searchResults {
      entity {
        urn
        type
        ... on Dataset {
          name
          platform { name }
          properties { name description }
        }
      }
    }
  }
}
"""


def search(query: str) -> list[dict[str, Any]]:
    """Entity discovery. Routed through the official DataHub MCP Server when
    available (BlackBox is a real MCP client of DataHub's agent surface); falls
    back to direct GraphQL so MCP is additive, never a point of failure."""
    try:
        from .mcp_bridge import bridge

        if bridge.available:
            res = bridge.call_tool("search", {"query": query})
            hits = res.get("searchResults", []) if isinstance(res, dict) else []
            out = []
            for h in hits:
                e = h.get("entity") or {}
                urn = e.get("urn")
                if not urn:
                    continue
                props = e.get("properties") or {}
                out.append(
                    {
                        "urn": urn,
                        "name": props.get("name") or _short_name(urn),
                        "platform": _platform_of(urn),
                        "description": props.get("description"),
                        "via": "datahub-mcp-server",
                    }
                )
            if out:
                return out
    except Exception:
        pass  # fall through to GraphQL

    res = _graph().execute_graphql(_SEARCH_QUERY, variables={"q": query})
    out = []
    for hit in res["searchAcrossEntities"]["searchResults"]:
        e = hit["entity"]
        props = e.get("properties") or {}
        out.append(
            {
                "urn": e["urn"],
                "name": props.get("name") or e.get("name"),
                "platform": (e.get("platform") or {}).get("name"),
                "description": props.get("description"),
                "via": "datahub-graphql",
            }
        )
    return out


# -------------------------------------------------------------------- dataset

_DATASET_QUERY = """
query getDataset($urn: String!) {
  dataset(urn: $urn) {
    urn
    name
    platform { name }
    properties { name description customProperties { key value } }
    editableProperties { description }
    schemaMetadata {
      fields { fieldPath nativeDataType description }
    }
    editableSchemaMetadata {
      editableSchemaFieldInfo { fieldPath description }
    }
    ownership {
      owners {
        type
        owner {
          ... on CorpUser { urn username properties { displayName } }
          ... on CorpGroup { urn name }
        }
      }
    }
    tags { tags { tag { urn name } } }
    domain { domain { urn properties { name } } }
  }
}
"""


def get_dataset(urn: str) -> dict[str, Any]:
    res = _graph().execute_graphql(_DATASET_QUERY, variables={"urn": urn})
    d = res.get("dataset")
    if d is None:
        raise ValueError(f"dataset not found in DataHub: {urn}")
    props = d.get("properties") or {}
    editable_fields = {
        f["fieldPath"]: f.get("description")
        for f in ((d.get("editableSchemaMetadata") or {}).get("editableSchemaFieldInfo") or [])
    }
    fields = []
    for f in ((d.get("schemaMetadata") or {}).get("fields") or []):
        fields.append(
            {
                "field": f["fieldPath"],
                "type": f.get("nativeDataType"),
                "description": editable_fields.get(f["fieldPath"]) or f.get("description"),
            }
        )
    owners = []
    for o in ((d.get("ownership") or {}).get("owners") or []):
        ow = o.get("owner") or {}
        owners.append(
            {
                "urn": ow.get("urn"),
                "name": ((ow.get("properties") or {}).get("displayName")) or ow.get("username") or ow.get("name"),
                "type": o.get("type"),
            }
        )
    description = ((d.get("editableProperties") or {}).get("description")) or props.get("description")
    result = {
        "urn": d["urn"],
        "name": props.get("name") or d.get("name"),
        "platform": (d.get("platform") or {}).get("name"),
        "description": description,
        "custom_properties": {p["key"]: p["value"] for p in (props.get("customProperties") or [])},
        "schema_fields": fields,
        "owners": owners,
        "tags": [t["tag"]["name"] for t in ((d.get("tags") or {}).get("tags") or [])],
        "domain": ((d.get("domain") or {}).get("domain") or {}).get("urn"),
        "via": "datahub-graphql",
    }
    # enrich with health signals from the DataHub MCP Server (best-effort)
    try:
        from .mcp_bridge import bridge

        if bridge.available:
            ents = bridge.call_tool("get_entities", {"urns": [urn]})
            if isinstance(ents, list) and ents and isinstance(ents[0], dict):
                health = ents[0].get("health")
                if health:
                    result["health"] = health
                result["via"] = "datahub-mcp-server+graphql"
    except Exception:
        pass
    return result


# -------------------------------------------------------------------- lineage

_LINEAGE_QUERY = """
query lineage($urn: String!, $direction: LineageDirection!) {
  dataset(urn: $urn) {
    lineage(input: {direction: $direction, start: 0, count: 100}) {
      relationships {
        degree
        entity {
          urn
          type
          ... on Dataset { name platform { name } }
        }
      }
    }
  }
}
"""

_FIELD_URN_RE = re.compile(r"^urn:li:schemaField:\((?P<dataset>.+),(?P<field>[^,]+)\)$")


def _parse_field_urn(furn: str) -> tuple[str, str] | None:
    m = _FIELD_URN_RE.match(furn)
    if not m:
        return None
    return m.group("dataset"), m.group("field")


def _column_lineage_for(downstream_urn: str) -> dict[str, list[dict[str, str]]]:
    """Column mappings keyed by upstream dataset urn, read from the real
    UpstreamLineage aspect (fineGrainedLineages)."""
    from datahub.metadata.schema_classes import UpstreamLineageClass

    aspect = _graph().get_aspect(downstream_urn, UpstreamLineageClass)
    out: dict[str, list[dict[str, str]]] = {}
    if aspect is None or not aspect.fineGrainedLineages:
        return out
    for fgl in aspect.fineGrainedLineages:
        for up in fgl.upstreams or []:
            up_parsed = _parse_field_urn(up)
            if not up_parsed:
                continue
            up_ds, up_field = up_parsed
            for down in fgl.downstreams or []:
                down_parsed = _parse_field_urn(down)
                if not down_parsed:
                    continue
                _, down_field = down_parsed
                out.setdefault(up_ds, []).append({"upstream": up_field, "downstream": down_field})
    return out


def _mcp_hop(urn: str, direction: str) -> list[dict[str, Any]] | None:
    """One lineage hop via the official DataHub MCP Server. Returns None if the
    MCP server is unavailable so the caller can fall back to GraphQL."""
    try:
        from .mcp_bridge import bridge

        if not bridge.available:
            return None
        res = bridge.call_tool(
            "get_lineage", {"urn": urn, "upstream": direction == "UPSTREAM"}
        )
        if not isinstance(res, dict):
            return None
        block = res.get("upstreams" if direction == "UPSTREAM" else "downstreams") or {}
        results = block.get("searchResults") or block.get("results") or []
        out = []
        for r in results:
            ent = r.get("entity") or r
            u = ent.get("urn")
            if not u or not u.startswith("urn:li:dataset:"):
                continue
            out.append({"urn": u, "name": _short_name(u), "platform": _platform_of(u)})
        return out
    except Exception:
        return None


def lineage(urn: str, direction: str = "UPSTREAM", max_hops: int = 3) -> dict[str, Any]:
    """BFS over DataHub lineage, one hop at a time, collecting nodes, edges and
    column-level mappings. Each hop is served by the official DataHub MCP Server
    when available, falling back to GraphQL."""
    direction = direction.upper()
    if direction not in ("UPSTREAM", "DOWNSTREAM"):
        raise ValueError("direction must be UPSTREAM or DOWNSTREAM")
    transports: set[str] = set()

    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []
    seen_edges: set[tuple[str, str]] = set()

    def note_node(u: str, name: str | None = None, platform: str | None = None) -> None:
        if u not in nodes:
            nodes[u] = {"urn": u, "name": name or _short_name(u), "platform": platform or "duckdb"}
        else:
            if name:
                nodes[u]["name"] = name
            if platform:
                nodes[u]["platform"] = platform

    note_node(urn)
    frontier = [urn]
    for _hop in range(max_hops):
        next_frontier: list[str] = []
        for cur in frontier:
            neighbours = _mcp_hop(cur, direction)
            if neighbours is not None:
                transports.add("datahub-mcp-server")
            else:
                transports.add("datahub-graphql")
                res = _graph().execute_graphql(
                    _LINEAGE_QUERY, variables={"urn": cur, "direction": direction}
                )
                ds = res.get("dataset")
                if ds is None:
                    continue
                rels = ((ds.get("lineage") or {}).get("relationships")) or []
                neighbours = [
                    {
                        "urn": rel["entity"]["urn"],
                        "name": rel["entity"].get("name"),
                        "platform": (rel["entity"].get("platform") or {}).get("name"),
                    }
                    for rel in rels
                    if rel.get("degree", 1) == 1 and rel["entity"].get("type") == "DATASET"
                ]
            for n in neighbours:
                note_node(n["urn"], n.get("name"), n.get("platform"))
                edge = (n["urn"], cur) if direction == "UPSTREAM" else (cur, n["urn"])
                if edge not in seen_edges:
                    seen_edges.add(edge)
                    edges.append({"source": edge[0], "target": edge[1], "columns": []})
                if n["urn"] not in next_frontier:
                    next_frontier.append(n["urn"])
        frontier = [u for u in dict.fromkeys(next_frontier)]
        if not frontier:
            break

    # attach real column-level lineage per edge
    for target_urn in {e["target"] for e in edges}:
        try:
            col_map = _column_lineage_for(target_urn)
        except Exception:
            col_map = {}
        for e in edges:
            if e["target"] == target_urn and e["source"] in col_map:
                e["columns"] = col_map[e["source"]]

    return {
        "root": urn,
        "direction": direction,
        "nodes": list(nodes.values()),
        "edges": edges,
        "via": "+".join(sorted(transports)) or "datahub-graphql",
    }


def _short_name(urn: str) -> str:
    # urn:li:dataset:(urn:li:dataPlatform:duckdb,marts.fct_revenue,PROD) -> marts.fct_revenue
    m = re.match(r"^urn:li:dataset:\(urn:li:dataPlatform:[^,]+,(?P<name>.+),[^,]+\)$", urn)
    return m.group("name") if m else urn


def _platform_of(urn: str) -> str:
    m = re.match(r"^urn:li:dataset:\(urn:li:dataPlatform:(?P<p>[^,]+),", urn)
    return m.group("p") if m else "unknown"
