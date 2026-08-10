import type {
  IncidentState,
  LineageGraph,
  MetricSnapshot,
} from "./types";

/**
 * PLACEHOLDER FIXTURES — dev preview only.
 *
 * Consumed exclusively through the `?preview=1[&state=…]` dev preview mode in
 * Dashboard.tsx, which always renders the "PREVIEW DATA" watermark badge.
 * Placeholder data must NEVER be rendered without that watermark. Do not
 * import these into live data paths.
 *
 * Numbers/shapes mirror the REAL demo fixture (pipeline/generate_sources.py):
 * ~$29k/day baseline, anomalous kpi_day 2026-08-09 at ~$2.74M (93× expected),
 * 8 duckdb assets raw_* → stg_* → fct_revenue → exec_revenue_metric, and the
 * cloudpay_v2 integer-cents encoding as root cause.
 */

const URN = (table: string) =>
  `urn:li:dataset:(urn:li:dataPlatform:duckdb,${table},PROD)`;

/* ------------------------------------------------------------------ */
/* Metrics — 28 daily points ending at the anomalous kpi_day           */
/* ------------------------------------------------------------------ */

// Healthy-baseline revenue per day (deterministic, ~$29k ± $3k).
const BASELINES = [
  29684.2, 27102.55, 31240.87, 28873.11, 26492.4, 30118.62, 32405.9,
  28210.34, 29957.03, 27684.72, 30861.15, 29244.58, 26930.81, 31514.27,
  28466.9, 30273.44, 27891.06, 29610.5, 32010.19, 28755.62, 26557.18,
  30489.71, 29131.86, 27948.33, 31122.04, 26557.18, 27383.61, 27373.23,
];

// The provider cutover happened 2026-08-07: the last 3 days report integer
// cents → ~100× inflated revenue.
const SPIKED: Record<string, number> = {
  "2026-08-07": 2655717.7,
  "2026-08-08": 2738360.82,
  "2026-08-09": 2737323.5,
};

function dayString(offsetFromEnd: number): string {
  // 28 days ending 2026-08-09
  const d = new Date(Date.UTC(2026, 7, 9));
  d.setUTCDate(d.getUTCDate() - offsetFromEnd);
  return d.toISOString().slice(0, 10);
}

const DAILY = BASELINES.map((baseline, i) => {
  const day = dayString(BASELINES.length - 1 - i);
  return {
    day,
    revenue_usd: SPIKED[day] ?? baseline,
    baseline,
  };
});

export const PLACEHOLDER_METRICS: MetricSnapshot = {
  kpi_day: "2026-08-09",
  revenue: 2737323.5,
  expected_revenue: 29349.39,
  anomaly_ratio: 93.2668,
  status: "anomalous",
  daily: DAILY,
};

export const PLACEHOLDER_METRICS_AFTER: MetricSnapshot = {
  kpi_day: "2026-08-09",
  revenue: 27373.24,
  expected_revenue: 29349.39,
  anomaly_ratio: 0.9327,
  status: "ok",
  daily: DAILY.map((d) =>
    d.day in SPIKED ? { ...d, revenue_usd: SPIKED[d.day] / 100 } : d,
  ),
};

/* ------------------------------------------------------------------ */
/* Lineage — the real 8-asset duckdb graph                             */
/* ------------------------------------------------------------------ */

export const PLACEHOLDER_GRAPH: LineageGraph = {
  nodes: [
    { urn: URN("raw.raw_orders"), name: "raw.raw_orders", platform: "duckdb", layer: "source", status: "healthy" },
    { urn: URN("raw.raw_customers"), name: "raw.raw_customers", platform: "duckdb", layer: "source", status: "healthy" },
    { urn: URN("raw.raw_fx_rates"), name: "raw.raw_fx_rates", platform: "duckdb", layer: "source", status: "healthy" },
    { urn: URN("staging.stg_orders"), name: "staging.stg_orders", platform: "duckdb", layer: "staging", status: "healthy" },
    { urn: URN("staging.stg_customers"), name: "staging.stg_customers", platform: "duckdb", layer: "staging", status: "healthy" },
    { urn: URN("staging.stg_fx_rates"), name: "staging.stg_fx_rates", platform: "duckdb", layer: "staging", status: "healthy" },
    { urn: URN("marts.fct_revenue"), name: "marts.fct_revenue", platform: "duckdb", layer: "marts", status: "healthy" },
    { urn: URN("marts.exec_revenue_metric"), name: "marts.exec_revenue_metric", platform: "duckdb", layer: "metric", status: "affected" },
  ],
  edges: [
    {
      source: URN("raw.raw_orders"),
      target: URN("staging.stg_orders"),
      columns: [{ upstream: "amount", downstream: "amount" }],
    },
    { source: URN("raw.raw_customers"), target: URN("staging.stg_customers") },
    {
      source: URN("raw.raw_fx_rates"),
      target: URN("staging.stg_fx_rates"),
      columns: [{ upstream: "usd_rate", downstream: "usd_rate" }],
    },
    {
      source: URN("staging.stg_orders"),
      target: URN("marts.fct_revenue"),
      columns: [{ upstream: "amount", downstream: "revenue_usd" }],
    },
    {
      source: URN("staging.stg_fx_rates"),
      target: URN("marts.fct_revenue"),
      columns: [{ upstream: "usd_rate", downstream: "revenue_usd" }],
    },
    {
      source: URN("marts.fct_revenue"),
      target: URN("marts.exec_revenue_metric"),
      columns: [{ upstream: "revenue_usd", downstream: "revenue" }],
    },
  ],
};

