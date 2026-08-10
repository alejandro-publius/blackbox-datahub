# ◼ BlackBox — Autonomous Data Incident Response

> **Sentry for your data stack.** Tell BlackBox what looks wrong. It traces the real DataHub lineage, proves the root cause with machine-checked evidence, repairs the pipeline, verifies the fix against the full invariant suite, and writes the incident back to DataHub.

Built for **[Build with DataHub: The Agent Hackathon](https://datahub.devpost.com)** · Categories: **Agents That Do Real Work** + **Metadata-Aware Code Generation & Development** · Apache-2.0

---

## The problem

The worst data incidents don't crash anything. An upstream provider quietly changes `amount` from dollars to cents; every schema still validates, every job stays green — and the executive revenue dashboard is suddenly wrong by 100×. Humans find out days later, then spend hours spelunking through pipelines by hand.

## What BlackBox does about it

A human reports a symptom ("Revenue just jumped ~100×. Is this real?"). BlackBox then autonomously:

1. **Finds the affected asset** in DataHub (search via the official **DataHub MCP Server**) and reads its context: descriptions, ownership, and the **data contract in schema field docs**.
2. **Walks upstream lineage** — table-level *and column-level* — from the corrupted KPI. The lineage graph in DataHub is the map; the agent never guesses topology.
3. **Quantifies the symptom** against committed healthy baselines (onset date, magnitude) and **forms hypotheses** covering every upstream branch.
4. **Collects real evidence** with deterministic tools — per-day/per-segment distribution profiling, read-only SQL, invariant runs — and **eliminates distractors quantitatively** (e.g. a stale FX feed that looks suspicious but is orders of magnitude too small).
5. **Proves the root cause.** `confirm_root_cause` is machine-validated: it is *rejected* unless the agent cites DataHub lineage evidence **and** quantitative evidence naming the blamed field. No vibes-based conclusions.
6. **Raises a real ACTIVE incident in DataHub** on the affected assets the moment the cause is proven.
7. **Repairs the pipeline**: proposes new transform SQL, the system computes the real diff, applies it, **rebuilds the warehouse and runs all 32 invariants + KPI recomputation**. A fix that restores the top-line while breaking history is rejected; the agent iterates.
8. **Commits the verified fix** on a `blackbox/fix-*` branch (isolated git worktree) — a PR-ready artifact.
9. **Resolves the DataHub incident** (`RESOLVED / FIXED` with the full remediation record), appends an incident-history note to the dataset docs, and tags it — durable institutional memory in the catalog.

In real runs: **KPI 93.3× → 0.93×, 32/32 invariants green, incident RESOLVED in DataHub.** Inspect an actual run without installing anything: [`examples/sample-incident/`](examples/sample-incident/).

## Detect → investigate → evidence → root cause → repair → execute → verify → artifact → writeback

Not a chatbot. Every number, edge, diff, and test result in the UI is real output of real execution (DuckDB, DataHub GraphQL/MCP, pytest, difflib, git). The demo *scenario* is synthetic and deterministic — the *analysis* of it is not.

## Quickstart

Prereqs: Docker (≥8GB RAM allocated), Python 3.11+ via [uv](https://docs.astral.sh/uv/), Node 20+, the DataHub CLI (`uv tool install acryl-datahub`), an Anthropic API key.

```bash
git clone https://github.com/alejandro-publius/blackbox-datahub && cd blackbox-datahub
make setup                       # uv sync + npm install
make datahub-up                  # DataHub OSS quickstart v1.7.0 (UI :9002, GMS :8080)
make datahub-setup               # mint PAT → .env, ingest pipeline metadata, verify round-trip
echo 'ANTHROPIC_API_KEY=sk-ant-...' >> .env
make demo-reset                  # seed the broken state (revenue silently ~93x too high)
make demo-run                    # backend :8400 + frontend :3000
```

Open http://localhost:3000 → **Investigate Incident**. Colima users: `export DOCKER_HOST="unix://$HOME/.colima/default/docker.sock"` first (see `docs/DATAHUB_FEEDBACK_LOG.md` — we hit this ourselves).

Verify everything without the UI:

```bash
make test                        # 32 pipeline invariants (incident mode fails exactly 7 — by design)
uv run pytest tests/             # 13 unit tests on the evidence gates
uv run python scripts/vertical_slice.py   # full autonomous run in the terminal
make evals                       # eval battery (see evals/README.md)
```

## How DataHub is load-bearing

BlackBox does not work without DataHub — topology, contracts, and the writeback target all live there (the `BLACKBOX_DISABLE_DATAHUB=true` ablation in `evals/` demonstrates it).

| Surface | Used for | Where |
|---|---|---|
| **DataHub MCP Server** (official, `uvx mcp-server-datahub`) | agent's entity discovery + health signals | `backend/blackbox/datahub/mcp_bridge.py`, `client.py` |
| GraphQL API | dataset context, schema contracts, lineage BFS | `backend/blackbox/datahub/client.py` |
| Column-level lineage (`fineGrainedLineages`) | tracing the KPI to specific upstream fields | `client.py` (read), `ingest.py` (emit) |
| Python SDK v2 | metadata ingestion: schemas (introspected from the real warehouse), data-contract field docs, ownership, tags, table+column lineage with attached transform SQL | `backend/blackbox/datahub/ingest.py` |
| **Incidents API** (`raiseIncident` / `updateIncidentStatus`) | ACTIVE incident at root-cause confirmation → RESOLVED/FIXED after verified repair | `backend/blackbox/datahub/writeback.py` |
| Dataset docs + tags | durable remediation note + `blackbox-remediated` tag | `writeback.py` |
| DataHub Skills | development workflow (skills registry plugin) | dev environment |

## Architecture

Full design — state machine, evidence gating, repair verification loop — in **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**.

```
Next.js command center ── SSE ── FastAPI ── Investigator (Claude, tool loop)
                                              │  facts only via deterministic tools:
                                              ├─ DataHub (MCP Server + GraphQL + SDK): search, contracts, lineage, writeback
                                              ├─ DuckDB warehouse: profiling, baselines, read-only SQL
                                              ├─ pytest: 32 pipeline invariants
                                              └─ git: real diffs, fix branches (isolated worktree)
```

## What's real vs. synthetic (full disclosure)

- **Synthetic (disclosed):** the retail pipeline's source data is generated deterministically (`pipeline/generate_sources.py`, seed 42), including the seeded incident — a payment-provider migration that silently switches `raw_orders.amount` from dollars to integer cents on 2026-08-07 — and a stale-FX distractor. `make demo-reset` restores this exact broken state.
- **Real:** the DuckDB warehouse and SQL transforms execute; DataHub OSS v1.7.0 runs locally with genuinely ingested metadata; the agent's every fact comes from live tool calls; the diff, tests, KPI recomputation, git branch, and DataHub incident are all real. Nothing in prompts or metadata names the incident's nature — the agent discovers it from evidence (see `CLAUDE.md`, "No incident leakage").

## Evals

`evals/` contains a deterministic harness: seeded-incident diagnosis, a no-incident control (healthy data must not produce an invented incident), a bad-repair rejection proof (a naive blanket fix is caught by historical-immutability invariants), and a DataHub-ablation run. Results live in `evals/results/`.

## Repo map

`pipeline/` demo data stack + invariants · `backend/blackbox/` engine + API · `frontend/` command center · `evals/` eval harness · `examples/` inspectable sample-run artifacts · `docs/` architecture, demo script, judge scorecard, hackathon requirements, progress log.

## License

Apache-2.0 — see [LICENSE](LICENSE).
