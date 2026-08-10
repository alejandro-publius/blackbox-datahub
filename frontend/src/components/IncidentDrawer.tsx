"use client";

import { AnimatePresence, motion } from "framer-motion";
import { RootCauseCard } from "@/components/RootCauseCard";
import { ResolutionCard } from "@/components/ResolutionCard";
import { AFFECTED_STATUSES } from "@/lib/status";
import type { IncidentState } from "@/lib/types";

const ROOT_CAUSE_STAGES: IncidentState["stage"][] = [
  "ROOT_CAUSE_CONFIRMED",
  "REPAIR_GENERATED",
  "REPAIR_TESTING",
];

const RESOLVED_STAGES: IncidentState["stage"][] = [
  "VERIFIED",
  "WRITEBACK_COMPLETE",
];

/**
 * Bottom drawer that surfaces the RootCauseCard / ResolutionCard at the
 * appropriate incident stages. Placeholder wiring — driven entirely by the
 * IncidentState passed in.
 */
export function IncidentDrawer({
  incident,
  onRepair,
  repairing,
}: {
  incident: IncidentState | null;
  onRepair: () => void;
  repairing?: boolean;
}) {
  const showRootCause =
    incident?.root_cause && ROOT_CAUSE_STAGES.includes(incident.stage);
  const showResolution = incident && RESOLVED_STAGES.includes(incident.stage);

  return (
    <AnimatePresence>
      {(showRootCause || showResolution) && (
        <motion.div
          key={showResolution ? "resolution" : "root-cause"}
          initial={{ y: 40, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          exit={{ y: 40, opacity: 0 }}
          transition={{ duration: 0.3, ease: "easeOut" }}
          className="pointer-events-none fixed inset-x-0 bottom-0 z-40 px-4 pb-4"
        >
          <div className="pointer-events-auto mx-auto max-h-[60vh] max-w-4xl overflow-y-auto rounded-xl shadow-2xl shadow-black/60">
            {showResolution ? (
              <ResolutionCard
                patch={incident.patch}
                testsAfter={incident.tests_after}
                metricBefore={incident.metric_before}
                metricAfter={incident.metric_after}
                writeback={incident.writeback}
              />
            ) : showRootCause && incident.root_cause ? (
              <RootCauseCard
                rootCause={incident.root_cause}
                metric={incident.metric_before}
                evidence={incident.evidence}
                affectedCount={
                  incident.nodes.filter((n) =>
                    AFFECTED_STATUSES.includes(n.status),
                  ).length
                }
                onRepair={onRepair}
                repairing={repairing}
              />
            ) : null}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
