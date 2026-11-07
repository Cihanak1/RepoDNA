import React from 'react';
import {
  AlertTriangle,
  ArrowDownLeft,
  ArrowUpRight,
  Box,
  Code2,
  FileCode2,
  GitCommitHorizontal,
  Package,
  RefreshCcw,
  ShieldAlert,
} from 'lucide-react';
import type { CycleGroup, FileNode, RuleFinding } from '../types/repodna';

interface InspectorPanelProps {
  selectedFile: FileNode | null;
  allCycles: CycleGroup[];
  allFindings: RuleFinding[];
  onSelectFile: (fileId: string) => void;
}

export const InspectorPanel: React.FC<InspectorPanelProps> = ({
  selectedFile,
  allCycles,
  allFindings,
  onSelectFile,
}) => {
  if (!selectedFile) {
    return (
      <aside
        aria-label="Selected module inspector"
        className="w-full lg:w-96 shrink-0 border-t lg:border-t-0 lg:border-l border-slate-800/80 bg-slate-950/60 p-6 flex flex-col items-center justify-center text-center text-xs text-slate-400"
      >
        <FileCode2 className="w-8 h-8 text-slate-600 mb-2" aria-hidden="true" />
        <h2 className="text-sm font-semibold text-slate-300 m-0">No Module Selected</h2>
        <p className="mt-1 max-w-xs">
          Click any node on the interactive dependency graph or choose a file in the Explorer to inspect its AST imports, stability metrics, and architectural findings.
        </p>
      </aside>
    );
  }

  const fileCycles = allCycles.filter((c) => selectedFile.cycle_ids.includes(c.id));
  const fileFindings = allFindings.filter((f) => f.affected_files.includes(selectedFile.id));

  const stabilityLabel =
    selectedFile.fan_in + selectedFile.fan_out === 0
      ? 'Isolated (No Internal Edges)'
      : selectedFile.instability <= 0.3
      ? 'Stable Core Provider (Low I)'
      : selectedFile.instability >= 0.7
      ? 'Volatile Orchestrator / Dependent (High I)'
      : 'Balanced Intermediate Module';

  return (
    <aside
      aria-label="Selected module inspector"
      data-testid="inspector-panel"
      className="w-full lg:w-96 shrink-0 border-t lg:border-t-0 lg:border-l border-slate-800/80 bg-slate-950/75 flex flex-col overflow-y-auto max-h-[45vh] lg:max-h-none"
    >
      {/* Module Header */}
      <div className="p-3.5 border-b border-slate-800/80 bg-slate-900/50">
        <div className="flex items-center justify-between gap-2">
          <span className="text-[10px] font-mono uppercase tracking-wider px-2 py-0.5 rounded bg-sky-500/15 text-sky-300 border border-sky-500/30">
            {selectedFile.language}
          </span>
          <span
            className={`text-[10px] font-mono px-2 py-0.5 rounded border ${
              selectedFile.support_level === 'full_ast'
                ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
                : selectedFile.support_level === 'partial_static'
                ? 'bg-amber-500/15 text-amber-300 border-amber-500/30'
                : 'bg-slate-800 text-slate-400 border-slate-700'
            }`}
          >
            {selectedFile.support_level}
          </span>
        </div>

        <h2
          data-testid="inspector-file-title"
          className="text-sm font-bold font-mono text-slate-100 mt-2 mb-0.5 break-all"
        >
          {selectedFile.id}
        </h2>
        <div className="text-[11px] text-slate-400 flex items-center gap-3 mt-1">
          <span>{selectedFile.lines_code.toLocaleString()} LOC</span>
          <span>&bull;</span>
          <span>{selectedFile.lines_comment} comments</span>
          <span>&bull;</span>
          <span>{(selectedFile.size_bytes / 1024).toFixed(1)} KB</span>
        </div>
      </div>

      <div className="p-3.5 space-y-4 text-xs">
        {/* Coupling & Stability Metrics */}
        <section aria-labelledby="inspector-coupling-heading" className="bg-slate-900/70 border border-slate-800 rounded-xl p-3">
          <h3 id="inspector-coupling-heading" className="text-[11px] font-bold uppercase tracking-wider text-slate-400 m-0 mb-2">
            Topological Coupling &amp; Stability
          </h3>
          <div className="grid grid-cols-3 gap-2 text-center">
            <div className="bg-slate-950/70 border border-slate-800/80 rounded-lg p-2">
              <div className="text-[10px] text-slate-400">Fan-In (Ca)</div>
              <div className="text-sm font-bold text-emerald-400 font-mono">{selectedFile.fan_in}</div>
            </div>
            <div className="bg-slate-950/70 border border-slate-800/80 rounded-lg p-2">
              <div className="text-[10px] text-slate-400">Fan-Out (Ce)</div>
              <div className="text-sm font-bold text-sky-400 font-mono">{selectedFile.fan_out}</div>
            </div>
            <div className="bg-slate-950/70 border border-slate-800/80 rounded-lg p-2">
              <div className="text-[10px] text-slate-400">Instability (I)</div>
              <div className="text-sm font-bold text-amber-300 font-mono">
                {selectedFile.instability.toFixed(2)}
              </div>
            </div>
          </div>
          <div className="mt-2 text-[11px] text-slate-300 flex items-center justify-between">
            <span>Role:</span>
            <span className="font-medium text-sky-300">{stabilityLabel}</span>
          </div>
        </section>

        {/* Circular Dependency Alert for this File */}
        {selectedFile.in_cycle && (
          <section
            aria-labelledby="inspector-cycles-heading"
            className="bg-red-950/35 border border-red-500/40 rounded-xl p-3 space-y-2"
          >
            <h3
              id="inspector-cycles-heading"
              className="text-xs font-bold text-red-300 m-0 flex items-center gap-1.5"
            >
              <RefreshCcw className="w-3.5 h-3.5 text-red-400" aria-hidden="true" />
              Circular Dependency Participant ({fileCycles.length})
            </h3>
            {fileCycles.map((cyc) => (
              <div key={cyc.id} className="text-[11px] bg-slate-950/70 rounded-lg p-2 border border-red-900/50">
                <div className="font-mono font-semibold text-red-300 mb-1">
                  {cyc.id} ({cyc.length} hops)
                </div>
                <div className="flex flex-wrap items-center gap-1 font-mono text-[10px]">
                  {cyc.nodes.map((nodeId, idx) => (
                    <React.Fragment key={`${cyc.id}-${idx}`}>
                      <button
                        type="button"
                        onClick={() => onSelectFile(nodeId)}
                        className="underline hover:text-sky-300 text-slate-200 cursor-pointer"
                      >
                        {nodeId.split('/').pop()}
                      </button>
                      {idx < cyc.nodes.length - 1 && <span className="text-red-400">&rarr;</span>}
                    </React.Fragment>
                  ))}
                </div>
              </div>
            ))}
          </section>
        )}

        {/* Rule Findings Affecting this File */}
        {fileFindings.length > 0 && (
          <section aria-labelledby="inspector-findings-heading" className="space-y-1.5">
            <h3
              id="inspector-findings-heading"
              className="text-[11px] font-bold uppercase tracking-wider text-amber-300 m-0 flex items-center gap-1.5"
            >
              <ShieldAlert className="w-3.5 h-3.5 text-amber-400" aria-hidden="true" />
              Triggered Health Rules ({fileFindings.length})
            </h3>
            <div className="space-y-1.5">
              {fileFindings.map((fn) => (
                <div
                  key={fn.rule_id}
                  className="bg-slate-900/80 border border-amber-500/30 rounded-lg p-2.5 text-[11px]"
                >
                  <div className="font-semibold text-slate-100">
                    <span className="font-mono text-amber-300">{fn.rule_id}</span>: {fn.title}
                  </div>
                  <p className="text-slate-400 m-0 mt-1">{fn.remediation}</p>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Direct Internal Imports (Outgoing) */}
        <section aria-labelledby="inspector-imports-heading" className="space-y-1.5">
          <h3
            id="inspector-imports-heading"
            className="text-[11px] font-bold uppercase tracking-wider text-slate-400 m-0 flex items-center gap-1.5"
          >
            <ArrowUpRight className="w-3.5 h-3.5 text-sky-400" aria-hidden="true" />
            Direct Internal Imports ({selectedFile.imports_internal.length})
          </h3>
          {selectedFile.imports_internal.length === 0 ? (
            <div className="text-[11px] text-slate-400 italic">
              No outgoing internal module dependencies.
            </div>
          ) : (
            <ul role="list" className="m-0 p-0 list-none space-y-1">
              {selectedFile.imports_internal.map((targetId) => (
                <li key={targetId}>
                  <button
                    type="button"
                    onClick={() => onSelectFile(targetId)}
                    className="w-full text-left px-2.5 py-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 border border-slate-800 font-mono text-[11px] text-sky-300 truncate cursor-pointer"
                  >
                    {targetId}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>

        {/* Imported By (Incoming Dependents) */}
        <section aria-labelledby="inspector-dependents-heading" className="space-y-1.5">
          <h3
            id="inspector-dependents-heading"
            className="text-[11px] font-bold uppercase tracking-wider text-slate-400 m-0 flex items-center gap-1.5"
          >
            <ArrowDownLeft className="w-3.5 h-3.5 text-emerald-400" aria-hidden="true" />
            Imported By ({selectedFile.imported_by.length})
          </h3>
          {selectedFile.imported_by.length === 0 ? (
            <div className="text-[11px] text-slate-400 italic">
              No internal modules import this file directly.
            </div>
          ) : (
            <ul role="list" className="m-0 p-0 list-none space-y-1">
              {selectedFile.imported_by.map((sourceId) => (
                <li key={sourceId}>
                  <button
                    type="button"
                    onClick={() => onSelectFile(sourceId)}
                    className="w-full text-left px-2.5 py-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 border border-slate-800 font-mono text-[11px] text-emerald-300 truncate cursor-pointer"
                  >
                    {sourceId}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>

        {/* External Packages */}
        {selectedFile.imports_external.length > 0 && (
          <section aria-labelledby="inspector-external-heading" className="space-y-1.5">
            <h3
              id="inspector-external-heading"
              className="text-[11px] font-bold uppercase tracking-wider text-slate-400 m-0 flex items-center gap-1.5"
            >
              <Package className="w-3.5 h-3.5 text-indigo-400" aria-hidden="true" />
              External Packages ({selectedFile.imports_external.length})
            </h3>
            <div className="flex flex-wrap gap-1">
              {selectedFile.imports_external.map((pkg) => (
                <span
                  key={pkg}
                  className="px-2 py-0.5 rounded bg-slate-900 border border-slate-800 font-mono text-[10px] text-slate-300"
                >
                  {pkg}
                </span>
              ))}
            </div>
          </section>
        )}

        {/* Unresolved / Dynamic Imports Transparency */}
        {selectedFile.unresolved_imports.length > 0 && (
          <section aria-labelledby="inspector-unresolved-heading" className="space-y-1.5">
            <h3
              id="inspector-unresolved-heading"
              className="text-[11px] font-bold uppercase tracking-wider text-amber-300 m-0 flex items-center gap-1.5"
            >
              <AlertTriangle className="w-3.5 h-3.5 text-amber-400" aria-hidden="true" />
              Unresolved / Dynamic Imports ({selectedFile.unresolved_imports.length})
            </h3>
            <ul role="list" className="m-0 p-0 list-none space-y-1">
              {selectedFile.unresolved_imports.map((u, idx) => (
                <li
                  key={`${u.raw_import}-${idx}`}
                  className="bg-amber-950/30 border border-amber-800/40 rounded-lg p-2 text-[11px] font-mono"
                >
                  <div className="text-amber-200">{u.raw_import}</div>
                  <div className="text-[10px] text-slate-400">
                    Line {u.line} &bull; Reason: {u.reason}
                  </div>
                </li>
              ))}
            </ul>
          </section>
        )}

        {/* Extracted AST Symbols */}
        {selectedFile.symbols.length > 0 && (
          <section aria-labelledby="inspector-symbols-heading" className="space-y-1.5">
            <h3
              id="inspector-symbols-heading"
              className="text-[11px] font-bold uppercase tracking-wider text-slate-400 m-0 flex items-center gap-1.5"
            >
              <Code2 className="w-3.5 h-3.5 text-violet-400" aria-hidden="true" />
              AST Declarations ({selectedFile.symbols.length})
            </h3>
            <div className="max-h-44 overflow-y-auto border border-slate-800 rounded-lg divide-y divide-slate-800/60 bg-slate-900/50">
              {selectedFile.symbols.map((sym, idx) => (
                <div
                  key={`${sym.name}-${sym.line}-${idx}`}
                  className="px-2.5 py-1.5 flex items-center justify-between text-[11px] font-mono"
                >
                  <span className="flex items-center gap-1.5 truncate">
                    <Box className="w-3 h-3 text-violet-400 shrink-0" aria-hidden="true" />
                    <span className="text-slate-200 truncate">{sym.name}</span>
                  </span>
                  <span className="text-[10px] text-slate-400 shrink-0">
                    {sym.kind} :L{sym.line}
                  </span>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Git Activity on this File */}
        <section aria-labelledby="inspector-git-heading" className="bg-slate-900/60 border border-slate-800 rounded-xl p-3">
          <h3
            id="inspector-git-heading"
            className="text-[11px] font-bold uppercase tracking-wider text-slate-400 m-0 mb-1.5 flex items-center gap-1.5"
          >
            <GitCommitHorizontal className="w-3.5 h-3.5 text-sky-400" aria-hidden="true" />
            Git Activity
          </h3>
          {selectedFile.git_commits > 0 ? (
            <div className="text-[11px] text-slate-300 space-y-1">
              <div>
                Recent Commits Touching File: <strong>{selectedFile.git_commits}</strong>
              </div>
              {selectedFile.git_last_author && (
                <div>
                  Last Author: <strong>{selectedFile.git_last_author}</strong> ({selectedFile.git_last_modified})
                </div>
              )}
            </div>
          ) : (
            <div className="text-[11px] text-slate-400">
              No recorded Git commit churn for this file.
            </div>
          )}
        </section>
      </div>
    </aside>
  );
};
