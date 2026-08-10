"use client";

import { useMemo } from "react";
import {
  Background,
  BackgroundVariant,
  Handle,
  Position,
  ReactFlow,
  type Edge,
  type Node,
  type NodeProps,
  type NodeTypes,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Database, Gauge, Layers, Table2, Warehouse } from "lucide-react";
import { NODE_STATUS_STYLES } from "@/lib/status";
import type { LineageEdge, LineageNode, NodeStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

/* ------------------------------------------------------------------ */
/* Layout: manual layered layout, 4 layers left → right                */
/* ------------------------------------------------------------------ */

const LAYER_ORDER: LineageNode["layer"][] = [
  "source",
  "staging",
  "marts",
  "metric",
];

const LAYER_LABELS: Record<LineageNode["layer"], string> = {
  source: "SOURCE",
  staging: "STAGING",
  marts: "MARTS",
  metric: "METRIC",
};

const PLATFORM_ICONS: Record<
  string,
  React.ComponentType<{ className?: string }>
> = {
  postgres: Database,
  mysql: Database,
  kafka: Layers,
  dbt: Table2,
  snowflake: Warehouse,
  bigquery: Warehouse,
  metric: Gauge,
};

const X_GAP = 280;
const Y_GAP = 118;

type LineageNodeData = {
  node: LineageNode;
} & Record<string, unknown>;

type LineageFlowNode = Node<LineageNodeData, "lineage">;

function layoutNodes(nodes: LineageNode[]): LineageFlowNode[] {
  const byLayer = new Map<LineageNode["layer"], LineageNode[]>();
  for (const layer of LAYER_ORDER) byLayer.set(layer, []);
  for (const node of nodes) {
    const bucket = byLayer.get(node.layer) ?? byLayer.get("staging")!;
    bucket.push(node);
  }
  const tallest = Math.max(
    1,
    ...LAYER_ORDER.map((l) => byLayer.get(l)!.length),
  );

  const flowNodes: LineageFlowNode[] = [];
  LAYER_ORDER.forEach((layer, layerIdx) => {
    const layerNodes = byLayer.get(layer)!;
    const offsetY = ((tallest - layerNodes.length) * Y_GAP) / 2;
    layerNodes.forEach((node, i) => {
      flowNodes.push({
        id: node.urn,
        type: "lineage",
        position: { x: layerIdx * X_GAP, y: offsetY + i * Y_GAP },
        data: { node },
        draggable: false,
        connectable: false,
      });
    });
  });
  return flowNodes;
}

/* ------------------------------------------------------------------ */
/* Custom node                                                         */
/* ------------------------------------------------------------------ */

function LineageNodeCard({ data }: NodeProps<LineageFlowNode>) {
  const { node } = data;
  const style = NODE_STATUS_STYLES[node.status];
  const Icon = PLATFORM_ICONS[node.platform.toLowerCase()] ?? Database;

  return (
    <div
      className={cn(
        "w-56 rounded-lg border bg-zinc-900 px-3 py-2.5 shadow-sm transition-colors",
        node.status === "healthy" ? "border-zinc-800" : style.border,
        node.status === "root_cause" && style.ring,
      )}
    >
      <Handle
        type="target"
        position={Position.Left}
        className="!size-1.5 !border-0 !bg-zinc-600"
      />
      <div className="flex items-start gap-2.5">
        <div
          className={cn(
            "mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-md border border-zinc-800 bg-zinc-950",
            style.text,
          )}
        >
          <Icon className="size-3.5" />
        </div>
        <div className="min-w-0 flex-1">
          <div
            className="truncate font-mono text-[13px] font-medium text-zinc-100"
            title={node.urn}
          >
            {node.name}
          </div>
          <div className="mt-0.5 flex items-center justify-between gap-2">
            <span className="text-[10px] font-medium uppercase tracking-wider text-zinc-500">
              {LAYER_LABELS[node.layer]} · {node.platform}
            </span>
            <span
              className={cn(
                "inline-flex items-center gap-1 text-[10px] font-medium uppercase tracking-wide",
                style.text,
              )}
            >
              <span className={cn("size-1.5 rounded-full", style.dot)} />
              {style.label}
            </span>
          </div>
        </div>
      </div>
      <Handle
        type="source"
        position={Position.Right}
        className="!size-1.5 !border-0 !bg-zinc-600"
      />
    </div>
  );
}

const nodeTypes: NodeTypes = { lineage: LineageNodeCard };

/* ------------------------------------------------------------------ */
/* Legend                                                              */
/* ------------------------------------------------------------------ */

const LEGEND_STATUSES: NodeStatus[] = [
  "healthy",
  "investigating",
  "suspicious",
  "affected",
  "root_cause",
  "repaired",
];

function Legend() {
  return (
    <div className="pointer-events-none absolute bottom-2 left-2 z-10 flex flex-wrap items-center gap-x-3 gap-y-1 rounded-md border border-zinc-800 bg-zinc-950/80 px-2.5 py-1.5 backdrop-blur">
      {LEGEND_STATUSES.map((status) => {
        const style = NODE_STATUS_STYLES[status];
        return (
          <span
            key={status}
            className="inline-flex items-center gap-1.5 text-[10px] font-medium uppercase tracking-wide text-zinc-400"
          >
            <span className={cn("size-1.5 rounded-full", style.dot)} />
            {style.label}
          </span>
        );
      })}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Panel                                                               */
/* ------------------------------------------------------------------ */

export function LineagePanel({
  nodes,
  edges,
}: {
  nodes: LineageNode[];
  edges: LineageEdge[];
}) {
  const flowNodes = useMemo(() => layoutNodes(nodes), [nodes]);

  const flowEdges = useMemo<Edge[]>(() => {
    const statusByUrn = new Map(nodes.map((n) => [n.urn, n.status]));
    return edges.map((edge) => {
      const investigating =
        statusByUrn.get(edge.source) === "investigating" ||
        statusByUrn.get(edge.target) === "investigating";
      return {
        id: `${edge.source}->${edge.target}`,
        source: edge.source,
        target: edge.target,
        type: "smoothstep",
        animated: investigating,
        style: {
          // literal colors: Tailwind v4 may prune unused --color-* vars
          stroke: investigating ? "#38bdf8" : "#3f3f46", // sky-400 : zinc-700
          strokeWidth: 1.5,
        },
      };
    });
  }, [nodes, edges]);

  return (
    <section className="relative flex min-h-0 flex-1 flex-col overflow-hidden rounded-lg border border-zinc-800 bg-zinc-900">
      <div className="flex shrink-0 items-center justify-between border-b border-zinc-800 px-3 py-2">
        <h2 className="text-[11px] font-semibold uppercase tracking-wider text-zinc-400">
          Lineage
        </h2>
        <span className="font-mono text-[11px] tabular-nums text-zinc-500">
          {nodes.length} assets · {edges.length} edges
        </span>
      </div>
      <div className="relative min-h-0 flex-1">
        <ReactFlow
          nodes={flowNodes}
          edges={flowEdges}
          nodeTypes={nodeTypes}
          fitView
          fitViewOptions={{ padding: 0.15 }}
          zoomOnScroll={false}
          zoomOnDoubleClick={false}
          panOnScroll
          panOnDrag
          nodesDraggable={false}
          nodesConnectable={false}
          elementsSelectable={false}
          minZoom={0.4}
          maxZoom={1.5}
          colorMode="dark"
        >
          <Background
            variant={BackgroundVariant.Dots}
            gap={24}
            size={1}
            color="#27272a" // zinc-800
          />
        </ReactFlow>
        <Legend />
      </div>
    </section>
  );
}
