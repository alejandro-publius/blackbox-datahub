"use client";

import { AnimatePresence, motion } from "framer-motion";
import { CircleCheck, Loader2, TriangleAlert } from "lucide-react";
import { ResolutionCard } from "@/components/ResolutionCard";
import { RootCauseCard } from "@/components/RootCauseCard";
import { AFFECTED_STATUSES, STAGE_STYLES } from "@/lib/status";
import type { IncidentState } from "@/lib/types";

const REPAIRING_STAGES: IncidentState["stage"][] = [
  "REPAIR_GENERATED",
  "REPAIR_TESTING",
];

const RESOLVED_STAGES: IncidentState["stage"][] = [
  "VERIFIED",
  "WRITEBACK_COMPLETE",
];

/**
 * Stage-driven overlays:
 *  - ROOT_CAUSE_CONFIRMED (root cause present, no patch yet): dramatic
 *    center-screen RootCauseCard with backdrop — the screenshot moment.
 *    Dismissible; a persistent Repair & Verify button lives in the TopBar.
 *  - REPAIR_GENERATED / REPAIR_TESTING: slim bottom progress strip while the
 *    repair pipeline runs (patch → rebuild → invariants).
 *  - VERIFIED / WRITEBACK_COMPLETE: bottom-drawer ResolutionCard.
 *  - FAILED: red error banner. NO_INCIDENT: calm all-clear.
 */
