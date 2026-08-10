"use client";

import { useEffect, useRef, useState } from "react";
import { getIncident, incidentEventsUrl } from "@/lib/api";
import { isTerminalStage, type IncidentState } from "@/lib/types";

const MAX_SSE_RETRIES = 5;
const BASE_RETRY_MS = 1000; // 1s, 2s, 4s, 8s, 16s
const POLL_INTERVAL_MS = 5000;

/**
 * Subscribes to the SSE stream for an incident.
 *
 * The backend emits named events:
 *  - `state`: a FULL IncidentState JSON snapshot (idempotent — just replace)
 *  - `ping`: keep-alive every ~15s
 *
 * Resilience:
 *  - on stream error: close + reconnect with exponential backoff, up to
 *    MAX_SSE_RETRIES attempts;
 *  - while the stream is down (including after retries are exhausted) the
 *    hook polls GET /api/incidents/{id} every 5s as belt-and-braces;
 *  - stale snapshots (a poll response racing a newer SSE event) are dropped
 *    by comparing `updated_at`;
 *  - on a terminal stage (WRITEBACK_COMPLETE / NO_INCIDENT / FAILED) the
 *    stream and the poller are both shut down for good.
 */
export function useIncidentStream(incidentId: string | null | undefined) {
  // State is keyed by incident id so switching incidents implicitly resets
  // to null without a synchronous setState inside the effect.
  const [snapshotById, setSnapshotById] = useState<{
    id: string;
    snapshot: IncidentState;
  } | null>(null);
  const [connectedId, setConnectedId] = useState<string | null>(null);
  const [lastPing, setLastPing] = useState<number | null>(null);

  const lastUpdatedRef = useRef<number>(0);

  useEffect(() => {
    lastUpdatedRef.current = 0;
    if (!incidentId) return;

    let disposed = false;
    let done = false;
    let source: EventSource | null = null;
    let retryTimer: ReturnType<typeof setTimeout> | undefined;
    let pollTimer: ReturnType<typeof setInterval> | undefined;
    let retries = 0;

    const stopPolling = () => {
      if (pollTimer) {
        clearInterval(pollTimer);
        pollTimer = undefined;
      }
    };

    const shutdown = () => {
      done = true;
      if (retryTimer) clearTimeout(retryTimer);
      stopPolling();
      source?.close();
      source = null;
      if (!disposed) {
        setConnectedId((c) => (c === incidentId ? null : c));
      }
    };

    const applySnapshot = (snapshot: IncidentState) => {
      if (disposed || snapshot.id !== incidentId) return;
      const ts = Date.parse(snapshot.updated_at);
      // Drop stale snapshots (a slow poll response racing a newer SSE event).
      if (!Number.isNaN(ts) && ts < lastUpdatedRef.current) return;
      if (!Number.isNaN(ts)) lastUpdatedRef.current = ts;
      setSnapshotById({ id: incidentId, snapshot });
      if (isTerminalStage(snapshot.stage)) shutdown();
    };

    const startPolling = () => {
      if (disposed || done || pollTimer) return;
      pollTimer = setInterval(() => {
        getIncident(incidentId)
          .then(applySnapshot)
          .catch(() => {
            /* backend unreachable — keep trying */
          });
      }, POLL_INTERVAL_MS);
    };

    const connect = () => {
      if (disposed || done) return;
      const es = new EventSource(incidentEventsUrl(incidentId));
      source = es;

      es.onopen = () => {
        setConnectedId(incidentId);
        retries = 0;
        stopPolling();
      };

      es.addEventListener("state", (event) => {
        try {
          applySnapshot(
            JSON.parse((event as MessageEvent<string>).data) as IncidentState,
          );
        } catch (err) {
          console.error("useIncidentStream: bad state payload", err);
        }
      });

      es.addEventListener("ping", () => setLastPing(Date.now()));

      es.onerror = () => {
        setConnectedId((c) => (c === incidentId ? null : c));
        es.close();
        if (disposed || done) return;
        // Belt-and-braces: poll while the stream is down.
        startPolling();
        if (retries < MAX_SSE_RETRIES) {
          const delay = BASE_RETRY_MS * 2 ** retries;
          retries += 1;
          retryTimer = setTimeout(connect, delay);
        }
        // After MAX_SSE_RETRIES the poller keeps state flowing on its own.
      };
    };

    connect();

    return () => {
      disposed = true;
      shutdown();
    };
  }, [incidentId]);

  const state =
    incidentId && snapshotById?.id === incidentId ? snapshotById.snapshot : null;
  const connected = !!incidentId && connectedId === incidentId;

  return { state, connected, lastPing };
}
