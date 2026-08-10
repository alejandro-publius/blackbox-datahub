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

## Architecture decisions (running list)
- Incident scenario: cents-vs-dollars semantic shift in raw_orders.amount → 100x revenue jump. Deterministic, seeded, resettable.
- Local data stack: DuckDB + Python transformations (dbt only if time permits) + metric snapshot consumer.
- DataHub is load-bearing: lineage traversal, schema/description context, ownership, incident writeback via OSS APIs.
- Backend: Python 3.11 via uv, FastAPI, Pydantic. Frontend: Next.js + TS + Tailwind + React Flow.
- Agent: Claude API with tool-use loop; deterministic tools for SQL/profiling/lineage; LLM for strategy/hypotheses/repair-planning.