/* ------------------------------------------------------------------ */
/* Incident presets                                                    */
/* ------------------------------------------------------------------ */

function withStatuses(
  statuses: Record<string, IncidentState["nodes"][number]["status"]>,
) {
  return PLACEHOLDER_GRAPH.nodes.map((n) =>
    statuses[n.name] ? { ...n, status: statuses[n.name] } : n,
  );
}

const EVIDENCE_EARLY: IncidentState["evidence"] = [
  {
    id: "ev_1",
    ts: "2026-08-09T08:02:14Z",
    kind: "baseline_comparison",
    title: "Revenue anomaly confirmed on exec_revenue_metric",
    detail:
      "2026-08-09 revenue_usd = 2,737,323.50 vs trailing-28d median 29,349.39 (ratio 93.27). "
      + "Days 2026-08-07..09 are all ~93-100× baseline.",
    source: "warehouse",
  },
  {
    id: "ev_2",
    ts: "2026-08-09T08:02:51Z",
    kind: "lineage",
    title: "Upstream lineage traversed from exec_revenue_metric",
    detail:
      "exec_revenue_metric ← fct_revenue ← {stg_orders, stg_fx_rates} ← {raw_orders, raw_fx_rates} "
      + "(column: revenue ← revenue_usd ← amount × usd_rate)",
    source: "datahub",
  },
  {
    id: "ev_3",
    ts: "2026-08-09T08:03:28Z",
    kind: "sql",
    title: "Order volume normal for 2026-08-07..09",
    detail:
      "SELECT order_day, count(*) FROM staging.stg_orders WHERE order_day >= '2026-08-07' GROUP BY 1;\n"
      + "-- 351 / 362 / 358 rows (baseline 350 ± 40) → no duplicate ingestion",
    source: "warehouse",
  },
  {
    id: "ev_4",
    ts: "2026-08-09T08:04:05Z",
    kind: "profile",
    title: "FX rates stable — distractor eliminated",
    detail:
      "stg_fx_rates.usd_rate per currency unchanged within ±0.4% across 2026-08-01..09. "
      + "Feed stopped updating 2026-08-05 but forward-fill carries the last known rate.",
    source: "warehouse",
  },
];

const EVIDENCE_ROOT_CAUSE: IncidentState["evidence"] = [
  ...EVIDENCE_EARLY,
  {
    id: "ev_5",
    ts: "2026-08-09T08:04:48Z",
    kind: "profile",
    title: "raw_orders.amount ×100 for cloudpay_v2 segment",
    detail:
      "profile_column(raw.raw_orders, amount, segment_by=payment_processor):\n"
      + "cloudpay_v2 mean 2026-08-06: 74.31 → 2026-08-07: 7,411.86 (×99.7). "
      + "All other processors unchanged; all orders route via cloudpay_v2 after the 2026-08-07 cutover.",
    source: "warehouse",
  },
  {
    id: "ev_6",
    ts: "2026-08-09T08:05:22Z",
    kind: "metadata",
    title: "Contract: amount must be decimal major currency units",
    detail:
      'DataHub doc for raw.raw_orders (payments-platform contract v1.3): "`amount` is a decimal '
      + 'in major currency units". Observed cloudpay_v2 values are integers — contract violation.',
    source: "datahub",
  },
  {
    id: "ev_7",
    ts: "2026-08-09T08:05:58Z",
    kind: "sql",
    title: "Cents interpretation reconciles the KPI",
    detail:
      "SELECT ROUND(SUM(o.amount/100.0 * fx.usd_rate),2) FROM staging.stg_orders o JOIN staging.stg_fx_rates fx\n"
      + "  ON fx.rate_day=o.order_day AND fx.currency=o.currency WHERE o.order_day='2026-08-09';\n"
      + "-- 27,373.24 ≈ trailing median 29,349.39 (ratio 0.93) → amount is integer CENTS",
    source: "warehouse",
  },
];

