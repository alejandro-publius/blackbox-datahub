"use client";

import { motion } from "framer-motion";
import { ArrowRight, CircleCheck, CloudUpload } from "lucide-react";
import { DiffView } from "@/components/DiffView";
import { formatUsd } from "@/lib/format";
import type {
  IncidentState,
  MetricSnapshot,
  ProposedPatch,
  TestReport,
} from "@/lib/types";
import { cn } from "@/lib/utils";

/**
 * Bottom-drawer panel shown once the repair is verified / written back.
 * Wired later to the live incident stream.
 */
export function ResolutionCard({
  patch,
  testsAfter,
  metricBefore,
  metricAfter,
  writeback,
}: {
  patch?: ProposedPatch;
  testsAfter?: TestReport;
  metricBefore?: MetricSnapshot;
  metricAfter?: MetricSnapshot;
  writeback?: IncidentState["writeback"];
}) {
  const allPassed = testsAfter ? testsAfter.failed === 0 : false;

  return (
    <motion.div
      initial={{ opacity: 0, y: 24 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 24 }}
      transition={{ duration: 0.25, ease: "easeOut" }}
      className="rounded-xl border border-emerald-400/40 bg-zinc-900 p-5"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2 text-emerald-400">
          <CircleCheck className="size-5" />
          <span className="text-sm font-bold tracking-[0.18em]">
            INCIDENT RESOLVED
          </span>
        </div>
        {testsAfter && (
          <span
            className={cn(
              "rounded-full border px-3 py-1 font-mono text-xs font-semibold tabular-nums",
              allPassed
                ? "border-emerald-400/40 bg-emerald-400/10 text-emerald-400"
                : "border-amber-400/40 bg-amber-400/10 text-amber-400",
            )}
          >
            TESTS {testsAfter.passed}/{testsAfter.total} PASSED
          </span>
        )}
      </div>

      {(metricBefore || metricAfter) && (
        <div className="mt-4 flex flex-wrap items-center gap-4 rounded-lg border border-zinc-800 bg-zinc-950 px-4 py-3">
          <div>
            <div className="text-[10px] uppercase tracking-wider text-zinc-500">
              Revenue · before
            </div>
            <div className="font-mono text-xl font-semibold tabular-nums text-red-400">
              {metricBefore
                ? formatUsd(metricBefore.revenue, metricBefore.revenue < 10_000)
                : "—"}
            </div>
          </div>
          <ArrowRight className="size-4 text-zinc-600" />
          <div>
            <div className="text-[10px] uppercase tracking-wider text-zinc-500">
              Revenue · after
            </div>
            <div className="font-mono text-xl font-semibold tabular-nums text-emerald-400">
              {metricAfter
                ? formatUsd(metricAfter.revenue, metricAfter.revenue < 10_000)
                : "—"}
            </div>
          </div>
          {metricAfter && (
            <div className="ml-auto text-right">
              <div className="text-[10px] uppercase tracking-wider text-zinc-500">
                Status
              </div>
              <div
                className={cn(
                  "font-mono text-sm font-semibold",
                  metricAfter.status === "ok"
                    ? "text-emerald-400"
                    : "text-red-400",
                )}
              >
                {metricAfter.status.toUpperCase()}
              </div>
            </div>
          )}
        </div>
      )}

      {patch && (
        <div className="mt-4">
          <DiffView diff={patch.diff} file={patch.file} />
          <p className="mt-2 text-xs leading-relaxed text-zinc-500">
            {patch.reasoning}
          </p>
        </div>
      )}

      {writeback && (
        <div className="mt-4 flex items-center gap-3 rounded-lg border border-zinc-800 bg-zinc-950 px-4 py-2.5">
          <CloudUpload className="size-4 shrink-0 text-sky-400" />
          <div className="min-w-0 flex-1">
            <span className="text-xs text-zinc-300">{writeback.detail}</span>
            {writeback.incident_urn && (
              <span
                className="ml-2 font-mono text-[11px] text-zinc-500"
                title={writeback.incident_urn}
              >
                {writeback.incident_urn}
              </span>
            )}
          </div>
          <span className="shrink-0 rounded border border-emerald-400/40 bg-emerald-400/10 px-1.5 py-px font-mono text-[10px] font-semibold text-emerald-400">
            {writeback.status}
          </span>
        </div>
      )}
    </motion.div>
  );
}
