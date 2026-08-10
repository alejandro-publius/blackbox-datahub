"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { formatUsd } from "@/lib/format";
import type { MetricSnapshot } from "@/lib/types";

/**
 * Daily revenue mini area chart with a thin baseline (expected) overlay.
 * Inline SVG — no chart library. Single series + reference line, so no
 * legend box; the baseline carries a direct "expected" label and anomalous
 * points are marked in the reserved critical color WITH a text badge
 * (never color alone).
 */

const PAD_TOP = 8;
const PAD_BOTTOM = 14;
const PAD_X = 4;

// zinc-400 series / zinc-500 baseline / red-400 anomaly — all >=3:1 vs zinc-900
const SERIES = "#a1a1aa";
const SERIES_FILL = "rgba(161, 161, 170, 0.12)";
const BASELINE = "#71717a";
const ANOMALY = "#f87171";

interface Point {
  day: string;
  revenue: number;
  baseline?: number;
  anomalous: boolean;
}

export function RevenueChart({ metrics }: { metrics: MetricSnapshot }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ w: 0, h: 0 });
  const [hover, setHover] = useState<number | null>(null);
  const width = size.w;
  const H = Math.max(48, size.h);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => {
      const rect = entries[0]?.contentRect;
      if (rect) setSize({ w: rect.width, h: rect.height });
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const points = useMemo<Point[]>(
    () =>
      metrics.daily.map((d) => ({
        day: d.day,
        revenue: d.revenue_usd,
        baseline: d.baseline,
        anomalous:
          d.baseline != null &&
          d.baseline > 0 &&
          (d.revenue_usd / d.baseline > 1.5 || d.revenue_usd / d.baseline < 0.6),
      })),
    [metrics.daily],
  );

  const n = points.length;
  const innerW = Math.max(0, width - PAD_X * 2);
  const plotH = H - PAD_TOP - PAD_BOTTOM;

  const maxY = useMemo(
    () =>
      Math.max(
        1,
        ...points.map((p) => Math.max(p.revenue, p.baseline ?? 0)),
      ) * 1.05,
    [points],
  );

  const x = (i: number) => PAD_X + (n <= 1 ? innerW / 2 : (i / (n - 1)) * innerW);
  const y = (v: number) => PAD_TOP + plotH - (v / maxY) * plotH;

  const { areaPath, linePath, baselinePath, anomalyPath } = useMemo(() => {
    if (n === 0 || innerW <= 0)
      return { areaPath: "", linePath: "", baselinePath: "", anomalyPath: "" };
    const line = points
      .map((p, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)},${y(p.revenue).toFixed(1)}`)
      .join("");
    const area = `${line}L${x(n - 1).toFixed(1)},${(PAD_TOP + plotH).toFixed(1)}L${x(0).toFixed(1)},${(PAD_TOP + plotH).toFixed(1)}Z`;
    const baseline = points
      .map((p, i) =>
        p.baseline == null
          ? ""
          : `${i === 0 || points[i - 1].baseline == null ? "M" : "L"}${x(i).toFixed(1)},${y(p.baseline).toFixed(1)}`,
      )
      .join("");
    // Overpaint the contiguous anomalous tail in the critical color.
    let anomaly = "";
    for (let i = 0; i < n; i++) {
      if (points[i].anomalous) {
        const from = Math.max(0, i - 1);
        anomaly = points
          .slice(from)
          .map(
            (p, j) =>
              `${j === 0 ? "M" : "L"}${x(from + j).toFixed(1)},${y(p.revenue).toFixed(1)}`,
          )
          .join("");
        break;
      }
    }
    return { areaPath: area, linePath: line, baselinePath: baseline, anomalyPath: anomaly };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [points, innerW, maxY, n, H]);

  const last = points[n - 1];
  const hovered = hover != null ? points[hover] : null;

  const handleMove = (e: React.PointerEvent<SVGSVGElement>) => {
    if (n === 0 || innerW <= 0) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const px = e.clientX - rect.left - PAD_X;
    const i = Math.round((px / innerW) * (n - 1));
    setHover(Math.min(n - 1, Math.max(0, i)));
  };

  return (
    <div className="flex h-full flex-col rounded-lg border border-zinc-800 bg-zinc-900 px-4 py-3">
      <div className="flex shrink-0 items-center justify-between gap-2">
        <span className="text-[11px] font-medium uppercase tracking-wider text-zinc-400">
          Daily Revenue · {metrics.daily.length}d
        </span>
        <span className="font-mono text-[10px] tabular-nums text-zinc-500">
          <span style={{ color: BASELINE }}>┄ expected</span>
          {last?.anomalous && (
            <span className="ml-2 rounded border border-red-400/40 bg-red-400/10 px-1 py-px font-semibold text-red-400">
              ANOMALY
            </span>
          )}
        </span>
      </div>
      <div
        ref={containerRef}
        className="relative mt-1 min-h-[72px] flex-1 overflow-visible"
      >
        {width > 0 && n > 0 && (
          <svg
            width={width}
            height={H}
            className="block cursor-crosshair"
            role="img"
            aria-label={`Daily revenue, ${metrics.daily.length} days. Latest ${formatUsd(last.revenue)} vs expected ${formatUsd(metrics.expected_revenue)}.`}
            onPointerMove={handleMove}
            onPointerLeave={() => setHover(null)}
          >
            <path d={areaPath} fill={SERIES_FILL} />
            <path d={linePath} fill="none" stroke={SERIES} strokeWidth={1.5} />
            {baselinePath && (
              <path
                d={baselinePath}
                fill="none"
                stroke={BASELINE}
                strokeWidth={1}
                strokeDasharray="3 3"
              />
            )}
            {anomalyPath && (
              <path d={anomalyPath} fill="none" stroke={ANOMALY} strokeWidth={1.8} />
            )}
            {last && (
              <circle
                cx={x(n - 1)}
                cy={y(last.revenue)}
                r={3}
                fill={last.anomalous ? ANOMALY : SERIES}
                stroke="#18181b"
                strokeWidth={2}
              />
            )}
            {hover != null && hovered && (
              <g>
                <line
                  x1={x(hover)}
                  x2={x(hover)}
                  y1={PAD_TOP}
                  y2={PAD_TOP + plotH}
                  stroke="#52525b"
                  strokeWidth={1}
                  strokeDasharray="2 2"
                />
                <circle
                  cx={x(hover)}
                  cy={y(hovered.revenue)}
                  r={3.5}
                  fill={hovered.anomalous ? ANOMALY : SERIES}
                  stroke="#09090b"
                  strokeWidth={2}
                />
              </g>
            )}
            {/* x-axis day labels: first + last only (recessive) */}
            <text
              x={PAD_X}
              y={H - 2}
              fill="#52525b"
              fontSize={9}
              fontFamily="var(--font-geist-mono, monospace)"
            >
              {points[0].day.slice(5)}
            </text>
            <text
              x={PAD_X + innerW}
              y={H - 2}
              fill="#52525b"
              fontSize={9}
              textAnchor="end"
              fontFamily="var(--font-geist-mono, monospace)"
            >
              {last.day.slice(5)}
            </text>
          </svg>
        )}
        {hover != null && hovered && width > 0 && (
          <div
            className="pointer-events-none absolute top-0 z-10 -translate-y-1 rounded-md border border-zinc-700 bg-zinc-950/95 px-2 py-1 shadow-lg"
            style={{
              left: Math.min(Math.max(x(hover) - 60, 0), Math.max(width - 130, 0)),
            }}
          >
            <div className="font-mono text-[10px] tabular-nums text-zinc-400">
              {hovered.day}
            </div>
            <div className="font-mono text-[11px] font-semibold tabular-nums text-zinc-100">
              {formatUsd(hovered.revenue)}
              {hovered.anomalous && (
                <span className="ml-1 text-red-400">
                  ×{(hovered.revenue / (hovered.baseline || 1)).toFixed(0)}
                </span>
              )}
            </div>
            {hovered.baseline != null && (
              <div className="font-mono text-[10px] tabular-nums text-zinc-500">
                expected {formatUsd(hovered.baseline)}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
