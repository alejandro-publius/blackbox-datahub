# Sample incident run (unedited artifacts)

Artifacts from a real autonomous BlackBox run against the seeded demo incident
(eval scenario `positive_incident` in `evals/results/run_0007.json`: all 11
machine-graded checks passed, 13 turns, 24 tool calls, ~180s wall time).
Nothing here is hand-written: these files are copied verbatim from the run's
outputs. The run started from a scrubbed DataHub (the harness hard-fails if any
prior run's writeback note is still present — see `evals/harness.py`), so every
conclusion was derived from lineage, contracts, and warehouse evidence alone.

| File | What it is |
|---|---|
| `incident_state.json` | The complete final `IncidentState`: stages, lineage graph (from DataHub), hypotheses (incl. the eliminated FX distractor), all 15+ evidence items with raw tool payloads, patch, before/after test reports and KPI, git artifact, DataHub writeback record. |
| `transcript.jsonl` | Turn-by-turn agent transcript: every tool call and (truncated) result. |
| `repair.patch` | The verified unified diff applied to `pipeline/transforms/stg_orders.sql` — a targeted, provider-scoped unit normalization, not a blanket rewrite. |
| `final_report.md` | The agent's closing report: symptom → lineage → evidence (cited by id) → root cause → repair → verification. |

Highlights to look for:

- `root_cause.asset_urn` = `raw.raw_orders`, `field` = `amount` — proven with cited evidence:
  onset pinned to 2026-08-07 (revenue ratio 1.0 → exactly 100.0), order counts identical to
  baseline (scale defect, not volume), cloudpay_v2 median ~100× legacy median, and 100% of
  cloudpay_v2 amounts integer-valued vs ~1% for legacy processors.
- `hypotheses[]` shows the FX-staleness distractor investigated and **eliminated** with
  byte-identical rate evidence.
- `writeback` contains the real DataHub incident urn (raised ACTIVE at confirmation,
  RESOLVED/FIXED after 32/32 invariants passed and the KPI returned to 0.93×).
