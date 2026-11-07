import React, { useMemo } from 'react';
import {
  Background,
  Controls,
  Handle,
  MiniMap,
  Position,
  ReactFlow,
  type Node,
  type NodeProps,
} from '@xyflow/react';
import { Eye, Grid, Layers, Orbit, RefreshCcw } from 'lucide-react';
import type { DependencyEdge, FileNode } from '../types/repodna';
import {
  buildFlowElements,
  type LayoutMode,
  type ModuleNodeData,
} from '../utils/graphLayout';

interface DependencyGraphProps {
  files: FileNode[];
  edges: DependencyEdge[];
  selectedFileId: string | null;
  neighborIds: Set<string>;
  onSelectFile: (fileId: string) => void;
  layoutMode: LayoutMode;
  onLayoutModeChange: (mode: LayoutMode) => void;
  focusNeighborhood: boolean;
  onToggleFocusNeighborhood: () => void;
  highlightCycles: boolean;
  onToggleHighlightCycles: () => void;
}

const LANGUAGE_BADGE_COLORS: Record<string, string> = {
  Python: 'bg-sky-500/20 text-sky-300 border-sky-500/40',
  TypeScript: 'bg-indigo-500/20 text-indigo-300 border-indigo-500/40',
  'TypeScript (TSX)': 'bg-violet-500/20 text-violet-300 border-violet-500/40',
  JavaScript: 'bg-amber-500/20 text-amber-300 border-amber-500/40',
  Go: 'bg-cyan-500/20 text-cyan-300 border-cyan-500/40',
  Rust: 'bg-orange-500/20 text-orange-300 border-orange-500/40',
};

const ModuleGraphNode: React.FC<NodeProps<Node<ModuleNodeData>>> = ({ data }) => {
  const { file, isSelected, isNeighbor, highlightCycles } = data;
  const inCycleHighlight = file.in_cycle && highlightCycles;

  const borderClass = isSelected
    ? 'border-sky-400 ring-2 ring-sky-400/50 bg-slate-900'
    : inCycleHighlight
    ? 'border-red-500 ring-1 ring-red-500/40 bg-red-950/30'
    : isNeighbor
    ? 'border-sky-500/60 bg-slate-900/95'
    : 'border-slate-700/80 bg-slate-900/90';

  const langColor =
    LANGUAGE_BADGE_COLORS[file.language] ??
    'bg-slate-800 text-slate-300 border-slate-700';

  return (
    <div
      data-testid={`graph-node-${file.id}`}
      className={`w-64 rounded-xl border p-2.5 shadow-lg transition select-none ${borderClass}`}
    >
      <Handle
        type="target"
        position={Position.Top}
        className="!w-2.5 !h-2.5 !bg-sky-400 !border-slate-950"
      />

      <div className="flex items-center justify-between gap-1.5 mb-1">
        <span className="text-[10px] font-mono text-slate-400 truncate max-w-[145px]">
          {file.directory || '(root)'}
        </span>
        <span className={`text-[9px] font-semibold px-1.5 py-0.5 rounded border ${langColor}`}>
          {file.language}
        </span>
      </div>

      <div className="font-mono text-xs font-bold text-slate-100 truncate" title={file.id}>
        {file.name}
      </div>

      <div className="mt-2 pt-1.5 border-t border-slate-800/90 flex items-center justify-between text-[10px] font-mono text-slate-300">
        <span>{file.lines_code} LOC</span>
        <span title="Incoming / Outgoing internal dependencies">
          In:{file.fan_in} &bull; Out:{file.fan_out}
        </span>
        <span
          title="Robert C. Martin Instability Index I = Ce / (Ca + Ce)"
          className={
            file.in_cycle
              ? 'text-red-400 font-bold'
              : file.instability > 0.7
              ? 'text-amber-300'
              : 'text-emerald-300'
          }
        >
          I={file.instability.toFixed(2)}
        </span>
      </div>

      <Handle
        type="source"
        position={Position.Bottom}
        className="!w-2.5 !h-2.5 !bg-indigo-400 !border-slate-950"
      />
    </div>
  );
};

const nodeTypes = {
  moduleNode: ModuleGraphNode,
};

