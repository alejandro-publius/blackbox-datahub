"use client";

import { useEffect, useRef, useState } from "react";
import { incidentEventsUrl } from "@/lib/api";
import type { IncidentState } from "@/lib/types";

const RETRY_MS = 2000;

/**
 * Subscribes to the SSE stream for an incident.
 *
 * The backend emits:
 *  - `state` events whose data is a full IncidentState JSON snapshot
 *  - `ping` keep-alive events
 *
 * Reconnects with a fixed backoff when the connection errors.
 */
export function useIncidentStream(incidentId: string | null | undefined) {
  const [state, setState] = useState<IncidentState | null>(null);
  const [connected, setConnected] = useState(false);
  const [lastPing, setLastPing] = useState<number | null>(null);
  const sourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    setState(null);
    setConnected(false);
    if (!incidentId) return;

    let disposed = false;
    let retryTimer: ReturnType<typeof setTimeout> | undefined;

    const connect = () => {
      if (disposed) return;
      const es = new EventSource(incidentEventsUrl(incidentId));
      sourceRef.current = es;

      es.onopen = () => setConnected(true);

      es.addEventListener("state", (event) => {
        try {
          const snapshot = JSON.parse(
            (event as MessageEvent<string>).data,
          ) as IncidentState;
          setState(snapshot);
        } catch (err) {
          console.error("useIncidentStream: bad state payload", err);
        }
      });

      es.addEventListener("ping", () => setLastPing(Date.now()));

      es.onerror = () => {
        setConnected(false);
        es.close();
        if (!disposed) retryTimer = setTimeout(connect, RETRY_MS);
      };
    };

    connect();

    return () => {
      disposed = true;
      if (retryTimer) clearTimeout(retryTimer);
      sourceRef.current?.close();
      sourceRef.current = null;
      setConnected(false);
    };
  }, [incidentId]);

  return { state, connected, lastPing };
}
