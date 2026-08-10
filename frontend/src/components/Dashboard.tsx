"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { BackendOffline } from "@/components/BackendOffline";
import { IncidentDrawer } from "@/components/IncidentDrawer";
import { KpiStrip } from "@/components/KpiStrip";
import { LineagePanel } from "@/components/LineagePanel";
import { PreviewBadge } from "@/components/PreviewBadge";
import { RightPanel } from "@/components/RightPanel";
import { TopBar } from "@/components/TopBar";
import { useIncidentStream } from "@/hooks/useIncidentStream";
import {
  getLineageGraph,
  getMetricsSnapshot,
  repairIncident,
  resetDemo,
} from "@/lib/api";
import {
  PLACEHOLDER_INCIDENT,
  PLACEHOLDER_INCIDENT_RESOLVED,
  PLACEHOLDER_METRICS,
  PLACEHOLDER_METRICS_AFTER,
} from "@/lib/placeholder";
import type {
  IncidentState,
  LineageGraph,
  MetricSnapshot,
} from "@/lib/types";

type ConnectionState = "loading" | "online" | "offline";

export function Dashboard() {
  const searchParams = useSearchParams();
  const previewParam = searchParams.get("preview");
  // Dev preview mode: ?preview=1 (root-cause stage) or ?preview=resolved.
  // Placeholder fixtures are ONLY consumed on this path, and the PREVIEW DATA
  // watermark is always rendered alongside them.
  const preview =
    previewParam === "1" || previewParam === "true"
      ? "root-cause"
      : previewParam === "resolved"
        ? "resolved"
        : null;

  const [connection, setConnection] = useState<ConnectionState>("loading");
  const [metrics, setMetrics] = useState<MetricSnapshot | null>(null);
  const [graph, setGraph] = useState<LineageGraph | null>(null);
  const [incidentId, setIncidentId] = useState<string | null>(null);
  const [repairing, setRepairing] = useState(false);
  const [resetting, setResetting] = useState(false);

  const { state: streamedIncident } = useIncidentStream(
    preview ? null : incidentId,
  );

  const loadBase = useCallback(async () => {
    setConnection("loading");
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
  }, []);

  useEffect(() => {
    if (preview) return;
    void loadBase();
  }, [preview, loadBase]);

  /* ---------------- derive displayed data ---------------- */

  const previewIncident: IncidentState | null = useMemo(() => {
    if (preview === "root-cause") return PLACEHOLDER_INCIDENT;
    if (preview === "resolved") return PLACEHOLDER_INCIDENT_RESOLVED;
    return null;
  }, [preview]);

  const incident = preview ? previewIncident : streamedIncident;

  const displayedMetrics: MetricSnapshot | null = preview
    ? preview === "resolved"
      ? PLACEHOLDER_METRICS_AFTER
      : PLACEHOLDER_METRICS
    : (incident?.metric_after ?? incident?.metric_before ?? metrics);

  const nodes = incident?.nodes ?? graph?.nodes ?? [];
  const edges = incident?.edges ?? graph?.edges ?? [];
  const stage = incident?.stage ?? null;

  /* ---------------- actions (stubs wired to API) ---------------- */

  const handleResetDemo = useCallback(async () => {
    setResetting(true);
    try {
      if (!preview) {
        await resetDemo();
        setIncidentId(null);
        await loadBase();
      }
    } catch (err) {
      console.error("Reset demo failed:", err);
    } finally {
      setResetting(false);
    }
  }, [preview, loadBase]);

  const handleRepair = useCallback(async () => {
    if (!incident || preview) return;
    setRepairing(true);
    try {
      await repairIncident(incident.id);
    } catch (err) {
      console.error("Repair failed:", err);
    } finally {
      setRepairing(false);
    }
  }, [incident, preview]);

  // Exposed for later wiring (report form / demo trigger will set this).
  void setIncidentId;

  /* ---------------- render ---------------- */

  const offline = !preview && connection === "offline";
  const loading = !preview && connection === "loading";

  return (
    <div className="flex h-dvh flex-col overflow-hidden bg-zinc-950">
      <TopBar
        stage={stage}
        onResetDemo={handleResetDemo}
        resetting={resetting}
      />

      {offline ? (
        <BackendOffline onRetry={loadBase} retrying={loading} />
      ) : loading ? (
        <div className="flex flex-1 items-center justify-center">
          <p className="animate-pulse font-mono text-xs tracking-widest text-zinc-500">
            CONNECTING TO BLACKBOX API…
          </p>
        </div>
      ) : (
        <>
          <KpiStrip metrics={displayedMetrics} nodes={nodes} stage={stage} />
          <main className="grid min-h-0 flex-1 grid-cols-1 gap-3 px-4 pb-4 lg:grid-cols-[62fr_38fr]">
            <LineagePanel nodes={nodes} edges={edges} />
            <RightPanel
              evidence={incident?.evidence ?? []}
              hypotheses={incident?.hypotheses ?? []}
            />
          </main>
        </>
      )}

      <IncidentDrawer
        incident={incident ?? null}
        onRepair={handleRepair}
        repairing={repairing}
      />

      {preview && <PreviewBadge variant={preview} />}
    </div>
  );
}
