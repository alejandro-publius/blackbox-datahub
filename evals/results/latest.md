# BlackBox eval run 8

- started: 2026-08-10T09:33:58.379075+00:00
- finished: 2026-08-10T09:37:24.434879+00:00
- full results: `evals/results/run_0008.json`

| scenario | status | key checks | notes |
|---|---|---|---|
| bad_repair_rejected | passed | bad_repair_rejected ✓ immutability_caught ✓ environment_restored ✓ | verify gate returned ok=False; 11/32 invariants failed; immutability caught it (4 historical failures); 19.74s |
| control_no_incident | failed | stage_no_incident ✗ no_patch ✓ transforms_unchanged ✓ no_false_positive ✓ | stage=FAILED; error: BadRequestError: Error code: 400 - {'type': 'error', 'error': {'type': 'invalid_request_error', 'message': 'Your credit balance is too low to access the Anthropic API. Please go to Plans & Billing to… |

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

