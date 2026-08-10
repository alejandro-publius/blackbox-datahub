# BlackBox eval run 4

- started: 2026-08-10T05:48:13.336731+00:00
- finished: 2026-08-10T05:50:22.540976+00:00
- full results: `evals/results/run_0004.json`

| scenario | status | key checks | notes |
|---|---|---|---|
| positive_incident | passed | terminal_ok ✓ root_cause_correct ✓ semantic_identified ✓ distractor_avoided ✓ repair_correct_file ✓ repair_verified ✓ repair_targeted ✓ evidence_coverage ✓ writeback_done ✓ | stage=WRITEBACK_COMPLETE; turns=13; tool_calls=22; 128.71s |

## positive_incident — passed
- **root_cause**: `{"summary": "The cloudpay_v2 processor migration on 2026-08-07 began reporting raw_orders.amount in cents while the contract mandates major currency units, and stg_orders passed it through unnormalized \u2014 inflating executive revenue exactly 100x.", "asset_urn": "urn:li:dataset:(urn:li:dataPlatform:duckdb,raw.raw_orders,PROD)", "field": "amount", "detail": "Symptom: marts.exec_revenue_metric.revenue jumped from ~$27k/day to ~$2.74M/day, anomaly_ratio 93.3x. Onset is sharp and dated: 2026-08-06 revenue_ratio 1.0, 2026-08-07 revenue_ratio 100.0, and 08-08/08-09 also exactly 100.0 [ev_86836d9b`
- **final_summary**: `"## Incident: 100x revenue spike on executive dashboard \u2014 NOT real. Root cause found, repaired, verified.\n\n**Verdict:** genuine data incident (unit-semantics defect), now resolved. Revenue was never real.\n\n### Symptom\n`marts.exec_revenue_metric.revenue` jumped from ~$27k/day to ~$2.74M/day (anomaly_ratio 93.3x) [ev_c957e5b969]. Onset was sharp and exact: 2026-08-06 ratio 1.0 \u2192 2026-08-07 ratio **100.0**, holding at 100.0 on 08-08 and 08-09 [ev_86836d9b65].\n\nThe giveaway: **order_count matched the committed baseline exactly** on every affected day (334/334, 349/349, 327/327) wh`

```diff
--- a/pipeline/transforms/stg_orders.sql
+++ b/pipeline/transforms/stg_orders.sql
@@ -1,5 +1,16 @@
 -- stg_orders: cleaned order stream.
 -- Excludes cancelled and refunded orders from the revenue path.
+--
+-- UNIT NORMALIZATION (incident: 100x revenue spike from 2026-08-07)
+-- raw_orders.amount is contracted (payments-platform v1.3) to be in MAJOR
+-- currency units (e.g. 49.99 = $49.99). The cloudpay_v2 provider, introduced
+-- by the migration that began 2026-08-07, violates that contract and emits
+-- MINOR units (cents): 100% of its rows are integer-valued and its median
+-- amount is ~100x that of legacy_pos/shopgate.
+-- We convert cloudpay_v2 amounts back to major units here, at the staging
+-- boundary, so that every downstream consumer of stg_orders.amount sees a
+-- single, contract-compliant unit. No rows are dropped or hidden.
+-- Remove this clause once the provider is fixed upstream.
 CREATE OR REPLACE TABLE staging.stg_orders AS
 SELECT
     order_id,
@@ -7,7 +18,11 @@
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

