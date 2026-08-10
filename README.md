# ◼ BlackBox — Autonomous Data Incident Response

> **Sentry for your data stack.** Tell BlackBox what looks wrong. It traces the real DataHub lineage, proves the root cause with machine-checked evidence, repairs the pipeline, verifies the fix against the full invariant suite, and writes the incident back to DataHub.

Built for **[Build with DataHub: The Agent Hackathon](https://datahub.devpost.com)** · Categories: **Agents That Do Real Work** + **Metadata-Aware Code Generation & Development** · Apache-2.0

---

## The problem

The worst data incidents don't crash anything. An upstream provider quietly changes `amount` from dollars to cents; every schema still validates, every job stays green — and the executive revenue dashboard is suddenly wrong by 100×. Humans find out days later, then spend hours spelunking through pipelines by hand.

## What BlackBox does about it

A human reports a symptom ("Revenue just jumped ~100×. Is this real?"). BlackBox then autonomously:

1. **Maps the blast radius** — finds the affected KPI via the official **DataHub MCP Server**, reads its data contract and ownership, and walks upstream lineage (table *and* column level). DataHub's graph is the map; the agent never guesses topology.
2. **Proves the root cause** — quantifies the symptom against committed baselines, forms hypotheses across every upstream branch, and eliminates them with real profiling and SQL. `confirm_root_cause` is machine-validated: *rejected* unless the agent cites DataHub lineage evidence **and** quantitative evidence naming the blamed field. No vibes-based conclusions.
3. **Repairs and verifies** — writes new transform SQL, the system computes the real diff, applies it, **rebuilds the warehouse and runs all 32 invariants + KPI recomputation**. A fix that restores the top-line while corrupting history is rejected and the agent iterates. The verified fix lands on a `blackbox/fix-*` branch.
4. **Writes the incident back to DataHub** — raised ACTIVE at confirmation, then `RESOLVED / FIXED` with the remediation record, an incident-history note on the dataset docs, and a tag. Institutional memory that outlives the incident.

In real runs: **KPI 93.3× → 0.93×, 32/32 invariants green, incident RESOLVED in DataHub.** Inspect an actual run without installing anything: [`examples/sample-incident/`](examples/sample-incident/).

![Root cause confirmed](docs/screenshots/03-rootcause.png)

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

Topology, data contracts, and the writeback target all live in DataHub. The `BLACKBOX_DISABLE_DATAHUB=true` ablation in `evals/` measures exactly what it contributes: the ablated agent loses the lineage map (falling back to reading pipeline source files — viable in this 5-transform demo, unscalable in a real estate), loses the documented contract that turns "weird numbers" into a provable contract violation, produces zero DataHub-grounded evidence citations, and cannot raise or resolve the incident. On this small fixture it can still brute-force the right diagnosis from the files — we report that honestly; what DataHub provides is the scalable map, the contract evidence, and the durable institutional memory.

| Surface | Used for | Where |
|---|---|---|
| **DataHub MCP Server** (official, `uvx mcp-server-datahub`) | agent's entity discovery + health signals | `backend/blackbox/datahub/mcp_bridge.py`, `client.py` |
| GraphQL API | dataset context, schema contracts, lineage BFS | `backend/blackbox/datahub/client.py` |
| Column-level lineage (`fineGrainedLineages`) | tracing the KPI to specific upstream fields | `client.py` (read), `ingest.py` (emit) |
| Python SDK v2 | metadata ingestion: schemas (introspected from the real warehouse), data-contract field docs, ownership, tags, table+column lineage with attached transform SQL | `backend/blackbox/datahub/ingest.py` |
| **Incidents API** (`raiseIncident` / `updateIncidentStatus`) | ACTIVE incident at root-cause confirmation → RESOLVED/FIXED after verified repair | `backend/blackbox/datahub/writeback.py` |
| Dataset docs + tags | durable remediation note + `blackbox-remediated` tag | `writeback.py` |
| DataHub Skills | development workflow (skills registry plugin) | dev environment |

**Contributed back:** building this surfaced a silent `datahub docker quickstart` hang under Colima/Rancher Desktop/Podman (docker-py reads `DOCKER_HOST` but not Docker CLI contexts). Filed upstream as a troubleshooting-docs PR: [datahub-project/datahub#19046](https://github.com/datahub-project/datahub/pull/19046). Full friction log: [`docs/DATAHUB_FEEDBACK_LOG.md`](docs/DATAHUB_FEEDBACK_LOG.md).

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

## What it would take to point this at a real stack

The demo runs on DuckDB because it has to be reproducible on a judge's laptop in one command. The engine is deliberately separated from it — three seams, no rewrite:

| Seam | Demo implementation | Production swap |
|---|---|---|
| Profiling + query execution (`backend/blackbox/warehouse.py`) | DuckDB over local CSVs | Snowflake/BigQuery/Databricks connector — same `profile_column` / `compare_to_baseline` / `run_sql` signatures |
| Verification (`repair.verify_repair`) | rebuild warehouse + 32 pytest invariants | `dbt build --select state:modified+` + `dbt test` in a CI branch or Snowflake zero-copy clone |
| Repair surface (`repair._resolve_transform`) | `pipeline/transforms/*.sql` | dbt models directory, with the existing git-worktree branch flow opening a PR |

DataHub, the agent loop, the evidence gates, and the incident writeback are unchanged by those swaps — they already speak the metadata layer a real platform team runs on. What stays honest: we demonstrate on a pipeline we authored, so treat the *incident realism* as illustrative and the *machinery* as the contribution.

## Evals

`evals/` contains a deterministic harness: seeded-incident diagnosis (graded on 11 machine-checked criteria, including that the repair restores the committed baseline to within 1% — not merely the loose KPI window), a no-incident control (healthy data must not produce an invented incident), a bad-repair rejection proof (a naive blanket fix is caught by historical-immutability invariants), and a DataHub-ablation comparison. Every conclusion is graded by deterministic code — never by an LLM judging itself. An independent adversarial review of the methodology ran during development; its critical findings (a DataHub writeback note that could contaminate later runs; a circular ablation) were fixed, and the harness now scrubs BlackBox-written DataHub state before every scenario and hard-fails on contamination. Results + full per-run artifacts live in `evals/results/`.

## Verification

Every P0 claim in this README is enumerated with runnable evidence in [`docs/ACCEPTANCE.md`](docs/ACCEPTANCE.md), including the limitations we chose to state rather than hide.

## Repo map

`pipeline/` demo data stack + invariants · `backend/blackbox/` engine + API · `frontend/` command center · `evals/` eval harness · `examples/` inspectable sample-run artifacts · `docs/` architecture, demo script, judge scorecard, hackathon requirements, progress log.

## License

Apache-2.0 — see [LICENSE](LICENSE).
