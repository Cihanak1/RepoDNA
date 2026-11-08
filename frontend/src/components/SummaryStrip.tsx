import React from 'react';
import { useTranslation } from 'react-i18next';
import {
  ArrowRight,
  CheckCircle2,
  FileStack,
  GitCommitHorizontal,
  Layers,
  Network,
  RefreshCcw,
  Sparkles,
} from 'lucide-react';
import type { AnalysisResult } from '../types/repodna';
import type { WorkstationMode } from '../utils/preferences';

interface SummaryStripProps {
  result: AnalysisResult;
  cyclesOnly: boolean;
  onToggleCyclesOnly: () => void;
  onOpenReportTab: () => void;
  isPreviousAnalysis?: boolean;
  workstationMode?: WorkstationMode;
}

export const SummaryStrip: React.FC<SummaryStripProps> = ({
  result,
  cyclesOnly,
  onToggleCyclesOnly,
  onOpenReportTab,
  isPreviousAnalysis = false,
  workstationMode = 'simple',
}) => {
  const { t } = useTranslation();
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

  const isLowCoverage = hr.status === 'insufficient_dependency_coverage';
  const hasCycles = result.cycles.length > 0;
  const topFinding = hr.findings[0];

  const recommendationText = isLowCoverage
    ? t('summary.actionLowCoverage')
    : hasCycles
    ? t('summary.actionCycle')
    : topFinding
    ? topFinding.remediation
    : t('summary.actionClean');

  return (
    <section
      aria-label="Repository analysis summary metrics"
      className="summary-strip text-xs"
      data-mode={workstationMode}
    >
      {/* 1. Architecture Health Score */}
      <button
        type="button"
        onClick={onOpenReportTab}
        className="flex items-center justify-between p-2 rounded-lg bg-panel hover:bg-raised border border-line text-left cursor-pointer transition"
      >
        <div>
          <div className="text-[11px] tracking-wide text-muted font-semibold flex items-center gap-1.5">
            <span>{t('summary.architectureHealth')}</span>
            {isPreviousAnalysis && (
              <span
                data-testid="previous-analysis-badge"
                className="px-1.5 py-0.5 rounded bg-warning/20 border border-warning/40 text-warning text-[11px] font-bold uppercase"
              >
                {t('summary.previousAnalysis')}
              </span>
            )}
          </div>
          <div className="text-base font-bold text-ink mt-0.5 flex items-baseline gap-1.5">
            {hr.overall_score !== null ? (
              <>
                <span data-testid="summary-health-score">{hr.overall_score.toFixed(1)}</span>
                <span className="text-[11px] font-normal text-muted">/ 100</span>
              </>
            ) : isLowCoverage ? (
              <span data-testid="summary-health-score" className="text-xs text-warning font-semibold">
                {t('common.insufficientCoverage')}
              </span>
            ) : (
              <span data-testid="summary-health-score" className="text-sm text-muted">
                N/A ({t('common.notEvaluated')})
              </span>
            )}
          </div>
          {hr.confidence && hr.confidence !== 'none' && (
            <div className="text-[11px] text-muted mt-0.5">
              {t('report.confidenceLabel')}{' '}
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

      {/* 2. Files & Code Volume */}
      <div className="flex items-center justify-between p-2 rounded-lg bg-panel border border-line">
        <div>
          <div className="text-[11px] tracking-wide text-muted font-semibold">
            {t('summary.codeVolume')}
          </div>
          <div className="text-sm font-bold text-ink mt-0.5">
            <span data-testid="summary-total-files">{result.total_files.toLocaleString()}</span> {t('summary.files')} &bull;{' '}
            <span className="text-accent">{result.total_lines_code.toLocaleString()}</span> LOC
          </div>
        </div>
        <FileStack className="w-4 h-4 text-accent shrink-0" aria-hidden="true" />
      </div>

      {/* In Simple Mode: Key Finding & Cycles */}
      {workstationMode === 'simple' && (
        <button
          type="button"
          onClick={onToggleCyclesOnly}
          className={`flex items-center justify-between p-2 rounded-lg border text-left cursor-pointer transition ${
            cyclesOnly
              ? 'bg-accent/15 border-accent text-accent'
              : 'bg-panel hover:bg-raised border-line text-ink'
          }`}
        >
          <div className="min-w-0 pr-1">
            <div className="text-[11px] tracking-wide text-muted font-semibold flex items-center gap-1">
              <span>{t('summary.circularDeps')}</span>
              {cyclesOnly && (
                <span className="text-[10px] text-accent font-bold uppercase">
                  ({t('common.active')})
                </span>
              )}
            </div>
            <div className="text-sm font-bold mt-0.5 truncate">
              {isLowCoverage ? (
                <span data-testid="summary-cycle-count" className="text-warning text-xs font-semibold">
                  {t('summary.notEvaluatedLowAst')}
                </span>
              ) : hasCycles ? (
                <span data-testid="summary-cycle-count" className="text-danger font-mono">
                  {t('summary.cyclesBreakdown', {
                    cycles: result.cycles.length,
                    sccs: gm.scc_count,
                    modules: gm.nodes_in_cycles,
                  })}
                </span>
              ) : (
                <span data-testid="summary-cycle-count" className="text-success text-xs font-semibold flex items-center gap-1">
                  <CheckCircle2 className="w-3.5 h-3.5 text-success" />
                  {t('summary.acyclicZero')}
                </span>
              )}
            </div>
          </div>
          <RefreshCcw
            className={`w-4 h-4 shrink-0 ${
              hasCycles ? 'text-danger' : 'text-success'
            } ${cyclesOnly ? 'rotate-180 transition-transform' : ''}`}
            aria-hidden="true"
          />
        </button>
      )}

      {/* In Simple Mode: Recommended Next Action */}
      {workstationMode === 'simple' && (
        <div className="hidden lg:flex items-center justify-between p-2 rounded-lg bg-panel border border-line">
          <div className="min-w-0 pr-2">
            <div className="text-[11px] tracking-wide text-accent font-semibold flex items-center gap-1">
              <Sparkles className="w-3 h-3 text-accent" />
              <span>{t('summary.recommendedAction')}</span>
            </div>
            <p className="text-xs text-muted mt-0.5 truncate leading-snug" title={recommendationText}>
              {recommendationText}
            </p>
          </div>
          <ArrowRight className="w-3.5 h-3.5 text-muted shrink-0" aria-hidden="true" />
        </div>
      )}

      {/* In Advanced Mode: Full 4 Additional Technical Metrics */}
      {workstationMode === 'advanced' && (
        <>
          {/* Module Topology */}
          <div className="flex items-center justify-between p-2 rounded-lg bg-panel border border-line">
            <div>
              <div className="text-[11px] tracking-wide text-muted font-semibold">
                {t('summary.moduleTopology')}
              </div>
              <div className="text-sm font-bold text-ink mt-0.5 font-mono">
                {gm.total_edges} <span className="font-sans font-normal text-xs text-muted">{t('summary.edges')}</span> &bull;{' '}
                <span className="text-accent">I={gm.average_instability.toFixed(2)}</span>
              </div>
            </div>
            <Network className="w-4 h-4 text-muted shrink-0" aria-hidden="true" />
          </div>

          {/* Circular Dependencies */}
          <button
            type="button"
            onClick={onToggleCyclesOnly}
            className={`flex items-center justify-between p-2 rounded-lg border text-left cursor-pointer transition ${
              cyclesOnly
                ? 'bg-accent/15 border-accent text-accent'
                : 'bg-panel hover:bg-raised border-line text-ink'
            }`}
          >
            <div>
              <div className="text-[11px] tracking-wide text-muted font-semibold flex items-center gap-1">
                <span>{t('summary.circularDeps')}</span>
                {cyclesOnly && (
                  <span className="text-[10px] text-accent font-bold uppercase">
                    ({t('common.active')})
                  </span>
                )}
              </div>
              <div className="text-sm font-bold mt-0.5 font-mono">
                {isLowCoverage ? (
                  <span data-testid="summary-cycle-count" className="text-warning text-xs font-sans font-semibold">
                    {t('summary.notEvaluatedLowAst')}
                  </span>
                ) : result.cycles.length > 0 ? (
                  <span data-testid="summary-cycle-count" className="text-danger">
                    {t('summary.cyclesBreakdown', {
                      cycles: result.cycles.length,
                      sccs: gm.scc_count,
                      modules: gm.nodes_in_cycles,
                    })}
                  </span>
                ) : (
                  <span data-testid="summary-cycle-count" className="text-success text-xs font-sans font-semibold">
                    {t('summary.acyclicZero')}
                  </span>
                )}
              </div>
            </div>
            <RefreshCcw
              className={`w-4 h-4 shrink-0 ${
                result.cycles.length > 0 ? 'text-danger' : 'text-success'
              } ${cyclesOnly ? 'rotate-180 transition-transform' : ''}`}
              aria-hidden="true"
            />
          </button>

          {/* AST Language Coverage */}
          <div data-testid="summary-ast-coverage" className="flex items-center justify-between p-2 rounded-lg bg-panel border border-line">
            <div>
              <div className="text-[11px] tracking-wide text-muted font-semibold">
                {t('summary.astCoverage')}
              </div>
              <div className="text-xs font-bold text-ink mt-0.5">
                <span className="text-accent">{(tr.ast_loc_coverage_pct ?? 0).toFixed(1)}% LOC</span>{' '}
                <span className="text-muted font-normal">
                  ({(tr.ast_file_coverage_pct ?? 0).toFixed(1)}% {t('summary.files')}) AST
                </span>
                {tr.unsupported_files_count > 0 && (
                  <span className="text-warning ml-1">
                    &bull; {tr.unsupported_files_count} {t('summary.unsupported')}
                  </span>
                )}
              </div>
            </div>
            <Layers className="w-4 h-4 text-muted shrink-0" aria-hidden="true" />
          </div>

          {/* Git History & Hotspots */}
          <div data-testid="summary-git-hotspots" className="flex items-center justify-between p-2 rounded-lg bg-panel border border-line">
            <div>
              <div className="text-[11px] tracking-wide text-muted font-semibold">
                {t('summary.gitHotspots')}
              </div>
              <div className="text-xs font-bold text-ink mt-0.5 font-mono">
                {result.git_insights.is_git_repo ? (
                  <>
                    <span>{result.git_insights.total_commits_scanned} {t('summary.commits')}</span> &bull;{' '}
                    <span className="text-warning">{result.git_insights.hotspots.length} {t('summary.hotspots')}</span>
                  </>
                ) : (
                  <span className="text-muted font-sans font-normal">{t('summary.gitNotAvailable')}</span>
                )}
              </div>
            </div>
            <GitCommitHorizontal className="w-4 h-4 text-muted shrink-0" aria-hidden="true" />
          </div>
        </>
      )}
    </section>
  );
};
