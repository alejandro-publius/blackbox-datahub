"use client";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { EvidenceList } from "@/components/EvidenceList";
import { HypothesisList } from "@/components/HypothesisList";
import { TimelineFeed } from "@/components/TimelineFeed";
import type { EvidenceItem, Hypothesis } from "@/lib/types";

export function RightPanel({
  evidence,
  hypotheses,
}: {
  evidence: EvidenceItem[];
  hypotheses: Hypothesis[];
}) {
  return (
    <section className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-lg border border-zinc-800 bg-zinc-900">
      <Tabs defaultValue="timeline" className="flex h-full min-h-0 flex-col gap-0">
        <div className="shrink-0 border-b border-zinc-800 px-2 py-2">
          <TabsList className="w-full bg-zinc-950/60">
            <TabsTrigger value="timeline">Timeline</TabsTrigger>
            <TabsTrigger value="hypotheses">
              Hypotheses
              {hypotheses.length > 0 && (
                <span className="ml-1 rounded bg-zinc-800 px-1 font-mono text-[10px] tabular-nums text-zinc-400">
                  {hypotheses.length}
                </span>
              )}
            </TabsTrigger>
            <TabsTrigger value="evidence">
              Evidence
              {evidence.length > 0 && (
                <span className="ml-1 rounded bg-zinc-800 px-1 font-mono text-[10px] tabular-nums text-zinc-400">
                  {evidence.length}
                </span>
              )}
            </TabsTrigger>
          </TabsList>
        </div>
        <TabsContent
          value="timeline"
          className="min-h-0 flex-1 overflow-y-auto p-3"
        >
          <TimelineFeed items={evidence} />
        </TabsContent>
        <TabsContent
          value="hypotheses"
          className="min-h-0 flex-1 overflow-y-auto p-3"
        >
          <HypothesisList hypotheses={hypotheses} />
        </TabsContent>
        <TabsContent
          value="evidence"
          className="min-h-0 flex-1 overflow-y-auto p-3"
        >
          <EvidenceList items={evidence} />
        </TabsContent>
      </Tabs>
    </section>
  );
}
