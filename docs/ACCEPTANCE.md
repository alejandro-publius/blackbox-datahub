# Acceptance gates — verified evidence

Every claim below was checked against the running system on 2026-08-10. Commands are
runnable by a judge; artifacts are committed so they can be inspected without an API key.

| # | Gate | Status | How to verify / evidence |
|---|---|---|---|
| 1 | DataHub OSS actually runs | ✅ | `datahub docker quickstart --version v1.7.0`; UI at :9002, GMS `/health` 200 |
| 2 | BlackBox connects to DataHub | ✅ | `curl localhost:8400/api/health` → `datahub_connected: true` |
| 3 | DataHub context materially participates | ✅ | Search, entity context **and** lineage BFS route through the official **DataHub MCP Server** (`via: datahub-mcp-server`); evidence items in `examples/sample-incident/incident_state.json` carry the transport |
| 4 | Seeded incident is real + reproducible | ✅ | `make demo-reset` → KPI 2,737,324 at **93.3×** expected; byte-identical regeneration (seed 42, pinned ANCHOR_DAY) |
| 5 | Agent finds the root cause | ✅ | `evals/results/run_0007.json` → `root_cause_correct ✓` (`raw.raw_orders`, field `amount`) |
| 6 | Evidence proves *why* | ✅ | `evidence_coverage ✓`; 19 evidence items incl. DataHub lineage + segmented profiling; full derivation in `examples/sample-incident/final_report.md` |
| 7 | Real code repair generated | ✅ | `examples/sample-incident/repair.patch` — difflib-computed unified diff |
| 8 | Repair actually executed | ✅ | Applied to `pipeline/transforms/stg_orders.sql`, warehouse rebuilt |
| 9 | Tests validate it | ✅ | `repair_verified ✓` — **32/32** invariants green post-repair |
| 10 | Business metric demonstrably restored | ✅ | KPI 93.3× → **0.93×**; `repair_restores_baseline ✓` (within 1% of committed healthy baseline, not just the loose KPI window) |
| 11 | Git artifact exists | ✅ | `blackbox/fix-<incident>` branch, real commit, via isolated worktree (`git_artifact` in incident state) |
| 12 | Incident context written back to DataHub | ✅ | `writeback_done ✓` — native incident raised ACTIVE at confirmation → `RESOLVED/FIXED`; docs note + `blackbox-remediated` tag. Screenshots `05-datahub-incident.png`, `05b-datahub-remediation.png` |
| 13 | UI demonstrates the full workflow | ✅ | `docs/screenshots/01..06` — intake → investigation → root cause → resolution → reset |
| 14 | Demo reset works | ✅ | `POST /api/demo/reset` idempotent: transforms restored, sources regenerated, incidents cleared, fix branches dropped, **DataHub writeback state scrubbed**, metadata re-synced |
| 15 | End-to-end browser test passes | ✅ | `uv run python scripts/demo_drill.py` — 6 acts green in ~150s, fails on console errors or missing assertions |
| 16 | No secrets in git | ✅ | Independent security review swept full history (`git log --all -p`, blob-level scan): 0 real keys; `.env` untracked + ignored |
| 17 | Apache 2.0 license visible | ✅ | GitHub detects `spdx_id: Apache-2.0` in the About section |
| 18 | README complete | ✅ | 60-second comprehension: problem, what it does, quickstart, DataHub table, disclosure, evals |
| 19 | `examples/` inspectable | ✅ | `examples/sample-incident/` — unedited incident state, transcript, patch, report |
| 20 | Eval results exist | ✅ | `evals/results/` runs 0001–0007 + per-run artifacts under `artifacts/` |
| 21 | Clean-install path tested | ⚠️ | Verified on this machine from empty dir (colima → quickstart → `make setup` → `make datahub-setup` → `make demo-reset` → `make demo-run`). Not re-tested on a second physical machine. |
| 22 | Submission materials match reality | ✅ | Claims cross-checked by an adversarial judge simulation + evals-methodology review; ablation wording corrected to the measured result |

## Honest limitations (stated up front)

- The pipeline and its incident are **authored by us** and deterministic by design. The incident realism is illustrative; the machinery (evidence gates, verification loop, writeback) is the contribution.
- The DataHub ablation shows the agent *can* still reach a correct diagnosis on this 5-transform fixture by reading pipeline source files. What DataHub supplies is the scalable topology map, the contract evidence that makes the violation *provable*, and the durable incident record — not helplessness without it.
- Positive-path consistency is measured over a handful of runs, not a large N.
- PR publication is wired but **opt-in** (`BLACKBOX_CREATE_PR`, default off) so the demo never pushes to a remote; the local git branch + commit is the demo artifact. With the flag on, a reset leaves the pushed branch and open PR behind.
- Repairs are scoped to a single `pipeline/transforms/*.sql` file.
