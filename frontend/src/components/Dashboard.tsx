"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { useSearchParams } from "next/navigation";
import { Siren } from "lucide-react";
import { BackendOffline } from "@/components/BackendOffline";
import { IncidentDialog } from "@/components/IncidentDialog";
import { IncidentDrawer } from "@/components/IncidentDrawer";
import { KpiStrip } from "@/components/KpiStrip";
import { LineagePanel } from "@/components/LineagePanel";
import { PreviewBadge } from "@/components/PreviewBadge";
import { RightPanel } from "@/components/RightPanel";
import { TopBar } from "@/components/TopBar";
import { Button } from "@/components/ui/button";
import { useIncidentStream } from "@/hooks/useIncidentStream";
import {
  ApiError,
  createIncident,
  getLineageGraph,
  getMetricsSnapshot,
  listIncidents,
  repairIncident,
  resetDemo,
} from "@/lib/api";
import {
  PLACEHOLDER_GRAPH,
  PLACEHOLDER_INCIDENT,
  PLACEHOLDER_INCIDENT_INVESTIGATING,
  PLACEHOLDER_INCIDENT_RESOLVED,
  PLACEHOLDER_METRICS,
  PLACEHOLDER_METRICS_AFTER,
} from "@/lib/placeholder";
import {
  isTerminalStage,
  type IncidentState,
  type LineageEdge,
  type LineageGraph,
  type LineageNode,
  type MetricSnapshot,
} from "@/lib/types";

type ConnectionState = "loading" | "online" | "offline";

type PreviewState = "intake" | "investigating" | "rootcause" | "resolved";

const PREVIEW_INCIDENTS: Record<PreviewState, IncidentState | null> = {
  intake: null,
  investigating: PLACEHOLDER_INCIDENT_INVESTIGATING,
  rootcause: PLACEHOLDER_INCIDENT,
  resolved: PLACEHOLDER_INCIDENT_RESOLVED,
};

/**
 * Dev preview mode (layout QA without the backend):
 *   ?preview=1&state=intake|investigating|rootcause|resolved
 * Legacy aliases: ?preview=1 → intake, ?preview=resolved → resolved.
 * Placeholder fixtures are ONLY consumed on this path and the PREVIEW DATA
 * watermark is always rendered alongside them.
 */
function parsePreview(
  previewParam: string | null,
  stateParam: string | null,
): PreviewState | null {
  if (!previewParam) return null;
  if (previewParam === "resolved") return "resolved";
  if (previewParam !== "1" && previewParam !== "true") return null;
  if (
    stateParam === "intake" ||
    stateParam === "investigating" ||
    stateParam === "rootcause" ||
    stateParam === "resolved"
  ) {
    return stateParam;
  }
  return "intake";
}

