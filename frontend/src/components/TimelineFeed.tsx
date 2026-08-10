"use client";

import { motion } from "framer-motion";
import {
  BarChart3,
  CloudUpload,
  Database,
  FileDiff,
  FlaskConical,
  GitBranch,
  Terminal,
  TrendingDown,
} from "lucide-react";
import type { ComponentType } from "react";
import { formatTime } from "@/lib/format";
import { SOURCE_STYLES } from "@/lib/status";
import type { EvidenceItem } from "@/lib/types";
import { cn } from "@/lib/utils";

const KIND_ICONS: Record<
  EvidenceItem["kind"],
  ComponentType<{ className?: string }>
> = {
  metadata: Database,
  profile: BarChart3,
  baseline_comparison: TrendingDown,
  sql: Terminal,
  lineage: GitBranch,
  test: FlaskConical,
  patch: FileDiff,
  writeback: CloudUpload,
};

export function TimelineFeed({ items }: { items: EvidenceItem[] }) {
  if (items.length === 0) {
    return (
      <p className="px-1 py-8 text-center text-xs text-zinc-500">
        No events yet. The timeline populates as the agent investigates.
      </p>
    );
  }

  const sorted = [...items].sort(
    (a, b) => new Date(a.ts).getTime() - new Date(b.ts).getTime(),
  );

  return (
    <ol className="relative space-y-0.5">
      {sorted.map((item, idx) => {
        const Icon = KIND_ICONS[item.kind];
        const source = SOURCE_STYLES[item.source];
        const last = idx === sorted.length - 1;
        return (
          <motion.li
            key={item.id}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.2 }}
            className="relative flex gap-3 pb-4"
          >
            {!last && (
              <span
                aria-hidden
                className="absolute top-7 left-[13px] h-[calc(100%-1.25rem)] w-px bg-zinc-800"
              />
            )}
            <span className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-full border border-zinc-800 bg-zinc-950 text-zinc-400">
              <Icon className="size-3.5" />
            </span>
            <div className="min-w-0 flex-1">
              <div className="flex items-start justify-between gap-2">
                <p className="text-[13px] font-medium leading-snug text-zinc-100">
                  {item.title}
                </p>
                <span
                  className={cn(
                    "shrink-0 rounded border px-1.5 py-px text-[9px] font-semibold tracking-wider",
                    source.className,
                  )}
                >
                  {source.label}
                </span>
              </div>
              <p className="mt-1 line-clamp-3 font-mono text-[11px] leading-relaxed break-words whitespace-pre-wrap text-zinc-400">
                {item.detail}
              </p>
              <p className="mt-1 font-mono text-[10px] tabular-nums text-zinc-600">
                {formatTime(item.ts)}
              </p>
            </div>
          </motion.li>
        );
      })}
    </ol>
  );
}