const HYPOTHESES: IncidentState["hypotheses"] = [
  {
    id: "hyp_1",
    description:
      "cloudpay_v2 (post-cutover processor) reports `amount` in integer cents instead of decimal dollars, inflating revenue ~100×.",
    target_urn: URN("raw.raw_orders"),
    status: "confirmed",
    confidence: 0.96,
    evidence_ids: ["ev_5", "ev_6", "ev_7"],
  },
  {
    id: "hyp_2",
    description:
      "Stale FX feed: raw_fx_rates stopped updating, so stg_fx_rates forward-fill applies a wrong usd_rate.",
    target_urn: URN("staging.stg_fx_rates"),
    status: "eliminated",
    confidence: 0.05,
    evidence_ids: ["ev_4"],
  },
  {
    id: "hyp_3",
    description:
      "Duplicate order ingestion after the 2026-08-07 payment-provider cutover double-counts revenue.",
    target_urn: URN("staging.stg_orders"),
    status: "eliminated",
    confidence: 0.04,
    evidence_ids: ["ev_3"],
  },
];

const PLACEHOLDER_DIFF = `--- a/pipeline/transforms/stg_orders.sql
+++ b/pipeline/transforms/stg_orders.sql
@@ -6,7 +6,10 @@ SELECT
     CAST(CAST(order_ts AS TIMESTAMP) AS DATE) AS order_day,
     customer_id,
     currency,
-    CAST(amount AS DOUBLE) AS amount,
+    -- cloudpay_v2 reports integer cents (contract violation since the
+    -- 2026-08-07 cutover); normalize back to decimal dollars.
+    CAST(CASE WHEN payment_processor = 'cloudpay_v2'
+              THEN amount / 100.0 ELSE amount END AS DOUBLE) AS amount,
     payment_processor,
     status
 FROM raw.raw_orders
`;

/** Mid-flight investigation: evidence collection, hypotheses still open. */
export const PLACEHOLDER_INCIDENT_INVESTIGATING: IncidentState = {
  id: "inc_preview0001",
  report_text:
    "Revenue just jumped roughly 100x on the executive dashboard. Is this real?",
  stage: "EVIDENCE_COLLECTION",
  created_at: "2026-08-09T08:02:11Z",
  updated_at: "2026-08-09T08:04:05Z",
  nodes: withStatuses({
    "marts.exec_revenue_metric": "affected",
    "marts.fct_revenue": "affected",
    "staging.stg_orders": "investigating",
    "staging.stg_fx_rates": "investigating",
    "raw.raw_orders": "suspicious",
  }),
  edges: PLACEHOLDER_GRAPH.edges,
  hypotheses: [
    { ...HYPOTHESES[0], status: "investigating", confidence: 0.62 },
    { ...HYPOTHESES[1], status: "investigating", confidence: 0.31 },
    { ...HYPOTHESES[2], status: "eliminated", confidence: 0.04 },
  ],
  evidence: EVIDENCE_EARLY,
  metric_before: PLACEHOLDER_METRICS,
};

/** Root cause confirmed, repair not yet started (patch absent). */
export const PLACEHOLDER_INCIDENT: IncidentState = {
  ...PLACEHOLDER_INCIDENT_INVESTIGATING,
  stage: "ROOT_CAUSE_CONFIRMED",
  updated_at: "2026-08-09T08:06:12Z",
  nodes: withStatuses({
    "marts.exec_revenue_metric": "affected",
    "marts.fct_revenue": "affected",
    "staging.stg_orders": "affected",
    "raw.raw_orders": "root_cause",
  }),
  hypotheses: HYPOTHESES,
  evidence: EVIDENCE_ROOT_CAUSE,
  tests_before: {
    total: 32,
    passed: 25,
    failed: 7,
    failures: [
      {
        name: "invariants::test_revenue_within_baseline_band",
        message: "revenue_usd 2,737,323.50 is 93.3× the committed baseline for 2026-08-09",
      },
      {
        name: "invariants::test_aov_median_reasonable",
        message: "aov_median_usd 6,271.14 exceeds ceiling 250.00",
      },
      {
        name: "invariants::test_daily_revenue_continuity",
        message: "day-over-day revenue jump 79.6× exceeds 3.0× on 2026-08-07",
      },
      {
        name: "invariants::test_amount_distribution_stable",
        message: "stg_orders.amount p50 shifted 99.7× vs profile baseline",
      },
      {
        name: "invariants::test_kpi_anomaly_ratio_band",
        message: "exec_revenue_metric.anomaly_ratio 93.27 outside [0.6, 1.5]",
      },
      {
        name: "invariants::test_amount_within_plausible_range",
        message: "max(stg_orders.amount) 199,846.00 exceeds plausible ceiling 10,000.00",
      },
      {
        name: "invariants::test_revenue_reconciles_with_orders",
        message: "fct_revenue 2026-08-08 does not reconcile with order-level totals baseline",
      },
    ],
  },
  root_cause: {
    summary:
      "cloudpay_v2 orders report `amount` in integer CENTS, not dollars — revenue inflated ~100×",
    asset_urn: URN("raw.raw_orders"),
    field: "amount",
    detail:
      "At the 2026-08-07 payment-provider cutover every order began routing through cloudpay_v2, "
      + "which encodes `amount` as integer cents (contract v1.3 requires decimal major currency "
      + "units). stg_orders passes the value straight through, so fct_revenue and the executive "
      + "KPI are inflated ~100× from 2026-08-07 onward.",
    evidence_ids: ["ev_5", "ev_6", "ev_7"],
  },
};

