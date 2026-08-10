"""Tool layer for the investigator: deterministic implementations + anthropic tool
schemas + the evidence-gated state machine.

Every fact-producing tool automatically records an EvidenceItem carrying the raw
result, and returns its evidence_id to the model for citation. Workflow tools
(hypotheses, root cause, no-incident, repair) validate their inputs against the
recorded evidence before allowing stage transitions.
"""

from __future__ import annotations

import json
from typing import Any

from .. import repair, warehouse
from ..models import (
    EvidenceItem,
    GitArtifact,
    Hypothesis,
    IncidentStage,
    IncidentState,
    ProposedPatch,
)
from ..store import IncidentStore

MAX_RESULT_CHARS = 9000

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "datahub_search",
        "description": "Search the DataHub metadata graph for datasets/metrics by name or business meaning. Returns urns, names, descriptions.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
    {
        "name": "datahub_get_dataset",
        "description": "Fetch full DataHub context for a dataset urn: description, schema fields with documented meanings (the data contract), ownership, tags, custom properties.",
        "input_schema": {
            "type": "object",
            "properties": {"urn": {"type": "string"}},
            "required": ["urn"],
        },
    },
    {
        "name": "datahub_lineage",
        "description": "Traverse the DataHub lineage graph from an asset. Returns upstream/downstream nodes and edges (with column-level mappings where available).",
        "input_schema": {
            "type": "object",
            "properties": {
                "urn": {"type": "string"},
                "direction": {"type": "string", "enum": ["UPSTREAM", "DOWNSTREAM"]},
                "max_hops": {"type": "integer", "default": 3},
            },
            "required": ["urn", "direction"],
        },
    },
    {
        "name": "get_metric_history",
        "description": "Current value + 90-day daily history of the reported business metric, with healthy baseline overlay.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "compare_to_baseline",
        "description": "Compare recent daily revenue / median order value / order counts against the committed healthy baseline. Shows exactly when and how much metrics diverged.",
        "input_schema": {
            "type": "object",
            "properties": {"last_days": {"type": "integer", "default": 10}},
        },
    },
    {
        "name": "profile_column",
        "description": "Per-day distribution stats (count/mean/median/min/max/null-rate) for a numeric column of a warehouse table, optionally segmented by a categorical column. Table names are schema-qualified (e.g. staging.stg_orders).",
        "input_schema": {
            "type": "object",
            "properties": {
                "table": {"type": "string"},
                "column": {"type": "string"},
                "segment_by": {"type": "string"},
                "last_days": {"type": "integer", "default": 14},
            },
            "required": ["table", "column"],
        },
    },
    {
        "name": "run_sql",
        "description": "Run a single read-only SQL query (DuckDB) against the warehouse. Use for targeted checks the other tools don't cover.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
    {
        "name": "list_transforms",
        "description": "List the pipeline's SQL transformation files.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "read_transform",
        "description": "Read the SQL source of one pipeline transformation.",
        "input_schema": {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        },
    },
    {
        "name": "run_invariants",
        "description": "Run the pipeline's full data-quality invariant test suite against the current warehouse; returns pass/fail per test.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "record_hypothesis",
        "description": "Register a candidate explanation to investigate. target_urn = the DataHub urn of the suspected asset.",
        "input_schema": {
            "type": "object",
            "properties": {
                "description": {"type": "string"},
                "target_urn": {"type": "string"},
            },
            "required": ["description", "target_urn"],
        },
    },
    {
        "name": "update_hypothesis",
        "description": "Update a hypothesis after gathering evidence. Eliminating or confirming REQUIRES citing evidence_ids returned by fact tools.",
        "input_schema": {
            "type": "object",
            "properties": {
                "hypothesis_id": {"type": "string"},
                "status": {"type": "string", "enum": ["investigating", "eliminated", "confirmed"]},
                "confidence": {"type": "number"},
                "evidence_ids": {"type": "array", "items": {"type": "string"}},
                "note": {"type": "string"},
            },
            "required": ["hypothesis_id", "status", "confidence"],
        },
    },
    {
        "name": "confirm_root_cause",
        "description": "Declare the confirmed root cause. asset_urn must be the MOST UPSTREAM asset where the defect enters the pipeline (the true origin, not where it becomes visible). Requires cited evidence: at least one DataHub lineage/metadata item AND one quantitative item (profile or baseline comparison) that names the blamed field. Rejected otherwise.",
        "input_schema": {
            "type": "object",
            "properties": {
                "summary": {"type": "string", "description": "One dramatic, precise sentence."},
                "asset_urn": {"type": "string"},
                "field": {"type": "string"},
                "detail": {"type": "string", "description": "Full explanation with magnitudes and onset."},
                "evidence_ids": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["summary", "asset_urn", "field", "detail", "evidence_ids"],
        },
    },
    {
        "name": "declare_no_incident",
        "description": "Conclude the reported symptom is NOT a data incident. Requires cited quantitative evidence showing metrics within normal range.",
        "input_schema": {
            "type": "object",
            "properties": {
                "reasoning": {"type": "string"},
                "evidence_ids": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["reasoning", "evidence_ids"],
        },
    },
    {
        "name": "propose_repair",
        "description": "Propose the FULL new content of one pipeline transform file as the repair. The system computes the real diff, applies it, rebuilds the warehouse, reruns the entire invariant suite and the KPI. Iterate if verification fails.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file": {"type": "string", "description": "Repo-relative path, e.g. pipeline/transforms/stg_orders.sql"},
                "new_content": {"type": "string"},
                "reasoning": {"type": "string"},
            },
            "required": ["file", "new_content", "reasoning"],
        },
    },
    {
        "name": "finish",
        "description": "End the investigation with a final report (symptom → lineage → evidence → root cause → repair → verification), citing evidence ids.",
        "input_schema": {
            "type": "object",
            "properties": {"summary": {"type": "string"}},
            "required": ["summary"],
        },
    },
]


