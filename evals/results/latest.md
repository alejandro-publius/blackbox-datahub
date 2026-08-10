# BlackBox eval run 7

- started: 2026-08-10T07:14:23.433993+00:00
- finished: 2026-08-10T07:20:24.443059+00:00
- full results: `evals/results/run_0007.json`

| scenario | status | key checks | notes |
|---|---|---|---|
| positive_incident | passed | terminal_ok ✓ root_cause_correct ✓ semantic_identified ✓ distractor_avoided ✓ repair_correct_file ✓ repair_verified ✓ repair_targeted ✓ repair_restores_baseline ✓ repair_single_file ✓ evidence_coverage ✓ writeback_done ✓ | stage=WRITEBACK_COMPLETE; turns=13; tool_calls=24; 180.1s |
| datahub_ablation | passed | run_executed ✓ no_false_all_clear ✓ | ablated run ended stage=VERIFIED, root_cause=correct; 180.06s |

## positive_incident — passed
- **root_cause**: `{"summary": "On 2026-08-07 the payments platform cut the entire order feed over to the new cloudpay_v2 processor, which reports raw_orders.amount in minor units (cents) instead of the contractually required major units \u2014 silently multiplying executive revenue by exactly 100x.", "asset_urn": "urn:li:dataset:(urn:li:dataPlatform:duckdb,raw.raw_orders,PROD)", "field": "amount", "detail": "SYMPTOM: marts.exec_revenue_metric.revenue = $2,737,323.50 on 2026-08-09 vs expected $29,349.39 (anomaly_ratio 93.3) [ev_316112b8a3]. The break is exactly 100.0x on 2026-08-07/08/09 and 1.0x on every prior `
- **final_summary**: `"## Incident resolved \u2014 the 100x revenue jump was NOT real.\n\n**SYMPTOM.** `marts.exec_revenue_metric.revenue` reported $2,737,323.50 for 2026-08-09 against an expected $29,349.39 (anomaly_ratio 93.3) [ev_316112b8a3]. Baseline comparison localized a razor-sharp onset: exactly **100.0x on 2026-08-07, 08-08 and 08-09**, and exactly 1.0x on every prior day. The decisive clue was that `order_count` was **identical** to baseline on all three days (334/349/327) while `aov_median_usd` was inflated 100x (6483.5 vs 64.84) [ev_5b29c51a06] \u2014 this was a per-unit *amount* defect, not volume, dup`

```diff
--- a/pipeline/transforms/stg_orders.sql
+++ b/pipeline/transforms/stg_orders.sql
@@ -1,5 +1,18 @@
 -- stg_orders: cleaned order stream.
 -- Excludes cancelled and refunded orders from the revenue path.
+--
+-- UNIT NORMALIZATION (incident 2026-08-07, exec revenue 100x):
+-- The payments platform rolled out a new provider, `cloudpay_v2`, on 2026-08-07.
+-- Contrary to payments-platform contract v1.3 (`amount` is a decimal in MAJOR
+-- currency units, e.g. 49.99 = $49.99), cloudpay_v2 reports `amount` in MINOR
+-- units (cents): 100% of its rows are integer-valued and its median order is
+-- ~6076 where legacy_pos/shopgate report ~62. Left uncorrected this inflated
+-- revenue_usd and aov_median_usd by exactly 100x.
+--
+-- We normalize cloudpay_v2 back to major units here, at the staging boundary
+-- where the "major currency units" contract is asserted. legacy_pos and
+-- shopgate are passed through untouched so healthy history is unchanged.
+-- Remove this branch only once the provider is fixed upstream to emit decimals.
 CREATE OR REPLACE TABLE staging.stg_orders AS
 SELECT
     order_id,
@@ -7,7 +20,11 @@
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
- **root_cause**: `{"summary": "A payment-processor cutover to cloudpay_v2 on 2026-08-07 began emitting raw.raw_orders.amount in minor units (cents) instead of dollars, multiplying executive revenue by exactly 100x.", "asset_urn": "urn:li:dataset:(urn:li:dataPlatform:duckdb,raw.raw_orders,PROD)", "field": "amount", "detail": "Symptom: exec revenue for 2026-08-09 is $2,737,323.50 vs expected $29,349.39; baseline comparison shows revenue_ratio exactly 100.0x on 2026-08-07/08/09 and median AOV 100.0x ($6,213.00 vs $62.13) while order_count is IDENTICAL to baseline (334/349/327) \u2014 a pure per-unit scaling defect`
- **final_summary**: `"## Incident: \"Revenue jumped ~100x on the executive dashboard\" \u2014 CONFIRMED DATA INCIDENT, resolved.\n\n**Answer to on-call: No, it is not real.** It was a unit-of-measure defect from a payment-processor cutover.\n\n### Symptom (quantified)\n`marts.exec_revenue_metric` reported $2,737,323.50 for 2026-08-09 against an expected $29,349.39 [ev_caa76f59e7]. Baseline comparison isolated the onset precisely: revenue_ratio and median-AOV ratio are **exactly 100.0x on 2026-08-07, 08-08 and 08-09**, and 1.0x on every prior day, while **order_count is identical to baseline** (334/349/327) [ev_0b9`
