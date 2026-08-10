import type {
  IncidentState,
  LineageGraph,
  MetricSnapshot,
} from "./types";

/**
 * PLACEHOLDER FIXTURES — dev preview only.
 *
 * These are consumed exclusively through the `?preview=1` /
 * `?preview=resolved` dev preview mode in Dashboard.tsx, which always renders
 * the "PREVIEW DATA" watermark badge. Placeholder data must NEVER be rendered
 * without that watermark. Do not import these into live data paths.
 */

const URN = (name: string) =>
  `urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.${name},PROD)`;

export const PLACEHOLDER_METRICS: MetricSnapshot = {
  kpi_day: "2026-08-08",
  revenue: 1247.19,
  expected_revenue: 124583.4,
  anomaly_ratio: 0.01,
  status: "anomalous",
  daily: [
    { day: "2026-08-01", revenue_usd: 118204.11, baseline: 119000 },
    { day: "2026-08-02", revenue_usd: 121876.02, baseline: 120500 },
    { day: "2026-08-03", revenue_usd: 119433.87, baseline: 120000 },
    { day: "2026-08-04", revenue_usd: 123901.54, baseline: 121500 },
    { day: "2026-08-05", revenue_usd: 122417.9, baseline: 122000 },
    { day: "2026-08-06", revenue_usd: 125002.33, baseline: 123000 },
    { day: "2026-08-07", revenue_usd: 124118.76, baseline: 123500 },
    { day: "2026-08-08", revenue_usd: 1247.19, baseline: 124583.4 },
  ],
};

export const PLACEHOLDER_METRICS_AFTER: MetricSnapshot = {
  ...PLACEHOLDER_METRICS,
  revenue: 124719.42,
  anomaly_ratio: 1.0,
  status: "ok",
  daily: PLACEHOLDER_METRICS.daily.map((d) =>
    d.day === "2026-08-08" ? { ...d, revenue_usd: 124719.42 } : d,
  ),
};

export const PLACEHOLDER_GRAPH: LineageGraph = {
  nodes: [
    // sources
    { urn: URN("raw_orders"), name: "raw_orders", platform: "postgres", layer: "source", status: "healthy" },
    { urn: URN("raw_payments"), name: "raw_payments", platform: "postgres", layer: "source", status: "root_cause" },
    { urn: URN("raw_customers"), name: "raw_customers", platform: "postgres", layer: "source", status: "healthy" },
    // staging
    { urn: URN("stg_orders"), name: "stg_orders", platform: "dbt", layer: "staging", status: "healthy" },
    { urn: URN("stg_payments"), name: "stg_payments", platform: "dbt", layer: "staging", status: "affected" },
    { urn: URN("stg_customers"), name: "stg_customers", platform: "dbt", layer: "staging", status: "healthy" },
    // marts
    { urn: URN("fct_orders"), name: "fct_orders", platform: "dbt", layer: "marts", status: "affected" },
    { urn: URN("dim_customers"), name: "dim_customers", platform: "dbt", layer: "marts", status: "healthy" },
    // metric
    { urn: URN("kpi_daily_revenue"), name: "kpi_daily_revenue", platform: "snowflake", layer: "metric", status: "affected" },
  ],
  edges: [
    { source: URN("raw_orders"), target: URN("stg_orders") },
    {
      source: URN("raw_payments"),
      target: URN("stg_payments"),
      columns: [{ upstream: "amount", downstream: "amount_usd" }],
    },
    { source: URN("raw_customers"), target: URN("stg_customers") },
    { source: URN("stg_orders"), target: URN("fct_orders") },
    {
      source: URN("stg_payments"),
      target: URN("fct_orders"),
      columns: [{ upstream: "amount_usd", downstream: "order_revenue_usd" }],
    },
    { source: URN("stg_customers"), target: URN("dim_customers") },
    {
      source: URN("fct_orders"),
      target: URN("kpi_daily_revenue"),
      columns: [{ upstream: "order_revenue_usd", downstream: "revenue_usd" }],
    },
    { source: URN("dim_customers"), target: URN("kpi_daily_revenue") },
  ],
};

const PLACEHOLDER_DIFF = `--- a/models/staging/stg_payments.sql
+++ b/models/staging/stg_payments.sql
@@ -8,7 +8,7 @@ renamed as (
     select
         payment_id,
         order_id,
-        amount as amount_usd,
+        amount / 100.0 as amount_usd,
         payment_method,
         created_at
     from source
`;

