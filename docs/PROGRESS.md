# BlackBox — Progress Log

Concise, append-only. Newest entries at the bottom. Survives context compaction.

## 2026-08-09 ~22:05 — Session start
- Machine audit: git ✓, gh authenticated (alejandro-publius) ✓, node v26 ✓, uv ✓, 8 cores / 16GB / 1.3TB free.
- Docker MISSING → installing colima + docker CLI via Homebrew (background). Colima VM: 6 CPU / 10GB RAM / 80GB disk.
- Figma MCP: NOT connected (only Cloudflare MCP servers present). Decision: design UI directly in code, no Figma dependency.
- Repo initialized (`main`), Apache 2.0 LICENSE, .gitignore, .env.example laid down.
- Background agents launched: (1) DataHub OSS technical research (quickstart/MCP/SDK/incidents/GraphQL/skills), (2) official Devpost requirements → docs/HACKATHON_REQUIREMENTS.md.
- Confirmed from initial search: deadline Aug 10 2026 5:00 PM ET; judging favors deep DataHub use (context graph, MCP, Agent Context Kit, Skills) + working end-to-end + writeback ("contribute back to the graph").

## 2026-08-09 ~22:40 — Core engine complete, DataHub pulling
- Fixture DONE (32 invariants; incident mode fails exactly 7; anomaly 93.27x; deterministic hashes verified; cloudpay/legacy median ratio 99.6≈100 discoverable).
- Backend DONE (untested vs live LLM): models/state machine, evidence-gated tools, investigator 2-phase loop (pause before repair for demo CTA), repair engine (worktree git artifacts), FastAPI+SSE, DataHub client (GraphQL search/context/lineage+CLL)/ingest (SDK v2)/writeback (raiseIncident→RESOLVED + docs note + tag).
- Deterministic tool layer smoke-tested against real warehouse: all green, evidence chain airtight.
- DataHub quickstart v1.7.0: first attempt hung 15min (docker-py needs DOCKER_HOST with colima — fixed); now genuinely pulling (~4GB done). Auth is ON by default → scripts/setup_datahub.sh mints PAT → .env.
- Public repo live: github.com/alejandro-publius/blackbox-datahub (Apache 2.0).
- Agents running: frontend wiring, eval harness, docs (ARCHITECTURE/DEMO_SCRIPT/JUDGE_SCORECARD/CLAUDE.md).
- BLOCKER (human): ANTHROPIC_API_KEY needed in .env for live investigation runs — requested from Alex.

## 2026-08-10 ~00:15 — P0 vertical slice PROVEN, frontend wired
- THREE successful end-to-end runs (Claude Opus): root cause proven w/ cited evidence, FX distractor eliminated, targeted CASE-WHEN repair, 32/32 invariants, KPI 93.3x→0.93x, git fix branch, DataHub incident RESOLVED+docs+tag. Flagship eval: 9/9 checks, 129s, 22 tool calls (examples/sample-incident/).
- Fixes applied along the way: temperature param removed (Claude 5 rejects it), updateIncidentStatus input type (IncidentStatusInput!), raise-ACTIVE-at-confirm, most-upstream prompt nudge (raw_orders now blamed), MCP Server = primary search transport + health enrichment (mcp_bridge.py), eval grading accepts raw/stg (tracks blamed_most_upstream).
- Frontend COMPLETE: SSE hook (reconnect+poll fallback), 4 macro-states, inline-SVG revenue chart w/ baseline, RootCauseCard overlay, ResolutionCard (diff/git/writeback), reset flow. Build+lint green, verified against live backend.
- README, DEVPOST.md draft, examples/ (real artifacts), scripts/demo_drill.py (Playwright judge-flow with screenshots) written.
- Orphaned ACTIVE incident from run 1 resolved in DataHub. data/incidents/ now gitignored.
- IN FLIGHT: eval battery (control/bad-repair/ablation), chromium install, security review agent, evals-methodology review agent.
- NEXT: demo drill E2E + screenshots → fix review findings → judge-simulation review → video script polish → submit.

