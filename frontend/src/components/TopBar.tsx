"use client";

import { RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { StagePill } from "@/components/StagePill";
import type { IncidentStage } from "@/lib/types";

export function TopBar({
  stage,
  onResetDemo,
  resetting,
}: {
  stage: IncidentStage | null;
  onResetDemo: () => void;
  resetting?: boolean;
}) {
  return (
    <header className="flex h-14 shrink-0 items-center justify-between border-b border-zinc-800 bg-zinc-950 px-4">
      <div className="flex items-baseline gap-3">
        <span className="select-none text-lg font-semibold tracking-[0.14em] text-zinc-100">
          ◼ BLACKBOX
        </span>
        <span className="hidden text-xs text-zinc-400 sm:inline">
          Autonomous Data Incident Response
        </span>
      </div>
      <div className="flex items-center gap-3">
        {stage ? (
          <StagePill stage={stage} />
        ) : (
          <span className="inline-flex items-center gap-1.5 rounded-full border border-zinc-700 bg-zinc-800/50 px-2.5 py-0.5 text-xs font-medium tracking-wide text-zinc-400">
            <span className="size-1.5 rounded-full bg-zinc-500" />
            STANDBY
          </span>
        )}
        <Button
          variant="outline"
          size="sm"
          onClick={onResetDemo}
          disabled={resetting}
          className="border-zinc-700 bg-zinc-900 text-zinc-300 hover:bg-zinc-800 hover:text-zinc-100"
        >
          <RotateCcw data-icon="inline-start" />
          Reset Demo
        </Button>
      </div>
    </header>
  );
}