export const PLACEHOLDER_INCIDENT: IncidentState = {
  id: "inc_placeholder_001",
  report_text:
    "Daily revenue KPI dropped ~99% overnight (2026-08-08). Dashboard shows $1,247 vs expected ~$124,583.",
  stage: "ROOT_CAUSE_CONFIRMED",
  created_at: "2026-08-09T08:02:11Z",
  updated_at: "2026-08-09T08:06:47Z",
  nodes: PLACEHOLDER_GRAPH.nodes,
  edges: PLACEHOLDER_GRAPH.edges,
  hypotheses: [
    {
      id: "hyp_1",
      description:
        "Upstream schema change in raw_payments: `amount` switched from dollars to integer cents.",
      target_urn: URN("raw_payments"),
      status: "confirmed",
      confidence: 0.97,
      evidence_ids: ["ev_4", "ev_5", "ev_6"],
    },
    {
      id: "hyp_2",
      description:
        "Pipeline partial load: fct_orders missing rows for 2026-08-08.",
      target_urn: URN("fct_orders"),
      status: "eliminated",
      confidence: 0.08,
      evidence_ids: ["ev_3"],
    },
    {
      id: "hyp_3",
      description:
        "Currency conversion regression in kpi_daily_revenue aggregation.",
      target_urn: URN("kpi_daily_revenue"),
      status: "eliminated",
      confidence: 0.11,
      evidence_ids: ["ev_2"],
    },
  ],
  evidence: [
    {
      id: "ev_1",
      ts: "2026-08-09T08:02:14Z",
      kind: "baseline_comparison",
      title: "Revenue anomaly detected on kpi_daily_revenue",
      detail:
        "2026-08-08 revenue_usd = 1,247.19 vs 28d baseline 124,583.40 (ratio 0.010)",
      source: "warehouse",
    },
    {
      id: "ev_2",
      ts: "2026-08-09T08:03:02Z",
      kind: "lineage",
      title: "Upstream lineage traversed from kpi_daily_revenue",
      detail:
        "kpi_daily_revenue ← fct_orders ← stg_payments ← raw_payments (column: revenue_usd ← order_revenue_usd ← amount_usd ← amount)",
      source: "datahub",
    },
    {
      id: "ev_3",
      ts: "2026-08-09T08:03:40Z",
      kind: "sql",
      title: "Row counts normal for 2026-08-08",
      detail:
        "SELECT count(*) FROM fct_orders WHERE order_date = '2026-08-08';\n-- 18,204 rows (baseline 17,900 ± 600) → no partial load",
      source: "warehouse",
    },
    {
      id: "ev_4",
      ts: "2026-08-09T08:04:19Z",
      kind: "profile",
      title: "raw_payments.amount distribution shifted x100",
      detail:
        "avg(amount) 2026-08-07: 68.42 → 2026-08-08: 6,853.11 (x100.16). min/max also x100.",
      source: "warehouse",
    },
    {
      id: "ev_5",
      ts: "2026-08-09T08:05:03Z",
      kind: "metadata",
      title: "Schema doc updated: amount now integer cents",
      detail:
        'DataHub description for raw_payments.amount changed 2026-08-07: "Payment amount in USD" → "Payment amount in integer cents".',
      source: "datahub",
    },
    {
      id: "ev_6",
      ts: "2026-08-09T08:05:41Z",
      kind: "sql",
      title: "Join check: cents interpretation reconciles KPI",
      detail:
        "SELECT sum(amount)/100.0 FROM raw_payments WHERE created_at::date = '2026-08-08';\n-- 124,719.42 ≈ expected 124,583.40 (within 0.11%)",
      source: "warehouse",
    },
    {
      id: "ev_7",
      ts: "2026-08-09T08:06:47Z",
      kind: "patch",
      title: "Patch proposed for stg_payments.sql",
      detail: "amount as amount_usd → amount / 100.0 as amount_usd",
      source: "agent",
    },
  ],
  patch: {
    file: "models/staging/stg_payments.sql",
    diff: PLACEHOLDER_DIFF,
    reasoning:
      "raw_payments.amount changed unit from dollars to integer cents on 2026-08-07. Dividing by 100.0 in the staging rename restores amount_usd semantics for all downstream models.",
    status: "proposed",
  },
  tests_before: {
    total: 12,
    passed: 10,
    failed: 2,
    failures: [
      {
        name: "assert_revenue_within_baseline",
        message: "revenue_usd 1,247.19 outside 3σ of baseline 124,583.40",
      },
      {
        name: "assert_amount_usd_reasonable_range",
        message: "max(amount_usd) 91,204 exceeds threshold 5,000",
      },
    ],
  },
  metric_before: PLACEHOLDER_METRICS,
  root_cause: {
    summary: "raw_payments.amount changed from DOLLARS to integer CENTS",
    asset_urn: URN("raw_payments"),
    field: "amount",
    detail:
      "An upstream service migration on 2026-08-07 switched raw_payments.amount to integer cents. stg_payments passes the value through as amount_usd, deflating every downstream revenue metric by x100.",
    evidence_ids: ["ev_4", "ev_5", "ev_6"],
  },
};

/** Resolved-state variant: shows ResolutionCard, repaired lineage, writeback. */
export const PLACEHOLDER_INCIDENT_RESOLVED: IncidentState = {
  ...PLACEHOLDER_INCIDENT,
  stage: "WRITEBACK_COMPLETE",
  updated_at: "2026-08-09T08:11:22Z",
  nodes: PLACEHOLDER_GRAPH.nodes.map((n) =>
    ["raw_payments", "stg_payments", "fct_orders", "kpi_daily_revenue"].includes(
      n.name,
    )
      ? { ...n, status: "repaired" as const }
      : n,
  ),
  patch: {
    ...PLACEHOLDER_INCIDENT.patch!,
    status: "verified",
  },
  tests_after: { total: 12, passed: 12, failed: 0, failures: [] },
  metric_after: PLACEHOLDER_METRICS_AFTER,
  evidence: [
    ...PLACEHOLDER_INCIDENT.evidence,
    {
      id: "ev_8",
      ts: "2026-08-09T08:09:10Z",
      kind: "test",
      title: "Post-patch test suite green",
      detail: "12/12 dbt tests passed after applying stg_payments patch.",
      source: "pipeline",
    },
    {
      id: "ev_9",
      ts: "2026-08-09T08:11:22Z",
      kind: "writeback",
      title: "Incident written back to DataHub",
      detail:
        "Incident resolved + root-cause annotation attached to raw_payments.amount.",
      source: "datahub",
    },
  ],
  writeback: {
    incident_urn: "urn:li:incident:kpi_daily_revenue_2026-08-08",
    status: "RESOLVED",
    detail:
      "Resolution + root-cause annotation written to DataHub; owners notified.",
  },
};
