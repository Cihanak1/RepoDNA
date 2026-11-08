import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  AlertTriangle,
  CheckCircle2,
  Layers,
  RefreshCcw,
  ShieldCheck,
  Sparkles,
} from 'lucide-react';
import type { AnalysisResult } from '../types/repodna';
import type { WorkstationMode } from '../utils/preferences';

interface HealthReportViewProps {
  result: AnalysisResult;
  onSelectFileInStudio: (fileId: string) => void;
  workstationMode?: WorkstationMode;
}

export const HealthReportView: React.FC<HealthReportViewProps> = ({
  result,
  onSelectFileInStudio,
}) => {
  const { t } = useTranslation();
  const [activeReportTab, setActiveReportTab] = useState<'summary' | 'evidence'>('summary');
  const hr = result.health_report;
  const tr = result.transparency;

  const isLowCoverage = hr.status === 'insufficient_dependency_coverage';

  return (
    <div
      data-testid="health-report-view"
      className="report-document flex-1 overflow-y-auto p-4 lg:p-6 space-y-6 mx-auto w-full"
    >
      {/* Top Architecture Health Rubric Banner */}
      <section
        aria-labelledby="rubric-heading"
        className="bg-panel border border-line rounded-lg p-5 flex flex-col lg:flex-row items-start lg:items-center justify-between gap-6"
      >
        <div className="space-y-2 max-w-3xl">
          <div className="flex items-center gap-2">
            <ShieldCheck className="w-5 h-5 text-accent" aria-hidden="true" />
            <h2 id="rubric-heading" className="text-lg font-bold m-0 text-ink">
              {t('report.title')}
            </h2>
          </div>
          <p className="text-xs text-muted m-0 leading-relaxed">{hr.methodology}</p>

          {isLowCoverage && (
            <div className="p-3 rounded-md bg-warning/15 border border-warning/40 text-xs text-warning leading-relaxed space-y-2">
              <div>
                <strong className="block text-ink font-semibold mb-0.5">{t('report.lowCoverageTitle')}</strong>
                {t('report.lowCoverageExplanation')}
              </div>
              {(hr.unverified_rules?.length ?? 0) > 0 && (
                <div data-testid="unverified-rules-box" className="pt-2 border-t border-warning/30">
                  <span className="font-semibold text-warning block mb-1">
                    Unverified / Not Evaluated Rules ({hr.unverified_rules!.length}):
                  </span>
                  <ul role="list" className="m-0 pl-4 space-y-0.5 text-ink font-mono text-[11px]">
                    {hr.unverified_rules!.map((ur) => (
                      <li key={ur}>{ur}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}

          {hr.confidence && (
            <div className="flex flex-wrap items-center gap-2 text-xs pt-1" data-testid="health-confidence-banner">
              <span
                className={`px-2 py-0.5 rounded font-bold uppercase border text-[11px] ${
                  hr.confidence === 'high'
                    ? 'bg-success/20 text-success border-success/40'
                    : hr.confidence === 'medium'
                    ? 'bg-accent/20 text-accent border-accent/40'
                    : 'bg-warning/20 text-warning border-warning/40'
                }`}
              >
                {t('report.confidenceLabel')} {hr.confidence}
              </span>
              <span className="text-muted">
                {t('report.fullAstCoverage')}{' '}
                <strong>
                  {(hr.ast_loc_coverage_pct ?? tr.ast_loc_coverage_pct ?? 0).toFixed(1)}% {t('report.ofLoc')}
                </strong>{' '}
                ({(hr.ast_file_coverage_pct ?? tr.ast_file_coverage_pct ?? 0).toFixed(1)}% {t('report.ofFiles')})
              </span>
              {hr.confidence_reason && (
                <span className="text-muted">&bull; {hr.confidence_reason}</span>
              )}
            </div>
          )}
        </div>

        <div className="flex items-center gap-4 bg-canvas border border-line rounded-md px-5 py-3 shrink-0">
          <div>
            <div className="text-[11px] tracking-wide text-muted font-semibold">
              {t('report.overallScore')}
            </div>
            <div className="text-3xl font-extrabold text-accent font-mono">
              {hr.overall_score !== null ? (
                <>
                  {hr.overall_score.toFixed(1)}
                  <span className="text-sm text-muted font-normal"> / 100</span>
                </>
              ) : isLowCoverage ? (
                <span className="text-base text-warning font-sans font-bold" data-testid="report-overall-score-status">
                  Not Evaluated — Insufficient Dependency Coverage
                </span>
              ) : (
                <span className="text-xl text-muted" data-testid="report-overall-score-status">
                  N/A (Insufficient Data)
                </span>
              )}
            </div>
          </div>
          <div className="w-12 h-12 rounded-md bg-accent/15 border border-accent/40 flex items-center justify-center text-2xl font-black text-accent">
            {hr.grade}
          </div>
        </div>
      </section>

      {/* Report Level Tabs (Summary vs Detailed Evidence) */}
      <div className="flex items-center justify-between border-b border-line pb-2">
        <div role="tablist" aria-label="Report views" className="flex items-center bg-panel p-1 rounded-lg border border-line gap-1">
          <button
            type="button"
            role="tab"
            data-testid="report-tier-summary-btn"
            aria-selected={activeReportTab === 'summary'}
            onClick={() => setActiveReportTab('summary')}
            className={`px-3 py-1 rounded-md text-xs font-semibold cursor-pointer transition ${
              activeReportTab === 'summary'
                ? 'bg-accent-solid text-white shadow-sm'
                : 'text-muted hover:text-ink'
            }`}
          >
            {t('report.summaryTab')}
          </button>
          <button
            type="button"
            role="tab"
            data-testid="report-tier-evidence-btn"
            aria-selected={activeReportTab === 'evidence'}
            onClick={() => setActiveReportTab('evidence')}
            className={`px-3 py-1 rounded-md text-xs font-semibold cursor-pointer transition ${
              activeReportTab === 'evidence'
                ? 'bg-accent-solid text-white shadow-sm'
                : 'text-muted hover:text-ink'
            }`}
          >
            {t('report.evidenceTab')}
          </button>
        </div>
      </div>

      {/* Category Score Breakdown */}
      <section aria-labelledby="categories-heading" className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
        <h2 id="categories-heading" className="visually-hidden">
          Architecture Health Categories
        </h2>
        {hr.category_scores.map((cat) => (
          <div
            key={cat.category}
            className="bg-panel border border-line rounded-md p-3.5 flex flex-col justify-between gap-2"
          >
            <div>
              <div className="text-[11px] font-semibold text-muted">{cat.label}</div>
              <div className="text-[11px] text-muted">
                {t('report.weight')} {cat.weight} {t('report.pts')} &bull;{' '}
                {cat.status === 'not_evaluated'
                  ? t('common.notEvaluated')
                  : `${t('report.deductionLabel')} -${cat.deductions.toFixed(1)}`}
              </div>
            </div>
            <div className="flex items-baseline justify-between mt-1">
              <span className="text-lg font-bold font-mono text-ink">
                {cat.score !== null
                  ? `${cat.score.toFixed(0)}%`
                  : cat.status === 'not_evaluated'
                  ? t('common.notEvaluated')
                  : 'N/A'}
              </span>
              <span className="text-[11px] text-muted">
                {cat.status === 'not_evaluated'
                  ? 'low AST coverage'
                  : `${cat.findings_count} issue${cat.findings_count === 1 ? '' : 's'}`}
              </span>
            </div>
            <div className="w-full h-1.5 rounded-full bg-canvas overflow-hidden mt-1">
              {cat.score !== null ? (
                <div
                  className={`h-full rounded-full ${
                    cat.score >= 80 ? 'bg-success' : cat.score >= 60 ? 'bg-accent' : 'bg-danger'
                  }`}
                  style={{ width: `${Math.max(0, Math.min(100, cat.score))}%` }}
                />
              ) : (
                <div className="h-full bg-line" style={{ width: '100%' }} />
              )}
            </div>
          </div>
        ))}
      </section>

      {/* Summary View Content */}
      {activeReportTab === 'summary' && (
        <section aria-label="Key architectural findings" className="space-y-4">
          <h3 className="text-sm font-bold text-ink m-0 flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-accent" />
            Key Findings &amp; Remediation Plan
          </h3>

          {hr.findings.length === 0 ? (
            <div className="p-5 rounded-lg bg-success/10 border border-success/30 text-success text-xs font-medium flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-success" />
              {t('report.noFindings')}
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-3">
              {hr.findings.map((fn) => (
                <div
                  key={fn.rule_id}
                  data-testid={`rule-card-${fn.rule_id}`}
                  className={`p-4 rounded-lg border ${
                    fn.severity === 'critical'
                      ? 'bg-danger/10 border-danger/40'
                      : 'bg-warning/10 border-warning/40'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs font-bold text-ink">{fn.rule_id}</span>
                      <span className="text-xs font-bold text-ink">{fn.title}</span>
                    </div>
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase font-mono border ${
                        fn.severity === 'critical'
                          ? 'bg-danger/20 text-danger border-danger/40'
                          : 'bg-warning/20 text-warning border-warning/40'
                      }`}
                    >
                      {fn.severity} (-{fn.score_deduction.toFixed(1)} pts)
                    </span>
                  </div>

                  <p className="mt-2 text-xs text-ink leading-relaxed font-normal m-0">
                    <strong>Remediation:</strong> {fn.remediation}
                  </p>

                  <div className="mt-2.5 pt-2 border-t border-line/40 flex flex-wrap items-center gap-2 text-[11px] text-muted">
                    <span>Affected modules:</span>
                    {fn.affected_files.slice(0, 4).map((f) => (
                      <button
                        key={f}
                        type="button"
                        onClick={() => onSelectFileInStudio(f)}
                        className="font-mono text-accent hover:underline cursor-pointer"
                      >
                        {f}
                      </button>
                    ))}
                    {fn.affected_files.length > 4 && (
                      <span>+{fn.affected_files.length - 4} more</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      )}

      {/* Detailed Evidence View Content */}
      {activeReportTab === 'evidence' && (
        <section aria-labelledby="rules-report-heading" className="space-y-4">
          <h3 id="rules-report-heading" className="text-sm font-bold text-ink m-0">
            Rule Evaluations &amp; Mathematical Deductions ({hr.findings.length} Triggered, {hr.passed_rules.length} Passed)
          </h3>

          <div tabIndex={0} role="region" aria-labelledby="rules-report-heading" className="table-wrapper">
            <table
              style={
                {
                  '--label-2': '"Severity"',
                  '--label-3': '"Deduction"',
                  '--label-4': '"Formula & Evidence"',
                  '--label-5': '"Remediation"',
                } as React.CSSProperties
              }
            >
              <caption className="visually-hidden">
                Detailed architecture health rule findings, mathematical formulas, and remediation guidance
              </caption>
              <thead>
                <tr className="text-xs text-muted">
                  <th scope="col" className="p-3 text-left">{t('report.ruleCol')}</th>
                  <th scope="col" className="p-3 text-left">{t('report.severityCol')}</th>
                  <th scope="col" className="p-3 text-left">{t('report.deductionCol')}</th>
                  <th scope="col" className="p-3 text-left">{t('report.evidenceCol')}</th>
                  <th scope="col" className="p-3 text-left">{t('report.remediationCol')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line text-xs">
                {hr.findings.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="p-6 text-center text-success font-medium">
                      {hr.dependency_graph_evaluated === false
                        ? 'No findings from evaluated rules. Dependency rules remain unverified because AST coverage is insufficient.'
                        : 'No findings in the evaluated rules. See coverage and unverified rules below.'}
                    </td>
                  </tr>
                ) : (
                  hr.findings.map((fn) => (
                    <tr key={fn.rule_id} data-testid={`rule-card-${fn.rule_id}`} className="hover:bg-panel">
                      <th scope="row" className="p-3 text-left align-top font-semibold text-ink">
                        <div className="font-mono text-accent">{fn.rule_id}</div>
                        <div>{fn.title}</div>
                      </th>
                      <td className="p-3 align-top">
                        <span
                          className={`px-2 py-0.5 rounded-full text-[11px] font-bold uppercase border ${
                            fn.severity === 'critical'
                              ? 'bg-danger/20 text-danger border-danger/40'
                              : fn.severity === 'warning'
                              ? 'bg-warning/20 text-warning border-warning/40'
                              : 'bg-accent/20 text-accent border-accent/40'
                          }`}
                        >
                          {fn.severity}
                        </span>
                      </td>
                      <td className="p-3 align-top font-mono font-bold text-danger">
                        -{fn.score_deduction.toFixed(1)} <span className="text-muted font-normal">/ -{fn.max_deduction}</span>
                      </td>
                      <td className="p-3 align-top space-y-1.5">
                        <div className="text-[11px] font-mono text-muted bg-canvas px-2 py-1 rounded border border-line">
                          {fn.formula_explanation}
                        </div>
                        <div className="text-[11px] text-muted">
                          <strong>Threshold:</strong> {fn.threshold_description}
                        </div>
                        <ul role="list" className="m-0 pl-4 space-y-0.5 text-[11px] font-mono text-muted">
                          {fn.evidence.slice(0, 5).map((ev, i) => (
                            <li key={i}>{ev}</li>
                          ))}
                        </ul>
                      </td>
                      <td className="p-3 align-top text-muted leading-relaxed max-w-xs">
                        {fn.remediation}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          {/* Passed Rules Box */}
          {hr.passed_rules.length > 0 && (
            <div className="bg-success/10 border border-success/40 rounded-md p-3.5 text-xs">
              <div className="font-semibold text-success mb-1.5 flex items-center gap-1.5">
                <CheckCircle2 className="w-4 h-4 text-success" aria-hidden="true" />
                {t('report.passedRulesHeading')} ({hr.passed_rules.length})
              </div>
              <ul role="list" className="m-0 pl-5 space-y-1 text-muted">
                {hr.passed_rules.map((pr) => (
                  <li key={pr}>{pr}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Unverified / Not Evaluated Rules Box */}
          {(hr.unverified_rules?.length ?? 0) > 0 && (
            <div
              data-testid="unverified-rules-box"
              className="bg-warning/10 border border-warning/40 rounded-md p-3.5 text-xs"
            >
              <div className="font-semibold text-warning mb-1.5 flex items-center gap-1.5">
                <AlertTriangle className="w-4 h-4 text-warning" aria-hidden="true" />
                Unverified / Not Evaluated Rules ({hr.unverified_rules!.length})
              </div>
              <ul role="list" className="m-0 pl-5 space-y-1 text-muted">
                {hr.unverified_rules!.map((ur) => (
                  <li key={ur}>{ur}</li>
                ))}
              </ul>
            </div>
          )}
        </section>
      )}

      {/* Circular Dependency Chains Section (Always Accessible) */}
      <section aria-labelledby="cycles-report-heading" className="space-y-3">
        <h3
          id="cycles-report-heading"
          className="text-sm font-bold tracking-wide text-ink m-0 flex items-center gap-1.5"
        >
          <RefreshCcw className="w-4 h-4 text-danger" aria-hidden="true" />
          Circular Dependency Chains ({result.cycles.length} Cycles in {result.graph_metrics.scc_count} Cyclic SCCs)
        </h3>

        {result.graph_metrics.cycles_truncated && (
          <div className="bg-warning/10 border border-warning/40 rounded-md p-3 text-xs text-warning flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-warning shrink-0" aria-hidden="true" />
            <span>
              <strong>Cycle Enumeration Truncated:</strong>{' '}
              {result.graph_metrics.cycle_truncation_reason ||
                'Reached cycle reporting cap or Johnson operation budget.'}
            </span>
          </div>
        )}

        <div tabIndex={0} role="region" aria-labelledby="cycles-report-heading" className="table-wrapper">
          <table
            style={
              {
                '--label-2': '"Hops"',
                '--label-3': '"Severity"',
                '--label-4': '"Cycle Chain"',
              } as React.CSSProperties
            }
          >
            <caption className="visually-hidden">Detected circular dependency paths</caption>
            <thead>
              <tr className="text-xs text-muted">
                <th scope="col" className="p-3 text-left">Cycle ID</th>
                <th scope="col" className="p-3 text-left">Length</th>
                <th scope="col" className="p-3 text-left">Severity</th>
                <th scope="col" className="p-3 text-left">Cycle Module Path (Click to Inspect in Studio)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line text-xs">
              {result.cycles.length === 0 ? (
                <tr>
                  <td
                    colSpan={4}
                    data-testid="cycle-analysis-summary-cell"
                    className={`p-5 text-center ${
                      hr.dependency_graph_evaluated === false ? 'text-warning' : 'text-success'
                    }`}
                  >
                    {hr.cycle_analysis_summary ||
                      'No cycles detected in analyzed graph (Acyclic Dependencies Principle satisfied in analyzed modules)'}
                  </td>
                </tr>
              ) : (
                result.cycles.map((cyc) => (
                  <tr key={cyc.id} className="hover:bg-panel">
                    <th scope="row" className="p-3 text-left font-mono text-danger">
                      {cyc.id}
                    </th>
                    <td className="p-3 font-mono">{cyc.length} hops</td>
                    <td className="p-3 uppercase font-bold text-danger text-[11px]">{cyc.severity}</td>
                    <td className="p-3 font-mono">
                      <div className="flex flex-wrap items-center gap-1.5">
                        {cyc.nodes.map((nodeId, idx) => (
                          <React.Fragment key={`${cyc.id}-${idx}`}>
                            <button
                              type="button"
                              onClick={() => onSelectFileInStudio(nodeId)}
                              className="px-2 py-0.5 rounded bg-panel hover:bg-accent/10 border border-line text-accent cursor-pointer"
                            >
                              {nodeId}
                            </button>
                            {idx < cyc.nodes.length - 1 && <span className="text-danger">&rarr;</span>}
                          </React.Fragment>
                        ))}
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      {/* Language Distribution & Parser Transparency */}
      <section aria-labelledby="transparency-report-heading" className="space-y-3">
        <h3
          id="transparency-report-heading"
          className="text-sm font-bold tracking-wide text-ink m-0 flex items-center gap-1.5"
        >
          <Layers className="w-4 h-4 text-accent" aria-hidden="true" />
          Language Distribution &amp; Parser Transparency
        </h3>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3 text-xs">
          <div className="bg-panel border border-line rounded-md p-3">
            <div className="text-muted font-semibold uppercase text-[10px]">
              Supported AST Languages (full_ast)
            </div>
            <div className="text-ink font-medium mt-1" data-testid="supported-ast-languages-list">
              {tr.supported_languages_detected.join(', ') || 'None'}
            </div>
          </div>

          <div className="bg-panel border border-line rounded-md p-3">
            <div className="text-warning font-semibold uppercase text-[10px] flex items-center gap-1">
              <AlertTriangle className="w-3.5 h-3.5 text-warning" aria-hidden="true" />
              Partial Static Languages (partial_static)
            </div>
            <div className="text-ink font-medium mt-1" data-testid="partial-static-languages-list">
              {(tr.partial_static_languages_detected?.length ?? 0) > 0
                ? `${tr.partial_static_languages_detected!.join(', ')} (${tr.partial_static_files_count ?? 0} files — static using/include scan only; no AST symbol or namespace-to-file graph resolution)`
                : 'None'}
            </div>
          </div>

          <div className="bg-panel border border-line rounded-md p-3">
            <div className="text-warning font-semibold uppercase text-[10px] flex items-center gap-1">
              <AlertTriangle className="w-3.5 h-3.5 text-warning" aria-hidden="true" />
              Unsupported Languages (unsupported)
            </div>
            <div className="text-ink font-medium mt-1" data-testid="unsupported-languages-list">
              {tr.unsupported_languages_detected.length > 0
                ? `${tr.unsupported_languages_detected.join(', ')} (${tr.unsupported_files_count} files)`
                : (tr.partial_static_languages_detected?.length ?? 0) > 0
                ? 'None (remaining files use partial_static header/using scanning)'
                : 'None — 100% of detected languages have AST import support'}
            </div>
          </div>

          <div className="bg-panel border border-line rounded-md p-3">
            <div className="text-muted font-semibold uppercase text-[10px]">
              Parser Coverage Ratio
            </div>
            <div className="text-ink font-medium mt-1">
              {(tr.ast_loc_coverage_pct ?? 0).toFixed(1)}% LOC ({tr.ast_file_coverage_pct?.toFixed(1) ?? 0}% files)
            </div>
          </div>
        </div>
      </section>
    </div>
  );
};
