# BlackBox evals

Deterministic, non-self-graded evaluation of the autonomous incident-response
agent. Every grade is computed from the final `IncidentState` JSON, the
tool-call transcript, real pytest results, and real `git diff` state — never
from what the LLM says about itself.

## Run

```bash
# everything (sequential — scenarios share the warehouse and transforms)
uv run python -m evals.run_evals

# a subset
uv run python -m evals.run_evals --scenarios bad_repair_rejected
uv run python -m evals.run_evals --scenarios positive_incident,control_no_incident

# consistency measurement (N trials of the positive scenario)
uv run python -m evals.run_evals --scenarios positive_incident_repeat --trials 5

# one scenario by hand (what the orchestrator spawns internally)
uv run python -m evals.run_one positive_incident --out /tmp/result.json
uv run python -m evals.run_one datahub_ablation --out /tmp/result.json   # sets BLACKBOX_DISABLE_DATAHUB
```

Outputs: `evals/results/run_<seq>.json` (full structured results, incrementing
run number) and `evals/results/latest.md` (compact table + diffs for human
review). The table is also printed to stdout. Exit code is non-zero if any
scenario failed or errored (skips are fine).

## Architecture

`run_evals` (orchestrator) → one `uv run python -m evals.run_one <scenario>`
subprocess per scenario → `harness.run_scenario` → scenario runner + grader.

Each scenario gets its own subprocess because `blackbox.config.settings` is a
module-level pydantic-settings singleton: env-dependent behavior (notably
`BLACKBOX_DISABLE_DATAHUB=true` for the ablation) must be in `os.environ`
before the first `blackbox` import. `run_one` sets the env var from argv before
importing anything from `blackbox`; the orchestrator additionally injects it
into the subprocess env. A fresh process per scenario also guarantees clean
caches and client state. Scenarios still run **sequentially** — they share
`data/warehouse` and `pipeline/transforms/` on disk.

`harness.reset_environment(mode)` runs before every scenario:
`git checkout -- pipeline/transforms/` → delete `*.sql.orig` backups →
regenerate deterministic sources in the requested mode → rebuild the DuckDB
warehouse → clear `data/incidents/` (via a dedicated `IncidentStore`). After
each scenario the harness restores clean transforms and an incident-mode
warehouse, so the demo environment is always left ready.

## Scenarios — what each one proves

| scenario | needs | proves |
|---|---|---|
| `positive_incident` | LLM + DataHub | The full autonomous loop works on the seeded incident (cloudpay_v2 reports integer **cents** in `raw_orders.amount`): correct root cause (`raw.raw_orders` / `amount`), the semantic unit error is named, the stale-FX distractor is not blamed, the repair edits `stg_orders.sql`, is **targeted** (conditions on cloudpay/CASE-WHEN rather than blanket-dividing), passes all 32 invariants with the KPI back in range, and the incident is written back to DataHub. Also reports efficiency (turns / tool calls) and evidence coverage. |
| `control_no_incident` | LLM + DataHub | False-positive control: on healthy data with a vague "revenue felt slightly off" report, the agent concludes `NO_INCIDENT`, proposes no patch, and leaves `pipeline/transforms/` untouched. |
| `bad_repair_rejected` | nothing (no LLM, no DataHub) | The verification gate itself: a deliberately naive blanket `/ 100.0` patch (which makes the *latest* KPI look correct but corrupts all pre-cutover history) is applied via the real `blackbox.repair` path and must be **rejected**, with the historical-immutability/baseline invariants among the failures. Fully deterministic; runs in CI with no key. |
| `datahub_ablation` | LLM only | Measures what DataHub context contributes. With `BLACKBOX_DISABLE_DATAHUB=true` the DataHub tools *and* writeback error out **and the confirm gate's DataHub-citation requirement is relaxed** — otherwise the test would be circular (the gate demands DataHub evidence, so failure would prove wiring, not information value). Graded honestly: `run_executed` and `no_false_all_clear` are pass/fail; identification accuracy, turns and writeback are **reported**. Measured result: on this 5-transform fixture the ablated agent can still brute-force a correct diagnosis by reading transform files. What it loses is the topology map, the contract that makes the violation provable, every DataHub-grounded citation, and any durable record. We report that rather than claiming helplessness. |
| `positive_incident_repeat` | LLM + DataHub | Same as `positive_incident`, run `--trials` times; the run JSON includes a pass-rate consistency aggregate. |

## What "skipped" means

The harness **never fakes a result**. Before running, each scenario's
preconditions are checked fail-fast; if one fails, the result status is
`skipped: <reason>` and nothing is executed or graded:

- `skipped: ANTHROPIC_API_KEY missing` — LLM scenarios need a key (set it in
  `.env` or the environment; read via `blackbox.config.settings`).
- `skipped: DataHub GMS unreachable at <url>` — scenarios whose agent tools and
  grading depend on DataHub ping GMS first (`datahub docker quickstart`).
- `skipped: warehouse not buildable: ...` — the fixture reset (source
  generation + pipeline build) failed.

A skip is expected on a laptop without the key or without DataHub running;
`bad_repair_rejected` should always run and pass anywhere.
