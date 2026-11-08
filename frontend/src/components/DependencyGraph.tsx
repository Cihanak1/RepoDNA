import React, { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Background,
  Controls,
  Handle,
  MiniMap,
  Panel,
  Position,
  ReactFlow,
  ReactFlowProvider,
  useReactFlow,
  useStore,
  type Node,
  type NodeProps,
} from '@xyflow/react';
import {
  Eye,
  FolderTree,
  Grid,
  Layers,
  Maximize2,
  Orbit,
  RefreshCcw,
  SlidersHorizontal,
} from 'lucide-react';
import type { DependencyEdge, FileNode } from '../types/repodna';
import type { WorkstationMode } from '../utils/preferences';
import {
  buildFlowElements,
  type GraphDensityMode,
  type GraphGroupingMode,
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
  densityMode: GraphDensityMode;
  onDensityModeChange: (mode: GraphDensityMode) => void;
  groupingMode: GraphGroupingMode;
  onGroupingModeChange: (mode: GraphGroupingMode) => void;
  focusNeighborhood: boolean;
  onToggleFocusNeighborhood: () => void;
  highlightCycles: boolean;
  onToggleHighlightCycles: () => void;
  workstationMode?: WorkstationMode;
}

const ModuleGraphNode = React.memo(({ data }: NodeProps<Node<ModuleNodeData>>) => {
  const { file, isSelected, highlightCycles, isPackageCluster } = data;
  return (
    <div
      data-testid={`graph-node-${file.id}`}
      className="module-node"
      data-selected={isSelected}
      data-cycle={file.in_cycle && highlightCycles}
      data-package={isPackageCluster}
      title={file.id}
    >
      <Handle type="target" position={Position.Top} />
      <small>{isPackageCluster ? 'Package / ' : ''}{file.directory || 'Repository root'}</small>
      <strong>{file.name}</strong>
      <div className="node-meta">
        <span>{isPackageCluster ? 'Directory' : file.language}</span>
        <span className={file.in_cycle ? 'cycle-label' : ''}>
          {file.in_cycle
            ? 'Cycle'
            : file.support_level === 'full_ast'
            ? `${file.fan_in} in / ${file.fan_out} out`
            : file.support_level === 'partial_static'
            ? 'Partial static'
            : 'Unsupported'}
        </span>
      </div>
      <Handle type="source" position={Position.Bottom} />
    </div>
  );
});

ModuleGraphNode.displayName = 'ModuleGraphNode';

const nodeTypes = {
  moduleNode: ModuleGraphNode,
};

const FitViewController: React.FC<{ triggerKey: string }> = ({ triggerKey }) => {
  const { fitView } = useReactFlow();
  const width = useStore((state) => state.width);
  const height = useStore((state) => state.height);
  useEffect(() => {
    const id = window.setTimeout(() => {
      void fitView({
        padding: 0.18,
        duration: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : 200,
      });
    }, 40);
    return () => window.clearTimeout(id);
  }, [triggerKey, fitView, width, height]);
  return null;
};

function SelectionZoom({ selectedId }: { selectedId: string | null }) {
  const { fitView } = useReactFlow();
  const { t } = useTranslation();
  return (
    <Panel position="top-right">
      <button
        disabled={!selectedId}
        type="button"
        className="bg-panel border border-line rounded px-3 py-1 text-xs text-accent cursor-pointer hover:bg-raised transition disabled:opacity-40 disabled:cursor-not-allowed"
        onClick={() => {
          if (selectedId) {
            void fitView({
              nodes: [{ id: selectedId }],
              padding: 0.6,
              minZoom: 0.9,
              maxZoom: 1.2,
              duration: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : 200,
            });
          }
        }}
      >
        {t('graph.zoomSelection')}
      </button>
    </Panel>
  );
}