/** Fully resolved: patch verified, tests green, writeback + git artifact. */
export const PLACEHOLDER_INCIDENT_RESOLVED: IncidentState = {
  ...PLACEHOLDER_INCIDENT,
  stage: "WRITEBACK_COMPLETE",
  updated_at: "2026-08-09T08:11:22Z",
  nodes: withStatuses({
    "marts.exec_revenue_metric": "repaired",
    "marts.fct_revenue": "repaired",
    "staging.stg_orders": "repaired",
    "raw.raw_orders": "root_cause",
  }),
  patch: {
    file: "pipeline/transforms/stg_orders.sql",
    diff: PLACEHOLDER_DIFF,
    reasoning:
      "cloudpay_v2 amounts changed unit from dollars to integer cents at the 2026-08-07 cutover. "
      + "Normalizing the cloudpay_v2 rows back to dollars in stg_orders restores correct semantics "
      + "for every downstream revenue model without touching healthy processors.",
    status: "verified",
  },
  tests_after: { total: 32, passed: 32, failed: 0, failures: [] },
  metric_after: PLACEHOLDER_METRICS_AFTER,
  evidence: [
    ...EVIDENCE_ROOT_CAUSE,
    {
      id: "ev_8",
      ts: "2026-08-09T08:07:31Z",
      kind: "patch",
      title: "Patch proposed for stg_orders.sql",
      detail:
        "Normalize cloudpay_v2 amounts: amount → CASE WHEN payment_processor='cloudpay_v2' THEN amount/100.0 ELSE amount END",
      source: "agent",
    },
    {
      id: "ev_9",
      ts: "2026-08-09T08:09:10Z",
      kind: "test",
      title: "Post-patch invariant suite green",
      detail:
        "32/32 pipeline invariants passed after rebuild. exec_revenue_metric 2026-08-09: 27,373.24 (ratio 0.93 vs trailing median).",
      source: "pipeline",
    },
    {
      id: "ev_10",
      ts: "2026-08-09T08:10:02Z",
      kind: "writeback",
      title: "Fix committed on blackbox/fix-inc_preview0001",
      detail:
        "pipeline/transforms/stg_orders.sql | 7 +++++--  (commit 9f3c2ab)",
      source: "git",
    },
    {
      id: "ev_11",
      ts: "2026-08-09T08:11:22Z",
      kind: "writeback",
      title: "Incident written back to DataHub",
      detail:
        "Incident resolved + root-cause annotation attached to raw.raw_orders.amount; owners notified.",
      source: "datahub",
    },
  ],
  writeback: {
    incident_urn: "urn:li:incident:exec_revenue_metric_2026-08-09",
    status: "RESOLVED",
    detail:
      "Resolution + root-cause annotation written to DataHub; asset owners notified.",
  },
  git_artifact: {
    branch: "blackbox/fix-inc_preview0001",
    commit: "9f3c2ab41d7e0b6c88f2",
    diff_stat: "pipeline/transforms/stg_orders.sql | 7 +++++--",
    pr_url: null,
  },
  final_summary:
    "Root cause: cloudpay_v2 reports amount in integer cents since the 2026-08-07 cutover. "
    + "Patched stg_orders to normalize cloudpay_v2 amounts (÷100), rebuilt the warehouse, "
    + "verified 32/32 invariants, and wrote the resolution back to DataHub.",
};
