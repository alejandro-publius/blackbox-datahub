# BlackBox — Judge Scorecard (living gap analysis)

Self-assessment against the official criteria in `docs/HACKATHON_REQUIREMENTS.md`. The **weakness** column is deliberately critical — it is the work queue, not marketing. Updated 2026-08-09.

> **Stage One viability note (read first):** the rules require the OSS platform **plus at least one of** MCP Server, Agent Context Kit, DataHub Skills, or Analytics Agent. BlackBox currently integrates via the **Python SDK + GraphQL directly** — deep, but arguably not one of the four named tools. This is the single biggest submission risk in this document. Mitigation options: route the agent's read tools through the DataHub MCP Server, or document how the integration maps onto the Agent Context Kit guidance, before submission.

---

## 1. Use of DataHub

| | |
|---|---|
| **What BlackBox does** | DataHub is load-bearing, both directions. Reads: GraphQL search, dataset context (schema + field-level data contracts + ownership + tags), lineage BFS with **column-level lineage from real `fineGrainedLineages` aspects**. Writes: SDK-v2 ingestion of introspected schemas + table/column lineage with real transform SQL attached; native OSS **incident** raise/resolve; docs remediation note; `blackbox-remediated` tag. Root-cause confirmation is *rejected* unless DataHub lineage evidence is cited — the graph is structurally required, not decorative. An ablation flag (`BLACKBOX_DISABLE_DATAHUB`) exists to prove it. |
| **Evidence in repo** | `backend/blackbox/datahub/client.py`, `backend/blackbox/datahub/ingest.py`, `backend/blackbox/datahub/writeback.py`, `backend/blackbox/agent/tools.py` (`t_confirm_root_cause`, `_datahub_disabled`), `backend/blackbox/config.py` |
| **Demo moment** | 0:35–1:15 (lineage graph drawn from DataHub) and 2:10–2:35 (resolved incident + docs note + tag shown in DataHub's own UI) |
| **Current weakness** | **Does not use any of the four named integrations (MCP Server / Agent Context Kit / Skills / Analytics Agent) — a literal reading of the rules could fail Stage One.** Also: all metadata is self-ingested for one 8-table synthetic pipeline; the ablation eval that would *quantify* "load-bearing" has not been run (`evals/results/` is empty). |
| **Next improvement** | Swap or dual-path the three read tools onto the DataHub MCP Server (same GraphQL underneath); run and commit the ablation eval results. |

## 2. Technical Execution

| | |
|---|---|
| **What BlackBox does** | Works end-to-end: report → investigation → machine-validated root cause → operator-authorized repair → warehouse rebuild → full 32-test invariant suite + KPI gate → git branch via temp worktree → DataHub writeback → live SSE UI. Evidence-gated state machine (forward-only stages, terminal `NO_INCIDENT`/`FAILED`), unverified-patch rollback, read-only SQL guard, path-restricted repairs, byte-identical resettable fixture, JSONL agent transcripts. |
| **Evidence in repo** | `backend/blackbox/agent/investigator.py`, `agent/tools.py`, `repair.py`, `warehouse.py`, `store.py`, `models.py`, `pipeline/invariants/test_invariants.py` (32 collected tests), `pipeline/README.md` |
| **Demo moment** | 1:40–2:10 (real diff, 32/32 green, KPI 93.3x → ~1.0x) |
| **Current weakness** | **Proven on exactly one seeded scenario.** No committed evidence of robustness: no backend unit tests (`tests/` referenced in pyproject but absent), no eval harness runs, no record of the agent handling the healthy-mode / no-incident path or a failed-verification iteration. Repairs limited to single-file `pipeline/transforms/*.sql`; UI lacks the incident-report form (curl only); `try_create_pr` unwired; background threads are fire-and-forget (no cancellation/timeout surfacing to the UI). |
| **Next improvement** | Run and commit at least: one incident-mode run, one healthy-mode (`NO_INCIDENT`) run, one DataHub-ablation run — transcripts + results in `evals/results/`. Wire the report form. |

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
| **Current weakness** | **The two things judges grade first don't exist yet: the README is a stub and the video is unrecorded — with the deadline on 2026-08-10 5:00 PM ET.** No `examples/` folder with sample outputs (explicitly expected for the code-gen category). Setup requires four moving parts (Docker/DataHub, uv backend, npm frontend, Anthropic key) with no single `make demo-run`; judges without an Anthropic key cannot see the agent run (no recorded transcript/incident JSON committed as a fallback). |
| **Next improvement** | Write the README with copy-paste judge instructions; record the video; commit `examples/` (a real incident JSON, transcript, diff, and DataHub screenshots); add `make demo-run`. |

## Category fit A — "Agents That Do Real Work"

| | |
|---|---|
| **Fit** | Strong on the category's literal definition: the agent *reads DataHub to understand what's connected to what* (search/context/lineage tools), *takes action* (applies a verified patch, commits a branch, rebuilds the warehouse), and *writes results back* (incident entity, docs note, tag). Autonomy is bounded by an explicit human authorization gate — defensible, and worth framing as a feature. |
| **Evidence in repo** | `agent/tools.py`, `repair.py`, `datahub/writeback.py`; two-phase flow in `api.py` |
| **Demo moment** | Entire arc; especially 2:10–2:35 (writeback in DataHub UI) |
| **Current weakness** | The category examples name the MCP Server / Agent Context Kit as the mechanism, which BlackBox doesn't use (see Stage One note). "Real work" is demonstrated on synthetic work — one pipeline the authors built. |
| **Next improvement** | MCP-server routing for reads; one run against a non-authored fixture (e.g. the `fiction-retail` datapack) even if investigation-only. |

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

1. **Use of DataHub / Stage One:** no MCP Server / Agent Context Kit / Skills / Analytics Agent usage — a rules-literal viability risk despite deep SDK+GraphQL integration.
2. **Submission Quality:** README stub, no video, no `examples/` folder, ~19 hours before the deadline.
3. **Technical Execution:** zero committed run evidence — no eval results, no NO_INCIDENT path demonstration, no ablation numbers backing the "DataHub is load-bearing" claim.
