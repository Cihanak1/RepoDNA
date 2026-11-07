import type { Edge, Node } from '@xyflow/react';
import { MarkerType } from '@xyflow/react';
import type { DependencyEdge, FileNode } from '../types/repodna';

export type LayoutMode = 'layered' | 'cluster' | 'radial';

export interface GraphFilterOptions {
  searchQuery: string;
  languageFilter: string;
  supportFilter: string;
  cyclesOnly: boolean;
  hubsOnly: boolean;
  orphansOnly: boolean;
  focusSelectedNeighborhood: boolean;
  selectedFileId: string | null;
  highlightCycles: boolean;
}

export interface ModuleNodeData extends Record<string, unknown> {
  file: FileNode;
  isSelected: boolean;
  isNeighbor: boolean;
  highlightCycles: boolean;
}

export function filterFiles(
  files: FileNode[],
  edges: DependencyEdge[],
  options: GraphFilterOptions
): { filteredFiles: FileNode[]; filteredEdges: DependencyEdge[]; neighborIds: Set<string> } {
  const q = options.searchQuery.trim().toLowerCase();

  let baseFiles = files.filter((f) => {
    if (options.languageFilter !== 'ALL' && f.language !== options.languageFilter) {
      return false;
    }
    if (options.supportFilter !== 'ALL' && f.support_level !== options.supportFilter) {
      return false;
    }
    if (options.cyclesOnly && !f.in_cycle) {
      return false;
    }
    if (options.hubsOnly && !f.is_hub) {
      return false;
    }
    if (options.orphansOnly && !f.is_orphan) {
      return false;
    }
    if (q) {
      const pathMatch = f.id.toLowerCase().includes(q);
      const symMatch = f.symbols.some((s) => s.name.toLowerCase().includes(q));
      if (!pathMatch && !symMatch) {
        return false;
      }
    }
    return true;
  });

  const neighborIds = new Set<string>();
  if (options.selectedFileId) {
    for (const e of edges) {
      if (e.source === options.selectedFileId) {
        neighborIds.add(e.target);
      } else if (e.target === options.selectedFileId) {
        neighborIds.add(e.source);
      }
    }
  }

  if (options.focusSelectedNeighborhood && options.selectedFileId) {
    const focusSet = new Set<string>([options.selectedFileId, ...neighborIds]);
    baseFiles = baseFiles.filter((f) => focusSet.has(f.id));
  }

  const visibleIds = new Set(baseFiles.map((f) => f.id));
  const filteredEdges = edges.filter((e) => visibleIds.has(e.source) && visibleIds.has(e.target));

  return { filteredFiles: baseFiles, filteredEdges, neighborIds };
}

export function buildFlowElements(
  files: FileNode[],
  edges: DependencyEdge[],
  layoutMode: LayoutMode,
  selectedFileId: string | null,
  neighborIds: Set<string>,
  highlightCycles: boolean
): { nodes: Node<ModuleNodeData>[]; edges: Edge[] } {
  const positions = computeNodePositions(files, edges, layoutMode);

  const flowNodes: Node<ModuleNodeData>[] = files.map((file) => {
    const pos = positions.get(file.id) ?? { x: 0, y: 0 };
    return {
      id: file.id,
      type: 'moduleNode',
      position: pos,
      data: {
        file,
        isSelected: file.id === selectedFileId,
        isNeighbor: neighborIds.has(file.id),
        highlightCycles,
      },
    };
  });

  const flowEdges: Edge[] = edges.map((edge) => {
    const isCycleEdge = edge.in_cycle && highlightCycles;
    const isFocusedEdge =
      selectedFileId !== null &&
      (edge.source === selectedFileId || edge.target === selectedFileId);

    const strokeColor = isCycleEdge
      ? '#ef4444'
      : isFocusedEdge
      ? '#38bdf8'
      : '#64748b';

    return {
      id: edge.id,
      source: edge.source,
      target: edge.target,
      animated: isCycleEdge || isFocusedEdge,
      label: edge.import_names.length > 0 ? edge.import_names.slice(0, 2).join(', ') : undefined,
      labelStyle: { fontSize: 10, fill: '#94a3b8', fontWeight: 500 },
      labelBgStyle: { fill: 'rgba(15, 23, 42, 0.82)', rx: 4, ry: 4 },
      style: {
        stroke: strokeColor,
        strokeWidth: isCycleEdge ? 2.5 : isFocusedEdge ? 2.2 : 1.4,
        opacity:
          selectedFileId && !isFocusedEdge && !isCycleEdge
            ? 0.35
            : 0.92,
      },
      markerEnd: {
        type: MarkerType.ArrowClosed,
        color: strokeColor,
        width: 16,
        height: 16,
      },
    };
  });

  return { nodes: flowNodes, edges: flowEdges };
}

