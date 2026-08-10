"use client";

import { Loader2, PanelBottomOpen, Radar, RotateCcw, Wrench } from "lucide-react";
import { Button } from "@/components/ui/button";
import { StagePill } from "@/components/StagePill";
import { isTerminalStage, type IncidentStage } from "@/lib/types";

export function TopBar({
  stage,
  onInvestigate,
  onRepair,
  repairing,
  onResetDemo,
  resetting,
  overlayDismissed,
  onShowOverlay,
}: {
  stage: IncidentStage | null;
  /** opens the intake dialog; hidden while an incident is active */
  onInvestigate?: () => void;
  /** persistent Repair & Verify while stage === ROOT_CAUSE_CONFIRMED */
  onRepair?: () => void;
  repairing?: boolean;
  onResetDemo: () => void;
  resetting?: boolean;
  /** an overlay exists for the current stage but was dismissed */
  overlayDismissed?: boolean;
  onShowOverlay?: () => void;
}) {
  const active = stage !== null && !isTerminalStage(stage);
  const showInvestigate = onInvestigate && !active;
  const showRepair = onRepair && stage === "ROOT_CAUSE_CONFIRMED";

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
        {active && (
          <span
            className="hidden items-center gap-1.5 font-mono text-[10px] font-semibold tracking-widest text-sky-400 md:inline-flex"
            title="Investigation streaming live"
          >
            <span className="relative flex size-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-sky-400 opacity-60" />
              <span className="relative inline-flex size-2 rounded-full bg-sky-400" />
            </span>
            LIVE
          </span>
        )}
        {stage ? (
          <StagePill stage={stage} />
        ) : (
          <span className="inline-flex items-center gap-1.5 rounded-full border border-zinc-700 bg-zinc-800/50 px-2.5 py-0.5 text-xs font-medium tracking-wide text-zinc-400">
            <span className="size-1.5 rounded-full bg-zinc-500" />
            STANDBY
          </span>
        )}

        {overlayDismissed && onShowOverlay && (
          <Button
            variant="outline"
            size="sm"
            onClick={onShowOverlay}
            className="border-zinc-700 bg-zinc-900 text-zinc-300 hover:bg-zinc-800 hover:text-zinc-100"
          >
            <PanelBottomOpen data-icon="inline-start" />
            Details
          </Button>
        )}

        {showRepair && (
          <Button
            size="sm"
            onClick={onRepair}
            disabled={repairing}
            className="bg-red-500 text-white hover:bg-red-600"
          >
            {repairing ? (
              <Loader2 data-icon="inline-start" className="animate-spin" />
            ) : (
              <Wrench data-icon="inline-start" />
            )}
            {repairing ? "Repairing…" : "Repair & Verify"}
          </Button>
        )}

        {showInvestigate && (
          <Button
            size="sm"
            onClick={onInvestigate}
            className="bg-sky-500 text-white hover:bg-sky-600"
          >
            <Radar data-icon="inline-start" />
            Investigate Incident
          </Button>
        )}

        <Button
          variant="outline"
          size="sm"
          onClick={onResetDemo}
          disabled={resetting}
          className="border-zinc-700 bg-zinc-900 text-zinc-300 hover:bg-zinc-800 hover:text-zinc-100"
        >
          {resetting ? (
            <Loader2 data-icon="inline-start" className="animate-spin" />
          ) : (
            <RotateCcw data-icon="inline-start" />
          )}
          {resetting ? "Resetting…" : "Reset Demo"}
        </Button>
      </div>
    </header>
  );
}
