## Incident: 100x revenue spike on executive dashboard — NOT real. Root cause found, repaired, verified.

**Verdict:** genuine data incident (unit-semantics defect), now resolved. Revenue was never real.

### Symptom
`marts.exec_revenue_metric.revenue` jumped from ~$27k/day to ~$2.74M/day (anomaly_ratio 93.3x) [ev_c957e5b969]. Onset was sharp and exact: 2026-08-06 ratio 1.0 → 2026-08-07 ratio **100.0**, holding at 100.0 on 08-08 and 08-09 [ev_86836d9b65].

The giveaway: **order_count matched the committed baseline exactly** on every affected day (334/334, 349/349, 327/327) while median AOV was exactly 100x baseline ($6,483.50 vs $64.84) [ev_86836d9b65]. Same orders, same customers, 100x the money — that is arithmetic, not commerce.

### Lineage (DataHub, UPSTREAM)
`exec_revenue_metric` ← `marts.fct_revenue` ← {`staging.stg_orders`, `staging.stg_fx_rates`}; `stg_orders` ← `raw.raw_orders`, with column-level edges `raw_orders.amount` → `stg_orders.amount` → `fct_revenue.revenue_usd` → `exec_revenue_metric.revenue` [ev_c16d6ce4ca]. Two candidate branches: orders and FX.

### Evidence
- **FX branch eliminated:** `usd_rate` is identical across the onset (EUR 1.070478, GBP 1.270418, CAD 0.718958, USD 1.0 on 08-05→08-09) [ev_78f1e93383].
- **Cohort isolated:** on 2026-08-07 the processor mix cuts over completely — `legacy_pos`/`shopgate` stop on 08-06, `cloudpay_v2` becomes 100% of orders (1,010 rows) [ev_a0cfe5c5b9][ev_e997bf3b56].
- **Decisive fingerprint:** **all 1,010** cloudpay_v2 amounts are exactly integer-valued (334/334, 349/349, 327/327), versus ~1% for legacy processors (22,080/22,347 and 9,325/9,420 non-integer) [ev_e4865b6b04][ev_e997bf3b56]. Integer-only values at 100x scale = minor units (cents). Its min of 562 = $5.62 matches the $5.00 price floor of the other processors.
- **Contract violation:** `raw_orders.amount` is documented as "MAJOR currency units as a decimal (e.g. 49.99 = $49.99). Contract v1.3", and `payment_processor` notes "cloudpay_v2 (provider migration began **2026-08-07**)" — the defect date equals the documented migration date [ev_c3a5049a70].

### Root cause
`raw.raw_orders.amount` — the **cloudpay_v2** provider migration began emitting amounts in **cents** instead of dollars on 2026-08-07, violating contract v1.3. `stg_orders.sql` passed the value through with a bare `CAST(amount AS DOUBLE)` and no unit normalization [ev_66dc99bbfc], and `fct_revenue.sql` multiplied it straight by `usd_rate` [ev_af1682b298], so the 100x error reached the executive KPI untouched.

*Note:* the `stg_orders` DataHub description carried an "incident history" claiming this exact issue was already remediated. The transform source contained no normalization and the KPI was live-anomalous, so that documentation was stale — I treated it as a claim to verify, not as evidence.

### Repair
Patched `pipeline/transforms/stg_orders.sql`: a provider-scoped `CASE` converting only `cloudpay_v2` amounts to major units (`/100.0`). Minimal and honest — no rows filtered, no history rewritten, all 1,010 orders retained, legacy processors untouched, and the metric layer not manipulated to mask the number. Scoped by processor rather than date so future cloudpay_v2 batches stay correct.

### Verification
- **32/32 invariants passed**, 0 failures.
- KPI anomaly ratio: 93.27x → **0.93x** (target ~1.0).
- Post-rebuild, all three affected days reconcile to baseline exactly: 08-07 $26,557.18, 08-08 $27,383.61, 08-09 $27,373.23 — revenue_ratio and aov_ratio **1.0**, with order counts unchanged [ev_6d414ad32c].
- Shipped on branch `blackbox/fix-inc_631dde6595` @ `838c73f`; DataHub incident marked RESOLVED.

### Follow-up for humans
Escalate to the payments-platform team (owner: Jordan Lee) — cloudpay_v2 should be fixed at source to emit major units; the staging clause is a compensating control and should be removed once upstream complies. Recommend a persistent invariant asserting per-processor AOV stays within a sane band, which would have caught this on day one.