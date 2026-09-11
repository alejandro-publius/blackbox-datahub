# Changelog

All notable changes to this project are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Dates are taken from
`git log --date=short`.

## [Unreleased]

### Added
- `tests/test_engine.py`: five new evidence-gate tests — unknown `evidence_ids`
  are rejected, quantitative evidence that never names the blamed asset is
  rejected, and (new coverage) evidence that is topically on-point but
  numerically contradicts the claim being made is rejected for both
  `confirm_root_cause` and `declare_no_incident`.
- `pyproject.toml`: an explicit `[tool.ruff.lint] select` so `ruff check`
  enforces a fixed, intentional rule set instead of drifting with whichever
  rules a given ruff release enables by default.
- `.github/workflows/ci.yml`: a `lint` job running `ruff check .`.
- `.pre-commit-config.yaml`, `CITATION.cff`, this `CHANGELOG.md`.
- `README.md`: a grand-prize note under the title, linking DataHub's
  winners write-up and the Devpost project page.

### Fixed
- `backend/blackbox/agent/tools.py`: `confirm_root_cause` and
  `declare_no_incident` accepted evidence that named the right field/asset (or
  the right evidence *kind*) without checking that the evidence's own numbers
  actually supported the conclusion — a citation that reads as normal could
  "confirm" an incident, and a citation showing a live anomaly could "declare"
  no incident. Both gates now also require the cited evidence's ratio-like
  values to agree with the claim.
- Six ruff findings under the newly-pinned rule set: unused imports in
  `tools.py`, `api.py`, `store.py`, `datahub/ingest.py`; an f-string with no
  placeholders in `datahub/writeback.py`; an ambiguous variable name (`l`) in
  `evals/scenarios.py`.
- README: the unit-test count (`50` → `55`, both places it's quoted) after the
  additions above.

## [0.1.0] - 2026-09-04

### Added
- Core engine: deterministic incident fixture, evidence-gated investigation
  state machine, DataHub integration, FastAPI backend, Next.js command-center
  frontend scaffold (2026-08-09).
- Two DataHub read transports — the official MCP Server and the embedded
  Agent Context Kit — alongside GraphQL, each fact tagged with the transport
  that produced it.
- DataHub writeback: `raiseIncident` at confirmed root cause,
  `updateIncidentStatus` to `RESOLVED/FIXED` after a verified repair, plus a
  durable remediation note and tag.
- Autonomous repair path: real git worktree + `difflib` patch, warehouse
  rebuild, full invariant re-run, and an opt-in (`BLACKBOX_CREATE_PR`,
  default off) real GitHub PR — isolated so publication failure never changes
  a verified outcome.
- Eval harness and battery: seeded incident, no-incident control, bad-repair
  rejection, and a DataHub ablation that measures what the metadata graph
  actually contributes.
- Read-only SQL sandboxing: `run_sql` denylist plus DuckDB-level
  `enable_external_access=false`, closing a filesystem-exfiltration path
  found in a security review (2026-08-09).
- Optional Phoenix/OpenTelemetry tracing (`BLACKBOX_TRACING`, default off),
  one trace per incident, off-by-default with 7 regression tests including a
  double-`yield` bug caught on the span error path.
- `make judge-check`: a deterministic, keyless proof path — backend unit
  tests, the healthy fixture's invariants, frontend lint/build, and a
  tracked-secret scan — mirroring CI.
- Two upstream DataHub OSS contributions: `datahub-skills#133` (an
  `datahub-incident-investigation` skill) and `datahub#19046` (quickstart
  troubleshooting docs for Docker-context detection under Colima/Rancher/
  Podman).

### Fixed
- Adversarial-review findings: a writeback note that could contaminate later
  eval runs, and a circular DataHub ablation — the harness now scrubs
  BlackBox-written DataHub state before every scenario and hard-fails on
  contamination (2026-08-10).
- CI: pinned `setup-uv` to a version compatible with the `uv.lock` revision;
  asserted the invariant count from the JUnit XML report instead of grepping
  pytest's prose summary, so a shrunken suite can't silently read as green.

### Changed
- README rewritten for a visual-first read: inline Mermaid architecture
  diagram, real screenshots, stale-claim purge (2026-08-10).
- `.github/workflows/ci.yml`: `actions/checkout` and `actions/setup-node`
  bumped to their current majors (2026-09-04).
