# Devpost submission — copy-paste source

**Project title:** BlackBox — Autonomous Data Incident Response

**Tagline (≤60 chars):** Sentry for your data stack, powered by DataHub lineage.

**Submitted challenge:** Agents That Do Real Work
**Also demonstrates:** Metadata-Aware Code Generation & Development (the agent authors, executes and verifies real transform SQL from DataHub metadata — see "How we built it")

---

## Inspiration

The worst data incidents don't crash anything. A payments provider migration quietly starts reporting `amount` in cents instead of dollars. Every schema validates. Every job is green. And the executive revenue dashboard is wrong by 100× until a human notices, then spends a day spelunking through pipelines. We wanted the response to be: tell an agent "revenue looks 100× too high — is this real?" and have it *actually fix the problem* — with proof, not vibes.

## What it does

BlackBox is an incident-response command center for data pipelines. Report a symptom, and it autonomously:

- finds the affected KPI in DataHub (via the official **DataHub MCP Server**) and reads its data contract, ownership and docs;
- walks **table- and column-level lineage** upstream — DataHub's graph is the map, the agent never guesses topology;
- quantifies the symptom against committed baselines, forms hypotheses over every upstream branch, and eliminates distractors with real profiling (a suspicious stale-FX feed is ruled out quantitatively);
- **proves the root cause** — the `confirm_root_cause` action is machine-validated and rejected unless the agent cites DataHub lineage evidence plus quantitative evidence naming the blamed field;
- raises a real **ACTIVE incident in DataHub** on affected assets, then **repairs the pipeline**: it writes new transform SQL, the system computes the actual diff, applies it, rebuilds the warehouse, and reruns all 32 data invariants plus the KPI;
- commits the verified fix on a `blackbox/fix-*` git branch and **opens a real pull request** — [PR #1](https://github.com/alejandro-publius/blackbox-datahub/pull/1) was opened by the agent itself and is left open for judges; then resolves the DataHub incident (**RESOLVED/FIXED** with the remediation record), appends an incident-history note to the dataset docs, and tags the asset — durable institutional memory in the catalog.

Demo result: revenue 93.3× → 0.93×, 32/32 invariants green, real incident urn in DataHub.

## How we built it

- **Engine:** Python + FastAPI + Pydantic. A Claude (Opus) tool loop drives strategy; every *fact* comes from deterministic tools (DuckDB profiling, baseline comparisons, read-only SQL, pytest, difflib, git). An explicit state machine (REPORTED → … → WRITEBACK_COMPLETE) is gated on machine-checkable evidence.
- **DataHub (load-bearing):** OSS quickstart v1.7.0. Metadata ingested with the Python SDK v2 — schemas introspected from the live warehouse, contract docs on fields, ownership, tags, and table+column lineage with the real transform SQL attached. Reads via the official MCP Server + GraphQL; writeback via the native Incidents API.
- **Demo fixture:** a deterministic DuckDB retail pipeline (raw → staging → marts → executive KPI) with a seeded, disclosed semantic failure and a distractor; byte-identical regeneration and one-command reset.
- **Frontend:** Next.js + TypeScript + React Flow command center streaming the investigation live over SSE: lineage traversal, hypotheses, evidence timeline, the ROOT CAUSE CONFIRMED reveal, diff viewer, before/after KPI, and writeback confirmation.
- **Evals:** a deterministic harness proving the four things demos usually hand-wave: the incident is correctly diagnosed and repaired (11/11 machine-graded checks, incl. restoring the committed baseline within 1%); healthy data does **not** produce an invented incident; a superficially-plausible bad repair is **rejected** by historical invariants; and a DataHub-ablation run measures what the metadata graph contributes (the lineage map, the contract evidence that makes the root cause *provable*, and the incident writeback — reported honestly, including that a small fixture can be brute-forced from source files).

## Challenges we ran into

- Making the agent honest: LLMs happily declare root causes. We gated every conclusion behind evidence-citation checks enforced in code, and made verification full-suite (a fix that restores the top-line while corrupting history is rejected).
- Silent quickstart hang on colima: docker-py ignores docker CLI contexts (needs `DOCKER_HOST`). Diagnosed, worked around, and logged as feedback with a proposed fix (docs/DATAHUB_FEEDBACK_LOG.md).
- GraphQL schema drift (incident mutations' input types, v1.7 filter changes) — resolved against the live schema.
- Our own red team caught our agent cheating: the DataHub writeback (a remediation note on the dataset docs) from one run became the *answer key* for the next — durable institutional memory and clean-room evaluation are in tension. We now scrub BlackBox-written DataHub state on every reset and hard-fail evals on contamination. The agent, to its credit, had flagged the stale note as "a claim to verify, not evidence" and re-proved everything from data.

## Accomplishments we're proud of

- A complete detect → investigate → prove → repair → verify → writeback loop with zero mocked steps.
- The agent found evidence we didn't design: it noticed 100% of the new provider's amounts were integer-valued vs ~1% for legacy processors — a decisive unit-semantics fingerprint.
- Incident knowledge that outlives the incident: the resolved DataHub incident, dataset doc note, and tag are all durable catalog artifacts.

## What we learned

Metadata is what turns an LLM from a guesser into an investigator: the data contract ("amount is major currency units") plus column lineage is exactly the context that makes a semantic failure *provable*. And native OSS incident entities make DataHub a natural system of record for agent work.

## Contributing back

Two upstream PRs, both open at submission time (neither merged — we're not claiming otherwise):

**[datahub-skills#133](https://github.com/datahub-project/datahub-skills/pull/133) — a new `datahub-incident-investigation` skill.** We took the methodology BlackBox implements and generalized it into a reusable agent workflow for anyone with DataHub: locate the affected asset, traverse lineage to localize the fault, form competing hypotheses, hold evidence to a necessity-and-sufficiency standard so distractors get eliminated quantitatively, pass a 5-point confirmation gate before declaring a cause, then assess blast radius, remediate, verify, and write the resolution back. It's deliberately vendor-neutral — no DuckDB, no cents-vs-dollars, nothing from our repo. Every command in it was run against live DataHub OSS before we opened the PR, which surfaced three things worth reporting upstream: `health` returns a list, not an object; `properties.description` can be null while `editableProperties.description` holds the actual contract; and OSS has no top-level `incident(urn:)` query. It also slots deliberately alongside the existing `datahub-quality` skill rather than duplicating it — quality *detects and records*, investigation *explains and resolves*.

**[datahub#19046](https://github.com/datahub-project/datahub/pull/19046) — quickstart troubleshooting docs.** `datahub docker quickstart` hangs silently at "Starting up DataHub..." on Colima, Rancher Desktop, and Podman because docker-py reads `DOCKER_HOST` but not Docker CLI contexts — no error, no images, while `docker ps` works fine in the same shell. Cost us 15 minutes of a blank screen.

Our full friction log (stale auth defaults, the removed `:head` tag, the one-hour default PAT duration, MCP mutation ambiguity for OSS) is in `docs/DATAHUB_FEEDBACK_LOG.md`.

## What's next

Real warehouse connectors (Snowflake/BigQuery), dbt-aware repairs as PRs, assertion emission so BlackBox's invariants live in DataHub itself, and multi-incident triage.

## Built with

Python, FastAPI, Pydantic, DuckDB, pytest, Anthropic Claude (Opus), DataHub OSS v1.7 (MCP Server, Python SDK v2, GraphQL, Incidents API), Next.js, TypeScript, Tailwind, React Flow, SSE, git.

---

### Submission checklist (fill on Devpost)

- [ ] Public repo URL: https://github.com/alejandro-publius/blackbox-datahub (Apache-2.0 visible)
- [ ] Video: <3:00, public YouTube/Vimeo, shows the working app (script: docs/DEMO_SCRIPT.md)
- [ ] 3–5 screenshots (intake / investigation / root cause / resolution / DataHub incident)
- [ ] Challenge selected: **Agents That Do Real Work** (single submitted challenge; the code-gen fit is described in the write-up, not selected as a second category)
- [ ] Testing instructions incl. `make` quickstart + examples/ pointer
- [ ] Feedback survey (bonus)
