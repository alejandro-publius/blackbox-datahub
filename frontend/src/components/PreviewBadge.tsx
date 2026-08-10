"use client";

import { FlaskConical } from "lucide-react";

/**
 * Watermark badge for dev preview mode (?preview=1).
 * MUST be rendered whenever placeholder fixtures are on screen.
 */
export function PreviewBadge({ variant }: { variant?: string }) {
  return (
    <div className="pointer-events-none fixed right-4 bottom-4 z-50 flex items-center gap-2 rounded-md border-2 border-dashed border-amber-400/70 bg-zinc-950/90 px-3 py-2 shadow-lg backdrop-blur">
      <FlaskConical className="size-4 text-amber-400" />
      <span className="text-xs font-bold tracking-[0.14em] text-amber-400">
        PREVIEW DATA
      </span>
      {variant && (
        <span className="font-mono text-[10px] text-zinc-500">({variant})</span>
      )}
      <span className="text-[10px] text-zinc-500">— not live</span>
    </div>
  );
}
