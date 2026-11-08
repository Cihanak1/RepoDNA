import React, { useState } from 'react';
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
  packageFiles?: FileNode[];
  onExpandPackage?: () => void;
}

export const InspectorPanel: React.FC<InspectorPanelProps> = ({
  selectedFile,
  allCycles,
  allFindings,
  onSelectFile,
  packageFiles,
  onExpandPackage,
}) => {
  const [copyStatus, setCopyStatus] = useState('');
  const copy = async (value: string) => {
    try { await navigator.clipboard.writeText(value); setCopyStatus('Copied'); }
    catch { setCopyStatus('Copy unavailable. Select the path text to copy.'); }
  };
  if (!selectedFile) {
    return (
      <aside
        aria-label="Selected module inspector"
        className="w-full lg:w-96 shrink-0 border-t lg:border-t-0 lg:border-l border-line bg-canvas p-6 flex flex-col items-center justify-center text-center text-xs text-muted"
      >
        <FileCode2 className="w-8 h-8 text-muted mb-2" aria-hidden="true" />
        <h2 className="text-sm font-semibold text-muted m-0">No Module Selected</h2>
        <p className="mt-1 max-w-xs">
          Click any node on the interactive dependency graph or choose a file in the Explorer to inspect its AST imports, stability metrics, and architectural findings.
        </p>
      </aside>
    );
  }

  const fileCycles = allCycles.filter((c) => selectedFile.cycle_ids.includes(c.id));
  const fileFindings = allFindings.filter((f) => f.affected_files.includes(selectedFile.id));

  const stabilityLabel =
    selectedFile.support_level !== 'full_ast' ? 'Dependency coverage incomplete' :
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
      className="w-full lg:w-96 shrink-0 border-t lg:border-t-0 lg:border-l border-line bg-canvas flex flex-col overflow-y-auto max-h-[45vh] lg:max-h-none"
    >
      {/* Module Header */}
      <div className="p-3.5 border-b border-line bg-panel">
        {packageFiles && <section aria-label="Selected package" className="mb-4 border-b border-line pb-3">
          <h2 className="text-base font-semibold break-all">{selectedFile.directory || 'Repository root'}</h2>
          <p className="text-xs text-muted mt-1">{packageFiles.length} modules / {packageFiles.reduce((sum, file) => sum + file.lines_code, 0).toLocaleString()} LOC</p>
          <p className="text-xs text-muted mt-1">{packageFiles.filter(file => file.support_level === 'full_ast').length} full AST / {packageFiles.filter(file => file.support_level === 'partial_static').length} partial static / {packageFiles.filter(file => file.support_level === 'unsupported').length} unsupported</p>
          <button className="text-xs text-accent cursor-pointer mt-2" onClick={onExpandPackage}>Expand package to modules</button>
          <p className="text-xs text-muted mt-2">Module details below: {selectedFile.name}</p>
        </section>}
        <div className="flex items-center justify-between gap-2">
          <span className="text-[11px] font-mono tracking-wide px-2 py-0.5 rounded bg-accent/15 text-accent border border-accent/30">
            {selectedFile.language}
          </span>
          <span
            className={`text-[11px] font-mono px-2 py-0.5 rounded border ${
              selectedFile.support_level === 'full_ast'
                ? 'bg-success/15 text-success border-success/30'
                : selectedFile.support_level === 'partial_static'
                ? 'bg-warning/15 text-warning border-warning/30'
                : 'bg-raised text-muted border-line'
            }`}
          >
            {selectedFile.support_level}
          </span>
        </div>

        <h2
          data-testid="inspector-file-title"
          className="text-sm font-bold font-mono text-ink mt-2 mb-0.5 break-all"
        >
          {selectedFile.id}
        </h2>
        <div className="copy-actions">
          <button onClick={() => void copy(selectedFile.id)}>Copy path</button>
          <button onClick={() => void copy(JSON.stringify({ path: selectedFile.id, fan_in: selectedFile.fan_in, fan_out: selectedFile.fan_out, instability: selectedFile.instability, support_level: selectedFile.support_level }, null, 2))}>Copy metrics</button>
          <span role="status" className="text-xs text-muted">{copyStatus}</span>
        </div>
        <div className="text-[11px] text-muted flex items-center gap-3 mt-1">
          <span>{selectedFile.lines_code.toLocaleString()} LOC</span>
          <span>&bull;</span>
          <span>{selectedFile.lines_comment} comments</span>
          <span>&bull;</span>
          <span>{(selectedFile.size_bytes / 1024).toFixed(1)} KB</span>
        </div>
      </div>

      <div className="inspector-body p-3.5 space-y-4 text-xs">
        {/* Coupling & Stability Metrics */}
        <section aria-labelledby="inspector-coupling-heading" className="bg-panel border border-line rounded-md p-3">
          <h3 id="inspector-coupling-heading" className="text-[11px] font-bold tracking-wide text-muted m-0 mb-2">
            Topological Coupling &amp; Stability
          </h3>
          <div className="grid grid-cols-3 gap-2 text-center">
            <div className="bg-canvas border border-line rounded-lg p-2">
              <div className="text-[11px] text-muted">Fan-In (Ca)</div>
              <div className="text-sm font-bold text-success font-mono">{selectedFile.fan_in}</div>
            </div>
            <div className="bg-canvas border border-line rounded-lg p-2">
              <div className="text-[11px] text-muted">Fan-Out (Ce)</div>
              <div className="text-sm font-bold text-accent font-mono">{selectedFile.fan_out}</div>
            </div>
            <div className="bg-canvas border border-line rounded-lg p-2">
              <div className="text-[11px] text-muted">Instability (I)</div>
              <div className="text-sm font-bold text-warning font-mono">
                {selectedFile.instability.toFixed(2)}
              </div>
            </div>
          </div>
          <div className="mt-2 text-[11px] text-muted flex items-center justify-between">
            <span>Role:</span>
            <span className="font-medium text-accent">{stabilityLabel}</span>
          </div>
        </section>

        {/* Circular Dependency Alert for this File */}
        {selectedFile.in_cycle && (
          <section
            aria-labelledby="inspector-cycles-heading"
            className="bg-danger/10 border border-danger/40 rounded-md p-3 space-y-2"
          >
            <h3
              id="inspector-cycles-heading"
              className="text-xs font-bold text-danger m-0 flex items-center gap-1.5"
            >
              <RefreshCcw className="w-3.5 h-3.5 text-danger" aria-hidden="true" />
              Circular Dependency Participant ({fileCycles.length})
            </h3>
            {fileCycles.map((cyc) => (
              <div key={cyc.id} className="text-[11px] bg-canvas rounded-lg p-2 border border-danger/50">
                <div className="font-mono font-semibold text-danger mb-1">
                  {cyc.id} ({cyc.length} hops)
                </div>
                <div className="flex flex-wrap items-center gap-1 font-mono text-[11px]">
                  {cyc.nodes.map((nodeId, idx) => (
                    <React.Fragment key={`${cyc.id}-${idx}`}>
                      <button
                        type="button"
                        onClick={() => onSelectFile(nodeId)}
                        className="underline hover:text-accent text-ink cursor-pointer"
                      >
                        {nodeId.split('/').pop()}
                      </button>
                      {idx < cyc.nodes.length - 1 && <span className="text-danger">&rarr;</span>}
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
              className="text-[11px] font-bold tracking-wide text-warning m-0 flex items-center gap-1.5"
            >
              <ShieldAlert className="w-3.5 h-3.5 text-warning" aria-hidden="true" />
              Triggered Health Rules ({fileFindings.length})
            </h3>
            <div className="space-y-1.5">
              {fileFindings.map((fn) => (
                <div
                  key={fn.rule_id}
                  className="bg-panel border border-warning/30 rounded-lg p-2.5 text-[11px]"
                >
                  <div className="font-semibold text-ink">
                    <span className="font-mono text-warning">{fn.rule_id}</span>: {fn.title}
                  </div>
                  <p className="text-muted m-0 mt-1">{fn.remediation}</p>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Direct Internal Imports (Outgoing) */}
        <section aria-labelledby="inspector-imports-heading" className="space-y-1.5">
          <h3
            id="inspector-imports-heading"
            className="text-[11px] font-bold tracking-wide text-muted m-0 flex items-center gap-1.5"
          >
            <ArrowUpRight className="w-3.5 h-3.5 text-accent" aria-hidden="true" />
            Direct Internal Imports ({selectedFile.imports_internal.length})
          </h3>
          {selectedFile.imports_internal.length === 0 ? (
            <div className="text-[11px] text-muted italic">
              {selectedFile.support_level === 'full_ast' ? 'No outgoing internal module dependencies resolved.' : 'No outgoing dependencies resolved. Static coverage is incomplete.'}
            </div>
          ) : (
            <ul role="list" className="m-0 p-0 list-none space-y-1">
              {selectedFile.imports_internal.map((targetId) => (
                <li key={targetId}>
                  <button
                    type="button"
                    onClick={() => onSelectFile(targetId)}
                    className="w-full text-left px-2.5 py-1.5 rounded-lg bg-panel hover:bg-raised border border-line font-mono text-[11px] text-accent truncate cursor-pointer"
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
            className="text-[11px] font-bold tracking-wide text-muted m-0 flex items-center gap-1.5"
          >
            <ArrowDownLeft className="w-3.5 h-3.5 text-success" aria-hidden="true" />
            Imported By ({selectedFile.imported_by.length})
          </h3>
          {selectedFile.imported_by.length === 0 ? (
            <div className="text-[11px] text-muted italic">
              {selectedFile.support_level === 'full_ast' ? 'No incoming internal dependencies resolved.' : 'No incoming dependencies resolved. Static coverage is incomplete.'}
            </div>
          ) : (
            <ul role="list" className="m-0 p-0 list-none space-y-1">
              {selectedFile.imported_by.map((sourceId) => (
                <li key={sourceId}>
                  <button
                    type="button"
                    onClick={() => onSelectFile(sourceId)}
                    className="w-full text-left px-2.5 py-1.5 rounded-lg bg-panel hover:bg-raised border border-line font-mono text-[11px] text-success truncate cursor-pointer"
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
              className="text-[11px] font-bold tracking-wide text-muted m-0 flex items-center gap-1.5"
            >
              <Package className="w-3.5 h-3.5 text-accent" aria-hidden="true" />
              External Packages ({selectedFile.imports_external.length})
            </h3>
            <div className="flex flex-wrap gap-1">
              {selectedFile.imports_external.map((pkg) => (
                <span
                  key={pkg}
                  className="px-2 py-0.5 rounded bg-panel border border-line font-mono text-[11px] text-muted"
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
              className="text-[11px] font-bold tracking-wide text-warning m-0 flex items-center gap-1.5"
            >
              <AlertTriangle className="w-3.5 h-3.5 text-warning" aria-hidden="true" />
              Unresolved / Dynamic Imports ({selectedFile.unresolved_imports.length})
            </h3>
            <ul role="list" className="m-0 p-0 list-none space-y-1">
              {selectedFile.unresolved_imports.map((u, idx) => (
                <li
                  key={`${u.raw_import}-${idx}`}
                  className="bg-warning/10 border border-warning/40 rounded-lg p-2 text-[11px] font-mono"
                >
                  <div className="text-warning">{u.raw_import}</div>
                  <div className="text-[11px] text-muted">
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
              className="text-[11px] font-bold tracking-wide text-muted m-0 flex items-center gap-1.5"
            >
              <Code2 className="w-3.5 h-3.5 text-accent" aria-hidden="true" />
              {selectedFile.support_level === 'full_ast' ? 'AST' : 'Static'} Declarations ({selectedFile.symbols.length})
            </h3>
            <div className="max-h-44 overflow-y-auto border border-line rounded-lg divide-y divide-line bg-panel">
              {selectedFile.symbols.map((sym, idx) => (
                <div
                  key={`${sym.name}-${sym.line}-${idx}`}
                  className="px-2.5 py-1.5 flex items-center justify-between text-[11px] font-mono"
                >
                  <span className="flex items-center gap-1.5 truncate">
                    <Box className="w-3 h-3 text-accent shrink-0" aria-hidden="true" />
                    <span className="text-ink truncate">{sym.name}</span>
                  </span>
                  <span className="text-[11px] text-muted shrink-0">
                    {sym.kind} :L{sym.line}
                  </span>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Git Activity on this File */}
        <section aria-labelledby="inspector-git-heading" className="bg-panel border border-line rounded-md p-3">
          <h3
            id="inspector-git-heading"
            className="text-[11px] font-bold tracking-wide text-muted m-0 mb-1.5 flex items-center gap-1.5"
          >
            <GitCommitHorizontal className="w-3.5 h-3.5 text-accent" aria-hidden="true" />
            Git Activity
          </h3>
          {selectedFile.git_commits > 0 ? (
            <div className="text-[11px] text-muted space-y-1">
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
            <div className="text-[11px] text-muted">
              No recorded Git commit churn for this file.
            </div>
          )}
        </section>
      </div>
    </aside>
  );
};
