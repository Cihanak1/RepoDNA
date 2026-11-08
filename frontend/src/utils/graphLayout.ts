import type { Edge, Node } from '@xyflow/react';
import { MarkerType } from '@xyflow/react';
import type { DependencyEdge, FileNode } from '../types/repodna';

export type LayoutMode = 'layered' | 'cluster' | 'radial';
export type GraphDensityMode = 'compact' | 'balanced' | 'spacious';
export type GraphGroupingMode = 'files' | 'directories';

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
  isPackageCluster?: boolean;
  clusterFileCount?: number;
  representativeFileId?: string;
}

export function normalizeSearchText(text: string): string {
  return text
    .replace(/[İIı]/g, 'i')
    .replace(/[Şş]/g, 's')
    .replace(/[Ğğ]/g, 'g')
    .replace(/[Üü]/g, 'u')
    .replace(/[Öö]/g, 'o')
    .replace(/[Çç]/g, 'c')
    .toLowerCase();
}

export function filterFiles(
  files: FileNode[],
  edges: DependencyEdge[],
  options: GraphFilterOptions
): { filteredFiles: FileNode[]; filteredEdges: DependencyEdge[]; neighborIds: Set<string> } {
  const q = normalizeSearchText(options.searchQuery.trim());

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
      const pathMatch = normalizeSearchText(f.id).includes(q);
      const symMatch = f.symbols.some((s) => normalizeSearchText(s.name).includes(q));
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

export function collapseByDirectory(
  files: FileNode[],
  edges: DependencyEdge[],
  selectedFileId: string | null
): {
  clusterFiles: FileNode[];
  clusterEdges: DependencyEdge[];
  clusterRepMap: Map<string, string>;
  activeClusterId: string | null;
} {
  const dirGroups = new Map<string, FileNode[]>();
  const fileToDir = new Map<string, string>();

  for (const f of files) {
    const dir = f.directory || '(root)';
    const clusterId = `dir:${dir}`;
    fileToDir.set(f.id, clusterId);
    const list = dirGroups.get(clusterId) ?? [];
    list.push(f);
    dirGroups.set(clusterId, list);
  }

  const clusterFiles: FileNode[] = [];
  const clusterRepMap = new Map<string, string>();
  let activeClusterId: string | null = null;

  for (const [clusterId, group] of Array.from(dirGroups.entries()).sort((a, b) =>
    a[0].localeCompare(b[0])
  )) {
    const dirName = clusterId.slice(4);
    const totalLoc = group.reduce((s, f) => s + f.lines_code, 0);
    const totalLines = group.reduce((s, f) => s + f.lines_total, 0);
    const totalBytes = group.reduce((s, f) => s + f.size_bytes, 0);
    const hasCycle = group.some((f) => f.in_cycle);
    const isHub = group.some((f) => f.is_hub);
    const rep =
      group.find((f) => f.id === selectedFileId) ??
      [...group].sort((a, b) => b.fan_in + b.fan_out - (a.fan_in + a.fan_out))[0];

    clusterRepMap.set(clusterId, rep.id);
    if (selectedFileId && group.some((f) => f.id === selectedFileId)) {
      activeClusterId = clusterId;
    }

    clusterFiles.push({
      id: clusterId,
      name: `${dirName} (${group.length} files)`,
      directory: 'Directory Package',
      extension: '',
      language: rep.language,
      support_level: group.every(file => file.support_level === 'full_ast') ? 'full_ast' : group.every(file => file.support_level === 'unsupported') ? 'unsupported' : 'partial_static',
      size_bytes: totalBytes,
      lines_total: totalLines,
      lines_code: totalLoc,
      lines_comment: 0,
      lines_blank: 0,
      imports_internal: [],
      imported_by: [],
      imports_external: [],
      unresolved_imports: [],
      symbols: [],
      fan_in: 0,
      fan_out: 0,
      instability: 0,
      in_cycle: hasCycle,
      cycle_ids: hasCycle ? ['CLUSTER-CYCLE'] : [],
      is_orphan: false,
      is_hub: isHub,
      git_commits: group.reduce((s, f) => s + f.git_commits, 0),
      git_last_author: rep.git_last_author,
      git_last_modified: rep.git_last_modified,
      secret_warnings: [],
    });
  }

  const edgeMap = new Map<string, DependencyEdge>();
  const outCounts = new Map<string, Set<string>>();
  const inCounts = new Map<string, Set<string>>();

  for (const e of edges) {
    const srcCluster = fileToDir.get(e.source);
    const dstCluster = fileToDir.get(e.target);
    if (!srcCluster || !dstCluster || srcCluster === dstCluster) continue;

    const key = `${srcCluster}->${dstCluster}`;
    if (!outCounts.has(srcCluster)) outCounts.set(srcCluster, new Set());
    if (!inCounts.has(dstCluster)) inCounts.set(dstCluster, new Set());
    outCounts.get(srcCluster)!.add(dstCluster);
    inCounts.get(dstCluster)!.add(srcCluster);

    const existing = edgeMap.get(key);
    if (!existing) {
      edgeMap.set(key, {
        id: key,
        source: srcCluster,
        target: dstCluster,
        import_names: [...e.import_names.slice(0, 3)],
        line: e.line,
        in_cycle: e.in_cycle,
      });
    } else {
      if (e.in_cycle) existing.in_cycle = true;
    }
  }

  for (const cf of clusterFiles) {
    const fi = inCounts.get(cf.id)?.size ?? 0;
    const fo = outCounts.get(cf.id)?.size ?? 0;
    cf.fan_in = fi;
    cf.fan_out = fo;
    cf.instability = fi + fo > 0 ? Number((fo / (fi + fo)).toFixed(3)) : 0;
  }

  return {
    clusterFiles,
    clusterEdges: Array.from(edgeMap.values()),
    clusterRepMap,
    activeClusterId,
  };
}

export function buildFlowElements(
  files: FileNode[],
  edges: DependencyEdge[],
  layoutMode: LayoutMode,
  selectedFileId: string | null,
  neighborIds: Set<string>,
  highlightCycles: boolean,
  densityMode: GraphDensityMode = 'balanced',
  groupingMode: GraphGroupingMode = 'files'
): { nodes: Node<ModuleNodeData>[]; edges: Edge[]; clusterRepMap: Map<string, string> } {
  let targetFiles = files;
  let targetEdges = edges;
  let effectiveSelectedId = selectedFileId;
  let clusterRepMap = new Map<string, string>();

  if (groupingMode === 'directories') {
    const collapsed = collapseByDirectory(files, edges, selectedFileId);
    targetFiles = collapsed.clusterFiles;
    targetEdges = collapsed.clusterEdges;
    clusterRepMap = collapsed.clusterRepMap;
    effectiveSelectedId = collapsed.activeClusterId;
  }

  // In compact density mode on large graphs (>40 nodes), prioritize cycle and focused edges
  if (densityMode === 'compact' && targetFiles.length > 40) {
    targetEdges = targetEdges.filter(
      (e) =>
        e.in_cycle ||
        e.source === effectiveSelectedId ||
        e.target === effectiveSelectedId
    );
  }

  const positions = computeNodePositions(targetFiles, targetEdges, layoutMode, densityMode);

  const flowNodes: Node<ModuleNodeData>[] = targetFiles.map((file) => {
    const pos = positions.get(file.id) ?? { x: 0, y: 0 };
    const isCluster = groupingMode === 'directories';
    return {
      id: file.id,
      type: 'moduleNode',
      width: 256,
      height: 100,
      selected: file.id === effectiveSelectedId,
      ariaLabel: `${file.name}, ${file.language}, ${file.support_level}${file.in_cycle ? ', cycle participant' : ''}`,
      style: { opacity: effectiveSelectedId && file.id !== effectiveSelectedId && !neighborIds.has(file.id) && !file.in_cycle && groupingMode === 'files' ? 0.92 : 1 },
      position: pos,
      data: {
        file,
        isSelected: file.id === effectiveSelectedId,
        isNeighbor: neighborIds.has(file.id),
        highlightCycles,
        isPackageCluster: isCluster,
        representativeFileId: clusterRepMap.get(file.id),
      },
    };
  });

  const showEdgeLabels = densityMode !== 'compact' && targetEdges.length <= 80;

  const flowEdges: Edge[] = targetEdges.map((edge) => {
    const isCycleEdge = edge.in_cycle && highlightCycles;
    const isFocusedEdge =
      effectiveSelectedId !== null &&
      (edge.source === effectiveSelectedId || edge.target === effectiveSelectedId);

    const strokeColor = isCycleEdge
      ? 'var(--danger)'
      : isFocusedEdge
      ? 'var(--brand-accent)'
      : 'var(--edge-color)';

    return {
      id: edge.id,
      source: edge.source,
      target: edge.target,
      animated: false,
      label:
        showEdgeLabels && isFocusedEdge && edge.import_names.length > 0
          ? edge.import_names.slice(0, 2).join(', ')
          : undefined,
      labelStyle: { fontSize: 10, fill: 'var(--text-secondary)', fontWeight: 500 },
      labelBgStyle: { fill: 'var(--bg-panel)', rx: 4, ry: 4 },
      style: {
        stroke: strokeColor,
        strokeWidth: isCycleEdge ? 2.5 : isFocusedEdge ? 2.2 : 1.4,
        opacity:
          effectiveSelectedId && !isFocusedEdge && !isCycleEdge
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

  return { nodes: flowNodes, edges: flowEdges, clusterRepMap };
}

function computeNodePositions(
  files: FileNode[],
  edges: DependencyEdge[],
  mode: LayoutMode,
  densityMode: GraphDensityMode = 'balanced'
): Map<string, { x: number; y: number }> {
  const positions = new Map<string, { x: number; y: number }>();
  const n = files.length;
  if (n === 0) return positions;

  const spacingScale =
    densityMode === 'compact' ? 0.82 : densityMode === 'spacious' ? 1.24 : 1.0;

  if (mode === 'radial') {
    const radius = Math.round(Math.max(240, n * 38) * spacingScale);
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
    const dirGroups = new Map<string, FileNode[]>();
    for (const f of files) {
      const d = f.directory || '(root)';
      const list = dirGroups.get(d) ?? [];
      list.push(f);
      dirGroups.set(d, list);
    }
    const sortedDirs = Array.from(dirGroups.entries()).sort((a, b) => a[0].localeCompare(b[0]));
    const cols = Math.max(1, Math.ceil(Math.sqrt(sortedDirs.length)));
    const groupW = Math.round(680 * spacingScale);
    const groupH = Math.max(440, Math.ceil(Math.max(...sortedDirs.map(([, items]) => items.length)) / 2) * 145 + 80) * spacingScale;
    const cellW = Math.max(280, Math.round(300 * spacingScale));
    const cellH = Math.round(145 * spacingScale);

    sortedDirs.forEach(([, groupFiles], groupIdx) => {
      const gx = (groupIdx % cols) * groupW;
      const gy = Math.floor(groupIdx / cols) * groupH;
      groupFiles.forEach((f, idx) => {
        const localCol = idx % 2;
        const localRow = Math.floor(idx / 2);
        positions.set(f.id, {
          x: gx + localCol * cellW,
          y: gy + localRow * cellH,
        });
      });
    });
    return positions;
  }

  // Default 'layered'
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

  const layerMap = new Map<string, number>();
  const sortedByStability = [...files].sort((a, b) => {
    if (a.fan_in === 0 && b.fan_in > 0) return -1;
    if (b.fan_in === 0 && a.fan_in > 0) return 1;
    return b.instability - a.instability || a.id.localeCompare(b.id);
  });

  for (const f of sortedByStability) {
    let layer: number;
    if (f.fan_in === 0 && f.fan_out > 0) {
      layer = 0;
    } else if (f.instability >= 0.65) {
      layer = 1;
    } else if (f.instability >= 0.35) {
      layer = 2;
    } else if (f.fan_in > 0 && f.fan_out === 0) {
      layer = 3;
    } else {
      layer = 4;
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

  const maxRowItems = densityMode === 'compact' ? 6 : 5;
  const colSpacing = Math.max(280, Math.round(300 * spacingScale));
  const rowSpacing = Math.max(120, Math.round(125 * spacingScale));
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
      const rowWidth = (itemsInThisRow - 1) * colSpacing;
      const xOffset = -rowWidth / 2 + col * colSpacing;
      positions.set(f.id, {
        x: Math.round(xOffset),
        y: currentY + row * rowSpacing,
      });
    });
    currentY += totalRows * rowSpacing + 24;
  }

  return positions;
}
