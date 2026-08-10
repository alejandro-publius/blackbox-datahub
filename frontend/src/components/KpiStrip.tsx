"use client";

import { motion } from "framer-motion";
import { Activity, Boxes, DollarSign, Radar } from "lucide-react";
import type { ComponentType } from "react";
import { formatDeltaPct, formatUsd } from "@/lib/format";
import { AFFECTED_STATUSES, STAGE_STYLES } from "@/lib/status";
import type { IncidentStage, LineageNode, MetricSnapshot } from "@/lib/types";
import { cn } from "@/lib/utils";

interface Tile {
  key: string;
  label: string;
  icon: ComponentType<{ className?: string }>;
  value: string;
  detail: string;
  /** border-left accent */
  accent: string;
  valueClass?: string;
}

export function KpiStrip({
  metrics,
  nodes,
  stage,
}: {
  metrics: MetricSnapshot | null;
  nodes: LineageNode[];
  stage: IncidentStage | null;
}) {
  const affectedCount = nodes.filter((n) =>
    AFFECTED_STATUSES.includes(n.status),
  ).length;

  const healthy = metrics ? metrics.status === "ok" : null;
  const revenueBad = metrics ? metrics.status !== "ok" : false;

  const tiles: Tile[] = [
    {
      key: "revenue",
      label: `Revenue${metrics ? ` · ${metrics.kpi_day}` : ""}`,
      icon: DollarSign,
      value: metrics ? formatUsd(metrics.revenue, metrics.revenue < 10_000) : "—",
      detail: metrics
        ? `${formatDeltaPct(metrics.revenue, metrics.expected_revenue)} vs expected ${formatUsd(metrics.expected_revenue)}`
        : "no data",
      accent: revenueBad ? "border-l-red-400" : "border-l-emerald-400",
      valueClass: revenueBad ? "text-red-400" : "text-zinc-100",
    },
    {
      key: "health",
      label: "Data Health",
      icon: Activity,
      value: healthy === null ? "—" : healthy ? "OK" : "CRITICAL",
      detail:
        metrics && !healthy
          ? `anomaly ratio ${metrics.anomaly_ratio.toFixed(3)}`
          : "all checks passing",
      accent:
        healthy === null
          ? "border-l-zinc-700"
          : healthy
            ? "border-l-emerald-400"
            : "border-l-red-400",
      valueClass:
        healthy === null
          ? "text-zinc-500"
          : healthy
            ? "text-emerald-400"
            : "text-red-400",
    },
    {
      key: "affected",
      label: "Affected Assets",
      icon: Boxes,
      value: String(affectedCount),
      detail: `${nodes.length} assets in lineage`,
      accent: affectedCount > 0 ? "border-l-amber-400" : "border-l-emerald-400",
      valueClass: affectedCount > 0 ? "text-amber-400" : "text-zinc-100",
    },
    {
      key: "stage",
      label: "Active Incident",
      icon: Radar,
      value: stage ? STAGE_STYLES[stage].label : "None",
      detail: stage ? `stage ${stage}` : "no active investigation",
      accent: stage ? STAGE_STYLES[stage].accent : "border-l-zinc-700",
      valueClass: stage ? STAGE_STYLES[stage].text : "text-zinc-500",
    },
  ];

  return (
    <div className="grid shrink-0 grid-cols-2 gap-3 px-4 py-3 xl:grid-cols-4">
      {tiles.map((tile) => (
        <div
          key={tile.key}
          className={cn(
            "rounded-lg border border-zinc-800 border-l-2 bg-zinc-900 px-4 py-3",
            tile.accent,
          )}
        >
          <div className="flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wider text-zinc-400">
            <tile.icon className="size-3.5" />
            {tile.label}
          </div>
          <motion.div
            key={tile.value}
            initial={{ opacity: 0.4 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.25 }}
            className={cn(
              "mt-1 truncate font-mono text-2xl font-semibold tabular-nums",
              tile.valueClass,
            )}
            title={tile.value}
          >
            {tile.value}
          </motion.div>
          <div className="mt-0.5 truncate font-mono text-[11px] tabular-nums text-zinc-500">
            {tile.detail}
          </div>
        </div>
      ))}
    </div>
  );
}
