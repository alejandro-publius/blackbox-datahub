INCIDENT RESOLVED — cloudpay_v2 cent/dollar unit violation (100.0x revenue inflation)

SYMPTOM
marts.exec_revenue_metric.revenue jumped from ~$27–35k/day to ~$2.74M/day starting 2026-08-07 (anomaly_ratio 93.3). compare_to_baseline showed revenue_ratio = 100.0 and aov_ratio = 100.0 for 2026-08-07/08/09 while order_count was IDENTICAL to baseline (334/349/327) — a pure price-scale defect, not a volume event [ev_c48d8d926b, ev_d9f465ed82].

LINEAGE (DataHub, UPSTREAM from the KPI)
marts.exec_revenue_metric.revenue <- marts.fct_revenue.revenue_usd <- {staging.stg_orders.amount, staging.stg_fx_rates.usd_rate} <- {raw.raw_orders.amount, raw.raw_fx_rates.usd_rate} [ev_521cefd14c]. Both revenue-bearing branches were tested.

EVIDENCE
• FX branch eliminated: usd_rate byte-identical across the onset boundary (EUR 1.070478, GBP 1.270418, CAD 0.718958, USD 1.0) on healthy 2026-08-06 and all three anomalous days; USD orders at rate 1.0 were inflated too, which FX cannot cause [ev_e8b3f5df66].
• Defect present in RAW: raw.raw_orders.amount segmented by payment_processor — through 2026-08-06 legacy_pos + shopgate, median 61.66/66.97, mean ~$79–86; from 2026-08-07 onward 100% of volume is cloudpay_v2 with median 6373.5/5955.5/6076.0 and mean $7,873/$7,781/$8,239, min 562, null_rate 0.0 [ev_bebe4ecbd0]. Same 100x step propagates to staging.stg_orders.amount [ev_41d5fe247d].
• Cents fingerprint: cloudpay_v2 amounts are 100.00% integer-valued (1062/1062 rows) vs 1.18% / 1.08% for legacy_pos / shopgate [ev_bdd675446a, ev_b15b1ef046].
• Contract violation: DataHub documents raw_orders.amount as "Order amount in MAJOR currency units as a decimal … Contract v1.3" and cloudpay_v2 as a new provider rolled out early August 2026 [ev_f0ba66acd6]. Semantic failure — type still validates as DOUBLE, unit is wrong.
• Necessary & sufficient: cohort share goes 0% -> 100% in one day, so a 100x unit error yields exactly 100.0x revenue and 100.0x median AOV with order_count untouched. Failing invariants were exactly the value-scale ones [ev_bce22ad7e1].

ROOT CAUSE
raw.raw_orders.amount for payment_processor = 'cloudpay_v2' (urn:li:dataset:(urn:li:dataPlatform:duckdb,raw.raw_orders,PROD)) — minor units (integer cents) emitted instead of major units from 2026-08-07. stg_orders was NOT the origin: it did a bare CAST(amount AS DOUBLE) pass-through with no unit normalization [ev_fe9d187603, ev_0fcbed02d4].

REPAIR
raw is an immutable vendor landing table, so the fix was placed at the documented normalization boundary, pipeline/transforms/stg_orders.sql: amount is divided by 100.0 in a CASE scoped strictly to payment_processor = 'cloudpay_v2', with a comment explaining the contract violation and when to remove the branch. Legacy history is byte-identical, no rows filtered, no data deleted, downstream fct_revenue/exec_revenue_metric untouched.

VERIFICATION
Warehouse rebuilt; full invariant suite 32/32 passed, 0 failures (previously failing max_usd_amount_sane, aov_median_in_range, revenue_continuity now pass). KPI anomaly_ratio restored to 0.9327 (from 93.3). Post-repair compare_to_baseline shows revenue_ratio = 1.0 and aov_ratio = 1.0 with unchanged order_count for 2026-08-07 ($26,557.18/334), 08-08 ($27,383.61/349) and 08-09 ($27,373.23/327), and pre-onset days 08-04..08-06 unchanged at ratio 1.0 [ev_a47d2a5c59]. Committed on branch blackbox/fix-inc_686e61287f @ ca08219; DataHub incident marked RESOLVED (FIXED).

FOLLOW-UP
Payments-platform team should have cloudpay_v2 emit major units per contract v1.3; once shipped, delete the CASE branch in stg_orders and add a raw-layer contract test asserting per-processor integer-value rate to catch minor-unit regressions at landing rather than at the executive KPI.