## 2026-08-10 ~02:30 — Adversarial review fix cycle complete
- Security review: 0 critical (git history clean). HIGH fixed: run_sql filesystem exfiltration (enable_external_access=false + denylist + tests). Reminder: rotate Anthropic key post-hackathon.
- Evals methodology review (harsh, excellent): C1 writeback-note contamination (prior run's remediation note on dataset docs = answer key for next run) → reset.py scrubs DataHub state on every reset, harness hard-fails on contamination, demo-reset endpoint scrubs too. C2 circular ablation → confirm-gate DataHub requirements relax in ablation mode; scenario grades identification accuracy honestly. H2 metadata leaks trimmed ("unit/semantic drift" doc phrase removed, runbook date fuzzed, prompt repair-shape softened). H3 grader hardened (post-repair days must match committed baseline ±1%; targeted=provider-scoped; single-file diff). M3 field↔asset binding in confirm gate. Ablation writeback inconsistency fixed (flag now gates writes too).
- Fresh UNCONTAMINATED flagship run: 11/11 checks (stricter grader), WRITEBACK_COMPLETE, 145s. Honest ablation finding: agent can still brute-force diagnosis from transform files on this small fixture — README/DEVPOST wording corrected to the measured claim (DataHub = scalable map + contract evidence + writeback, not "agent is helpless").
- run_evals now archives full incident artifacts per scenario (evals/results/artifacts/).
- Session restart (re-login) orphaned servers; restarted. Drill click bug root-caused: top-bar button behind overlay backdrop; .last targets the card CTA (verified in preview).

## 2026-08-10 ~01:15 — SUBMISSION-READY (pending video)
- Judge simulation scored: Stage One PASS; Use of DataHub 8, Technical Execution 8, Originality 7, Real-World Usefulness 7, Submission Quality 7. Verdict: plausible category winner for "Agents That Do Real Work".
- Its #1 finding was self-inflicted: JUDGE_SCORECARD contradicted our own eval data ("ablation FAILED" vs. committed results showing it passed). Fixed everywhere; ablation now described as measured.
- MCP made structurally true: lineage BFS now routes through the MCP Server too (via=datahub-mcp-server across search + context + lineage).
- README condensed (9 steps → 4), hero screenshot, production-adapter seam table added.
- OSS bonus claimed: DataHub docs PR #19046 (silent quickstart hang under Colima/Rancher/Podman).
- UI fix: resolution/root-cause cards lead with evidence; long agent report collapsed (it was burying the KPI/diff/git/writeback below the fold).
- Demo drill hardened: captures + ASSERTS the ACTIVE DataHub incident and the durable remediation note. 6 acts green in 150s. 7 real screenshots committed.
- LICENSE swapped to GitHub's canonical Apache-2.0 text → now auto-detected (rules require it visible).
- docs/ACCEPTANCE.md written: all 22 gates with runnable evidence + honest limitations.
- REMAINING (human-only): record <3:00 video per docs/DEMO_SCRIPT.md, upload public, submit Devpost form (text ready in docs/DEVPOST.md).

## Architecture decisions (running list)
- Incident scenario: cents-vs-dollars semantic shift in raw_orders.amount → 100x revenue jump. Deterministic, seeded, resettable.
- Local data stack: DuckDB + Python transformations (dbt only if time permits) + metric snapshot consumer.
- DataHub is load-bearing: lineage traversal, schema/description context, ownership, incident writeback via OSS APIs.
- Backend: Python 3.11 via uv, FastAPI, Pydantic. Frontend: Next.js + TS + Tailwind + React Flow.
- Agent: Claude API with tool-use loop; deterministic tools for SQL/profiling/lineage; LLM for strategy/hypotheses/repair-planning.
