"use client";

import { motion } from "framer-motion";
import { ShieldAlert, Wrench, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { formatUsd, shortUrn } from "@/lib/format";
import type { EvidenceItem, IncidentState, MetricSnapshot } from "@/lib/types";

type RootCause = NonNullable<IncidentState["root_cause"]>;

/**
 * Dramatic panel shown when the agent confirms a root cause (the screenshot
 * moment). Driven entirely by the live IncidentState. Dismissible so the
 * operator can inspect the lineage graph underneath; a persistent
 * "Repair & Verify" button stays in the top bar while dismissed.
 */
export function RootCauseCard({
  rootCause,
  metric,
  evidence,
  affectedCount,
  onRepair,
  repairing,
  onDismiss,
}: {
  rootCause: RootCause;
  metric?: MetricSnapshot;
  evidence: EvidenceItem[];
  affectedCount: number;
  onRepair: () => void;
  repairing?: boolean;
  onDismiss?: () => void;
}) {
  const chips = rootCause.evidence_ids
    .map((id) => evidence.find((e) => e.id === id))
    .filter((e): e is EvidenceItem => Boolean(e));

  return (
    <motion.div
      initial={{ opacity: 0, y: 24 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 24 }}
      transition={{ duration: 0.25, ease: "easeOut" }}
      className="pulse-root-cause relative rounded-xl border border-red-500/50 bg-zinc-900 p-5"
    >
      {onDismiss && (
        <button
          type="button"
          onClick={onDismiss}
          className="absolute top-3 right-3 rounded-md p-1 text-zinc-500 hover:bg-zinc-800 hover:text-zinc-200"
          aria-label="Dismiss and inspect graph"
          title="Dismiss and inspect graph"
        >
          <X className="size-4" />
        </button>
      )}
      <div className="flex flex-wrap items-start justify-between gap-4 pr-6">
        <div className="min-w-0">
          <div className="flex items-center gap-2 text-red-500">
            <ShieldAlert className="size-5" />
            <span className="text-sm font-bold tracking-[0.18em]">
              ROOT CAUSE CONFIRMED
            </span>
          </div>
          <h3 className="mt-2 text-xl font-semibold text-zinc-100">
            {rootCause.summary}
          </h3>
          <p
            className="mt-1 truncate font-mono text-xs text-red-400"
            title={rootCause.asset_urn}
          >
            {shortUrn(rootCause.asset_urn)}
            <span className="text-zinc-500"> · field </span>
            {rootCause.field}
          </p>
          <p className="mt-2 max-w-2xl text-sm leading-relaxed text-zinc-400">
            {rootCause.detail}
          </p>
        </div>
        <div className="flex shrink-0 flex-col items-end gap-3">
          {metric && (
            <div className="grid grid-cols-2 gap-x-6 gap-y-1 text-right">
              <div>
                <div className="text-[10px] uppercase tracking-wider text-zinc-500">
                  Observed
                </div>
                <div className="font-mono text-lg font-semibold tabular-nums text-red-400">
                  {formatUsd(metric.revenue, metric.revenue < 10_000)}
                </div>
              </div>
              <div>
                <div className="text-[10px] uppercase tracking-wider text-zinc-500">
                  Expected
                </div>
                <div className="font-mono text-lg font-semibold tabular-nums text-zinc-100">
                  {formatUsd(metric.expected_revenue)}
                </div>
              </div>
            </div>
          )}
          <div className="text-right">
            <div className="text-[10px] uppercase tracking-wider text-zinc-500">
              Affected assets
            </div>
            <div className="font-mono text-lg font-semibold tabular-nums text-amber-400">
              {affectedCount}
            </div>
          </div>
        </div>
      </div>

      {chips.length > 0 && (
        <div className="mt-4 flex flex-wrap gap-1.5">
          {chips.map((chip) => (
            <span
              key={chip.id}
              className="rounded-full border border-zinc-700 bg-zinc-950 px-2.5 py-0.5 text-[11px] text-zinc-300"
              title={chip.detail}
            >
              {chip.title}
            </span>
          ))}
        </div>
      )}

      <div className="mt-5 flex items-center justify-end gap-2">
        {onDismiss && (
          <Button
            variant="ghost"
            onClick={onDismiss}
            className="text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200"
          >
            Inspect graph
          </Button>
        )}
        <Button
          onClick={onRepair}
          disabled={repairing}
          className="bg-red-500 text-white hover:bg-red-600"
        >
          <Wrench data-icon="inline-start" />
          {repairing ? "Repairing…" : "Repair & Verify"}
        </Button>
      </div>
    </motion.div>
  );
}
