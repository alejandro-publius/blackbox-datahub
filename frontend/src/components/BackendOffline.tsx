"use client";

import { RefreshCw, TriangleAlert } from "lucide-react";
import { Button } from "@/components/ui/button";
import { API_BASE_URL } from "@/lib/api";

export function BackendOffline({
  onRetry,
  retrying,
}: {
  onRetry: () => void;
  retrying?: boolean;
}) {
  return (
    <div className="flex flex-1 items-center justify-center p-8">
      <div className="w-full max-w-md rounded-xl border border-amber-400/40 bg-zinc-900 p-8 text-center">
        <TriangleAlert className="mx-auto size-8 text-amber-400" />
        <h2 className="mt-4 text-lg font-semibold text-amber-400">
          Backend offline
        </h2>
        <p className="mt-2 text-sm leading-relaxed text-zinc-400">
          Start the BlackBox API to bring the command center online.
        </p>
        <p className="mt-3 rounded-md border border-zinc-800 bg-zinc-950 px-3 py-2 font-mono text-xs text-zinc-500">
          {API_BASE_URL}
        </p>
        <div className="mt-5 flex items-center justify-center gap-3">
          <Button
            variant="outline"
            size="sm"
            onClick={onRetry}
            disabled={retrying}
            className="border-zinc-700 bg-zinc-900 text-zinc-300 hover:bg-zinc-800"
          >
            <RefreshCw data-icon="inline-start" />
            {retrying ? "Checking…" : "Retry"}
          </Button>
          <a
            href="?preview=1"
            className="text-xs text-zinc-500 underline-offset-4 hover:text-zinc-300 hover:underline"
          >
            or open dev preview
          </a>
        </div>
      </div>
    </div>
  );
}
