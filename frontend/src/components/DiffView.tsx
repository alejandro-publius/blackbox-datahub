"use client";

import { cn } from "@/lib/utils";

/**
 * Minimal unified-diff renderer. No diff library — just line-class mapping.
 */
export function DiffView({
  diff,
  file,
  className,
}: {
  diff: string;
  file?: string;
  className?: string;
}) {
  const lines = diff.replace(/\n$/, "").split("\n");

  return (
    <div
      className={cn(
        "overflow-hidden rounded-lg border border-zinc-800 bg-zinc-950",
        className,
      )}
    >
      {file && (
        <div className="border-b border-zinc-800 px-3 py-1.5 font-mono text-[11px] text-zinc-400">
          {file}
        </div>
      )}
      <pre className="overflow-x-auto py-2 font-mono text-xs leading-relaxed">
        {lines.map((line, i) => {
          let lineClass = "text-zinc-400";
          if (line.startsWith("+++") || line.startsWith("---")) {
            lineClass = "text-zinc-500";
          } else if (line.startsWith("@@")) {
            lineClass = "bg-sky-400/10 text-sky-400";
          } else if (line.startsWith("+")) {
            lineClass = "bg-emerald-400/10 text-emerald-300";
          } else if (line.startsWith("-")) {
            lineClass = "bg-red-400/10 text-red-300";
          }
          return (
            <div key={i} className={cn("px-3 whitespace-pre", lineClass)}>
              {line.length > 0 ? line : " "}
            </div>
          );
        })}
      </pre>
    </div>
  );
}