export function IncidentDrawer({
  incident,
  onRepair,
  repairing,
  dismissed,
  onDismiss,
}: {
  incident: IncidentState | null;
  onRepair: () => void;
  repairing?: boolean;
  /** overlay hidden by the operator to inspect the graph */
  dismissed?: boolean;
  onDismiss?: () => void;
}) {
  if (!incident) return null;

  const stage = incident.stage;
  const showRootCause =
    stage === "ROOT_CAUSE_CONFIRMED" && !!incident.root_cause && !incident.patch;
  const showRepairing =
    REPAIRING_STAGES.includes(stage) ||
    // brief window where repair started but the stage event hasn't landed yet
    (stage === "ROOT_CAUSE_CONFIRMED" && !!incident.patch);
  const showResolution = RESOLVED_STAGES.includes(stage);
  const showFailed = stage === "FAILED";
  const showAllClear = stage === "NO_INCIDENT";

  const affectedCount = incident.nodes.filter((n) =>
    AFFECTED_STATUSES.includes(n.status),
  ).length;

  return (
    <>
      {/* Root cause — dramatic center overlay */}
      <AnimatePresence>
        {showRootCause && !dismissed && (
          <motion.div
            key="root-cause-overlay"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.25 }}
            className="fixed inset-0 z-40 flex items-center justify-center bg-zinc-950/60 p-4 backdrop-blur-[2px]"
            onClick={onDismiss}
          >
            <motion.div
              initial={{ opacity: 0, y: 28, scale: 0.97 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 28, scale: 0.97 }}
              transition={{ duration: 0.3, ease: "easeOut" }}
              className="max-h-[85vh] w-full max-w-3xl overflow-y-auto rounded-xl shadow-2xl shadow-black/70"
              onClick={(e) => e.stopPropagation()}
            >
              <RootCauseCard
                rootCause={incident.root_cause!}
                metric={incident.metric_before}
                evidence={incident.evidence}
                affectedCount={affectedCount}
                onRepair={onRepair}
                repairing={repairing}
                onDismiss={onDismiss}
              />
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Repair in progress — slim bottom strip */}
      <AnimatePresence>
        {showRepairing && (
          <motion.div
            key="repair-strip"
            initial={{ y: 32, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: 32, opacity: 0 }}
            transition={{ duration: 0.25, ease: "easeOut" }}
            className="pointer-events-none fixed inset-x-0 bottom-0 z-40 px-4 pb-4"
          >
            <div className="pointer-events-auto mx-auto flex max-w-3xl items-center gap-3 rounded-xl border border-amber-400/40 bg-zinc-900 px-4 py-3 shadow-2xl shadow-black/60">
              <Loader2 className="size-4 shrink-0 animate-spin text-amber-400" />
              <span className="text-sm font-bold tracking-[0.14em] text-amber-400">
                {STAGE_STYLES[stage].label.toUpperCase()}
              </span>
              <span className="min-w-0 flex-1 truncate font-mono text-[11px] text-zinc-400">
                {incident.patch
                  ? `patching ${incident.patch.file} → rebuild → invariant suite`
                  : "generating repair…"}
              </span>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Resolution — bottom drawer */}
      <AnimatePresence>
        {showResolution && !dismissed && (
          <motion.div
            key="resolution"
            initial={{ y: 40, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: 40, opacity: 0 }}
            transition={{ duration: 0.3, ease: "easeOut" }}
            className="pointer-events-none fixed inset-x-0 bottom-0 z-40 px-4 pb-4"
          >
            <div className="pointer-events-auto mx-auto max-h-[70vh] max-w-4xl overflow-y-auto rounded-xl shadow-2xl shadow-black/60">
              <ResolutionCard
                patch={incident.patch}
                testsAfter={incident.tests_after}
                metricBefore={incident.metric_before}
                metricAfter={incident.metric_after}
                writeback={incident.writeback}
                gitArtifact={incident.git_artifact}
                finalSummary={incident.final_summary}
                onDismiss={onDismiss}
              />
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Failed — red banner */}
      <AnimatePresence>
        {showFailed && !dismissed && (
          <motion.div
            key="failed"
            initial={{ y: 40, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: 40, opacity: 0 }}
            transition={{ duration: 0.25, ease: "easeOut" }}
            className="pointer-events-none fixed inset-x-0 bottom-0 z-40 px-4 pb-4"
          >
            <div className="pointer-events-auto mx-auto flex max-w-3xl items-start gap-3 rounded-xl border border-red-400/50 bg-zinc-900 px-4 py-3.5 shadow-2xl shadow-black/60">
              <TriangleAlert className="mt-0.5 size-5 shrink-0 text-red-400" />
              <div className="min-w-0 flex-1">
                <div className="text-sm font-bold tracking-[0.14em] text-red-400">
                  INVESTIGATION FAILED
                </div>
                <p className="mt-1 font-mono text-[11px] leading-relaxed break-words whitespace-pre-wrap text-zinc-400">
                  {incident.error ?? "Unknown error — check the backend logs."}
                </p>
                <p className="mt-1.5 text-[11px] text-zinc-500">
                  Reset the demo to return to the initial broken state.
                </p>
              </div>
              {onDismiss && (
                <button
                  type="button"
                  onClick={onDismiss}
                  className="shrink-0 rounded-md px-1.5 text-lg leading-none text-zinc-500 hover:text-zinc-200"
                  aria-label="Dismiss"
                >
                  ×
                </button>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* No incident — calm all-clear */}
      <AnimatePresence>
        {showAllClear && !dismissed && (
          <motion.div
            key="all-clear"
            initial={{ y: 40, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: 40, opacity: 0 }}
            transition={{ duration: 0.25, ease: "easeOut" }}
            className="pointer-events-none fixed inset-x-0 bottom-0 z-40 px-4 pb-4"
          >
            <div className="pointer-events-auto mx-auto flex max-w-3xl items-start gap-3 rounded-xl border border-emerald-400/40 bg-zinc-900 px-4 py-3.5 shadow-2xl shadow-black/60">
              <CircleCheck className="mt-0.5 size-5 shrink-0 text-emerald-400" />
              <div className="min-w-0 flex-1">
                <div className="text-sm font-bold tracking-[0.14em] text-emerald-400">
                  ALL CLEAR — NO INCIDENT
                </div>
                <p className="mt-1 text-xs leading-relaxed text-zinc-400">
                  {incident.final_summary ??
                    "The agent found no evidence of a data incident. Metrics are within expected bounds."}
                </p>
              </div>
              {onDismiss && (
                <button
                  type="button"
                  onClick={onDismiss}
                  className="shrink-0 rounded-md px-1.5 text-lg leading-none text-zinc-500 hover:text-zinc-200"
                  aria-label="Dismiss"
                >
                  ×
                </button>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
