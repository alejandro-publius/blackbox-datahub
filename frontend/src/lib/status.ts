import type {
  EvidenceItem,
  Hypothesis,
  IncidentStage,
  NodeStatus,
} from "./types";

/**
 * Canonical status color system.
 *
 * The same colors are exposed as Tailwind theme tokens in globals.css
 * (`--color-status-*`, usable as e.g. `text-status-healthy`,
 * `bg-status-root-cause/10`) and as full class strings here so Tailwind's
 * scanner picks them up and components can consume them from a single map.
 */

export interface NodeStatusStyle {
  label: string;
  /** text color */
  text: string;
  /** border color (node accents, tile border-left) */
  border: string;
  /** faint fill */
  bg: string;
  /** legend / pill dot */
  dot: string;
  /** extra treatment (ring / pulse) — only root_cause uses this */
  ring: string;
}

export const NODE_STATUS_STYLES: Record<NodeStatus, NodeStatusStyle> = {
  healthy: {
    label: "Healthy",
    text: "text-emerald-400",
    border: "border-emerald-400",
    bg: "bg-emerald-400/10",
    dot: "bg-emerald-400",
    ring: "",
  },
  investigating: {
    label: "Investigating",
    text: "text-sky-400",
    border: "border-sky-400",
    bg: "bg-sky-400/10",
    dot: "bg-sky-400",
    ring: "pulse-investigating",
  },
  suspicious: {
    label: "Suspicious",
    text: "text-amber-400",
    border: "border-amber-400",
    bg: "bg-amber-400/10",
    dot: "bg-amber-400",
    ring: "",
  },
  affected: {
    label: "Affected",
    text: "text-red-400",
    border: "border-red-400",
    bg: "bg-red-400/10",
    dot: "bg-red-400",
    ring: "",
  },
  root_cause: {
    label: "Root cause",
    text: "text-red-500",
    border: "border-red-500",
    bg: "bg-red-500/10",
    dot: "bg-red-500",
    ring: "ring-2 ring-red-500/60 pulse-root-cause",
  },
  repaired: {
    label: "Repaired",
    text: "text-emerald-400",
    border: "border-emerald-400",
    bg: "bg-emerald-400/10",
    dot: "bg-emerald-400",
    ring: "",
  },
};

/** Incident stage → pill label + tone classes. */
export interface StageStyle {
  label: string;
  className: string; // full pill classes (text + border + bg)
  dot: string;
  /** text color token, reusable outside the pill */
  text: string;
  /** border-left accent for KPI tiles */
  accent: string;
}

