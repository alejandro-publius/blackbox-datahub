# BlackBox — Architecture

**One line:** Sentry for your data stack — BlackBox traces real DataHub lineage, proves the root cause of a silent semantic data failure, repairs the pipeline, verifies with the full invariant suite, and writes the incident back to DataHub.

**Honesty stance:** the demo scenario is synthetic and deterministic (fully disclosed in `pipeline/README.md`). But every number, lineage edge, test result, and diff shown in the product is the real output of real execution — DuckDB queries, DataHub GraphQL responses, pytest runs, `difflib` diffs, git commits. Nothing is mocked.

---

## 1. System overview

```
┌──────────────────────────┐  SSE: full IncidentState     ┌───────────────────────────────┐
│ Frontend (Next.js)       │  snapshots                   │ FastAPI  :8400                │
│ command center, dark UI  │◄─────────────────────────────│ backend/blackbox/api.py       │
│ • React Flow lineage     │  REST: report incident /     │ • incident store (JSON files  │
│ • evidence timeline      │─────────────────────────────►│   + SSE fan-out, store.py)    │
│ • root-cause + diff view │  repair / snapshot / reset   │ • demo reset endpoint         │
└──────────────────────────┘                              └──────────────┬────────────────┘
                                                                         │ background threads
                                                                         ▼
                                                   ┌─────────────────────────────────────┐
                                                   │ Investigator (Claude, claude-opus-5)│
                                                   │ backend/blackbox/agent/             │
                                                   │ investigator.py — tool-use loop;    │
                                                   │ LLM does strategy/hypotheses ONLY   │
                                                   └──────────────────┬──────────────────┘
                                                                      │ tool_use / tool_result
                                                                      ▼
        ┌─────────────────────────────────────────────────────────────────────────────────┐
        │ Deterministic tools + evidence gates  (backend/blackbox/agent/tools.py)         │
        │ every fact → EvidenceItem with an id; workflow tools machine-validate citations │
        └──────┬─────────────────────┬──────────────────────┬─────────────────────┬───────┘
               │                     │                      │                     │
               ▼                     ▼                      ▼                     ▼
   ┌──────────────────┐  ┌────────────────────┐  ┌─────────────────────┐  ┌───────────────┐
   │ DuckDB warehouse │  │ pipeline           │  │ DataHub OSS         │  │ git           │
   │ warehouse.py     │◄─│ transforms/*.sql   │  │ datahub/            │  │ repair.py     │
   │ • profiling      │  │ + 32 pytest        │  │ • ingest.py (SDK)   │  │ temp worktree │
   │ • baselines      │  │   invariants       │  │ • client.py (read,  │  │ → branch      │
   │ • read-only SQL  │  │ (repair target;    │  │   GraphQL+aspects)  │  │ blackbox/     │
   │ • KPI snapshot   │  │  rebuilt on fix)   │  │ • writeback.py      │  │ fix-<id>      │
   └──────────────────┘  └────────────────────┘  │   (incidents, docs, │  └───────────────┘
                                                 │    tags)            │
                                                 └─────────────────────┘
```

Division of labor, enforced in code:

- **Claude decides *what to look at next*** — hypotheses, elimination order, repair design. It never produces a displayed number.
- **Deterministic tools produce *all facts*** — DuckDB profiling and read-only SQL (`warehouse.py`), baseline comparisons against a committed healthy record, DataHub GraphQL search/context/lineage (`datahub/client.py`), pytest invariant runs, `difflib` diffs. Each fact-producing call records an `EvidenceItem` and returns its `evidence_id` for citation (`agent/tools.py`).
- **The state machine + evidence gates keep it honest** — workflow tools (`confirm_root_cause`, `update_hypothesis`, `declare_no_incident`) validate cited evidence before any stage transition is allowed.

## 2. The demo fixture (deterministic by construction)

A compact retail pipeline in DuckDB: `raw → staging → marts → executive KPI`. Full details in `pipeline/README.md`; the essentials:

