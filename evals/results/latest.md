# BlackBox eval run 5

- started: 2026-08-10T05:52:15.403629+00:00
- finished: 2026-08-10T05:59:34.255945+00:00
- full results: `evals/results/run_0005.json`

| scenario | status | key checks | notes |
|---|---|---|---|
| control_no_incident | passed | stage_no_incident ✓ no_patch ✓ transforms_unchanged ✓ no_false_positive ✓ | stage=NO_INCIDENT; 132.65s |
| bad_repair_rejected | passed | bad_repair_rejected ✓ immutability_caught ✓ environment_restored ✓ | verify gate returned ok=False; 11/32 invariants failed; immutability caught it (4 historical failures); 3.18s |
| datahub_ablation | passed | run_executed ✓ datahub_load_bearing ✓ | error: investigation phase ended without reaching a verified terminal state; ablated run ended stage=FAILED, root_cause=none; 302.29s |

## control_no_incident — passed
- **final_summary**: `"Revenue is healthy; there is no data defect to repair.\n\nQuantitative check: every one of the last 14 days matches the committed baseline (pipeline/baselines/daily_revenue_baseline.json) exactly \u2014 revenue_ratio = 1.0000 and aov_ratio = 1.0000 on all days, with identical order counts [ev_2c9bb3cd43]; the full 90-day series shows revenue_usd == baseline for every day [ev_b3d0acd2af]. The executive KPI's anomaly_ratio of 0.9327 on 2026-08-09 (status \"ok\") is ordinary weekend seasonality: 2026-08-09 is a Sunday, and prior Sundays sit in the same band (2026-08-02: 30,245; 2026-07-26: 28,05`
## bad_repair_rejected — passed
- **failing_tests**: `["pipeline.invariants.test_invariants::test_aov_median_in_range[2026-08-03]", "pipeline.invariants.test_invariants::test_aov_median_in_range[2026-08-04]", "pipeline.invariants.test_invariants::test_aov_median_in_range[2026-08-05]", "pipeline.invariants.test_invariants::test_aov_median_in_range[2026-08-06]", "pipeline.invariants.test_invariants::test_revenue_continuity[2026-08-07]", "pipeline.invariants.test_invariants::test_revenue_continuity[2026-08-08]", "pipeline.invariants.test_invariants::test_revenue_continuity[2026-08-09]", "pipeline.invariants.test_invariants::test_historical_immutabil`
- **immutability_failures**: `["pipeline.invariants.test_invariants::test_historical_immutability_aggregate"]`

```diff
--- a/pipeline/transforms/stg_orders.sql
+++ b/pipeline/transforms/stg_orders.sql
@@ -7,7 +7,7 @@
     CAST(CAST(order_ts AS TIMESTAMP) AS DATE) AS order_day,
     customer_id,
     currency,
-    CAST(amount AS DOUBLE) AS amount,
+    CAST(amount AS DOUBLE) / 100.0 AS amount,
     payment_processor,
     status
 FROM raw.raw_orders
```

## datahub_ablation — passed
- **final_summary**: `"INCIDENT: REAL \u2014 revenue inflated exactly 100x from 2026-08-07. Root cause identified with warehouse-grade proof, but the platform's confirm/repair gate could NOT be satisfied because DataHub has been unreachable for the entire investigation (~50 consecutive failed calls to datahub_search / datahub_get_dataset / datahub_lineage). No repair was applied; the pipeline is still in a failing state and needs a human to apply the patch below (or confirm once DataHub is back).\n\nSYMPTOM (quantified)\n- marts.exec_revenue_metric, kpi_day 2026-08-09: revenue 2,737,323.50 vs expected 29,349.39, an`