export const STAGE_STYLES: Record<IncidentStage, StageStyle> = {
  REPORTED: {
    label: "Reported",
    className: "text-amber-400 border-amber-400/40 bg-amber-400/10",
    dot: "bg-amber-400",
    text: "text-amber-400",
    accent: "border-l-amber-400",
  },
  CONTEXT_DISCOVERY: {
    label: "Context Discovery",
    className: "text-sky-400 border-sky-400/40 bg-sky-400/10",
    dot: "bg-sky-400",
    text: "text-sky-400",
    accent: "border-l-sky-400",
  },
  LINEAGE_TRAVERSAL: {
    label: "Lineage Traversal",
    className: "text-sky-400 border-sky-400/40 bg-sky-400/10",
    dot: "bg-sky-400",
    text: "text-sky-400",
    accent: "border-l-sky-400",
  },
  HYPOTHESIS_GENERATION: {
    label: "Hypothesis Generation",
    className: "text-sky-400 border-sky-400/40 bg-sky-400/10",
    dot: "bg-sky-400",
    text: "text-sky-400",
    accent: "border-l-sky-400",
  },
  EVIDENCE_COLLECTION: {
    label: "Evidence Collection",
    className: "text-sky-400 border-sky-400/40 bg-sky-400/10",
    dot: "bg-sky-400",
    text: "text-sky-400",
    accent: "border-l-sky-400",
  },
  ROOT_CAUSE_CONFIRMED: {
    label: "Root Cause Confirmed",
    className: "text-red-500 border-red-500/40 bg-red-500/10",
    dot: "bg-red-500",
    text: "text-red-500",
    accent: "border-l-red-500",
  },
  REPAIR_GENERATED: {
    label: "Repair Generated",
    className: "text-amber-400 border-amber-400/40 bg-amber-400/10",
    dot: "bg-amber-400",
    text: "text-amber-400",
    accent: "border-l-amber-400",
  },
  REPAIR_TESTING: {
    label: "Repair Testing",
    className: "text-amber-400 border-amber-400/40 bg-amber-400/10",
    dot: "bg-amber-400",
    text: "text-amber-400",
    accent: "border-l-amber-400",
  },
  VERIFIED: {
    label: "Verified",
    className: "text-emerald-400 border-emerald-400/40 bg-emerald-400/10",
    dot: "bg-emerald-400",
    text: "text-emerald-400",
    accent: "border-l-emerald-400",
  },
  WRITEBACK_COMPLETE: {
    label: "Writeback Complete",
    className: "text-emerald-400 border-emerald-400/40 bg-emerald-400/10",
    dot: "bg-emerald-400",
    text: "text-emerald-400",
    accent: "border-l-emerald-400",
  },
  NO_INCIDENT: {
    label: "No Incident",
    className: "text-zinc-400 border-zinc-700 bg-zinc-800/50",
    dot: "bg-zinc-400",
    text: "text-zinc-400",
    accent: "border-l-zinc-700",
  },
  FAILED: {
    label: "Failed",
    className: "text-red-400 border-red-400/40 bg-red-400/10",
    dot: "bg-red-400",
    text: "text-red-400",
    accent: "border-l-red-400",
  },
};

/** Evidence / timeline source → badge label + classes. */
export const SOURCE_STYLES: Record<
  EvidenceItem["source"],
  { label: string; className: string }
> = {
  datahub: {
    label: "DATAHUB",
    className: "text-sky-400 border-sky-400/40 bg-sky-400/10",
  },
  warehouse: {
    label: "WAREHOUSE",
    className: "text-violet-400 border-violet-400/40 bg-violet-400/10",
  },
  pipeline: {
    label: "PIPELINE",
    className: "text-amber-400 border-amber-400/40 bg-amber-400/10",
  },
  git: {
    label: "GIT",
    className: "text-orange-400 border-orange-400/40 bg-orange-400/10",
  },
  agent: {
    label: "AGENT",
    className: "text-emerald-400 border-emerald-400/40 bg-emerald-400/10",
  },
};

/** Hypothesis status → text/border tone. */
export const HYPOTHESIS_STATUS_STYLES: Record<
  Hypothesis["status"],
  { label: string; className: string; bar: string }
> = {
  proposed: {
    label: "PROPOSED",
    className: "text-zinc-400 border-zinc-700 bg-zinc-800/50",
    bar: "bg-zinc-500",
  },
  investigating: {
    label: "INVESTIGATING",
    className: "text-sky-400 border-sky-400/40 bg-sky-400/10",
    bar: "bg-sky-400",
  },
  eliminated: {
    label: "ELIMINATED",
    className: "text-zinc-500 border-zinc-800 bg-zinc-900 line-through",
    bar: "bg-zinc-700",
  },
  confirmed: {
    label: "CONFIRMED",
    className: "text-red-500 border-red-500/40 bg-red-500/10",
    bar: "bg-red-500",
  },
};

/** Stages during which lineage edges animate. */
export const INVESTIGATING_STAGES: IncidentStage[] = [
  "CONTEXT_DISCOVERY",
  "LINEAGE_TRAVERSAL",
  "HYPOTHESIS_GENERATION",
  "EVIDENCE_COLLECTION",
];

/** Node statuses counted as "affected assets" in the KPI strip. */
export const AFFECTED_STATUSES: NodeStatus[] = [
  "suspicious",
  "affected",
  "root_cause",
];
