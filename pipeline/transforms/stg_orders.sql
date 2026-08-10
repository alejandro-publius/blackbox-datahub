-- stg_orders: cleaned order stream.
-- Excludes cancelled and refunded orders from the revenue path.
--
-- UNIT NORMALIZATION (incident 2026-08-07):
-- raw.raw_orders contract v1.3 specifies `amount` in MAJOR currency units
-- (e.g. 49.99 = $49.99). The cloudpay_v2 provider, rolled out 2026-08-07,
-- instead reports amounts in MINOR units (integer cents), which inflated
-- executive revenue by exactly 100x. We rescale that provider's amounts back
-- to major units here so every downstream consumer sees contract-compliant
-- values. Scoped strictly to cloudpay_v2; legacy_pos and shopgate are
-- untouched. Remove this branch once the provider is fixed upstream.
CREATE OR REPLACE TABLE staging.stg_orders AS
SELECT
    order_id,
    CAST(order_ts AS TIMESTAMP) AS order_ts,
    CAST(CAST(order_ts AS TIMESTAMP) AS DATE) AS order_day,
    customer_id,
    currency,
    CASE
        WHEN payment_processor = 'cloudpay_v2'
            THEN ROUND(CAST(amount AS DOUBLE) / 100.0, 2)
        ELSE CAST(amount AS DOUBLE)
    END AS amount,
    payment_processor,
    status
FROM raw.raw_orders
WHERE status NOT IN ('cancelled', 'refunded');
