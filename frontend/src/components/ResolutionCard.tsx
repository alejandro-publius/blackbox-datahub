"use client";

import { motion } from "framer-motion";
import {
  ArrowRight,
  CircleCheck,
  CloudUpload,
  ExternalLink,
  GitBranch,
  GitCommitHorizontal,
  X,
} from "lucide-react";
import { DiffView } from "@/components/DiffView";
import { formatUsd } from "@/lib/format";
import type {
  GitArtifact,
  IncidentState,
  MetricSnapshot,
  ProposedPatch,
  TestReport,
} from "@/lib/types";
import { cn } from "@/lib/utils";

function ratioLabel(m: MetricSnapshot): string {
  const r = m.anomaly_ratio;
  return `${r >= 10 ? Math.round(r) : r.toFixed(2)}× expected`;
}

/**
 * Shown once the repair is verified / written back (stage VERIFIED or
 * WRITEBACK_COMPLETE). Everything rendered here is real execution output:
 * pytest report, difflib patch, git commit, DataHub writeback.
 */
export function ResolutionCard({
  patch,
  testsAfter,
  metricBefore,
  metricAfter,
  writeback,
  gitArtifact,
  finalSummary,
  onDismiss,
}: {
  patch?: ProposedPatch;
  testsAfter?: TestReport;
  metricBefore?: MetricSnapshot;
  metricAfter?: MetricSnapshot;
  writeback?: IncidentState["writeback"];
  gitArtifact?: GitArtifact;
  finalSummary?: string;
  onDismiss?: () => void;
}) {
  const allPassed = testsAfter ? testsAfter.failed === 0 : false;

  return (
    <motion.div
      initial={{ opacity: 0, y: 24 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 24 }}
      transition={{ duration: 0.25, ease: "easeOut" }}
      className="relative rounded-xl border border-emerald-400/40 bg-zinc-900 p-5"
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

      <div className="flex flex-wrap items-center justify-between gap-3 pr-6">
        <div className="flex items-center gap-2.5 text-emerald-400">
          <CircleCheck className="size-6" />
          <span className="text-lg font-bold tracking-[0.18em]">
            INCIDENT RESOLVED
          </span>
        </div>
        {testsAfter && (
          <span
            className={cn(
              "rounded-full border px-3 py-1 font-mono text-sm font-bold tabular-nums",
              allPassed
                ? "border-emerald-400/40 bg-emerald-400/10 text-emerald-400"
                : "border-amber-400/40 bg-amber-400/10 text-amber-400",
            )}
          >
            {testsAfter.passed}/{testsAfter.total} TESTS PASSED
          </span>
        )}
      </div>

      {(metricBefore || metricAfter) && (
        <div className="mt-4 flex flex-wrap items-center gap-4 rounded-lg border border-zinc-800 bg-zinc-950 px-4 py-3">
          <div>
            <div className="text-[10px] uppercase tracking-wider text-zinc-500">
              Revenue · before
            </div>
            <div className="font-mono text-xl font-semibold tabular-nums text-red-400 line-through decoration-red-400/70 decoration-2">
              {metricBefore
                ? formatUsd(metricBefore.revenue, metricBefore.revenue < 10_000)
                : "—"}
            </div>
            {metricBefore && (
              <div className="font-mono text-[10px] tabular-nums text-red-400/80">
                {ratioLabel(metricBefore)}
              </div>
            )}
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
            {metricAfter && (
              <div className="font-mono text-[10px] tabular-nums text-emerald-400/80">
                {ratioLabel(metricAfter)}
              </div>
            )}
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

      {gitArtifact && (
        <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-1.5 rounded-lg border border-zinc-800 bg-zinc-950 px-4 py-2.5">
          <span className="inline-flex items-center gap-1.5 font-mono text-[11px] text-orange-400">
            <GitBranch className="size-3.5" />
            {gitArtifact.branch}
          </span>
          <span
            className="inline-flex items-center gap-1.5 font-mono text-[11px] text-zinc-300"
            title={gitArtifact.commit}
          >
            <GitCommitHorizontal className="size-3.5 text-zinc-500" />
            {gitArtifact.commit.slice(0, 7)}
          </span>
          <span className="font-mono text-[11px] text-zinc-500">
            {gitArtifact.diff_stat}
          </span>
          {gitArtifact.pr_url && (
            <a
              href={gitArtifact.pr_url}
              target="_blank"
              rel="noreferrer"
              className="ml-auto inline-flex items-center gap-1 font-mono text-[11px] text-sky-400 underline-offset-4 hover:underline"
            >
              View PR
              <ExternalLink className="size-3" />
            </a>
          )}
        </div>
      )}

      {writeback && (
        <div className="mt-3 flex items-center gap-3 rounded-lg border border-zinc-800 bg-zinc-950 px-4 py-2.5">
          <CloudUpload className="size-4 shrink-0 text-sky-400" />
          <div className="min-w-0 flex-1">
            <span className="text-xs text-zinc-300">{writeback.detail}</span>
            {writeback.incident_urn && (
              <span
                className="ml-2 font-mono text-[11px] break-all text-zinc-500"
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

      {/* The agent's full post-mortem is long and markdown-flavoured: keep the
          hero stats above the fold and let judges expand the prose on demand. */}
      {finalSummary && (
        <details className="group mt-3 rounded-lg border border-zinc-800 bg-zinc-950">
          <summary className="cursor-pointer list-none px-4 py-2.5 text-xs font-semibold tracking-wider text-zinc-400 uppercase select-none hover:text-zinc-200">
            <span className="mr-1.5 inline-block transition-transform group-open:rotate-90">
              ›
            </span>
            Full incident report
          </summary>
          <pre className="max-h-80 overflow-auto border-t border-zinc-800 px-4 py-3 font-mono text-[11px] leading-relaxed whitespace-pre-wrap text-zinc-400">
            {finalSummary}
          </pre>
        </details>
      )}
    </motion.div>
  );
}
