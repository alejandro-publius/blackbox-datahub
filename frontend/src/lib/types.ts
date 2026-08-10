/**
 * BlackBox — shared type contract with the backend.
 * These types mirror the backend contract EXACTLY. Do not modify without
 * coordinating with the API implementation.
 */

export type IncidentStage =
  | "REPORTED"
  | "CONTEXT_DISCOVERY"
  | "LINEAGE_TRAVERSAL"
  | "HYPOTHESIS_GENERATION"
  | "EVIDENCE_COLLECTION"
  | "ROOT_CAUSE_CONFIRMED"
  | "REPAIR_GENERATED"
  | "REPAIR_TESTING"
  | "VERIFIED"
  | "WRITEBACK_COMPLETE"
  | "NO_INCIDENT"
  | "FAILED";

export type NodeStatus =
  | "healthy"
  | "investigating"
  | "suspicious"
  | "affected"
  | "root_cause"
  | "repaired";

export interface LineageNode {
  urn: string;
  name: string;
  platform: string;
  layer: "source" | "staging" | "marts" | "metric";
  status: NodeStatus;
}

export interface LineageEdge {
  source: string;
  target: string;
  columns?: { upstream: string; downstream: string }[];
}

export interface MetricSnapshot {
  kpi_day: string;
  revenue: number;
  expected_revenue: number;
  anomaly_ratio: number;
  status: "ok" | "anomalous";
  daily: { day: string; revenue_usd: number; baseline?: number }[];
}

export interface Hypothesis {
  id: string;
  description: string;
  target_urn: string;
  status: "proposed" | "investigating" | "eliminated" | "confirmed";
  confidence: number;
  evidence_ids: string[];
}

export interface EvidenceItem {
  id: string;
  ts: string;
  kind:
    | "metadata"
    | "profile"
    | "baseline_comparison"
    | "sql"
    | "lineage"
    | "test"
    | "patch"
    | "writeback";
  title: string;
  detail: string;
  data?: unknown;
  source: "datahub" | "warehouse" | "pipeline" | "git" | "agent";
  /** Concrete transport that produced this fact (e.g. "datahub-mcp-server",
   *  "datahub-agent-context", "datahub-graphql"). Provenance, not an
   *  independent source of truth — DataHub transports all read one graph. */
  transport?: string | null;
}

export interface ProposedPatch {
  file: string;
  diff: string;
  reasoning: string;
  status: "proposed" | "applied" | "testing" | "verified" | "rejected";
}

export interface TestReport {
  total: number;
  passed: number;
  failed: number;
  failures: { name: string; message: string }[];
}

export interface GitArtifact {
  branch: string;
  commit: string;
  diff_stat: string;
  pr_url?: string | null;
}

export interface IncidentState {
  id: string;
  report_text: string;
  stage: IncidentStage;
  created_at: string;
  updated_at: string;
  nodes: LineageNode[];
  edges: LineageEdge[];
  hypotheses: Hypothesis[];
  evidence: EvidenceItem[];
  patch?: ProposedPatch;
  tests_before?: TestReport;
  tests_after?: TestReport;
  metric_before?: MetricSnapshot;
  metric_after?: MetricSnapshot;
  root_cause?: {
    summary: string;
    asset_urn: string;
    field: string;
    detail: string;
    evidence_ids: string[];
  };
  writeback?: { incident_urn?: string; status: string; detail: string };
  git_artifact?: GitArtifact;
  final_summary?: string;
  error?: string;
}

export interface HealthStatus {
  status: string;
  warehouse_ready: boolean;
  datahub_connected: boolean;
  anthropic_configured: boolean;
}

/** Stages after which the incident will never change again. */
export const TERMINAL_STAGES: IncidentStage[] = [
  "WRITEBACK_COMPLETE",
  "NO_INCIDENT",
  "FAILED",
];

export function isTerminalStage(stage: IncidentStage): boolean {
  return TERMINAL_STAGES.includes(stage);
}

export interface LineageGraph {
  nodes: LineageNode[];
  edges: LineageEdge[];
}
