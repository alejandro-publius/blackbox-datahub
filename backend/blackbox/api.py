"""BlackBox API — serves the command-center frontend.

Run: uv run uvicorn blackbox.api:app --port 8400 --app-dir backend
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import threading

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from . import warehouse
from .agent.investigator import run_investigation, run_repair_phase
from .agent.tools import infer_layer
from .config import REPO_ROOT, settings
from .models import IncidentStage, IncidentState, LineageEdge, LineageNode
from .store import store

app = FastAPI(title="BlackBox", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def _bind_loop() -> None:
    store.bind_loop(asyncio.get_running_loop())


# ------------------------------------------------------------------ health


@app.get("/api/health")
def health() -> dict:
    warehouse_ready = settings.warehouse_path.exists() and settings.metric_snapshot_path.exists()
    from .datahub import client as dh

    return {
        "status": "ok",
        "warehouse_ready": warehouse_ready,
        "datahub_connected": dh.ping(),
        "anthropic_configured": bool(settings.anthropic_api_key),
    }


# ------------------------------------------------------------------ metrics


@app.get("/api/metrics/snapshot")
def metrics_snapshot() -> dict:
    try:
        return warehouse.get_metric_snapshot().model_dump()
    except FileNotFoundError:
        raise HTTPException(503, "warehouse not built — run `make demo-reset`")


# ------------------------------------------------------------------ lineage


@app.get("/api/lineage/graph")
def lineage_graph() -> dict:
    """The real pipeline graph as DataHub knows it (upstream of the KPI)."""
    from .datahub import client as dh
    from .datahub.ingest import dataset_urn

    if not dh.ping():
        raise HTTPException(503, "DataHub is not reachable — start it with `datahub docker quickstart`")
    metric_urn = dataset_urn("marts.exec_revenue_metric")
    lin = dh.lineage(metric_urn, direction="UPSTREAM", max_hops=4)
    try:
        anomalous = warehouse.get_metric_snapshot().status == "anomalous"
    except Exception:
        anomalous = False
    nodes = []
    for n in lin["nodes"]:
        status = "affected" if (anomalous and n["urn"] == metric_urn) else "healthy"
        nodes.append(
            LineageNode(
                urn=n["urn"], name=n["name"], platform=n.get("platform") or "duckdb",
                layer=infer_layer(n["name"]), status=status,
            ).model_dump()
        )
    edges = [
        LineageEdge(source=e["source"], target=e["target"], columns=e.get("columns") or None).model_dump()
        for e in lin["edges"]
    ]
    return {"nodes": nodes, "edges": edges}


# ---------------------------------------------------------------- incidents


class ReportIn(BaseModel):
    report_text: str


@app.post("/api/incidents")
def create_incident(body: ReportIn) -> dict:
    if not settings.anthropic_api_key:
        raise HTTPException(503, "ANTHROPIC_API_KEY is not configured — set it in .env")
    state = IncidentState(report_text=body.report_text.strip())
    store.save(state)
    threading.Thread(
        target=run_investigation, args=(state.id, store), kwargs={"pause_before_repair": True},
        daemon=True, name=f"investigate-{state.id}",
    ).start()
    return {"incident_id": state.id}


@app.get("/api/incidents")
def list_incidents() -> list[dict]:
    out = []
    for iid in store.list_ids():
        s = store.get(iid)
        if s:
            out.append({"id": s.id, "stage": s.stage, "report_text": s.report_text, "created_at": s.created_at})
    return sorted(out, key=lambda x: x["created_at"], reverse=True)


@app.get("/api/incidents/{incident_id}")
def get_incident(incident_id: str) -> dict:
    state = store.get(incident_id)
    if state is None:
        raise HTTPException(404, "unknown incident")
    return state.model_dump()


@app.post("/api/incidents/{incident_id}/repair")
def start_repair(incident_id: str) -> dict:
    state = store.get(incident_id)
    if state is None:
        raise HTTPException(404, "unknown incident")
    if state.root_cause is None or state.stage != IncidentStage.ROOT_CAUSE_CONFIRMED:
        raise HTTPException(409, f"incident is in stage {state.stage}; repair needs a confirmed root cause")
    threading.Thread(
        target=run_repair_phase, args=(incident_id, store), daemon=True, name=f"repair-{incident_id}",
    ).start()
    return {"ok": True}


@app.get("/api/incidents/{incident_id}/events")
async def incident_events(incident_id: str) -> EventSourceResponse:
    state = store.get(incident_id)
    if state is None:
        raise HTTPException(404, "unknown incident")
    queue = store.subscribe(incident_id)

    async def gen():
        try:
            yield {"event": "state", "data": state.model_dump_json()}
            while True:
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=15)
                    yield {"event": "state", "data": payload}
                except asyncio.TimeoutError:
                    yield {"event": "ping", "data": "{}"}
        finally:
            store.unsubscribe(incident_id, queue)

    return EventSourceResponse(gen())


# --------------------------------------------------------------------- demo


@app.post("/api/demo/reset")
def demo_reset() -> dict:
    """Return the whole demo to the exact broken initial state (idempotent)."""
    steps: list[str] = []
    # 1. restore any patched transforms
    subprocess.run(["git", "checkout", "--", "pipeline/transforms/"], cwd=REPO_ROOT, check=False)
    for orig in settings.transforms_dir.glob("*.sql.orig"):
        orig.unlink()
    steps.append("transforms restored")
    # 2. regenerate incident-mode sources + rebuild warehouse
    for cmd in (
        ["uv", "run", "python", "pipeline/generate_sources.py", "--mode", "incident"],
        ["uv", "run", "python", "pipeline/run.py"],
    ):
        proc = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True, timeout=300)
        if proc.returncode != 0:
            raise HTTPException(500, f"reset step failed: {' '.join(cmd)}: {proc.stderr[-500:]}")
    steps.append("incident data regenerated + warehouse rebuilt")
    # 3. clear incident records
    n = store.clear_all()
    steps.append(f"{n} incident record(s) cleared")
    # 4. drop old fix branches
    branches = subprocess.run(
        ["git", "branch", "--list", "blackbox/fix-*", "--format=%(refname:short)"],
        cwd=REPO_ROOT, capture_output=True, text=True,
    ).stdout.split()
    for b in branches:
        subprocess.run(["git", "branch", "-D", b], cwd=REPO_ROOT, capture_output=True)
    if branches:
        steps.append(f"dropped {len(branches)} fix branch(es)")
    # 5. scrub BlackBox-written DataHub state (incident notes / tags / ACTIVE
    #    incidents) — a leftover remediation note is the next run's answer key
    try:
        from .datahub.reset import reset_blackbox_state

        scrub = reset_blackbox_state()
        steps.append(f"DataHub scrubbed: {scrub}")
    except Exception as e:
        steps.append(f"DataHub scrub skipped ({type(e).__name__})")
    # 6. re-sync DataHub metadata (transform SQL text reverted; idempotent upserts)
    try:
        from .datahub import ingest as dh_ingest

        dh_ingest.ingest()
        steps.append("DataHub metadata re-synced")
    except Exception as e:
        steps.append(f"DataHub re-sync skipped ({type(e).__name__})")
    return {"ok": True, "steps": steps}
