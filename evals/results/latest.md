# BlackBox eval run 6

- started: 2026-08-10T07:06:13.415561+00:00
- finished: 2026-08-10T07:11:42.401221+00:00
- full results: `evals/results/run_0006.json`

| scenario | status | key checks | notes |
|---|---|---|---|
| positive_incident | passed | terminal_ok ✓ root_cause_correct ✓ semantic_identified ✓ distractor_avoided ✓ repair_correct_file ✓ repair_verified ✓ repair_targeted ✓ repair_restores_baseline ✓ repair_single_file ✓ evidence_coverage ✓ writeback_done ✓ | stage=WRITEBACK_COMPLETE; turns=13; tool_calls=24; 145.26s |
| datahub_ablation | passed | run_executed ✓ no_false_all_clear ✓ | ablated run ended stage=WRITEBACK_COMPLETE, root_cause=correct; 182.89s |

## positive_incident — passed
- **root_cause**: `{"summary": "The new payment processor cloudpay_v2 began reporting raw.raw_orders.amount in cents on 2026-08-07, and the pipeline ingests it as dollars \u2014 inflating executive revenue exactly 100x.", "asset_urn": "urn:li:dataset:(urn:li:dataPlatform:duckdb,raw.raw_orders,PROD)", "field": "amount", "detail": "Onset 2026-08-07. Lineage path: raw.raw_orders.amount \u2192 staging.stg_orders.amount \u2192 marts.fct_revenue.revenue_usd \u2192 marts.exec_revenue_metric.revenue [ev_37a5a0b7a1]. Profiling raw.raw_orders.amount segmented by payment_processor shows the exact break: 2026-08-04..06 traf`
- **final_summary**: `"**INCIDENT CONFIRMED AND RESOLVED \u2014 unit-of-measure regression from a payment-processor migration.**\n\n**Symptom.** Executive revenue for 2026-08-09 read $2,737,323.50 against an expected $29,349.39 (anomaly_ratio 93.3x); the jump began abruptly on 2026-08-07 after 87 clean days [ev_4acd11cce7]. Baseline comparison showed the distortion was exactly 100.0x on 08-07, 08-08 and 08-09 for both revenue AND median AOV, while order_count matched baseline exactly (334/349/327) \u2014 proving a per-unit scaling defect, not a volume or duplication event [ev_b1be6b6a49].\n\n**Lineage (from DataHub`

```diff
--- a/pipeline/transforms/stg_orders.sql
+++ b/pipeline/transforms/stg_orders.sql
@@ -1,5 +1,12 @@
 -- stg_orders: cleaned order stream.
 -- Excludes cancelled and refunded orders from the revenue path.
+--
+-- Unit normalization (incident 2026-08-07):
+-- The cloudpay_v2 provider (rolled out 2026-08-07) reports `amount` in MINOR
+-- currency units (cents), violating raw_orders contract v1.3 which specifies
+-- MAJOR currency units with two decimals. We rescale that provider's amounts
+-- by 1/100 here so every downstream consumer sees contract-compliant major
+-- units. legacy_pos and shopgate already comply and are left untouched.
 CREATE OR REPLACE TABLE staging.stg_orders AS
 SELECT
     order_id,
@@ -7,7 +14,11 @@
     CAST(CAST(order_ts AS TIMESTAMP) AS DATE) AS order_day,
     customer_id,
     currency,
-    CAST(amount AS DOUBLE) AS amount,
+    CASE
+        WHEN payment_processor = 'cloudpay_v2'
+            THEN ROUND(CAST(amount AS DOUBLE) / 100.0, 2)
+        ELSE CAST(amount AS DOUBLE)
+    END AS amount,
     payment_processor,
     status
 FROM raw.raw_orders
```

## datahub_ablation — passed
- **root_cause**: `{"summary": "A payment-processor migration to cloudpay_v2 on 2026-08-07 began emitting raw.raw_orders.amount in minor units (cents), and the pipeline ingested them as dollars \u2014 inflating executive revenue exactly 100x.", "asset_urn": "urn:li:dataset:(urn:li:dataPlatform:duckdb,raw.raw_orders,PROD)", "field": "amount", "detail": "SYMPTOM: marts.exec_revenue_metric reports revenue 2,737,323.50 on 2026-08-09 vs expected 29,349.39. compare_to_baseline [ev_fb838a8137] shows revenue_ratio EXACTLY 100.0 on 2026-08-07/08/09 and 1.0 on every prior day, with aov_median_usd 6483.50/5972.00/6213.00 v`
- **final_summary**: `"INCIDENT RESOLVED \u2014 the 100x revenue spike was real data corruption, not real revenue.\n\nSYMPTOM\nExecutive dashboard revenue for 2026-08-09 read 2,737,323.50 vs an expected 29,349.39 [ev_d7a9b73188]. compare_to_baseline [ev_fb838a8137] pinned the onset to 2026-08-07 and showed the ratio was EXACTLY 100.0 on 08-07/08/09 and 1.0 on every prior day. Critically, order_count matched baseline exactly (334/349/327) while aov_median went 64.84\u21926483.50, 59.72\u21925972.00, 62.13\u21926213.00. A pure per-unit scale error, not a volume event \u2014 which immediately ruled out duplicate rows,`
