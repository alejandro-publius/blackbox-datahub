"use client";

import { motion, AnimatePresence } from "framer-motion";
import { STAGE_STYLES } from "@/lib/status";
import type { IncidentStage } from "@/lib/types";
import { cn } from "@/lib/utils";

export function StagePill({
  stage,
  className,
}: {
  stage: IncidentStage;
  className?: string;
}) {
  const style = STAGE_STYLES[stage];
  return (
    <AnimatePresence mode="popLayout" initial={false}>
      <motion.span
        key={stage}
        initial={{ opacity: 0, y: 4 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -4 }}
        transition={{ duration: 0.18 }}
        className={cn(
          "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium tracking-wide",
          style.className,
          className,
        )}
      >
        <span className={cn("size-1.5 rounded-full", style.dot)} />
        {style.label.toUpperCase()}
      </motion.span>
    </AnimatePresence>
  );
}