export function Dashboard() {
  const searchParams = useSearchParams();
  const preview = parsePreview(
    searchParams.get("preview"),
    searchParams.get("state"),
  );

  const [connection, setConnection] = useState<ConnectionState>("loading");
  const [metrics, setMetrics] = useState<MetricSnapshot | null>(null);
  const [graph, setGraph] = useState<LineageGraph | null>(null);
  const [incidentId, setIncidentId] = useState<string | null>(null);

  const [dialogOpen, setDialogOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const [repairRequested, setRepairRequested] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [overlayDismissed, setOverlayDismissed] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const { state: streamedIncident } = useIncidentStream(
    preview ? null : incidentId,
  );

  /* ---------------- base data ---------------- */

  const loadBase = useCallback(async (resume = false) => {
    const [metricsResult, graphResult] = await Promise.allSettled([
      getMetricsSnapshot(),
      getLineageGraph(),
    ]);
    const anyOk =
      metricsResult.status === "fulfilled" ||
      graphResult.status === "fulfilled";
    if (metricsResult.status === "fulfilled") setMetrics(metricsResult.value);
    if (graphResult.status === "fulfilled") setGraph(graphResult.value);
    setConnection(anyOk ? "online" : "offline");
    if (anyOk && resume) {
      // Resume an in-flight investigation after a page refresh.
      try {
        const incidents = await listIncidents();
        const latest = incidents[0];
        if (latest && !isTerminalStage(latest.stage)) {
          setIncidentId(latest.id);
        }
      } catch {
        /* non-fatal */
      }
    }
  }, []);

  useEffect(() => {
    if (preview) return;
    const t = setTimeout(() => void loadBase(true), 0);
    return () => clearTimeout(t);
  }, [preview, loadBase]);

  /* ---------------- derive displayed data ---------------- */

  const incident: IncidentState | null = preview
    ? PREVIEW_INCIDENTS[preview]
    : streamedIncident;

  const displayedMetrics: MetricSnapshot | null = preview
    ? preview === "resolved"
      ? PLACEHOLDER_METRICS_AFTER
      : PLACEHOLDER_METRICS
    : (incident?.metric_after ?? metrics ?? incident?.metric_before ?? null);

  const baseGraph = preview ? PLACEHOLDER_GRAPH : graph;

  // Merge incident nodes/edges INTO the base canvas (incident status wins).
  const nodes = useMemo<LineageNode[]>(() => {
    const base = baseGraph?.nodes ?? [];
    const inc = incident?.nodes ?? [];
    if (inc.length === 0) return base;
    const merged = new Map(base.map((n) => [n.urn, n]));
    for (const n of inc) merged.set(n.urn, n);
    return Array.from(merged.values());
  }, [baseGraph, incident]);

  const edges = useMemo<LineageEdge[]>(() => {
    const base = baseGraph?.edges ?? [];
    const inc = incident?.edges ?? [];
    if (inc.length === 0) return base;
    const key = (e: LineageEdge) => `${e.source}->${e.target}`;
    const merged = new Map(base.map((e) => [key(e), e]));
    for (const e of inc) merged.set(key(e), e);
    return Array.from(merged.values());
  }, [baseGraph, incident]);

  const stage = incident?.stage ?? null;
  const repairing = repairRequested && stage === "ROOT_CAUSE_CONFIRMED";

  // Re-show the stage overlay whenever the stage advances
  // (render-time state adjustment, per React guidance).
  const [lastStage, setLastStage] = useState(stage);
  if (stage !== lastStage) {
    setLastStage(stage);
    setOverlayDismissed(false);
  }

  const overlayAvailable =
    !!incident &&
    ((stage === "ROOT_CAUSE_CONFIRMED" && !!incident.root_cause && !incident.patch) ||
      stage === "VERIFIED" ||
      stage === "WRITEBACK_COMPLETE" ||
      stage === "FAILED" ||
      stage === "NO_INCIDENT");

  /* ---------------- actions ---------------- */

  const handleInvestigate = useCallback(() => {
    setCreateError(null);
    setDialogOpen(true);
  }, []);

  const handleCreateIncident = useCallback(
    async (reportText: string) => {
      if (preview) {
        setDialogOpen(false);
        return;
      }
      setCreating(true);
      setCreateError(null);
      try {
        const { incident_id } = await createIncident(reportText);
        setRepairRequested(false);
        setOverlayDismissed(false);
        setIncidentId(incident_id);
        setDialogOpen(false);
      } catch (err) {
        setCreateError(
          err instanceof ApiError ? err.message : "Failed to create incident",
        );
      } finally {
        setCreating(false);
      }
    },
    [preview],
  );

  const handleRepair = useCallback(async () => {
    if (!incident || preview) return;
    setRepairRequested(true);
    setActionError(null);
    try {
      await repairIncident(incident.id);
    } catch (err) {
      setRepairRequested(false);
      setActionError(
        err instanceof ApiError ? err.message : "Repair request failed",
      );
    }
  }, [incident, preview]);

  const handleResetDemo = useCallback(async () => {
    if (preview) return;
    setResetting(true);
    setActionError(null);
    try {
      await resetDemo(); // ~15-30s: rebuilds the broken fixture
      setIncidentId(null);
      setRepairRequested(false);
      setOverlayDismissed(false);
      await loadBase();
    } catch (err) {
      setActionError(
        err instanceof ApiError ? err.message : "Reset demo failed",
      );
    } finally {
      setResetting(false);
    }
  }, [preview, loadBase]);

  /* ---------------- render ---------------- */

  const offline = !preview && connection === "offline";
  const loading = !preview && connection === "loading";
  const showAnomalyBanner =
    !incident && displayedMetrics?.status === "anomalous" && !offline && !loading;

  return (
    <div className="flex h-dvh flex-col overflow-hidden bg-zinc-950">
      <TopBar
        stage={stage}
        onInvestigate={handleInvestigate}
        onRepair={handleRepair}
        repairing={repairing}
        onResetDemo={handleResetDemo}
        resetting={resetting}
        overlayDismissed={overlayDismissed && overlayAvailable}
        onShowOverlay={() => setOverlayDismissed(false)}
      />

      {offline ? (
        <BackendOffline
          onRetry={() => {
            setConnection("loading");
            void loadBase(true);
          }}
          retrying={loading}
        />
      ) : loading ? (
        <div className="flex flex-1 items-center justify-center">
          <p className="animate-pulse font-mono text-xs tracking-widest text-zinc-500">
            CONNECTING TO BLACKBOX API…
          </p>
        </div>
      ) : (
        <>
          <KpiStrip metrics={displayedMetrics} nodes={nodes} stage={stage} />

          <AnimatePresence>
            {showAnomalyBanner && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                exit={{ opacity: 0, height: 0 }}
                transition={{ duration: 0.2 }}
                className="shrink-0 overflow-hidden px-4 pb-3"
              >
                <div className="flex flex-wrap items-center gap-3 rounded-lg border border-red-400/40 bg-red-400/5 px-4 py-2.5">
                  <Siren className="size-4 shrink-0 text-red-400" />
                  <p className="min-w-0 flex-1 text-xs text-zinc-300">
                    <span className="font-semibold text-red-400">
                      Revenue anomaly detected.
                    </span>{" "}
                    The executive KPI is far outside its expected band. Dispatch
                    the agent to find out why.
                  </p>
                  <Button
                    size="sm"
                    onClick={handleInvestigate}
                    className="bg-red-500 text-white hover:bg-red-600"
                  >
                    <Siren data-icon="inline-start" />
                    Investigate Incident
                  </Button>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          <main className="grid min-h-0 flex-1 grid-cols-1 gap-3 px-4 pb-4 lg:grid-cols-[62fr_38fr]">
            <LineagePanel nodes={nodes} edges={edges} />
            <RightPanel
              evidence={incident?.evidence ?? []}
              hypotheses={incident?.hypotheses ?? []}
            />
          </main>
        </>
      )}

      <IncidentDialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        onSubmit={handleCreateIncident}
        submitting={creating}
        error={createError}
      />

      <IncidentDrawer
        incident={incident}
        onRepair={handleRepair}
        repairing={repairing}
        dismissed={overlayDismissed}
        onDismiss={() => setOverlayDismissed(true)}
      />

      <AnimatePresence>
        {actionError && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 8 }}
            className="fixed bottom-4 left-4 z-50 max-w-sm rounded-lg border border-red-400/40 bg-zinc-950/95 px-3 py-2 shadow-lg"
          >
            <p className="font-mono text-[11px] text-red-400">{actionError}</p>
            <button
              type="button"
              onClick={() => setActionError(null)}
              className="mt-1 text-[10px] text-zinc-500 hover:text-zinc-300"
            >
              dismiss
            </button>
          </motion.div>
        )}
      </AnimatePresence>

      {preview && <PreviewBadge variant={preview} />}
    </div>
  );
}