export const DependencyGraph: React.FC<DependencyGraphProps> = ({
  files,
  edges,
  selectedFileId,
  neighborIds,
  onSelectFile,
  layoutMode,
  onLayoutModeChange,
  focusNeighborhood,
  onToggleFocusNeighborhood,
  highlightCycles,
  onToggleHighlightCycles,
}) => {
  const { nodes, edges: flowEdges } = useMemo(
    () =>
      buildFlowElements(
        files,
        edges,
        layoutMode,
        selectedFileId,
        neighborIds,
        highlightCycles
      ),
    [files, edges, layoutMode, selectedFileId, neighborIds, highlightCycles]
  );

  return (
    <div className="flex-1 flex flex-col relative min-h-[420px] bg-slate-950">
      {/* Floating Graph Toolbar */}
      <div className="absolute top-3 left-3 right-3 z-10 flex flex-wrap items-center justify-between gap-2 pointer-events-none">
        <div
          role="group"
          aria-label="Graph layout mode"
          className="flex items-center gap-1 bg-slate-900/90 backdrop-blur-md border border-slate-800 p-1 rounded-xl shadow-lg pointer-events-auto"
        >
          <button
            type="button"
            onClick={() => onLayoutModeChange('layered')}
            aria-pressed={layoutMode === 'layered'}
            className={`px-2.5 py-1 rounded-lg text-xs font-medium flex items-center gap-1 cursor-pointer ${
              layoutMode === 'layered'
                ? 'bg-sky-600 text-white'
                : 'text-slate-300 hover:bg-slate-800'
            }`}
          >
            <Layers className="w-3.5 h-3.5" aria-hidden="true" />
            Layered
          </button>
          <button
            type="button"
            onClick={() => onLayoutModeChange('cluster')}
            aria-pressed={layoutMode === 'cluster'}
            className={`px-2.5 py-1 rounded-lg text-xs font-medium flex items-center gap-1 cursor-pointer ${
              layoutMode === 'cluster'
                ? 'bg-sky-600 text-white'
                : 'text-slate-300 hover:bg-slate-800'
            }`}
          >
            <Grid className="w-3.5 h-3.5" aria-hidden="true" />
            Directory Clusters
          </button>
          <button
            type="button"
            onClick={() => onLayoutModeChange('radial')}
            aria-pressed={layoutMode === 'radial'}
            className={`px-2.5 py-1 rounded-lg text-xs font-medium flex items-center gap-1 cursor-pointer ${
              layoutMode === 'radial'
                ? 'bg-sky-600 text-white'
                : 'text-slate-300 hover:bg-slate-800'
            }`}
          >
            <Orbit className="w-3.5 h-3.5" aria-hidden="true" />
            Radial Ring
          </button>
        </div>

        <div className="flex items-center gap-1.5 bg-slate-900/90 backdrop-blur-md border border-slate-800 p-1 rounded-xl shadow-lg pointer-events-auto">
          <button
            type="button"
            onClick={onToggleFocusNeighborhood}
            disabled={!selectedFileId}
            aria-pressed={focusNeighborhood}
            className={`px-2.5 py-1 rounded-lg text-xs font-medium flex items-center gap-1 cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed ${
              focusNeighborhood
                ? 'bg-sky-600 text-white'
                : 'text-slate-300 hover:bg-slate-800'
            }`}
          >
            <Eye className="w-3.5 h-3.5" aria-hidden="true" />
            Focus 1-Hop Neighborhood
          </button>

          <button
            type="button"
            onClick={onToggleHighlightCycles}
            aria-pressed={highlightCycles}
            className={`px-2.5 py-1 rounded-lg text-xs font-medium flex items-center gap-1 cursor-pointer ${
              highlightCycles
                ? 'bg-red-500/25 text-red-300 border border-red-500/40'
                : 'text-slate-300 hover:bg-slate-800'
            }`}
          >
            <RefreshCcw className="w-3.5 h-3.5" aria-hidden="true" />
            Highlight Cycles
          </button>
        </div>
      </div>

      {/* Graph Canvas */}
      <div className="flex-1 w-full h-full" data-testid="dependency-graph-canvas">
        <ReactFlow
          nodes={nodes}
          edges={flowEdges}
          nodeTypes={nodeTypes}
          onNodeClick={(_event, node) => onSelectFile(node.id)}
          fitView
          fitViewOptions={{ padding: 0.2 }}
          minZoom={0.15}
          maxZoom={2.0}
          proOptions={{ hideAttribution: true }}
        >
          <Background color="#1e293b" gap={22} size={1} />
          <Controls
            showInteractive={false}
            className="!bg-slate-900 !border-slate-700 !rounded-lg !shadow-lg [&_button]:!bg-slate-900 [&_button]:!border-slate-800 [&_button]:!fill-slate-200 hover:[&_button]:!bg-slate-800"
          />
          <MiniMap
            pannable
            zoomable
            nodeColor={(n) => {
              const d = n.data as ModuleNodeData | undefined;
              if (d?.file?.in_cycle) return '#ef4444';
              if (d?.isSelected) return '#38bdf8';
              return '#475569';
            }}
            maskColor="rgba(2, 6, 23, 0.72)"
            className="!bg-slate-900/90 !border !border-slate-800 !rounded-lg"
          />
        </ReactFlow>
      </div>

      {/* Bottom Legend Bar */}
      <div className="border-t border-slate-800/80 bg-slate-900/80 px-3 py-1.5 flex flex-wrap items-center justify-between gap-2 text-[11px] text-slate-400">
        <div className="flex items-center gap-4">
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-sky-400 inline-block" />
            Selected / Focused Edge
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-red-500 inline-block" />
            Circular Dependency Cycle
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 inline-block" />
            Stable Core (Low I)
          </span>
        </div>
        <div>
          Showing <strong>{nodes.length}</strong> modules and <strong>{flowEdges.length}</strong> directed dependency edges
        </div>
      </div>
    </div>
  );
};
