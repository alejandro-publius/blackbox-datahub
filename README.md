# ◼ BlackBox — Autonomous Data Incident Response

> ### Evidence-gated autonomous recovery for data incidents.
>
> **Claude decides what to investigate; deterministic tools decide what is true.**
>
> Tell BlackBox what looks wrong. It reads DataHub's context graph, *proves* the root cause against a machine-enforced evidence gate, repairs the pipeline, executes and verifies the fix against the full invariant suite, opens a real pull request, and writes the resolution back into DataHub.
>
> `READ → PROVE → ACT → VERIFY → WRITE`

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![DataHub OSS](https://img.shields.io/badge/DataHub-OSS%20v1.7.0-1890ff)](https://datahubproject.io/)
[![MCP Server](https://img.shields.io/badge/DataHub-MCP%20Server-6f42c1)](https://docs.datahub.com/docs/features/feature-guides/mcp)
[![Invariants](https://img.shields.io/badge/invariants-32%2F32%20after%20repair-brightgreen)](evals/results/)
[![Eval](https://img.shields.io/badge/flagship%20eval-11%2F11%20checks-brightgreen)](evals/results/run_0007.json)

Built for **[Build with DataHub: The Agent Hackathon](https://datahub.devpost.com)** · Categories: **Agents That Do Real Work** + **Metadata-Aware Code Generation & Development**

The worst data incidents don't crash anything. A payment provider quietly starts reporting `amount` in cents instead of dollars. Every schema still validates. Every job stays green. The executive revenue dashboard is wrong by 100× — and nobody notices for days.

BlackBox is given one plain-English sentence — *"Revenue just jumped roughly 100×. Is this real?"* — and takes it from there.

![Root cause confirmed](docs/screenshots/03-rootcause.png)

<p align="center">
  <img src="docs/screenshots/01-intake.png" alt="Command center with the anomalous KPI" width="49%">
  <img src="docs/screenshots/02-investigation.png" alt="Live investigation over DataHub lineage" width="49%">
</p>
<p align="center">
  <img src="docs/screenshots/04-resolved.png" alt="Verified repair with before/after KPI and diff" width="49%">
  <img src="docs/screenshots/05-datahub-incident.png" alt="Real incident raised in DataHub" width="49%">
</p>
<p align="center"><sub><b>Top:</b> anomalous KPI at 93.3× · live lineage traversal &nbsp;|&nbsp; <b>Bottom:</b> verified repair (32/32, real diff, git branch) · the incident BlackBox raised in DataHub</sub></p>

## See it work

One autonomous run, [graded on 11 machine-checked criteria](evals/results/run_0007.json) — all passed, 13 turns, 24 tool calls, ~180 s:

| | |
|---|---|
| Reported symptom | Executive revenue **$2,737,324** — **93.3×** its expected baseline |
| Root cause found | `raw.raw_orders.amount` — `cloudpay_v2` migration emitting **integer cents**, violating the documented contract |
| Distractor rejected | stale FX feed eliminated quantitatively (max effect ~1.27×, two orders of magnitude too small) |
| Repair | provider-scoped `CASE WHEN` normalization in `stg_orders.sql`, written by the agent |
| Verification | **32/32** invariants green; KPI **restored to 0.93×**, within 1% of the committed healthy baseline |
| Writeback | DataHub incident `RESOLVED / FIXED` + docs note + tag → `WRITEBACK_COMPLETE` |
| Engineering artifact | **[a real pull request the agent opened itself →](https://github.com/alejandro-publius/blackbox-datahub/pull/1)** |

> ### 🔎 The receipt: [PR #1](https://github.com/alejandro-publius/blackbox-datahub/pull/1) — opened by BlackBox, left open for judges
>
> Not a mock-up and not hand-assembled: an incident run reached `VERIFIED`, and the verified-repair path pushed `blackbox/fix-inc_17b054bc01` and opened that PR. The body is rendered **only** from recorded evidence — autonomous-authorship and synthetic-fixture disclosures, the blamed DataHub asset and field, the DataHub evidence census, quantitative tables from the cited profiles, the real unified diff, the before/after KPI, and 32/32 invariants. Read it the way you would review any machine-authored change.

**Inspect the actual run, no install required:** [`examples/sample-incident/`](examples/sample-incident/) — unedited incident state, full agent transcript, the real patch, and the agent's final report. Every eval run and its artifacts: [`evals/results/`](evals/results/).

## Why trust the agent?

Anyone can get an LLM to *say* it found a root cause. The design question is what happens when it's wrong — so every way this could produce a confident falsehood has a structural defense that does not depend on the model behaving well.

| Failure mode | Structural defense | Proof |
|---|---|---|
| The model invents a plausible root cause | `confirm_root_cause` is **rejected** unless the agent cites DataHub lineage/metadata evidence *and* quantitative evidence that actually references the blamed asset and field | [`tests/test_engine.py`](tests/test_engine.py) · rejection paths unit-tested |
| It declares healthy data broken | `NO_INCIDENT` is itself evidence-gated; a healthy-fixture control run must not invent an incident | `control_no_incident` eval — [`evals/results/`](evals/results/) |
| It makes the headline KPI look right by corrupting history | Repair must pass the **entire** invariant suite (incl. historical immutability) *and* land the KPI within 1% of the committed baseline | `bad_repair_rejected` eval: a naive blanket `/100` is caught |
| A prior run leaks the answer via DataHub writeback | Reset **scrubs BlackBox-written DataHub state**; the eval harness hard-fails on contamination | [`datahub/reset.py`](backend/blackbox/datahub/reset.py) · [`evals/harness.py`](evals/harness.py) |
| The "repair" is merely plausible text | The real transform file is modified, the warehouse is **rebuilt**, and the diff is computed by `difflib` from disk | real patch in [`examples/sample-incident/repair.patch`](examples/sample-incident/repair.patch) |
| Remote publication fails | PR creation runs strictly **after** verification and is non-gating; failure is recorded as evidence | [`tests/test_repair_pr.py`](tests/test_repair_pr.py) |

The LLM is never the final judge of a fact, a root cause, a repair's correctness, or an evaluation result.

## Architecture

```mermaid
flowchart TB
    User([On-call engineer]):::human
    UI["Next.js Command Center<br/><i>lineage canvas · evidence timeline</i>"]:::app
    API["FastAPI + SSE<br/><i>incident state machine</i>"]:::app
    LLM["Claude Investigator<br/><i>chooses what to investigate</i>"]:::llm
    GATE{{"Evidence gates<br/><i>machine-checked citations</i>"}}:::gate

    subgraph TOOLS["Deterministic tools — the only source of facts"]
        DH["DataHub client<br/><i>MCP Server · GraphQL · SDK v2</i>"]:::tool
        WH["DuckDB warehouse<br/><i>profiling · baselines · read-only SQL</i>"]:::tool
        PT["pytest<br/><i>32 pipeline invariants</i>"]:::tool
        GIT["git worktree<br/><i>difflib patch · fix branch</i>"]:::tool
    end

    HUB[("DataHub OSS v1.7<br/>schemas · contracts · ownership<br/>table + column lineage")]:::hub
    PIPE[["pipeline/transforms/*.sql<br/>DuckDB warehouse"]]:::data

    User -->|"'Revenue jumped 100×. Is this real?'"| UI
    UI <-->|"live state stream"| API
    API --> LLM
    LLM -->|"tool calls"| TOOLS
    TOOLS -->|"EvidenceItems (facts)"| GATE
    GATE -->|"accepted / rejected"| LLM

    DH <-->|"search · context · lineage BFS"| HUB
    WH <--> PIPE
    GIT -->|"applies repair"| PIPE
    PIPE -->|"rebuild"| PT
    PT -->|"32/32 + KPI in range<br/>= verified"| GIT
    GIT -->|"fix branch + commit"| ART[/"Git repair artifact"/]:::out
    GATE -->|"root cause proven"| HUB
    PT -->|"resolution + remediation note + tag"| HUB

    classDef human fill:#1f2937,stroke:#6b7280,color:#f9fafb
    classDef app fill:#0c4a6e,stroke:#38bdf8,color:#f0f9ff
    classDef llm fill:#4c1d95,stroke:#a78bfa,color:#f5f3ff
    classDef gate fill:#7c2d12,stroke:#fb923c,color:#fff7ed
    classDef tool fill:#064e3b,stroke:#34d399,color:#ecfdf5
    classDef hub fill:#1e3a8a,stroke:#60a5fa,color:#eff6ff
    classDef data fill:#292524,stroke:#a8a29e,color:#fafaf9
    classDef out fill:#713f12,stroke:#facc15,color:#fefce8
```

### Why this architecture matters

The split between the model and the tools is the whole design:

- **Claude chooses *what* to investigate** — which branch of the lineage to walk, which cohort to profile, which hypothesis is worth the next query. That is genuinely a judgment problem.
- **Deterministic code produces every fact.** `EvidenceItem`s come only from tool execution — DuckDB profiles, DataHub lineage reads, pytest runs, difflib diffs. The model never free-types a number, an edge, or a test result.
- **Root-cause claims are machine-checked before they're accepted.** `confirm_root_cause` is *rejected* unless the agent cites DataHub lineage/metadata evidence **and** quantitative evidence that actually references the blamed field and asset. An LLM cannot talk its way past this gate — [see the evidence-gate unit tests that hold it down](tests/test_engine.py).
- **A generated repair only counts if it executes.** The patch is applied to the real transform, the warehouse is rebuilt, and all 32 invariants plus the KPI must pass. A fix that restores the headline number while corrupting history is rejected and the agent iterates — [proven by the `bad_repair_rejected` eval](evals/README.md).
- **DataHub is both the map and the memory.** Topology, schemas, and the data contracts come *from* the graph; the incident, root cause, remediation note, and tag go *back into* it. The next engineer inherits the investigation.

Deep version — state machine, evidence-gating internals, verification loop: **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**.

## How DataHub is used

| Surface | Used for | Where |
|---|---|---|
| **Official DataHub MCP Server** (`uvx mcp-server-datahub`) | the agent's entity discovery, entity context, and **lineage BFS** — BlackBox is a real MCP client of DataHub's agent surface | [`datahub/mcp_bridge.py`](backend/blackbox/datahub/mcp_bridge.py), [`client.py`](backend/blackbox/datahub/client.py) |
| **Agent Context Kit** (`datahub-agent-context`) | the same reads over a **native embedded Python path** — no subprocess, no stdio hop; second in the transport chain | [`datahub/context_kit.py`](backend/blackbox/datahub/context_kit.py) |
| GraphQL API | dataset context, schema contracts, fallback lineage | [`client.py`](backend/blackbox/datahub/client.py) |
| **Column-level lineage** (`fineGrainedLineages`) | tracing the KPI to the exact upstream field | `client.py` (read) · `ingest.py` (emit) |
| Python SDK v2 | ingestion: warehouse-introspected schemas, data-contract field docs, ownership, tags, table **and** column lineage with the real transform SQL attached | [`datahub/ingest.py`](backend/blackbox/datahub/ingest.py) |
| **Incidents API** (`raiseIncident` / `updateIncidentStatus`) | ACTIVE incident the moment the cause is proven → `RESOLVED/FIXED` after verified repair | [`datahub/writeback.py`](backend/blackbox/datahub/writeback.py) |
| Dataset docs + tags | durable remediation note + `blackbox-remediated` tag | `writeback.py` |
| DataHub Skills | development workflow (skills registry plugin) | dev environment |

**Two transports, one graph.** DataHub's context graph is reachable both through the interoperable **MCP Server** and through the **Agent Context Kit**'s embedded Python path; reads try MCP → ACK → GraphQL and each fact records the transport that produced it (`EvidenceItem.transport`, visible in [`examples/sample-incident/`](examples/sample-incident/)). That is provenance for the reader, **not** a claim of independent corroboration — every transport ultimately reads the same DataHub instance. The kit's Cloud-gated tools (`ask_datahub_chat`, document search) are deliberately unused; this targets OSS/Core, and a test enforces it.

**The honest ablation.** `BLACKBOX_DISABLE_DATAHUB=true` disables the DataHub tools *and* writeback, and relaxes the confirm gate so the test isn't circular. Measured result: on this 5-transform fixture the ablated agent can still brute-force a correct diagnosis by reading transform files. We report that instead of claiming helplessness. What it loses is what matters at scale — the topology map (unworkable across thousands of models), the documented contract that makes the violation *provable*, every DataHub-grounded citation, and any durable record of the incident.

### Contributed back to DataHub OSS

Two upstream PRs, both **open** (not merged) at time of submission:

- **[datahub-skills#133](https://github.com/datahub-project/datahub-skills/pull/133)** — a new `datahub-incident-investigation` skill (16 files, +1259/−48) generalizing this project's methodology into a reusable, vendor-neutral agent workflow: symptom → lineage localization → competing hypotheses → evidence standards (necessity **and** sufficiency) → a 5-point confirmation gate → blast radius → remediation → verification → writeback. It names no warehouse, no schema, and nothing from this repo. Every command in it was executed against live DataHub OSS first — log in [`docs/SKILL_VALIDATION.md`](docs/SKILL_VALIDATION.md), which also captured three upstream-relevant findings: `health` returns a list rather than an object; `properties.description` can be `null` while `editableProperties.description` holds the real contract (an agent reading only the former calls a documented column undocumented); and OSS has no top-level `incident(urn:)` query.
- **[datahub#19046](https://github.com/datahub-project/datahub/pull/19046)** — troubleshooting docs for a silent `datahub docker quickstart` hang under Colima/Rancher Desktop/Podman (docker-py reads `DOCKER_HOST` but not Docker CLI contexts), which cost us ~15 minutes of a blank screen.

Full friction log: [`docs/DATAHUB_FEEDBACK_LOG.md`](docs/DATAHUB_FEEDBACK_LOG.md).

## Quickstart

Prereqs: Docker (≥8 GB RAM), Python 3.11+ via [uv](https://docs.astral.sh/uv/), Node 20+, DataHub CLI (`uv tool install acryl-datahub`), an Anthropic API key.

```bash
git clone https://github.com/alejandro-publius/blackbox-datahub && cd blackbox-datahub
make setup                       # uv sync + npm install
make datahub-up                  # DataHub OSS quickstart v1.7.0 (UI :9002, GMS :8080)
make datahub-setup               # mint PAT → .env, ingest pipeline metadata, verify round-trip
echo 'ANTHROPIC_API_KEY=sk-ant-...' >> .env
make demo-reset                  # seed the broken state (revenue silently ~93× too high)
make demo-run                    # backend :8400 + frontend :3000
```

Open <http://localhost:3000> → **Investigate Incident**. Colima users: `export DOCKER_HOST="unix://$HOME/.colima/default/docker.sock"` first — that's [PR #19046](https://github.com/datahub-project/datahub/pull/19046).

Verify without the UI:

```bash
make test                        # 32 pipeline invariants (incident mode fails exactly 7 — by design)
uv run pytest tests/             # 50 unit tests: evidence gates, repair/PR, ACK, tracing
uv run python scripts/vertical_slice.py   # full autonomous run in the terminal
uv run python scripts/demo_drill.py       # Playwright drill of the whole judge flow
make evals                       # eval battery (see evals/README.md)
```

## Evals

A deterministic harness, graded entirely by code — never by an LLM judging itself:

- **Seeded incident** — 11 machine-checked criteria including that the repair restores the committed baseline to within 1%, is scoped to the defective cohort, and touches exactly one file.
- **No-incident control** — healthy data must *not* produce an invented incident (false-positive guard).
- **Bad-repair rejection** — a naive blanket `/100` is caught by historical-immutability invariants, proving the verification gate has teeth.
- **DataHub ablation** — measures what the metadata graph actually contributes.

An independent adversarial review of the methodology ran during development; its critical findings — a writeback note that could contaminate later runs, and a circular ablation — were fixed. The harness now scrubs BlackBox-written DataHub state before every scenario and **hard-fails on contamination**. Details: [`evals/README.md`](evals/README.md) · results: [`evals/results/`](evals/results/).

## What's real vs. synthetic (full disclosure)

- **Synthetic (disclosed):** the retail pipeline's source data is generated deterministically (`pipeline/generate_sources.py`, seed 42), including the seeded incident — a payment-provider migration silently switching `raw_orders.amount` from dollars to integer cents on 2026-08-07 — plus a stale-FX distractor. `make demo-reset` restores that exact broken state.
- **Real:** the DuckDB warehouse and SQL transforms execute; DataHub OSS v1.7.0 runs locally with genuinely ingested metadata; every agent fact comes from a live tool call; the diff, tests, KPI recomputation, git branch, and DataHub incident are all real. Nothing in the prompts or metadata names the incident's nature — the agent discovers it (see [`CLAUDE.md`](CLAUDE.md), "No incident leakage").

## Pointing this at a real stack

DuckDB is here because the demo must run on a judge's laptop in one command. The engine is separated from it by three seams:

| Seam | Demo | Production swap |
|---|---|---|
| Query + profiling (`warehouse.py`) | DuckDB over local CSVs | Snowflake/BigQuery/Databricks — same `profile_column` / `compare_to_baseline` / `run_sql` signatures |
| Verification (`repair.verify_repair`) | warehouse rebuild + 32 pytest invariants | `dbt build --select state:modified+` + `dbt test` on a CI branch or zero-copy clone |
| Repair surface (`repair._resolve_transform`) | `pipeline/transforms/*.sql` | dbt models directory; the existing git-worktree flow opens the PR |

DataHub, the agent loop, the evidence gates, and the writeback are unchanged by those swaps. What stays honest: we demonstrate on a pipeline we authored, so treat the *incident realism* as illustrative and the *machinery* as the contribution.

## Observability (optional)

An investigation is a long autonomous trajectory, so it is traceable end to end. With the `tracing` extra installed and `BLACKBOX_TRACING=true`, one incident renders as **one trace** in a self-hosted [Arize Phoenix](https://github.com/Arize-ai/phoenix): an agent-phase span containing a span per deterministic tool call and per Anthropic call (auto-instrumented via OpenInference), annotated with the outcomes that matter — root-cause gate result, `N/N` invariants, post-repair KPI ratio, writeback status, repair branch.

```bash
uv sync --extra tracing && uv run phoenix serve      # UI on :6006
BLACKBOX_TRACING=true make demo-run
```

Off by default and genuinely optional: with the flag unset no tracing package is imported and every hook is a no-op — pinned by [7 regression tests](tests/test_tracing.py), one of which reproduces a real bug this caught (a double-`yield` on the span error path that turned any exception inside a traced block into a failed investigation). No secrets or raw rows are recorded.

## CI

Every push runs backend unit tests, the healthy fixture's 32/32 invariants, frontend lint + build, and a secrets scan — all deterministic, no API key or live DataHub required, so the checks also pass on a fork ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)).

## For judges

**45-second path:** the [hero screenshot](#-blackbox--autonomous-data-incident-response) → [the result](#see-it-work) → [why trust it](#why-trust-the-agent) → [architecture](#architecture) → [DataHub usage](#how-datahub-is-used) → the [real repair PR](#see-it-work) → [eval evidence](#evals) → [OSS contributions](#contributed-back-to-datahub-oss) → [how to run](#quickstart).

| | |
|---|---|
| **Proof every claim here is real** | [`docs/ACCEPTANCE.md`](docs/ACCEPTANCE.md) — every gate with runnable evidence + stated limitations |
| **A real run, unedited** | [`examples/sample-incident/`](examples/sample-incident/) |
| **Eval results + artifacts** | [`evals/results/`](evals/results/) |
| **Deep architecture** | [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) |
| **Self-assessment vs. rubric** | [`docs/JUDGE_SCORECARD.md`](docs/JUDGE_SCORECARD.md) — weaknesses included |
| **Demo walkthrough** | [`docs/DEMO_SCRIPT.md`](docs/DEMO_SCRIPT.md) |
| **Design source** | [Figma — Incident Command Center](https://www.figma.com/design/8wzbrWC5OTte3iUgh66XOp) (4 product states + tokens, authored via Figma MCP) |

## Repo map

`pipeline/` demo data stack + 32 invariants · `backend/blackbox/` engine, agent, DataHub integration, API · `frontend/` Next.js command center · `evals/` harness + results · `examples/` inspectable run artifacts · `docs/` architecture, acceptance, scorecard, demo script, feedback log · `scripts/` vertical slice + browser drill.

## License

Apache-2.0 — see [LICENSE](LICENSE).