LAYER_BY_PREFIX = [
    ("raw_", "source"),
    ("stg_", "staging"),
    ("fct_", "marts"),
    ("dim_", "marts"),
    ("exec_", "metric"),
]


def infer_layer(name: str) -> str:
    n = name.lower().split(".")[-1]
    for prefix, layer in LAYER_BY_PREFIX:
        if n.startswith(prefix):
            return layer
    if "metric" in n or "dashboard" in n:
        return "metric"
    return "marts"


class ToolExecutor:
    def __init__(self, state: IncidentState, store: IncidentStore, allow_repair: bool = True):
        self.state = state
        self.store = store
        self.allow_repair = allow_repair
        self.finished = False

    # ------------------------------------------------------------------ utils

    def _save(self) -> None:
        self.store.save(self.state)

    def _advance(self, target: IncidentStage) -> None:
        if self.state.can_advance_to(target):
            self.state.stage = target

    # Default transport per evidence source; DataHub facts override this with the
    # concrete transport the client actually used (MCP server / ACK / GraphQL).
    _DEFAULT_TRANSPORT = {
        "warehouse": "duckdb",
        "pipeline": "pytest",
        "git": "git",
        "agent": "agent",
    }

    def _record(
        self,
        kind: str,
        source: str,
        title: str,
        detail: str,
        data: Any,
        transport: str | None = None,
    ) -> EvidenceItem:
        if transport is None:
            # DataHub clients report the transport they used as `via` on the payload.
            if isinstance(data, dict) and isinstance(data.get("via"), str):
                transport = data["via"]
            else:
                transport = self._DEFAULT_TRANSPORT.get(source)
        ev = EvidenceItem(
            kind=kind, source=source, title=title, detail=detail, data=data, transport=transport
        )
        self.state.evidence.append(ev)
        return ev

    def _set_node_status(self, urn: str, status: str, only_if: set[str] | None = None) -> None:
        node = self.state.node(urn)
        if node and (only_if is None or node.status in only_if):
            node.status = status  # type: ignore[assignment]

    def _downstream_of(self, urn: str) -> list[str]:
        out, frontier = [], [urn]
        while frontier:
            cur = frontier.pop()
            for e in self.state.edges:
                if e.source == cur and e.target not in out:
                    out.append(e.target)
                    frontier.append(e.target)
        return out

    def _result(self, payload: Any) -> str:
        s = json.dumps(payload, default=str)
        if len(s) > MAX_RESULT_CHARS:
            s = s[: MAX_RESULT_CHARS] + '... [truncated]"}'
        return s

    # --------------------------------------------------------------- dispatch

    def dispatch(self, name: str, args: dict[str, Any]) -> str:
        try:
            handler = getattr(self, f"t_{name}", None)
            if handler is None:
                return self._result({"error": f"unknown tool {name}"})
            out = handler(**args)
            self._save()
            return self._result(out)
        except Exception as e:  # surface tool errors to the model, keep investigating
            self._save()
            return self._result({"error": f"{type(e).__name__}: {e}"})

    # ---------------------------------------------------------- DataHub tools

    def _datahub_disabled(self) -> dict | None:
        from ..config import settings

        if settings.blackbox_disable_datahub:
            return {"error": "DataHub is unavailable (metadata service unreachable)"}
        return None

    def t_datahub_search(self, query: str) -> Any:
        if err := self._datahub_disabled():
            return err
        from ..datahub import client as dh

        res = dh.search(query)
        self._advance(IncidentStage.CONTEXT_DISCOVERY)
        # search returns a list; the transport is reported per-hit
        via = next((r.get("via") for r in res if isinstance(r, dict) and r.get("via")), None)
        ev = self._record(
            "metadata", "datahub", f"DataHub search: “{query}”",
            f"{len(res)} entities matched", res, transport=via,
        )
        return {"evidence_id": ev.id, "results": res}

    def t_datahub_get_dataset(self, urn: str) -> Any:
        if err := self._datahub_disabled():
            return err
        from ..datahub import client as dh

        res = dh.get_dataset(urn)
        self._advance(IncidentStage.CONTEXT_DISCOVERY)
        ev = self._record(
            "metadata", "datahub", f"DataHub context: {res.get('name', urn)}",
            "schema + contract + ownership retrieved", res,
        )
        return {"evidence_id": ev.id, "dataset": res}

    def t_datahub_lineage(self, urn: str, direction: str, max_hops: int = 3) -> Any:
        if err := self._datahub_disabled():
            return err
        from ..datahub import client as dh

        res = dh.lineage(urn, direction=direction, max_hops=max_hops)
        # merge into the incident's graph view
        known = {n.urn for n in self.state.nodes}
        for n in res["nodes"]:
            if n["urn"] not in known:
                from ..models import LineageNode

                self.state.nodes.append(
                    LineageNode(
                        urn=n["urn"], name=n["name"],
                        platform=n.get("platform", "duckdb"),
                        layer=infer_layer(n["name"]), status="investigating",
                    )
                )
                known.add(n["urn"])
        known_edges = {(e.source, e.target) for e in self.state.edges}
        for e in res["edges"]:
            if (e["source"], e["target"]) not in known_edges:
                from ..models import ColumnMapping, LineageEdge

                cols = [ColumnMapping(**c) for c in e.get("columns", [])] or None
                self.state.edges.append(LineageEdge(source=e["source"], target=e["target"], columns=cols))
        self._advance(IncidentStage.LINEAGE_TRAVERSAL)
        ev = self._record(
            "lineage", "datahub", f"Lineage {direction.lower()} of {urn.split(',')[-2] if ',' in urn else urn}",
            f"{len(res['nodes'])} nodes / {len(res['edges'])} edges from DataHub",
            res,
        )
        return {"evidence_id": ev.id, "lineage": res}

    # -------------------------------------------------------- warehouse tools

    def t_get_metric_history(self) -> Any:
        snap = warehouse.get_metric_snapshot()
        ev = self._record(
            "baseline_comparison", "warehouse", "Metric history vs baseline",
            f"KPI {snap.kpi_day}: {snap.revenue:,.0f} vs expected {snap.expected_revenue:,.0f} "
            f"(ratio {snap.anomaly_ratio:.1f}x)",
            snap.model_dump(),
        )
        return {"evidence_id": ev.id, "metric": snap.model_dump()}

    def t_compare_to_baseline(self, last_days: int = 10) -> Any:
        res = warehouse.compare_to_baseline(last_days=last_days)
        anomalous = [c["day"] for c in res["comparisons"] if c["revenue_ratio"] and c["revenue_ratio"] > 1.5]
        ev = self._record(
            "baseline_comparison", "warehouse", f"Baseline comparison (last {last_days} days)",
            f"days over 1.5x baseline: {anomalous or 'none'}", res,
        )
        self._maybe_evidence_stage()
        return {"evidence_id": ev.id, **res}

    def t_profile_column(
        self, table: str, column: str, segment_by: str | None = None, last_days: int = 14
    ) -> Any:
        res = warehouse.profile_column(table, column, segment_by=segment_by, last_days=last_days)
        seg = f" by {segment_by}" if segment_by else ""
        ev = self._record(
            "profile", "warehouse", f"Profile {table}.{column}{seg}",
            f"{len(res['days'])} day×segment rows", res,
        )
        self._maybe_evidence_stage()
        return {"evidence_id": ev.id, **res}

    def t_run_sql(self, query: str) -> Any:
        res = warehouse.run_sql(query)
        ev = self._record("sql", "warehouse", "Ad-hoc SQL", query.strip()[:200], res)
        self._maybe_evidence_stage()
        return {"evidence_id": ev.id, **res}

    def t_list_transforms(self) -> Any:
        return {"transforms": warehouse.list_transforms()}

    def t_read_transform(self, name: str) -> Any:
        res = warehouse.read_transform(name)
        ev = self._record("sql", "pipeline", f"Transform source: {res['file']}", "read", res)
        return {"evidence_id": ev.id, **res}

    def t_run_invariants(self) -> Any:
        report = warehouse.run_invariants()
        ev = self._record(
            "test", "pipeline", "Invariant suite",
            f"{report.passed}/{report.total} passed", report.model_dump(),
        )
        if self.state.tests_before is None:
            self.state.tests_before = report
        return {"evidence_id": ev.id, **report.model_dump()}

    def _maybe_evidence_stage(self) -> None:
        if self.state.hypotheses:
            self._advance(IncidentStage.EVIDENCE_COLLECTION)

    # --------------------------------------------------------- workflow tools

    def t_record_hypothesis(self, description: str, target_urn: str) -> Any:
        hyp = Hypothesis(description=description, target_urn=target_urn, status="proposed")
        self.state.hypotheses.append(hyp)
        self._advance(IncidentStage.HYPOTHESIS_GENERATION)
        self._set_node_status(target_urn, "suspicious", only_if={"healthy", "investigating"})
        return {"hypothesis_id": hyp.id}

    def t_update_hypothesis(
        self,
        hypothesis_id: str,
        status: str,
        confidence: float,
        evidence_ids: list[str] | None = None,
        note: str = "",
    ) -> Any:
        hyp = next((h for h in self.state.hypotheses if h.id == hypothesis_id), None)
        if hyp is None:
            return {"error": f"unknown hypothesis {hypothesis_id}"}
        evidence_ids = evidence_ids or []
        if status in ("eliminated", "confirmed"):
            missing = [e for e in evidence_ids if not self.state.evidence_by_id(e)]
            if not evidence_ids or missing:
                return {
                    "error": "eliminating/confirming a hypothesis requires valid evidence_ids "
                    f"(missing: {missing or 'none provided'})"
                }
        hyp.status = status  # type: ignore[assignment]
        hyp.confidence = max(0.0, min(1.0, confidence))
        hyp.evidence_ids = list(dict.fromkeys(hyp.evidence_ids + evidence_ids))
        if status == "eliminated":
            others = [h for h in self.state.hypotheses if h.target_urn == hyp.target_urn and h.id != hyp.id]
            if not any(o.status in ("proposed", "investigating", "confirmed") for o in others):
                self._set_node_status(hyp.target_urn, "healthy", only_if={"suspicious", "investigating"})
        if status == "investigating":
            self._set_node_status(hyp.target_urn, "suspicious", only_if={"healthy", "investigating"})
        return {"ok": True, "hypothesis": hyp.model_dump()}

    def t_confirm_root_cause(
        self, summary: str, asset_urn: str, field: str, detail: str, evidence_ids: list[str]
    ) -> Any:
        from ..config import settings

        cited = [self.state.evidence_by_id(e) for e in evidence_ids]
        if any(c is None for c in cited):
            return {"error": "one or more evidence_ids do not exist"}
        kinds = {c.kind for c in cited}
        sources = {c.source for c in cited}
        problems = []
        if not kinds & {"profile", "baseline_comparison"}:
            problems.append("no quantitative evidence (profile/baseline_comparison) cited")
        # DataHub-grounding requirements are relaxed when the metadata service is
        # down (ablation mode) so the gate measures evidence quality, not merely
        # DataHub availability — the ablation eval grades accuracy separately.
        if not settings.blackbox_disable_datahub:
            if "datahub" not in sources:
                problems.append("no DataHub metadata/lineage evidence cited")
            if self.state.node(asset_urn) is None:
                problems.append(
                    f"{asset_urn} is not in the traversed lineage graph — traverse lineage first"
                )
        quant = [c for c in cited if c.kind in ("profile", "baseline_comparison")]
        if quant and field:
            blob = json.dumps([c.data for c in quant], default=str).lower()
            if field.lower() not in blob:
                problems.append(
                    f"cited quantitative evidence never references field {field!r} — "
                    "profile the blamed column itself"
                )
            asset_name = asset_urn.split(",")[-2] if "," in asset_urn else asset_urn
            if asset_name.lower() not in blob:
                problems.append(
                    f"cited quantitative evidence never references the blamed asset "
                    f"{asset_name!r} — profile the blamed asset's own column"
                )
        if problems:
            return {"error": "root cause NOT accepted: " + "; ".join(problems)}
        from ..models import RootCause

        self.state.root_cause = RootCause(
            summary=summary, asset_urn=asset_urn, field=field, detail=detail, evidence_ids=evidence_ids
        )
        self._advance(IncidentStage.ROOT_CAUSE_CONFIRMED)
        self._set_node_status(asset_urn, "root_cause")
        for urn in self._downstream_of(asset_urn):
            self._set_node_status(urn, "affected", only_if={"healthy", "investigating", "suspicious"})
        for h in self.state.hypotheses:
            if h.target_urn == asset_urn and h.status != "eliminated":
                h.status = "confirmed"
                h.confidence = max(h.confidence, 0.95)
        # raise a real ACTIVE incident in DataHub the moment the cause is proven
        try:
            from ..datahub import writeback as wb_mod

            wb = wb_mod.raise_incident(self.state)
            self.state.writeback = wb
            self._record("writeback", "datahub", "DataHub incident raised (ACTIVE)", wb.detail, wb.model_dump())
        except Exception as e:
            self._record("writeback", "datahub", "DataHub incident raise failed", str(e), None)
        return {"ok": True, "message": "root cause accepted with machine-checked evidence"}

    def t_declare_no_incident(self, reasoning: str, evidence_ids: list[str]) -> Any:
        cited = [self.state.evidence_by_id(e) for e in evidence_ids]
        if any(c is None for c in cited) or not cited:
            return {"error": "declare_no_incident requires valid evidence_ids"}
        if not {c.kind for c in cited} & {"baseline_comparison", "profile"}:
            return {"error": "cite quantitative evidence (baseline comparison / profile) showing normal ranges"}
        self.state.stage = IncidentStage.NO_INCIDENT
        self.state.final_summary = reasoning
        for n in self.state.nodes:
            if n.status in ("investigating", "suspicious"):
                n.status = "healthy"
        self.finished = True
        return {"ok": True}

    def t_propose_repair(self, file: str, new_content: str, reasoning: str) -> Any:
        if self.state.root_cause is None:
            return {"error": "confirm_root_cause before proposing a repair"}
        if not self.allow_repair:
            return {
                "error": "repair phase not yet authorized by the operator — summarize the confirmed "
                "root cause with finish(...); the repair will be launched as a separate phase"
            }
        patch = repair.propose_patch(file, new_content, reasoning)
        self.state.patch = patch
        self._advance(IncidentStage.REPAIR_GENERATED)
        self._record("patch", "git", f"Patch proposed: {file}", reasoning[:300], {"diff": patch.diff})
        self._save()

        repair.apply_patch(patch, new_content)
        self._advance(IncidentStage.REPAIR_TESTING)
        patch.status = "testing"
        self._save()

        report, snapshot, ok = repair.verify_repair()
        self.state.tests_after = report
        self.state.metric_after = snapshot
        self._record(
            "test", "pipeline", "Post-repair verification",
            f"{report.passed}/{report.total} tests passed; KPI ratio {snapshot.anomaly_ratio:.2f}x",
            {"tests": report.model_dump(), "metric": snapshot.model_dump()},
        )
        if not ok:
            patch.status = "applied"
            return {
                "verified": False,
                "tests": report.model_dump(),
                "kpi_anomaly_ratio": snapshot.anomaly_ratio,
                "message": "verification FAILED — analyze the failures and propose a better repair",
            }

        patch.status = "verified"
        self._advance(IncidentStage.VERIFIED)
        rc_urn = self.state.root_cause.asset_urn
        self._set_node_status(rc_urn, "repaired")
        for urn in self._downstream_of(rc_urn):
            self._set_node_status(urn, "healthy", only_if={"affected", "suspicious", "investigating"})
        # real git artifact
        try:
            artifact = repair.make_git_artifact(
                patch, self.state.id, self.state.root_cause.summary[:70]
            )
            self.state.git_artifact = artifact
            self._record(
                "patch", "git", f"Fix committed on branch {artifact.branch}",
                artifact.diff_stat, artifact.model_dump(),
            )
        except Exception as e:
            self._record("patch", "git", "Git artifact creation failed", str(e), None)
        # Optional, opt-in (BLACKBOX_CREATE_PR): publish the verified fix as a real
        # GitHub PR. This runs strictly AFTER verification and is fully isolated —
        # any failure becomes an evidence item and the incident stays VERIFIED.
        if self.state.git_artifact is not None:
            try:
                pr = repair.publish_repair_pr(self.state, self.state.git_artifact)
                if pr.get("status") != "disabled":
                    self._record("patch", "git", pr["title"], pr["detail"], pr)
            except Exception as e:  # defence in depth: publish_repair_pr never raises
                self._record(
                    "patch", "git", "PR publication failed", f"{type(e).__name__}: {e}", None
                )
        self._save()
        # durable writeback into DataHub
        try:
            from ..datahub import writeback

            wb = writeback.resolve_incident(self.state)
            self.state.writeback = wb
            self._record("writeback", "datahub", "DataHub writeback", wb.detail, wb.model_dump())
            if wb.status == "complete":
                self._advance(IncidentStage.WRITEBACK_COMPLETE)
        except Exception as e:
            from ..models import Writeback

            self.state.writeback = Writeback(status="failed", detail=str(e))
        return {
            "verified": True,
            "tests": report.model_dump(),
            "kpi_anomaly_ratio": snapshot.anomaly_ratio,
            "git": self.state.git_artifact.model_dump() if self.state.git_artifact else None,
            "writeback": self.state.writeback.model_dump() if self.state.writeback else None,
            "message": "repair verified end-to-end — call finish with the final report",
        }

    def t_finish(self, summary: str) -> Any:
        self.state.final_summary = summary
        self.finished = True
        return {"ok": True}
