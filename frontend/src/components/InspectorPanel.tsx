import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  ArrowUpRight,
  Box,
  ChevronDown,
  FileCode2,
  GitCommitHorizontal,
  Package,
  RefreshCcw,
} from 'lucide-react';
import type { CycleGroup, FileNode, RuleFinding } from '../types/repodna';
import type { WorkstationMode } from '../utils/preferences';
import { InfoTooltip } from './InfoTooltip';

interface InspectorPanelProps {
  selectedFile: FileNode | null;
  allCycles: CycleGroup[];
  allFindings: RuleFinding[];
  onSelectFile: (fileId: string) => void;
  packageFiles?: FileNode[];
  onExpandPackage?: () => void;
  workstationMode?: WorkstationMode;
}

export const InspectorPanel: React.FC<InspectorPanelProps> = ({
  selectedFile,
  allCycles,
  allFindings,
  onSelectFile,
  packageFiles,
  onExpandPackage,
  workstationMode = 'simple',
}) => {
  const { t } = useTranslation();
  const [copyStatus, setCopyStatus] = useState('');

  const copy = async (value: string) => {
    try {
      await navigator.clipboard.writeText(value);
      setCopyStatus(t('common.copied'));
      window.setTimeout(() => setCopyStatus(''), 2500);
    } catch {
      setCopyStatus(t('common.copyFailed'));
      window.setTimeout(() => setCopyStatus(''), 2500);
    }
  };

  if (!selectedFile) {
    return (
      <aside
        aria-label={t('inspector.title')}
        data-testid="inspector-panel"
        className="w-full lg:w-96 shrink-0 border-t lg:border-t-0 lg:border-l border-line bg-canvas p-6 flex flex-col items-center justify-center text-center text-xs text-muted"
      >
        <FileCode2 className="w-8 h-8 text-muted mb-2" aria-hidden="true" />
        <h2 className="text-sm font-semibold text-muted m-0">{t('inspector.noSelectionTitle')}</h2>
        <p className="mt-1 max-w-xs leading-relaxed">
          {t('inspector.noSelectionDesc')}
        </p>
      </aside>
    );
  }

  const fileCycles = allCycles.filter((c) => selectedFile.cycle_ids.includes(c.id));
  const fileFindings = allFindings.filter((f) => f.affected_files.includes(selectedFile.id));

  const stabilityLabel =
    selectedFile.support_level !== 'full_ast'
      ? t('inspector.roleIncomplete')
      : selectedFile.fan_in + selectedFile.fan_out === 0
      ? t('inspector.roleIsolated')
      : selectedFile.instability <= 0.3
      ? t('inspector.roleStable')
      : selectedFile.instability >= 0.7
      ? t('inspector.roleVolatile')
      : t('inspector.roleBalanced');

  return (
    <aside
      aria-label={t('inspector.title')}
      data-testid="inspector-panel"
      className="w-full lg:w-96 shrink-0 border-t lg:border-t-0 lg:border-l border-line bg-canvas flex flex-col overflow-y-auto max-h-[45vh] lg:max-h-none"
    >
      {/* Module Header */}
      <div className="p-3.5 border-b border-line bg-panel">
        {packageFiles && (
          <section aria-label={t('inspector.packageTitle')} className="mb-3 border-b border-line pb-3">
            <h2 className="text-base font-semibold break-all text-ink">{selectedFile.directory || 'Repository root'}</h2>
            <p className="text-xs text-muted mt-0.5">
              {packageFiles.length} {t('summary.files')} / {packageFiles.reduce((sum, file) => sum + file.lines_code, 0).toLocaleString()} LOC
            </p>
            <button
              type="button"
              className="text-xs text-accent font-semibold hover:underline cursor-pointer mt-1.5 flex items-center gap-1"
              onClick={onExpandPackage}
            >
              <Package className="w-3.5 h-3.5" aria-hidden="true" />
              {t('inspector.expandPackage')}
            </button>
            <p className="text-[11px] text-muted mt-1.5">
              {t('inspector.moduleDetailsBelow')} <span className="font-mono text-ink">{selectedFile.name}</span>
            </p>
          </section>
        )}

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

        {/* Short filename display and full path */}
        <div className="mt-2 mb-1">
          <h2
            data-testid="inspector-file-title"
            className="text-sm font-bold font-mono text-ink break-all m-0"
            title={selectedFile.id}
          >
            {selectedFile.id}
          </h2>
        </div>

        <div className="copy-actions flex items-center gap-2 mt-1.5">
          <button
            type="button"
            className="text-xs px-2 py-1 rounded bg-raised hover:bg-line border border-line text-ink cursor-pointer"
            onClick={() => void copy(selectedFile.id)}
          >
            {t('inspector.copyPath')}
          </button>
          <button
            type="button"
            className="text-xs px-2 py-1 rounded bg-raised hover:bg-line border border-line text-ink cursor-pointer"
            onClick={() =>
              void copy(
                JSON.stringify(
                  {
                    path: selectedFile.id,
                    fan_in: selectedFile.fan_in,
                    fan_out: selectedFile.fan_out,
                    instability: selectedFile.instability,
                    support_level: selectedFile.support_level,
                  },
                  null,
                  2
                )
              )
            }
          >
            {t('inspector.copyMetrics')}
          </button>
          {copyStatus && (
            <span role="status" className="text-xs font-semibold text-accent animate-in fade-in">
              {copyStatus}
            </span>
          )}
        </div>

        <div className="text-[11px] text-muted flex items-center gap-2 mt-2">
          <span>{selectedFile.lines_code.toLocaleString()} LOC</span>
          <span>&bull;</span>
          <span>{selectedFile.lines_comment} comments</span>
          <span>&bull;</span>
          <span>{(selectedFile.size_bytes / 1024).toFixed(1)} KB</span>
        </div>
      </div>

      <div className="inspector-body p-3.5 space-y-3.5 text-xs">
        {/* Core Architectural Role */}
        <section aria-labelledby="inspector-role-heading" className="bg-panel border border-line rounded-md p-3">
          <div className="flex items-center justify-between">
            <span id="inspector-role-heading" className="text-[11px] font-bold text-muted uppercase tracking-wide">
              {t('inspector.role')}
            </span>
            <span className="font-semibold text-accent">{stabilityLabel}</span>
          </div>
          <div className="grid grid-cols-2 gap-2 mt-2.5 text-center">
            <div className="bg-canvas border border-line rounded p-2">
              <span className="text-[11px] text-muted block">
                <InfoTooltip title={t('help.fanInTitle')} description={t('help.fanInDesc')}>
                  {t('inspector.fanIn')}
                </InfoTooltip>
              </span>
              <span className="text-base font-bold text-success font-mono block mt-0.5">
                {selectedFile.fan_in}
              </span>
            </div>
            <div className="bg-canvas border border-line rounded p-2">
              <span className="text-[11px] text-muted block">
                <InfoTooltip title={t('help.fanOutTitle')} description={t('help.fanOutDesc')}>
                  {t('inspector.fanOut')}
                </InfoTooltip>
              </span>
              <span className="text-base font-bold text-accent font-mono block mt-0.5">
                {selectedFile.fan_out}
              </span>
            </div>
          </div>
        </section>

        {/* Circular Dependency Alert (If participant) */}
        {selectedFile.in_cycle && (
          <section
            aria-labelledby="inspector-cycles-heading"
            className="bg-danger/10 border border-danger/40 rounded-md p-3 space-y-2"
          >
            <div className="flex items-center gap-1.5 text-danger font-semibold text-[11px]">
              <RefreshCcw className="w-3.5 h-3.5" aria-hidden="true" />
              <h3 id="inspector-cycles-heading" className="m-0 font-bold">
                {t('inspector.cyclesHeading')} ({fileCycles.length})
              </h3>
            </div>
            {fileCycles.map((cycle) => (
              <div key={cycle.id} className="bg-panel/80 p-2 rounded border border-danger/30 text-[11px]">
                <div className="font-mono text-danger font-bold">
                  {cycle.id} ({cycle.length} hops)
                </div>
                <div className="mt-1 font-mono text-[11px] text-muted space-y-0.5 break-all">
                  {cycle.nodes.map((nodeId, idx) => (
                    <div key={idx} className="flex items-center gap-1">
                      {idx > 0 && <span>&rarr;</span>}
                      <span className={nodeId === selectedFile.id ? 'text-ink font-bold underline' : ''}>
                        {nodeId}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </section>
        )}

        {/* Triggered Health Rules */}
        {fileFindings.length > 0 && (
          <section aria-labelledby="inspector-findings-heading" className="bg-panel border border-line rounded-md p-3 space-y-2">
            <h3 id="inspector-findings-heading" className="text-[11px] font-bold text-muted uppercase tracking-wide m-0">
              {t('inspector.triggeredRulesHeading')} ({fileFindings.length})
            </h3>
            {fileFindings.map((finding, idx) => (
              <div
                key={idx}
                className={`p-2.5 rounded border text-[11px] ${
                  finding.severity === 'critical'
                    ? 'bg-danger/10 border-danger/40 text-danger'
                    : 'bg-warning/10 border-warning/40 text-warning'
                }`}
              >
                <div className="flex items-center justify-between font-bold">
                  <span>{finding.rule_id}: {finding.title}</span>
                  <span className="uppercase text-[10px] px-1.5 py-0.5 rounded bg-panel font-mono border">
                    {finding.severity}
                  </span>
                </div>
                <p className="mt-1 text-ink leading-relaxed m-0 text-xs">
                  {finding.remediation}
                </p>
              </div>
            ))}
          </section>
        )}

        {/* Direct Internal Imports (Outgoing) */}
        <section aria-labelledby="inspector-outgoing-heading" className="bg-panel border border-line rounded-md p-3">
          <h3 id="inspector-outgoing-heading" className="text-[11px] font-bold text-muted uppercase tracking-wide m-0 mb-1.5 flex items-center gap-1">
            <ArrowUpRight className="w-3.5 h-3.5 text-accent" />
            {t('inspector.directImportsHeading')} ({selectedFile.imports_internal.length})
          </h3>
          {selectedFile.imports_internal.length === 0 ? (
            <p className="text-[11px] text-muted m-0 italic">None</p>
          ) : (
            <div className="flex flex-col gap-1 max-h-32 overflow-y-auto">
              {selectedFile.imports_internal.map((targetId) => (
                <button
                  key={targetId}
                  type="button"
                  onClick={() => onSelectFile(targetId)}
                  className="text-left font-mono text-[11px] text-accent hover:underline truncate cursor-pointer"
                  title={targetId}
                >
                  {targetId}
                </button>
              ))}
            </div>
          )}
        </section>

        {/* Level 3: Advanced Metrics & Git Churn (Progressive Disclosure) */}
        <details
          data-testid="inspector-technical-details"
          open={workstationMode === 'advanced'}
          className="bg-panel border border-line rounded-md p-3 group"
        >
          <summary className="text-[11px] font-bold text-muted uppercase tracking-wide cursor-pointer flex items-center justify-between list-none select-none">
            <span className="flex items-center gap-1.5">
              <Box className="w-3.5 h-3.5 text-accent" />
              {t('inspector.advancedHeading')}
            </span>
            <ChevronDown className="w-3.5 h-3.5 text-muted transition-transform group-open:rotate-180" />
          </summary>

          <div className="mt-3 space-y-3 pt-2 border-t border-line text-xs">
            {/* Instability metric */}
            <div className="flex items-center justify-between p-2 rounded bg-canvas border border-line">
              <span className="text-[11px] text-muted">
                <InfoTooltip title={t('help.instabilityTitle')} description={t('help.instabilityDesc')}>
                  {t('inspector.instability')}
                </InfoTooltip>
              </span>
              <span className="font-mono font-bold text-ink">
                {selectedFile.instability.toFixed(2)}
              </span>
            </div>

            {/* Git Churn */}
            {selectedFile.git_commits > 0 && (
              <div className="p-2 rounded bg-canvas border border-line flex items-center justify-between">
                <span className="text-[11px] text-muted flex items-center gap-1">
                  <GitCommitHorizontal className="w-3.5 h-3.5 text-muted" />
                  {t('inspector.gitCommits')}
                </span>
                <span className="font-mono text-ink font-semibold">
                  {selectedFile.git_commits} commits
                </span>
              </div>
            )}

            {/* External Imports */}
            {selectedFile.imports_external.length > 0 && (
              <div>
                <span className="text-[11px] font-semibold text-muted block mb-1">
                  {t('inspector.externalImportsHeading')} ({selectedFile.imports_external.length})
                </span>
                <div className="flex flex-wrap gap-1">
                  {selectedFile.imports_external.map((pkg, idx) => (
                    <span
                      key={idx}
                      className="px-1.5 py-0.5 rounded bg-raised border border-line font-mono text-[11px] text-muted"
                    >
                      {pkg}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Declared Symbols */}
            {selectedFile.symbols.length > 0 && (
              <div>
                <span className="text-[11px] font-semibold text-muted block mb-1">
                  {t('inspector.symbolsHeading')} ({selectedFile.symbols.length})
                </span>
                <div className="max-h-28 overflow-y-auto font-mono text-[11px] text-muted space-y-0.5">
                  {selectedFile.symbols.map((sym, idx) => (
                    <div key={idx} className="truncate" title={sym.name}>
                      <span className="text-accent">{sym.kind}</span> {sym.name}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </details>
      </div>
    </aside>
  );
};