- **Seeded incident:** from the `2026-08-07T00:00Z` payment-provider cutover, orders captured by `cloudpay_v2` report `raw_orders.amount` as **integer cents instead of decimal dollars**. Schemas stay valid; nothing crashes; the executive revenue KPI silently inflates **93x** ($2,737,323.50 vs an expected ~$29,349).
- **Distractor:** the FX-rates feed goes stale after 2026-08-05 in *both* modes — suspicious, but quantitatively incapable of explaining the jump (non-USD ≈ 7% of revenue).
- **Determinism:** "today" is pinned to 2026-08-09, one RNG seed (42), no wall clock; runs are byte-identical. `make demo-reset` restores the exact broken state.
- **32 pytest invariants** (`pipeline/invariants/test_invariants.py`): healthy mode passes 32/32; incident mode fails exactly 7.
- Nothing in the metadata, prompts, or tests hardcodes the answer — the agent must discover it from data (`agent/prompts.py` deliberately contains no knowledge of the seeded incident).

## 3. Incident state machine

Defined in `backend/blackbox/models.py` (`IncidentStage`, `STAGE_ORDER`, `can_advance_to`). Stages move **forward only**; two terminal exits.

```
REPORTED → CONTEXT_DISCOVERY → LINEAGE_TRAVERSAL → HYPOTHESIS_GENERATION
        → EVIDENCE_COLLECTION → ROOT_CAUSE_CONFIRMED
        → REPAIR_GENERATED → REPAIR_TESTING → VERIFIED → WRITEBACK_COMPLETE

   Terminal exits from anywhere: NO_INCIDENT (evidence-gated), FAILED
```

Transitions are side effects of *tool activity*, not LLM claims: e.g. `datahub_lineage` advances to `LINEAGE_TRAVERSAL`, `record_hypothesis` to `HYPOTHESIS_GENERATION`, and only an *accepted* `confirm_root_cause` reaches `ROOT_CAUSE_CONFIRMED`. If a run ends anywhere else, `investigator.py` marks it `FAILED` and reverts any unverified patch (`_cleanup_unverified_patch` restores the transform and rebuilds the warehouse).

**Two-phase flow (operator in the loop):** `POST /api/incidents` runs phase 1 with `allow_repair=False` — `propose_repair` is rejected until the operator authorizes phase 2 via `POST /api/incidents/{id}/repair` (only allowed from `ROOT_CAUSE_CONFIRMED`). See `investigator.run_investigation` / `run_repair_phase` and `api.py`.

## 4. Evidence gating: facts vs hypotheses vs actions

Three distinct object kinds (mirrored exactly in `frontend/src/lib/types.ts`):

| Kind | Model | Producer | Rule |
|---|---|---|---|
| **Fact** | `EvidenceItem` | Deterministic tool code only | Carries raw tool output + `kind` (`metadata`, `profile`, `baseline_comparison`, `sql`, `lineage`, `test`, `patch`, `writeback`) and `source` (`datahub`, `warehouse`, `pipeline`, `git`, `agent`). Never free-typed by the LLM. |
| **Hypothesis** | `Hypothesis` | LLM via `record_hypothesis` | Must target a DataHub urn. Eliminating or confirming **requires valid cited `evidence_ids`** — the tool rejects otherwise. |
| **Action** | patch / writeback / git artifact | System code, LLM-initiated | Gated by state (e.g. no repair without a confirmed root cause) and verified by re-execution. |

`confirm_root_cause` is the hardest gate (`agent/tools.py::t_confirm_root_cause`). It is **machine-validated** and rejected unless the citations include:

1. at least one item with `source: datahub` (lineage/metadata — the cause must be located on the real graph),
2. at least one quantitative item (`profile` or `baseline_comparison`),
3. the blamed asset already present in the traversed lineage graph, and
4. quantitative evidence whose raw data actually references the blamed field — "profile the blamed column itself".

`declare_no_incident` is symmetric: concluding "nothing is wrong" also requires cited quantitative evidence. Inventing an incident and bluffing a root cause are both structurally blocked, not just prompted against.

## 5. Repair & verification loop

