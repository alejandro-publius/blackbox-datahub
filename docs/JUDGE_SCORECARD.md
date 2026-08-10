# BlackBox — Judge Scorecard (living gap analysis)

Self-assessment against the official criteria in `docs/HACKATHON_REQUIREMENTS.md`. The **weakness** column is deliberately critical — it is the work queue, not marketing. Updated 2026-08-09.

> **Stage One viability note — RESOLVED 2026-08-10:** the rules require the OSS platform **plus at least one of** MCP Server, Agent Context Kit, DataHub Skills, or Analytics Agent. BlackBox now runs the **official DataHub MCP Server** (`uvx mcp-server-datahub`) inside the product as the investigator's discovery transport (`backend/blackbox/datahub/mcp_bridge.py`; search + entity health run through it, with GraphQL fallback so it's additive, not fragile), and the DataHub Skills registry plugin is part of the dev workflow. Evidence: `examples/sample-incident/incident_state.json` search evidence carries `"via": "datahub-mcp-server"`.

---

## 1. Use of DataHub

| | |
|---|---|
| **What BlackBox does** | DataHub is used in both directions. Reads: MCP-Server search + entity context, dataset context (schema + field-level data contracts + ownership + tags), lineage BFS with **column-level lineage from real `fineGrainedLineages` aspects**. Writes: SDK-v2 ingestion of introspected schemas + table/column lineage with real transform SQL attached; native OSS **incident** raise/resolve; docs remediation note; `blackbox-remediated` tag. Root-cause confirmation is *rejected* unless DataHub lineage evidence is cited — the graph is structurally required in normal operation. **Honest ablation finding:** with `BLACKBOX_DISABLE_DATAHUB=true` (and the gate's DataHub requirement relaxed so the test isn't circular), the agent *can* still reach a correct diagnosis on this 5-transform fixture by reading pipeline source files — it loses the lineage map, the contract evidence that makes the violation provable, and the ability to record the incident. We report that rather than claiming the agent is helpless. |
| **Evidence in repo** | `backend/blackbox/datahub/client.py`, `backend/blackbox/datahub/ingest.py`, `backend/blackbox/datahub/writeback.py`, `backend/blackbox/agent/tools.py` (`t_confirm_root_cause`, `_datahub_disabled`), `backend/blackbox/config.py` |
| **Demo moment** | 0:35–1:15 (lineage graph drawn from DataHub) and 2:10–2:35 (resolved incident + docs note + tag shown in DataHub's own UI) |
| **Current weakness** | All metadata is self-ingested for one 8-table synthetic pipeline (no run against a non-authored metadata graph). MCP is used for discovery/health but lineage BFS + writeback go through GraphQL/SDK rather than MCP end-to-end. |
| **Next improvement** | Investigation-only run against a non-authored fixture (e.g. the `fiction-retail` datapack); route lineage reads through MCP `get_lineage` as well. |

## 2. Technical Execution

| | |
|---|---|
| **What BlackBox does** | Works end-to-end: report → investigation → machine-validated root cause → operator-authorized repair → warehouse rebuild → full 32-test invariant suite + KPI gate → git branch via temp worktree → DataHub writeback → live SSE UI. Evidence-gated state machine (forward-only stages, terminal `NO_INCIDENT`/`FAILED`), unverified-patch rollback, read-only SQL guard, path-restricted repairs, byte-identical resettable fixture, JSONL agent transcripts. |
| **Evidence in repo** | `backend/blackbox/agent/investigator.py`, `agent/tools.py`, `repair.py`, `warehouse.py`, `store.py`, `models.py`, `pipeline/invariants/test_invariants.py` (32 collected tests), `pipeline/README.md` |
| **Demo moment** | 1:40–2:10 (real diff, 32/32 green, KPI 93.3x → ~1.0x) |
| **Current weakness** | Repairs limited to single-file `pipeline/transforms/*.sql`; `try_create_pr` unwired (no live GitHub PR in the demo); background threads are fire-and-forget (no cancellation/timeout surfacing to the UI); positive-path consistency measured over a handful of runs, not a large N. |
| **Next improvement** | Multi-trial consistency stats (`--trials 5`); surface investigation-thread errors as UI toasts; wire `try_create_pr` for a real PR artifact. *(Since first draft: 14 gate unit tests committed in `tests/`, eval evidence committed in `evals/results/` — positive 11/11, control NO_INCIDENT, bad-repair rejected, ablation measured — and the UI report dialog is wired.)* |

## 3. Originality

| | |
|---|---|
| **What BlackBox does** | Goes beyond DataHub's shipped surface: DataHub stores incidents and lineage; BlackBox *autonomously produces* the incident resolution — root-cause proof, repair, verification — and writes it back. The distinctive ideas: (a) evidence-gated tool loop where the LLM cannot assert unmachine-checked facts, (b) `confirm_root_cause` as a validator that demands lineage + quantitative evidence naming the blamed field, (c) a *semantic* failure demo (contract violation with valid schemas) that schema-based monitors miss by construction. |
| **Evidence in repo** | `agent/tools.py` (validation logic), `agent/prompts.py` (no incident knowledge), `pipeline/generate_sources.py` (semantic seeding + distractor), `datahub/ingest.py` (contract docs the agent must interpret) |
| **Demo moment** | 1:15–1:40 ("the agent cannot bluff") |
| **Current weakness** | Autonomous data-incident RCA is a crowded claim (Monte Carlo, Anomalo, etc. market similar stories); the *repair* + *metadata writeback* combination is the differentiator but is demonstrated on a scenario designed to be solvable. One incident archetype (unit semantics) — no evidence the loop generalizes to schema drift, dropped columns, late data, etc. |
| **Next improvement** | Add a second seeded scenario family (even one) to show the same loop generalizes; sharpen the write-up's contrast with DataHub's built-in assertions/incidents. |

## 4. Real-World Usefulness

| | |
|---|---|
| **What BlackBox does** | The workflow mirrors what a staff data engineer actually does on-call: quantify symptom, walk lineage, hypothesize per branch, eliminate cheapest-first, prove, patch at the staging boundary, verify with tests, leave a paper trail where the team already looks (DataHub + git). Operator authorization before repair matches real change-management. Incident history in dataset docs is genuine institutional memory. |
| **Evidence in repo** | `agent/prompts.py` (playbook), two-phase flow in `api.py`/`investigator.py`, `datahub/writeback.py` (durable record), `repair.py` (branch, not direct-to-main) |
| **Demo moment** | 1:40–2:35 (human authorization → verified fix → durable record) |
| **Current weakness** | Demo stack is DuckDB + 5 SQL files with committed healthy baselines — real stacks have dbt/Airflow, hundreds of models, no clean baseline, and flaky tests. The verification gate assumes a trustworthy, fast, deterministic test suite; the KPI gate (`0.8–1.3x`) is scenario-specific. Nothing shows cost/latency of a run (a real team would ask). |
| **Next improvement** | Document the adapter surface honestly in the README (what you'd swap to run this on dbt + Snowflake: `warehouse.py`, `repair.verify_repair`, ingestion); publish tokens/latency per run from a transcript. |

## 5. Submission Quality

| | |
|---|---|
| **What BlackBox does** | Repo is coherent and judge-navigable: Apache-2.0 license, disclosed synthetic fixture (`pipeline/README.md`), architecture doc with diagram, timed demo script, this scorecard, deterministic `make demo-reset` so judges can reproduce the exact demo. |
| **Evidence in repo** | `LICENSE`, `docs/ARCHITECTURE.md`, `docs/DEMO_SCRIPT.md`, `pipeline/README.md`, `Makefile`, `POST /api/demo/reset` in `backend/blackbox/api.py` |
| **Demo moment** | Whole video + README setup steps |
| **Current weakness** | Setup requires four moving parts (Docker/DataHub, uv backend, npm frontend, Anthropic key) — mitigated by `make demo-run` and by committed run artifacts so a judge without an API key can still inspect a real run. Remaining: the demo video must be recorded and published before the deadline (script ready, timed to 2:55). |
| **Next improvement** | Write the README with copy-paste judge instructions; record the video; commit `examples/` (a real incident JSON, transcript, diff, and DataHub screenshots); add `make demo-run`. |

## Category fit A — "Agents That Do Real Work"

| | |
|---|---|
| **Fit** | Strong on the category's literal definition: the agent *reads DataHub to understand what's connected to what* (search/context/lineage tools), *takes action* (applies a verified patch, commits a branch, rebuilds the warehouse), and *writes results back* (incident entity, docs note, tag). Autonomy is bounded by an explicit human authorization gate — defensible, and worth framing as a feature. |
| **Evidence in repo** | `agent/tools.py`, `repair.py`, `datahub/writeback.py`; two-phase flow in `api.py` |
| **Demo moment** | Entire arc; especially 2:10–2:35 (writeback in DataHub UI) |
| **Current weakness** | "Real work" is demonstrated on synthetic work — one pipeline the authors built (disclosed, but a judge may discount it). |
| **Next improvement** | One run against a non-authored fixture (e.g. the `fiction-retail` datapack) even if investigation-only. *(MCP Server routing for reads: done — see Stage One note.)* |

## Category fit B — "Metadata-Aware Code Generation & Development"

| | |
|---|---|
| **Fit** | Partial but real: the repair engine generates production SQL (a full transform file) that works *because* the agent first read DataHub — the field-level contract ("major currency units"), column lineage, and the transform's own SQL attached to lineage edges. Generated code is validated by execution + 32 invariants before acceptance, which is exactly the category's "works on the first try" bar, enforced mechanically. |
| **Evidence in repo** | `agent/tools.py::t_propose_repair`, `repair.py`, `datahub/ingest.py` (contracts + `transformation_text` on edges), `pipeline/transforms/` |
| **Demo moment** | 1:40–2:10 (diff + verification) |
| **Current weakness** | Weaker fit than category A: generation is a single-file *repair*, not net-new models/DAGs/ingestion code, and the explicitly expected `examples/` folder of sample outputs does not exist. If forced to choose one category on the form, choose A. |
| **Next improvement** | Commit `examples/` with the generated diff + full generated transform from a real run; mention this category as secondary in the write-up rather than primary. |

## Bonus — OSS contribution to DataHub

| | |
|---|---|
| **Status** | None yet. No connector, skill, fix, RFC, or docs PR filed. The feedback survey ($50 track, also judge-visible goodwill) is likewise unsubmitted. |
| **Next improvement** | Lowest-cost credible option before the deadline: a docs improvement PR (e.g. documenting the `fineGrainedLineages` aspect read pattern used in `client.py`, which required non-obvious aspect-level access) and the feedback survey. |

---

## Three weakest cells (current triage order)

1. ~~Use of DataHub / Stage One~~ **RESOLVED:** official MCP Server runs inside the product (discovery transport) + Skills plugin in dev workflow.
2. **Submission Quality:** video still unrecorded (script ready in `docs/DEMO_SCRIPT.md`); screenshots pending the demo drill. README and `examples/` are done.
3. ~~Technical Execution run evidence~~ **RESOLVED:** eval evidence committed (`evals/results/`, incl. full per-run artifacts): positive **11/11** checks (run_0007), control NO_INCIDENT (no false positive), bad-repair rejected by immutability invariants, DataHub-ablation measured honestly (see below). 14 gate unit tests in `tests/`. Note: scenarios run sequentially and results span runs 0001–0007 — the "battery" is a composite, not one green button.
4. **Remaining:** demo on self-authored synthetic pipeline only; no live PR artifact; single-digit N on consistency.
