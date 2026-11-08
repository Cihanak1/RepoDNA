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
    A: 'text-success bg-success/15 border-success/30',
    B: 'text-accent bg-accent/15 border-accent/30',
    C: 'text-warning bg-warning/15 border-warning/30',
    D: 'text-warning bg-warning/15 border-warning/30',
    F: 'text-danger bg-danger/15 border-danger/30',
    'N/A': 'text-muted bg-raised border-line',
  };

  return (
    <section
      aria-label="Repository analysis summary metrics"
      className="summary-strip text-xs"
    >
      {/* Architecture Health Score */}
      <button
        type="button"
        onClick={onOpenReportTab}
        className="flex items-center justify-between p-2 rounded-lg bg-panel hover:bg-raised border border-line text-left cursor-pointer transition"
      >
        <div>
          <div className="text-[11px] tracking-wide text-muted font-semibold flex items-center gap-1.5">
            <span>Architecture Health</span>
            {isPreviousAnalysis && (
              <span
                data-testid="previous-analysis-badge"
                className="px-1.5 py-0.5 rounded bg-warning/20 border border-warning/40 text-warning text-[11px] font-bold uppercase"
              >
                Previous analysis
              </span>
            )}
          </div>
          <div className="text-base font-bold text-ink mt-0.5 flex items-baseline gap-1.5">
            {hr.overall_score !== null ? (
              <>
                <span data-testid="summary-health-score">{hr.overall_score.toFixed(1)}</span>
                <span className="text-[11px] font-normal text-muted">/ 100</span>
              </>
            ) : hr.status === 'insufficient_dependency_coverage' ? (
              <span data-testid="summary-health-score" className="text-xs text-warning font-semibold">
                Insufficient Dependency Coverage
              </span>
            ) : (
              <span data-testid="summary-health-score" className="text-sm text-muted">
                N/A (Insufficient Data)
              </span>
            )}
          </div>
          {hr.confidence && hr.confidence !== 'none' && (
            <div className="text-[11px] text-muted mt-0.5">
              Confidence:{' '}
              <span
                data-testid="summary-health-confidence"
                className={
                  hr.confidence === 'high'
                    ? 'text-success font-semibold uppercase'
                    : hr.confidence === 'medium'
                    ? 'text-accent font-semibold uppercase'
                    : 'text-warning font-semibold uppercase'
                }
              >
                {hr.confidence}
              </span>
            </div>
          )}
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
      <div className="flex items-center justify-between p-2 rounded-lg bg-panel border border-line">
        <div>
          <div className="text-[11px] tracking-wide text-muted font-semibold">
            Files &amp; Code Volume
          </div>
          <div className="text-sm font-bold text-ink mt-0.5">
            <span data-testid="summary-total-files">{result.total_files.toLocaleString()}</span> files &bull;{' '}
            <span className="text-accent">{result.total_lines_code.toLocaleString()}</span> LOC
          </div>
        </div>
        <FileStack className="w-4 h-4 text-accent shrink-0" aria-hidden="true" />
      </div>

      {/* Internal Dependency Graph */}
      <div className="flex items-center justify-between p-2 rounded-lg bg-panel border border-line">
        <div>
          <div className="text-[11px] tracking-wide text-muted font-semibold">
            Module Topology
          </div>
          <div className="text-sm font-bold text-ink mt-0.5">
            <span data-testid="summary-total-edges">{gm.total_edges.toLocaleString()}</span> edges &bull;{' '}
            <span className="text-muted font-mono text-xs">I={gm.average_instability.toFixed(2)}</span>
          </div>
        </div>
        <Network className="w-4 h-4 text-accent shrink-0" aria-hidden="true" />
      </div>

      {/* Circular Dependencies */}
      <button
        type="button"
        onClick={onToggleCyclesOnly}
        aria-pressed={cyclesOnly}
        className={`flex items-center justify-between p-2 rounded-lg border text-left cursor-pointer transition ${
          cyclesOnly
            ? 'bg-danger/10 border-danger/60'
            : gm.cycle_count > 0
            ? 'bg-danger/10 hover:bg-danger/10 border-danger/50'
            : 'bg-panel border-line'
        }`}
      >
        <div>
          <div className="text-[11px] tracking-wide text-muted font-semibold">
            Circular Dependencies
          </div>
          <div className="text-sm font-bold mt-0.5 flex items-center gap-1.5">
            {gm.cycle_count > 0 || gm.scc_count > 0 ? (
              <>
                <span data-testid="summary-cycle-count" className="text-danger">
                  {gm.cycle_count} cycles
                </span>
                <span className="text-[11px] font-normal text-muted">
                  ({gm.scc_count} SCCs, {gm.nodes_in_cycles} modules)
                </span>
              </>
            ) : hr.dependency_graph_evaluated === false ? (
              <span data-testid="summary-cycle-count" className="text-xs text-warning font-semibold">
                Not evaluated (Low AST coverage)
              </span>
            ) : (
              <span data-testid="summary-cycle-count" className="text-success">
                0 cycles (in analyzed graph)
              </span>
            )}
          </div>
        </div>
        {gm.cycle_count > 0 ? (
          <RefreshCcw className="w-4 h-4 text-danger shrink-0" aria-hidden="true" />
        ) : hr.dependency_graph_evaluated === false ? (
          <AlertTriangle className="w-4 h-4 text-warning shrink-0" aria-hidden="true" />
        ) : (
          <CheckCircle2 className="w-4 h-4 text-success shrink-0" aria-hidden="true" />
        )}
      </button>

      {/* Language Coverage & Unsupported Transparency */}
      <button
        type="button"
        onClick={onOpenReportTab}
        className="flex items-center justify-between p-2 rounded-lg bg-panel hover:bg-raised border border-line text-left cursor-pointer"
      >
        <div className="truncate pr-1">
          <div className="text-[11px] tracking-wide text-muted font-semibold">
            AST Language Coverage
          </div>
          <div className="text-xs font-semibold text-ink mt-0.5 truncate" data-testid="summary-ast-coverage">
            {tr.ast_loc_coverage_pct !== undefined
              ? `${tr.ast_loc_coverage_pct.toFixed(1)}% LOC (${(tr.ast_file_coverage_pct ?? 0).toFixed(1)}% files) AST`
              : `${tr.supported_languages_detected.length} AST supported`}
            {(tr.partial_static_files_count ?? 0) > 0 && (
              <>
                {' '}&bull;{' '}
                <span className="text-warning">
                  {tr.partial_static_files_count} partial_static
                </span>
              </>
            )}
            {' '}&bull;{' '}
            <span className={tr.unsupported_files_count > 0 ? 'text-warning' : 'text-muted'}>
              {tr.unsupported_files_count} unsupported
            </span>
          </div>
        </div>
        {tr.unsupported_files_count > 0 || (tr.partial_static_files_count ?? 0) > 0 ? (
          <AlertTriangle className="w-4 h-4 text-warning shrink-0" aria-hidden="true" />
        ) : (
          <Layers className="w-4 h-4 text-success shrink-0" aria-hidden="true" />
        )}
      </button>

      {/* Git Insights & Churn */}
      <div className="flex items-center justify-between p-2 rounded-lg bg-panel border border-line">
        <div>
          <div className="text-[11px] tracking-wide text-muted font-semibold">
            Git History &amp; Hotspots
          </div>
          <div className="text-xs font-semibold text-ink mt-0.5 flex items-center gap-1.5">
            {result.git_insights.is_git_repo ? (
              <>
                <GitCommitHorizontal className="w-3.5 h-3.5 text-accent" aria-hidden="true" />
                <span>{result.git_insights.total_commits_scanned} commits</span>
                <span>&bull;</span>
                <span className="text-warning">{result.git_insights.hotspots.length} hotspots</span>
              </>
            ) : (
              <span className="text-muted">Non-Git Folder</span>
            )}
          </div>
        </div>
        <Flame className="w-4 h-4 text-warning shrink-0" aria-hidden="true" />
      </div>
    </section>
  );
};