Implemented in `backend/blackbox/repair.py`, orchestrated by `agent/tools.py::t_propose_repair`:

1. **Propose:** the LLM supplies the *full new content* of one transform file. Repairs are path-restricted to `pipeline/transforms/*.sql` (`_resolve_transform`).
2. **Real diff:** `difflib.unified_diff` computes the patch from actual old/new file contents — the diff shown in the UI is always the diff that ran.
3. **Apply:** file written in place, original backed up (`.sql.orig`).
4. **Verify (`verify_repair`):** rebuild the entire warehouse (`pipeline/run.py`), run the **full 32-test invariant suite**, recompute the KPI. Success requires **all tests green AND anomaly ratio back in [0.8, 1.3]**. Failure returns the failing tests to the model to iterate; an abandoned patch is reverted.
5. **Git artifact:** the verified fix is committed on branch `blackbox/fix-<incident-id>` via a **temporary git worktree** so the main working tree is never disturbed (`make_git_artifact`). `try_create_pr` can push and open a PR via `gh`, but is deliberately not called during the demo — the run produces a local branch + commit and never touches a remote.
6. **Writeback:** the DataHub incident is resolved with the remediation record (section 6).

The repair prompt discipline lives in `agent/prompts.py`: fix at the right layer (staging boundary), targeted condition, no deleting/hiding data, "restoring the headline number by breaking something else is failure".

## 6. How DataHub is used (load-bearing, each surface)

DataHub OSS (quickstart, v1.7.0) is the agent's map of the pipeline and its durable memory. Surfaces:

| # | Surface | What happens | Where |
|---|---|---|---|
| 1 | **Ingestion (Python SDK v2)** | All 8 datasets upserted via `DataHubClient` / `Dataset`: schemas **introspected live from DuckDB** (`DESCRIBE`), so DataHub always mirrors reality. Run: `uv run python -m blackbox.datahub.ingest`. | `backend/blackbox/datahub/ingest.py` |
| 2 | **Schemas & data contracts** | Dataset descriptions + per-field docs encode the contract (e.g. `raw_orders.amount`: "MAJOR currency units as a decimal… contract v1.3"). The investigation hinges on comparing observed data against this documented meaning. Ownership (2 corp users) and tags (`kpi`, `executive-reporting`, `revenue`) included. | `ingest.py` (`DATASET_DOCS`, `FIELD_DOCS`, `OWNERS`, `TAGS`) |
| 3 | **Table + column lineage with transform SQL** | 6 lineage edges emitted via `client.lineage.add_lineage` with `column_lineage` maps and each edge's **real transform SQL** attached as `transformation_text`. | `ingest.py` (`LINEAGE`) |
| 4 | **GraphQL search (read)** | `datahub_search` tool → `searchAcrossEntities`; how the agent locates the affected KPI from a plain-English report. | `datahub/client.py::search` |
| 5 | **GraphQL dataset context (read)** | `datahub_get_dataset` tool → description, schema fields with docs (editable metadata merged), ownership, tags, domain, custom properties. | `client.py::get_dataset` |
| 6 | **GraphQL lineage traversal (read)** | `datahub_lineage` tool → BFS over the lineage graph, one hop per query, plus **column-level lineage read from the real `UpstreamLineage` aspect (`fineGrainedLineages`)** — this drives the React Flow graph in the UI. No topology is hardcoded. | `client.py::lineage`, `_column_lineage_for` |
| 7 | **Incident writeback (write)** | `raiseIncident` creates a native OSS incident entity (OPERATIONAL / CRITICAL) on the root-cause + affected asset urns; `updateIncidentStatus` marks it RESOLVED/FIXED with tests, KPI ratio, and fix branch in the message. | `datahub/writeback.py::raise_incident`, `resolve_incident` |
| 8 | **Docs writeback (write)** | `updateDescription` appends an "Incident history" remediation note to the root-cause dataset's docs — institutional memory that outlives the run. | `writeback.py::_append_incident_note` |
| 9 | **Tag writeback (write)** | Creates and applies a `blackbox-remediated` tag via `addTags`. | `writeback.py::_tag_remediated` |
| 10 | **Ablation flag** | `BLACKBOX_DISABLE_DATAHUB=true` makes the DataHub tools *and* writeback return errors, measuring what DataHub context contributes. Run and committed — see `evals/results/run_0007.json` and the honest finding in §9. | `config.py`, `agent/tools.py::_datahub_disabled`, `datahub/writeback.py` |

