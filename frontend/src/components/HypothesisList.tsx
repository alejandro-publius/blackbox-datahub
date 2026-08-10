"use client";

import { motion } from "framer-motion";
import { shortUrn } from "@/lib/format";
import { HYPOTHESIS_STATUS_STYLES } from "@/lib/status";
import type { Hypothesis } from "@/lib/types";
import { cn } from "@/lib/utils";

export function HypothesisList({ hypotheses }: { hypotheses: Hypothesis[] }) {
  if (hypotheses.length === 0) {
    return (
      <p className="px-1 py-8 text-center text-xs text-zinc-500">
        No hypotheses yet. Candidates appear once lineage traversal completes.
      </p>
    );
  }

  const order: Hypothesis["status"][] = [
    "confirmed",
    "investigating",
    "proposed",
    "eliminated",
  ];
  const sorted = [...hypotheses].sort(
    (a, b) => order.indexOf(a.status) - order.indexOf(b.status),
  );

  return (
    <div className="space-y-2.5">
      {sorted.map((hyp) => {
        const style = HYPOTHESIS_STATUS_STYLES[hyp.status];
        const eliminated = hyp.status === "eliminated";
        return (
          <motion.div
            key={hyp.id}
            layout
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.2 }}
            className={cn(
              "rounded-lg border border-zinc-800 bg-zinc-950/60 p-3",
              eliminated && "opacity-60",
            )}
          >
            <div className="flex items-start justify-between gap-2">
              <p
                className={cn(
                  "text-[13px] leading-snug text-zinc-100",
                  eliminated && "text-zinc-500 line-through",
                )}
              >
                {hyp.description}
              </p>
              <span
                className={cn(
                  "shrink-0 rounded border px-1.5 py-px text-[9px] font-semibold tracking-wider",
                  style.className,
                )}
              >
                {style.label}
              </span>
            </div>
            <div className="mt-2 flex items-center gap-2">
              <div className="h-1 flex-1 overflow-hidden rounded-full bg-zinc-800">
                <motion.div
                  className={cn("h-full rounded-full", style.bar)}
                  initial={{ width: 0 }}
                  animate={{ width: `${Math.round(hyp.confidence * 100)}%` }}
                  transition={{ duration: 0.4, ease: "easeOut" }}
                />
              </div>
              <span className="w-10 text-right font-mono text-[11px] tabular-nums text-zinc-400">
                {Math.round(hyp.confidence * 100)}%
              </span>
            </div>
            <p
              className="mt-1.5 truncate font-mono text-[10px] text-zinc-500"
              title={hyp.target_urn}
            >
              → {shortUrn(hyp.target_urn)}
            </p>
          </motion.div>
        );
      })}
    </div>
  );
}