export const DependencyGraph: React.FC<DependencyGraphProps> = ({
  files,
  edges,
  selectedFileId,
  neighborIds,
  onSelectFile,
  layoutMode,
  onLayoutModeChange,
  densityMode,
  onDensityModeChange,
  groupingMode,
  onGroupingModeChange,
  focusNeighborhood,
  onToggleFocusNeighborhood,
  highlightCycles,
  onToggleHighlightCycles,
  workstationMode = 'simple',
}) => {
  const { t, i18n } = useTranslation();
  const [fitTriggerCount, setFitTriggerCount] = useState(0);
  const positionScope = `${groupingMode}-${layoutMode}-${densityMode}`;
  const [manualPositions, setManualPositions] = useState<{
    scope: string;
    positions: Record<string, { x: number; y: number }>;
  }>({ scope: positionScope, positions: {} });

  const { nodes, edges: flowEdges, clusterRepMap } = useMemo(() => {
    return buildFlowElements(
      files,
      edges,
      layoutMode,
      selectedFileId,
      neighborIds,
      highlightCycles,
      densityMode,
      groupingMode
    );
  }, [files, edges, layoutMode, selectedFileId, neighborIds, highlightCycles, densityMode, groupingMode]);

  const displayNodes = useMemo(() => {
    if (manualPositions.scope !== positionScope) return nodes;
    return nodes.map((node) => {
      const manual = manualPositions.positions[node.id];
      return manual ? { ...node, position: manual } : node;
    });
  }, [nodes, manualPositions, positionScope]);

  const handleResetLayoutAndFit = () => {
    setManualPositions({ scope: positionScope, positions: {} });
    setFitTriggerCount((c) => c + 1);
  };

  return (
    <div className="graph-workspace" data-mode={workstationMode}>
      {/* Top Controls Toolbar */}
      <div className="graph-toolbar" role="toolbar" aria-label="Graph controls">
        <div className="flex flex-wrap items-center gap-1.5 pointer-events-auto">
          {/* Layout Mode Selector */}
          <div
            role="group"
            aria-label="Graph layout algorithm"
            className="flex items-center gap-1 bg-panel border border-line p-1 rounded-md"
          >
            <button
              type="button"
              data-testid="layout-layered-btn"
              onClick={() => onLayoutModeChange('layered')}
              aria-pressed={layoutMode === 'layered'}
              title="Hierarchical layered layout"
              className={`px-2 py-1 rounded text-xs font-medium flex items-center gap-1 cursor-pointer ${
                layoutMode === 'layered'
                  ? 'bg-accent-solid text-white'
                  : 'text-muted hover:bg-raised'
              }`}
            >
              <Layers className="w-3.5 h-3.5" aria-hidden="true" />
              <span>{t('graph.layered')}</span>
            </button>
            <button
              type="button"
              data-testid="layout-cluster-btn"
              onClick={() => onLayoutModeChange('cluster')}
              aria-pressed={layoutMode === 'cluster'}
              title="Directory package cluster grid"
              className={`px-2 py-1 rounded text-xs font-medium flex items-center gap-1 cursor-pointer ${
                layoutMode === 'cluster'
                  ? 'bg-accent-solid text-white'
                  : 'text-muted hover:bg-raised'
              }`}
            >
              <Grid className="w-3.5 h-3.5" aria-hidden="true" />
              <span>{t('graph.cluster')}</span>
            </button>
            <button
              type="button"
              data-testid="layout-radial-btn"
              onClick={() => onLayoutModeChange('radial')}
              aria-pressed={layoutMode === 'radial'}
              title="Concentric radial hierarchy"
              className={`px-2 py-1 rounded text-xs font-medium flex items-center gap-1 cursor-pointer ${
                layoutMode === 'radial'
                  ? 'bg-accent-solid text-white'
                  : 'text-muted hover:bg-raised'
              }`}
            >
              <Orbit className="w-3.5 h-3.5" aria-hidden="true" />
              <span>{t('graph.radial')}</span>
            </button>
          </div>

          {/* Grouping Mode (Modules vs Packages) */}
          <div
            role="group"
            aria-label="Node grouping mode"
            className="flex items-center gap-1 bg-panel border border-line p-1 rounded-md"
          >
            <button
              type="button"
              data-testid="grouping-files-btn"
              onClick={() => onGroupingModeChange('files')}
              aria-pressed={groupingMode === 'files'}
              className={`px-2 py-1 rounded text-xs font-medium flex items-center gap-1 cursor-pointer ${
                groupingMode === 'files'
                  ? 'bg-accent-solid text-white'
                  : 'text-muted hover:bg-raised'
              }`}
            >
              {t('graph.modules')} ({files.length})
            </button>
            <button
              type="button"
              data-testid="grouping-directories-btn"
              onClick={() => onGroupingModeChange('directories')}
              aria-pressed={groupingMode === 'directories'}
              className={`px-2 py-1 rounded text-xs font-medium flex items-center gap-1 cursor-pointer ${
                groupingMode === 'directories'
                  ? 'bg-accent-solid text-white'
                  : 'text-muted hover:bg-raised'
              }`}
            >
              <FolderTree className="w-3.5 h-3.5" aria-hidden="true" />
              {t('graph.collapsePackages')}
            </button>
          </div>

          {/* Graph Density Selector */}
          <div className="flex items-center gap-1 bg-panel border border-line px-2 py-1 rounded-md text-xs">
            <SlidersHorizontal className="w-3.5 h-3.5 text-muted" aria-hidden="true" />
            <label htmlFor="graph-density-select" className="visually-hidden">
              Graph Density
            </label>
            <select
              id="graph-density-select"
              data-testid="graph-density-select"
              value={densityMode}
              onChange={(e) => onDensityModeChange(e.target.value as GraphDensityMode)}
              className="bg-transparent text-xs font-medium text-ink cursor-pointer"
            >
              <option value="compact" className="bg-panel text-ink">
                Density: {t('graph.densityCompact')}
              </option>
              <option value="balanced" className="bg-panel text-ink">
                Density: {t('graph.densityBalanced')}
              </option>
              <option value="spacious" className="bg-panel text-ink">
                Density: {t('graph.densitySpacious')}
              </option>
            </select>
          </div>
        </div>

        <div className="flex items-center gap-1 bg-panel border border-line p-1 rounded-md pointer-events-auto">
          <button
            type="button"
            data-testid="reset-layout-fit-btn"
            onClick={handleResetLayoutAndFit}
            title={t('graph.fitReset')}
            className="px-2.5 py-1 rounded text-xs font-medium flex items-center gap-1 text-muted hover:bg-raised cursor-pointer"
          >
            <Maximize2 className="w-3.5 h-3.5" aria-hidden="true" />
            {t('graph.fitReset')}
          </button>

          <button
            type="button"
            onClick={onToggleFocusNeighborhood}
            disabled={!selectedFileId}
            aria-pressed={focusNeighborhood}
            className={`px-2.5 py-1 rounded text-xs font-medium flex items-center gap-1 cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed ${
              focusNeighborhood
                ? 'bg-accent-solid text-white'
                : 'text-muted hover:bg-raised'
            }`}
          >
            <Eye className="w-3.5 h-3.5" aria-hidden="true" />
            {t('graph.focus1Hop')}
          </button>

          <button
            type="button"
            onClick={onToggleHighlightCycles}
            aria-pressed={highlightCycles}
            className={`px-2.5 py-1 rounded text-xs font-medium flex items-center gap-1 cursor-pointer ${
              highlightCycles
                ? 'bg-danger/10 text-danger border border-danger/40'
                : 'text-muted hover:bg-raised'
            }`}
          >
            <RefreshCcw className="w-3.5 h-3.5" aria-hidden="true" />
            {t('graph.highlightCycles')}
          </button>
        </div>
      </div>

      {/* Graph Canvas */}
      <div className="graph-canvas" data-testid="dependency-graph-canvas">
        <ReactFlowProvider>
          <ReactFlow
            nodes={displayNodes}
            edges={flowEdges}
            nodesConnectable={false}
            deleteKeyCode={null}
            onNodesChange={(changes) => {
              const selection = changes.find((change) => change.type === 'select' && change.selected);
              if (selection?.type === 'select') onSelectFile(clusterRepMap.get(selection.id) ?? selection.id);
              const moved = changes.filter((change) => change.type === 'position' && change.position);
              if (moved.length) {
                setManualPositions((previous) => {
                  const positions = previous.scope === positionScope ? { ...previous.positions } : {};
                  for (const change of moved) {
                    if (change.type === 'position' && change.position) positions[change.id] = change.position;
                  }
                  return { scope: positionScope, positions };
                });
              }
            }}
            nodeTypes={nodeTypes}
            onNodeDoubleClick={(_event, node) => {
              if (groupingMode === 'directories') {
                onGroupingModeChange('files');
                onSelectFile(clusterRepMap.get(node.id) ?? node.id);
              }
            }}
            onNodeClick={(_event, node) => {
              const repId = clusterRepMap.get(node.id);
              onSelectFile(repId ?? node.id);
            }}
            fitView
            fitViewOptions={{ padding: 0.2 }}
            minZoom={0.12}
            maxZoom={2.2}
            onlyRenderVisibleElements={nodes.length > 60}
            proOptions={{ hideAttribution: true }}
          >
            <FitViewController
              triggerKey={`${layoutMode}-${densityMode}-${groupingMode}-${focusNeighborhood}-${nodes.length}-${fitTriggerCount}`}
            />
            <SelectionZoom selectedId={nodes.find((node) => node.data.isSelected)?.id ?? null} />
            <Background color="var(--border-subtle)" gap={22} size={1} />
            <Controls showInteractive={false} />
            <MiniMap
              pannable
              zoomable
              nodeColor={(n) => {
                const d = n.data as ModuleNodeData | undefined;
                if (d?.file?.in_cycle) return 'var(--danger)';
                if (d?.isSelected) return 'var(--brand-accent)';
                return 'var(--bg-elevated)';
              }}
              nodeStrokeColor="var(--border-subtle)"
              nodeStrokeWidth={2}
              maskColor="rgba(0, 0, 0, 0.45)"
            />
          </ReactFlow>
        </ReactFlowProvider>

        {files.length === 0 && (
          <div className="graph-empty" role="status">
            <strong>No modules in this view</strong>
            <p>{t('explorer.noResults')}</p>
          </div>
        )}
      </div>

      {/* Footer Info Strip */}
      <footer className="graph-legend flex items-center justify-between px-3 py-1.5 border-t border-line bg-panel text-[11px] text-muted shrink-0">
        <div className="flex items-center gap-4">
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-accent" aria-hidden="true" />
            {t('graph.legendSelected')}
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-danger" aria-hidden="true" />
            {t('graph.legendCycle')}
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-muted" aria-hidden="true" />
            {t('graph.legendDirection')}
          </span>
        </div>
        <div>
          {i18n.language.startsWith('tr') ? (
            <>
              Gösterilen <strong data-testid="graph-visible-nodes-count">{nodes.length}</strong>{' '}
              {groupingMode === 'directories' ? 'paket kümesi' : 'modül'} ve{' '}
              <strong data-testid="graph-visible-edges-count">{flowEdges.length}</strong> yönlü bağlantı
            </>
          ) : (
            <>
              Showing <strong data-testid="graph-visible-nodes-count">{nodes.length}</strong>{' '}
              {groupingMode === 'directories' ? 'package clusters' : 'modules'} and{' '}
              <strong data-testid="graph-visible-edges-count">{flowEdges.length}</strong> directed
              dependency edges
            </>
          )}
        </div>
      </footer>
    </div>
  );
};
