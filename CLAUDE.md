# BlackBox — repo guide for AI agents

Autonomous data incident response on DataHub (hackathon project). An evidence-gated Claude agent investigates a silent semantic data failure using real DataHub lineage/contracts, repairs the pipeline, verifies with the invariant suite, and writes the incident back to DataHub. Architecture: `docs/ARCHITECTURE.md`. Fixture details: `pipeline/README.md`.

## Layout

- `backend/blackbox/` — FastAPI app (`api.py`, port 8400), domain models (`models.py`), incident store (`store.py`), deterministic warehouse ops (`warehouse.py`), repair engine (`repair.py`), config (`config.py`).
  - `agent/` — Claude tool loop (`investigator.py`), tool implementations + evidence gates (`tools.py`), system prompt (`prompts.py`).
  - `datahub/` — SDK ingestion (`ingest.py`), GraphQL read client (`client.py`), incident/docs/tag writeback (`writeback.py`).
- `pipeline/` — deterministic DuckDB demo fixture: `generate_sources.py` (seeded incident), `run.py` (build), `transforms/*.sql`, `baselines/` (committed healthy record), `invariants/` (32 pytest tests).
- `frontend/` — Next.js 16 command center. Has its own `CLAUDE.md`/`AGENTS.md` — read them before frontend work.
- `data/` — generated warehouse + incident records (mostly gitignored; do not hand-edit).
- `docs/` — hackathon requirements, progress log, architecture, demo script, judge scorecard.

## Commands

```bash
make setup          # uv sync
make demo-reset     # seed INCIDENT fixture + rebuild warehouse (the demo's ground state)
make demo-healthy   # seed healthy fixture + rebuild
make build          # rebuild warehouse from existing CSVs
make test           # run the 32 pipeline invariants (incident mode fails exactly 7)
make baselines      # regenerate committed baselines (temp dir; never clobbers data/)

uv run uvicorn blackbox.api:app --port 8400 --app-dir backend   # backend
uv run python -m blackbox.datahub.ingest                        # push metadata to DataHub
cd frontend && npm run dev                                      # frontend on :3000
datahub docker quickstart                                       # DataHub OSS (UI :9002, GMS :8080)
```

## Conventions (load-bearing — do not break)

- **Types contract:** `backend/blackbox/models.py` and `frontend/src/lib/types.ts` mirror each other EXACTLY. Change both together or neither.
- **Facts vs hypotheses:** `EvidenceItem`s are produced only by deterministic tool code — never free-typed by the LLM. Hypotheses/root causes must cite evidence ids; `confirm_root_cause` is machine-validated (`agent/tools.py`). Do not weaken these gates.
- **No fabricated data:** every number/edge/diff shown in the UI must be real output of real execution (DuckDB, DataHub GraphQL, pytest, difflib, git). The scenario is synthetic and disclosed; the execution is not. Frontend placeholder fixtures may only render behind `?preview=` with the PREVIEW watermark.
- **No incident leakage:** nothing in prompts, metadata docs, or invariants may name the seeded incident's nature (cents-vs-dollars / cloudpay_v2 as the culprit). The agent must discover it from data. `pipeline/generate_sources.py` is the only place that knows.
- **Repairs** may only touch `pipeline/transforms/*.sql` (enforced in `repair.py`); verification = full warehouse rebuild + all 32 invariants green + KPI anomaly ratio in [0.8, 1.3].
- **Determinism:** the fixture is byte-identical per run (pinned ANCHOR_DAY 2026-08-09, seed 42, no wall clock). Don't introduce wall-clock or nondeterminism into `pipeline/`.
- `pipeline/baselines/*.json` are committed healthy references — regenerate only via `make baselines`, never edit by hand.

## Environment (.env at repo root; see .env.example)

- `ANTHROPIC_API_KEY` (required for investigations), `ANTHROPIC_MODEL` (default `claude-opus-5`)
- `DATAHUB_GMS_URL` (default `http://localhost:8080`), `DATAHUB_GMS_TOKEN` (optional)
- `BLACKBOX_DISABLE_DATAHUB=true` — ablation: DataHub tools return errors (for evals)
- `BLACKBOX_CREATE_PR=true` — after a VERIFIED repair, push the `blackbox/fix-*` branch and open a real PR via `gh`. **Default false**; the demo and evals must never push to a remote. Requires `gh auth`. Caveat: `demo/reset` only deletes *local* fix branches, so an opened PR/remote branch needs manual cleanup.
- `BLACKBOX_API_PORT` (default 8400); frontend: `NEXT_PUBLIC_BLACKBOX_API_URL`
- Never commit `.env`.

## Demo-reset contract

`POST /api/demo/reset` (or `make demo-reset` + re-ingest) must return the system to the exact broken initial state, idempotently: transforms restored from git (+ `.sql.orig` backups removed), incident-mode sources regenerated, warehouse rebuilt, incident records cleared, `blackbox/fix-*` branches deleted, DataHub metadata re-synced. Anything you add that mutates state during a run must be covered by this reset.