function computeNodePositions(
  files: FileNode[],
  edges: DependencyEdge[],
  mode: LayoutMode
): Map<string, { x: number; y: number }> {
  const positions = new Map<string, { x: number; y: number }>();
  const n = files.length;
  if (n === 0) return positions;

  if (mode === 'radial') {
    const radius = Math.max(240, n * 38);
    files.forEach((f, idx) => {
      const angle = (2 * Math.PI * idx) / n - Math.PI / 2;
      positions.set(f.id, {
        x: Math.round(radius * Math.cos(angle)),
        y: Math.round(radius * Math.sin(angle)),
      });
    });
    return positions;
  }

  if (mode === 'cluster') {
    // Group by directory
    const dirGroups = new Map<string, FileNode[]>();
    for (const f of files) {
      const d = f.directory || '(root)';
      const list = dirGroups.get(d) ?? [];
      list.push(f);
      dirGroups.set(d, list);
    }
    const sortedDirs = Array.from(dirGroups.entries()).sort((a, b) => a[0].localeCompare(b[0]));
    const cols = Math.max(1, Math.ceil(Math.sqrt(sortedDirs.length)));

    sortedDirs.forEach(([, groupFiles], groupIdx) => {
      const gx = (groupIdx % cols) * 680;
      const gy = Math.floor(groupIdx / cols) * 440;
      groupFiles.forEach((f, idx) => {
        const localCol = idx % 2;
        const localRow = Math.floor(idx / 2);
        positions.set(f.id, {
          x: gx + localCol * 300,
          y: gy + localRow * 145,
        });
      });
    });
    return positions;
  }

  // Default 'layered': rank nodes from high instability (orchestrators/entrypoints on top)
  // down to low instability (core schemas/models at bottom)
  const inDegree = new Map<string, number>();
  const adj = new Map<string, string[]>();
  for (const f of files) {
    inDegree.set(f.id, 0);
    adj.set(f.id, []);
  }
  for (const e of edges) {
    if (adj.has(e.source) && inDegree.has(e.target)) {
      adj.get(e.source)!.push(e.target);
      inDegree.set(e.target, (inDegree.get(e.target) ?? 0) + 1);
    }
  }

  // Assign layers (0..5) using topological depth + instability tie-breaking
  const layerMap = new Map<string, number>();
  const sortedByStability = [...files].sort((a, b) => {
    if (a.fan_in === 0 && b.fan_in > 0) return -1;
    if (b.fan_in === 0 && a.fan_in > 0) return 1;
    return b.instability - a.instability || a.id.localeCompare(b.id);
  });

  for (const f of sortedByStability) {
    let layer = 0;
    if (f.fan_in === 0 && f.fan_out > 0) {
      layer = 0;
    } else if (f.instability >= 0.65) {
      layer = 1;
    } else if (f.instability >= 0.35) {
      layer = 2;
    } else if (f.fan_in > 0 && f.fan_out === 0) {
      layer = 3;
    } else {
      layer = 4; // isolated / config / docs
    }
    layerMap.set(f.id, layer);
  }

  const layers = new Map<number, FileNode[]>();
  for (const f of files) {
    const l = layerMap.get(f.id) ?? 2;
    const arr = layers.get(l) ?? [];
    arr.push(f);
    layers.set(l, arr);
  }

  const maxRowItems = 5;
  let currentY = 0;
  for (const layerKey of [0, 1, 2, 3, 4]) {
    const items = layers.get(layerKey);
    if (!items || items.length === 0) continue;
    items.sort((a, b) => a.id.localeCompare(b.id));

    const totalRows = Math.ceil(items.length / maxRowItems);
    items.forEach((f, idx) => {
      const row = Math.floor(idx / maxRowItems);
      const col = idx % maxRowItems;
      const itemsInThisRow = Math.min(maxRowItems, items.length - row * maxRowItems);
      const rowWidth = (itemsInThisRow - 1) * 300;
      const xOffset = -rowWidth / 2 + col * 300;
      positions.set(f.id, {
        x: Math.round(xOffset),
        y: currentY + row * 155,
      });
    });
    currentY += totalRows * 165 + 45;
  }

  return positions;
}