The demo-reset endpoint (`POST /api/demo/reset`) also re-syncs DataHub metadata (idempotent upserts) so reverted transform SQL is reflected in the graph.

## 7. API & frontend

**FastAPI** (`backend/blackbox/api.py`, port 8400):

- `GET /api/health` — warehouse / DataHub / Anthropic readiness.
- `GET /api/metrics/snapshot` — the KPI + 90-day daily history with baseline overlay.
- `GET /api/lineage/graph` — the pipeline graph *as DataHub knows it* (upstream of the KPI).
- `POST /api/incidents` — file a report; starts phase-1 investigation in a background thread.
- `POST /api/incidents/{id}/repair` — operator authorization for phase 2.
- `GET /api/incidents/{id}/events` — **SSE stream of full `IncidentState` snapshots** (not deltas; reconnect-safe by construction, `store.py`).
- `POST /api/demo/reset` — full demo-reset contract: restore transforms, regenerate incident sources, rebuild warehouse, clear incident records, delete `blackbox/fix-*` branches, re-ingest DataHub metadata.

**Frontend** (`frontend/`, Next.js 16 + React 19 + Tailwind 4): a dark command center. `TopBar` (stage pill, Reset Demo), `KpiStrip`, `LineagePanel` (React Flow graph with node statuses `healthy → suspicious → root_cause → repaired`), `RightPanel` (Timeline / Hypotheses / Evidence tabs), `IncidentDrawer` surfacing the `RootCauseCard` (with the **Repair & Verify** button) and the `ResolutionCard` (diff viewer, post-repair tests, before/after KPI, writeback status). Type contract in `frontend/src/lib/types.ts` mirrors `models.py` exactly. A `?preview=1|resolved` mode renders placeholder fixtures for UI development only, always watermarked "PREVIEW DATA".

Incidents are filed from the UI's **Investigate Incident** dialog (`IncidentDialog.tsx`), which posts to `POST /api/incidents`; the same endpoint is available directly for scripted runs.

## 8. Known limitations

Stated plainly rather than hidden — the full list with evidence is in [`ACCEPTANCE.md`](ACCEPTANCE.md).

- **PR creation is not wired into the automated flow.** `repair.try_create_pr` exists and works, but the demo stops at a real local branch + commit; nothing pushes to a remote during a run.
- **Repairs are single-file**, scoped to `pipeline/transforms/*.sql` by `repair._resolve_transform`.
- **One incident archetype.** Every component is exercised against the seeded unit-semantics failure; a second archetype (timezone shift, duplicate rows) would reuse the same plumbing but is not implemented.
- **Consistency is measured over a handful of runs**, not a large N.
- **The fixture is self-authored**, so incident realism is illustrative; the machinery is the contribution.

## 9. The DataHub ablation, honestly

`BLACKBOX_DISABLE_DATAHUB=true` disables the DataHub read tools and the writeback, and relaxes the confirm gate's DataHub-citation requirement (otherwise the test would be circular — the gate *requires* DataHub evidence, so failure would be wiring, not information value).

The measured result: on this 5-transform fixture the ablated agent **can still reach a correct diagnosis** by reading pipeline source files directly. We report that rather than claiming helplessness. What it loses is what matters at real scale:

- the **topology map** — it substitutes reading every transform file, which does not survive a warehouse with thousands of models;
- the **documented contract** (`amount` is major currency units), which is what converts "these numbers look strange" into a provable contract violation;
- **zero DataHub-grounded evidence citations**, so the audit trail a reviewer would accept is gone;
- the ability to **record the incident** — no institutional memory survives the run.
