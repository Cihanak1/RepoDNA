import React from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  FileStack,
  Flame,
  GitCommitHorizontal,
  Layers,
  Network,
  RefreshCcw,
} from 'lucide-react';
import type { AnalysisResult } from '../types/repodna';

interface SummaryStripProps {
  result: AnalysisResult;
  cyclesOnly: boolean;
  onToggleCyclesOnly: () => void;
  onOpenReportTab: () => void;
  isPreviousAnalysis?: boolean;
}

export const SummaryStrip: React.FC<SummaryStripProps> = ({
  result,
  cyclesOnly,
  onToggleCyclesOnly,
  onOpenReportTab,
  isPreviousAnalysis = false,
}) => {
  const hr = result.health_report;
  const gm = result.graph_metrics;
  const tr = result.transparency;

  const gradeColors: Record<string, string> = {
    A: 'text-emerald-400 bg-emerald-500/15 border-emerald-500/30',
    B: 'text-sky-400 bg-sky-500/15 border-sky-500/30',
    C: 'text-amber-400 bg-amber-500/15 border-amber-500/30',
    D: 'text-orange-400 bg-orange-500/15 border-orange-500/30',
    F: 'text-red-400 bg-red-500/15 border-red-500/30',
    'N/A': 'text-slate-400 bg-slate-800/40 border-slate-700',
  };

  return (
    <section
      aria-label="Repository analysis summary metrics"
      className="border-b border-slate-800/80 bg-slate-900/55 px-4 py-2 grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2.5 text-xs"
    >
      {/* Architecture Health Score */}
      <button
        type="button"
        onClick={onOpenReportTab}
        className="flex items-center justify-between p-2 rounded-lg bg-slate-900/90 hover:bg-slate-800/80 border border-slate-800 text-left cursor-pointer transition"
      >
        <div>
          <div className="text-[10px] uppercase tracking-wider text-slate-400 font-semibold flex items-center gap-1.5">
            <span>Architecture Health</span>
            {isPreviousAnalysis && (
              <span
                data-testid="previous-analysis-badge"
                className="px-1.5 py-0.5 rounded bg-amber-500/20 border border-amber-500/40 text-amber-300 text-[9px] font-bold uppercase"
              >
                Previous analysis
              </span>
            )}
          </div>
          <div className="text-base font-bold text-slate-100 mt-0.5 flex items-baseline gap-1.5">
            {hr.overall_score !== null ? (
              <>
                <span data-testid="summary-health-score">{hr.overall_score.toFixed(1)}</span>
                <span className="text-[11px] font-normal text-slate-400">/ 100</span>
              </>
            ) : (
              <span data-testid="summary-health-score" className="text-sm text-slate-400">
                N/A (Insufficient Data)
              </span>
            )}
          </div>
        </div>
        <span
          className={`px-2.5 py-1 rounded-lg font-bold text-sm border ${
            gradeColors[hr.grade] ?? gradeColors['N/A']
          }`}
        >
          {hr.grade}
        </span>
      </button>

      {/* Files & LOC */}
      <div className="flex items-center justify-between p-2 rounded-lg bg-slate-900/90 border border-slate-800">
        <div>
          <div className="text-[10px] uppercase tracking-wider text-slate-400 font-semibold">
            Files &amp; Code Volume
          </div>
          <div className="text-sm font-bold text-slate-100 mt-0.5">
            <span data-testid="summary-total-files">{result.total_files.toLocaleString()}</span> files &bull;{' '}
            <span className="text-sky-400">{result.total_lines_code.toLocaleString()}</span> LOC
          </div>
        </div>
        <FileStack className="w-4 h-4 text-sky-400 shrink-0" aria-hidden="true" />
      </div>

      {/* Internal Dependency Graph */}
      <div className="flex items-center justify-between p-2 rounded-lg bg-slate-900/90 border border-slate-800">
        <div>
          <div className="text-[10px] uppercase tracking-wider text-slate-400 font-semibold">
            Module Topology
          </div>
          <div className="text-sm font-bold text-slate-100 mt-0.5">
            <span data-testid="summary-total-edges">{gm.total_edges.toLocaleString()}</span> edges &bull;{' '}
            <span className="text-slate-300 font-mono text-xs">I={gm.average_instability.toFixed(2)}</span>
          </div>
        </div>
        <Network className="w-4 h-4 text-indigo-400 shrink-0" aria-hidden="true" />
      </div>

      {/* Circular Dependencies */}
      <button
        type="button"
        onClick={onToggleCyclesOnly}
        aria-pressed={cyclesOnly}
        className={`flex items-center justify-between p-2 rounded-lg border text-left cursor-pointer transition ${
          cyclesOnly
            ? 'bg-red-950/60 border-red-500/60'
            : gm.cycle_count > 0
            ? 'bg-red-950/25 hover:bg-red-950/40 border-red-800/50'
            : 'bg-slate-900/90 border-slate-800'
        }`}
      >
        <div>
          <div className="text-[10px] uppercase tracking-wider text-slate-400 font-semibold">
            Circular Dependencies
          </div>
          <div className="text-sm font-bold mt-0.5 flex items-center gap-1.5">
            {gm.cycle_count > 0 || gm.scc_count > 0 ? (
              <>
                <span data-testid="summary-cycle-count" className="text-red-400">
                  {gm.cycle_count} cycles
                </span>
                <span className="text-[11px] font-normal text-slate-400">
                  ({gm.scc_count} SCCs, {gm.nodes_in_cycles} modules)
                </span>
              </>
            ) : (
              <span data-testid="summary-cycle-count" className="text-emerald-400">
                0 cycles (Acyclic)
              </span>
            )}
          </div>
        </div>
        {gm.cycle_count > 0 ? (
          <RefreshCcw className="w-4 h-4 text-red-400 shrink-0" aria-hidden="true" />
        ) : (
          <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" aria-hidden="true" />
        )}
      </button>

      {/* Language Coverage & Unsupported Transparency */}
      <button
        type="button"
        onClick={onOpenReportTab}
        className="flex items-center justify-between p-2 rounded-lg bg-slate-900/90 hover:bg-slate-800/80 border border-slate-800 text-left cursor-pointer"
      >
        <div className="truncate pr-1">
          <div className="text-[10px] uppercase tracking-wider text-slate-400 font-semibold">
            AST Language Coverage
          </div>
          <div className="text-xs font-semibold text-slate-100 mt-0.5 truncate">
            {tr.supported_languages_detected.length} AST supported
            {(tr.partial_static_files_count ?? 0) > 0 && (
              <>
                {' '}&bull;{' '}
                <span className="text-amber-300">
                  {tr.partial_static_files_count} partial_static
                </span>
              </>
            )}
            {' '}&bull;{' '}
            <span className={tr.unsupported_files_count > 0 ? 'text-amber-300' : 'text-slate-400'}>
              {tr.unsupported_files_count} unsupported
            </span>
          </div>
        </div>
        {tr.unsupported_files_count > 0 ? (
          <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" aria-hidden="true" />
        ) : (
          <Layers className="w-4 h-4 text-emerald-400 shrink-0" aria-hidden="true" />
        )}
      </button>

      {/* Git Insights & Churn */}
      <div className="flex items-center justify-between p-2 rounded-lg bg-slate-900/90 border border-slate-800">
        <div>
          <div className="text-[10px] uppercase tracking-wider text-slate-400 font-semibold">
            Git History &amp; Hotspots
          </div>
          <div className="text-xs font-semibold text-slate-100 mt-0.5 flex items-center gap-1.5">
            {result.git_insights.is_git_repo ? (
              <>
                <GitCommitHorizontal className="w-3.5 h-3.5 text-sky-400" aria-hidden="true" />
                <span>{result.git_insights.total_commits_scanned} commits</span>
                <span>&bull;</span>
                <span className="text-amber-300">{result.git_insights.hotspots.length} hotspots</span>
              </>
            ) : (
              <span className="text-slate-400">Non-Git Folder</span>
            )}
          </div>
        </div>
        <Flame className="w-4 h-4 text-orange-400 shrink-0" aria-hidden="true" />
      </div>
    </section>
  );
};
