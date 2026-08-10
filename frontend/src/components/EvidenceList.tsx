"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { ChevronRight } from "lucide-react";
import { formatTime } from "@/lib/format";
import { SOURCE_STYLES } from "@/lib/status";
import type { EvidenceItem } from "@/lib/types";
import { cn } from "@/lib/utils";

/** Compact labels for the transport that produced a fact. Unknown values fall
 *  through to the raw string rather than being hidden. */
const TRANSPORT_LABELS: Record<string, string> = {
  "datahub-mcp-server": "MCP",
  "datahub-mcp-server+graphql": "MCP",
  "datahub-agent-context": "ACK",
  "datahub-graphql": "GRAPHQL",
  duckdb: "DUCKDB",
  pytest: "PYTEST",
  git: "GIT",
};

export const KIND_LABELS: Record<EvidenceItem["kind"], string> = {
  metadata: "METADATA",
  profile: "PROFILE",
  baseline_comparison: "BASELINE",
  sql: "SQL",
  lineage: "LINEAGE",
  test: "TEST",
  patch: "PATCH",
  writeback: "WRITEBACK",
};

export function EvidenceList({ items }: { items: EvidenceItem[] }) {
  const [openId, setOpenId] = useState<string | null>(null);

  if (items.length === 0) {
    return (
      <p className="px-1 py-8 text-center text-xs text-zinc-500">
        No evidence collected yet.
      </p>
    );
  }

  return (
    <div className="space-y-1.5">
      {items.map((item) => {
        const open = openId === item.id;
        const source = SOURCE_STYLES[item.source];
        return (
          <div
            key={item.id}
            className="overflow-hidden rounded-lg border border-zinc-800 bg-zinc-950/60"
          >
            <button
              type="button"
              onClick={() => setOpenId(open ? null : item.id)}
              className="flex w-full items-center gap-2 px-3 py-2 text-left hover:bg-zinc-900"
            >
              <ChevronRight
                className={cn(
                  "size-3.5 shrink-0 text-zinc-500 transition-transform",
                  open && "rotate-90",
                )}
              />
              <span className="shrink-0 rounded border border-zinc-700 bg-zinc-800/60 px-1.5 py-px font-mono text-[9px] font-semibold tracking-wider text-zinc-300">
                {KIND_LABELS[item.kind]}
              </span>
              <span className="min-w-0 flex-1 truncate text-[13px] text-zinc-100">
                {item.title}
              </span>
              {/* Which concrete transport produced this fact. DataHub facts can
                  arrive over MCP, the Agent Context Kit or GraphQL — all reading
                  the same graph, so this is provenance, not corroboration. */}
              {item.transport && (
                <span
                  className="hidden shrink-0 rounded border border-zinc-700/70 bg-zinc-800/40 px-1.5 py-px font-mono text-[9px] tracking-wider text-zinc-400 sm:inline"
                  title={`produced by ${item.transport}`}
                >
                  {TRANSPORT_LABELS[item.transport] ?? item.transport}
                </span>
              )}
              <span
                className={cn(
                  "shrink-0 rounded border px-1.5 py-px text-[9px] font-semibold tracking-wider",
                  source.className,
                )}
              >
                {source.label}
              </span>
            </button>
            {open && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 0.15 }}
                className="border-t border-zinc-800 px-3 py-2"
              >
                <pre className="overflow-x-auto font-mono text-[11px] leading-relaxed whitespace-pre-wrap text-zinc-300">
                  {item.detail}
                </pre>
                <p className="mt-1.5 font-mono text-[10px] tabular-nums text-zinc-600">
                  {formatTime(item.ts)} · {item.id}
                </p>
              </motion.div>
            )}
          </div>
        );
      })}
    </div>
  );
}
