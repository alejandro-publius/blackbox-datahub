import type { IncidentState, LineageGraph, MetricSnapshot } from "./types";

/**
 * Typed client for the BlackBox backend API.
 * Base URL comes from NEXT_PUBLIC_BLACKBOX_API_URL (default http://localhost:8400).
 */

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_BLACKBOX_API_URL ?? "http://localhost:8400";

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status?: number,
    public readonly url?: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${API_BASE_URL}${path}`;
  let res: Response;
  try {
    res = await fetch(url, {
      cache: "no-store",
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...init?.headers,
      },
    });
  } catch (err) {
    throw new ApiError(
      `Backend unreachable: ${err instanceof Error ? err.message : String(err)}`,
      undefined,
      url,
    );
  }
  if (!res.ok) {
    throw new ApiError(`Request failed: ${res.status} ${res.statusText}`, res.status, url);
  }
  return (await res.json()) as T;
}

export function getHealth(): Promise<{ status: string }> {
  return fetchJson("/api/health");
}

export function getMetricsSnapshot(): Promise<MetricSnapshot> {
  return fetchJson("/api/metrics/snapshot");
}

export function getLineageGraph(): Promise<LineageGraph> {
  return fetchJson("/api/lineage/graph");
}

export function createIncident(
  report_text: string,
): Promise<{ incident_id: string }> {
  return fetchJson("/api/incidents", {
    method: "POST",
    body: JSON.stringify({ report_text }),
  });
}

export function getIncident(id: string): Promise<IncidentState> {
  return fetchJson(`/api/incidents/${encodeURIComponent(id)}`);
}

/** URL for the SSE stream of incident state snapshots (used by EventSource). */
export function incidentEventsUrl(id: string): string {
  return `${API_BASE_URL}/api/incidents/${encodeURIComponent(id)}/events`;
}

export function repairIncident(id: string): Promise<unknown> {
  return fetchJson(`/api/incidents/${encodeURIComponent(id)}/repair`, {
    method: "POST",
  });
}

export function resetDemo(): Promise<unknown> {
  return fetchJson("/api/demo/reset", { method: "POST" });
}
