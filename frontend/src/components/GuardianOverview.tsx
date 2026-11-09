import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  GitBranch,
  HelpCircle,
  Play,
  RotateCcw,
  ShieldAlert,
  ShieldCheck,
  TrendingDown,
  TrendingUp,
  XCircle,
} from 'lucide-react';
import { assessPRGuardian } from '../api/client';
import type { AnalysisResult, ContractMode, GuardianReport, GuardianVerdict } from '../types/repodna';
import type { WorkstationMode } from '../utils/preferences';

interface GuardianOverviewProps {
  result: AnalysisResult | null;
  defaultWorkspacePath: string;
  workstationMode?: WorkstationMode;
}

export const GuardianOverview: React.FC<GuardianOverviewProps> = ({
  result,
  defaultWorkspacePath,
  workstationMode = 'simple',
}) => {
  const { t } = useTranslation();
  const [baseRef, setBaseRef] = useState<string>('HEAD~1');
  const [headRef, setHeadRef] = useState<string>('HEAD');
  const [mode, setMode] = useState<ContractMode>('enforce');
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [report, setReport] = useState<GuardianReport | null>(null);

  const targetPath = result?.target_display || defaultWorkspacePath || '.';

  const handleRunAssessment = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    setLoading(true);
    setErrorMsg(null);
    try {
      const rep = await assessPRGuardian({
        target: targetPath,
        base_ref: baseRef.trim() || 'HEAD~1',
        head_ref: headRef.trim() || 'HEAD',
        mode,
      });
      setReport(rep);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setErrorMsg(msg);
    } finally {
      setLoading(false);
    }
  };

  const renderVerdictBadge = (verdict: GuardianVerdict) => {
    switch (verdict) {
      case 'PASS':
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30">
            <CheckCircle2 className="w-4 h-4" aria-hidden="true" />
            {t('guardian.verdictPass', 'PASS — ARCHITECTURE CLEAN')}
          </span>
        );
      case 'WARNING':
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-amber-500/15 text-amber-600 dark:text-amber-400 border border-amber-500/30">
            <AlertTriangle className="w-4 h-4" aria-hidden="true" />
            {t('guardian.verdictWarning', 'WARNING — ADVISORY ISSUES')}
          </span>
        );
      case 'FAIL':
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-red-500/15 text-red-600 dark:text-red-400 border border-red-500/30">
            <XCircle className="w-4 h-4" aria-hidden="true" />
            {t('guardian.verdictFail', 'FAIL — POLICY VIOLATED')}
          </span>
        );
      case 'INCONCLUSIVE':
      default:
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-purple-500/15 text-purple-600 dark:text-purple-400 border border-purple-500/30">
            <HelpCircle className="w-4 h-4" aria-hidden="true" />
            {t('guardian.verdictInconclusive', 'INCONCLUSIVE — LOW COVERAGE')}
          </span>
        );
    }
  };

  return (
    <div className="h-full flex flex-col overflow-y-auto bg-canvas text-ink p-4 sm:p-6 space-y-6">
      {/* Header Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-line">
        <div>
          <div className="flex items-center gap-2">
            <ShieldAlert className="w-5 h-5 text-accent" aria-hidden="true" />
            <h1 className="text-lg font-bold tracking-tight">
              {t('guardian.title', 'PR Architecture Guardian')}
            </h1>
          </div>
          <p className="text-xs text-muted mt-1">
            {t('guardian.subtitle', 'Continuous regression gate detecting new circular dependencies, policy violations, and coupling spikes.')}
          </p>
        </div>

        {/* Form Controls */}
        <form onSubmit={handleRunAssessment} className="flex flex-wrap items-center gap-2">
          <div className="flex items-center bg-panel border border-line rounded-lg px-2.5 py-1 text-xs gap-1.5">
            <GitBranch className="w-3.5 h-3.5 text-muted" aria-hidden="true" />
            <span className="text-muted">{t('guardian.baseLabel', 'Base')}:</span>
            <input
              type="text"
              value={baseRef}
              onChange={(e) => setBaseRef(e.target.value)}
              placeholder="origin/main"
              className="bg-transparent text-ink font-mono focus:outline-none w-24 sm:w-28"
            />
          </div>

          <ArrowRight className="w-3.5 h-3.5 text-muted hidden sm:inline" aria-hidden="true" />

          <div className="flex items-center bg-panel border border-line rounded-lg px-2.5 py-1 text-xs gap-1.5">
            <span className="text-muted">{t('guardian.headLabel', 'Head')}:</span>
            <input
              type="text"
              value={headRef}
              onChange={(e) => setHeadRef(e.target.value)}
              placeholder="HEAD"
              className="bg-transparent text-ink font-mono focus:outline-none w-20 sm:w-24"
            />
          </div>

          <div className="flex items-center bg-panel border border-line rounded-lg p-0.5 text-xs">
            <button
              type="button"
              onClick={() => setMode('advisory')}
              className={`px-2 py-0.5 rounded text-[11px] font-medium transition cursor-pointer ${
                mode === 'advisory' ? 'bg-accent-solid text-white shadow-xs' : 'text-muted hover:text-ink'
              }`}
            >
              {t('guardian.advisoryMode', 'Advisory')}
            </button>
            <button
              type="button"
              onClick={() => setMode('enforce')}
              className={`px-2 py-0.5 rounded text-[11px] font-medium transition cursor-pointer ${
                mode === 'enforce' ? 'bg-accent-solid text-white shadow-xs' : 'text-muted hover:text-ink'
              }`}
            >
              {t('guardian.enforceMode', 'Enforce')}
            </button>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="px-3 py-1.5 rounded-lg bg-accent-solid text-white text-xs font-medium flex items-center gap-1.5 cursor-pointer hover:opacity-90 disabled:opacity-50 transition shadow-xs"
          >
            {loading ? <RotateCcw className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5" />}
            {loading ? t('guardian.analyzing', 'Evaluating…') : t('guardian.runCheck', 'Assess PR')}
          </button>
        </form>
      </div>

      {errorMsg && (
        <div className="p-3 bg-red-500/10 border border-red-500/20 text-red-600 dark:text-red-400 rounded-lg text-xs flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 shrink-0" aria-hidden="true" />
          <span>{errorMsg}</span>
        </div>
      )}

      {!report && !loading && (
        <div className="p-8 text-center bg-panel border border-line rounded-xl space-y-3">
          <ShieldCheck className="w-10 h-10 text-muted mx-auto" aria-hidden="true" />
          <h2 className="text-sm font-semibold">{t('guardian.noReportTitle', 'Evaluate Pull Request Architecture')}</h2>
          <p className="text-xs text-muted max-w-md mx-auto">
            {t(
              'guardian.noReportDesc',
              'Specify base and head Git revisions (e.g. main vs HEAD) to inspect circular dependency regressions, contract policy violations, and risk score.'
            )}
          </p>
          <button
            type="button"
            onClick={() => void handleRunAssessment()}
            className="px-4 py-2 rounded-lg bg-accent-solid text-white text-xs font-medium cursor-pointer shadow-xs hover:opacity-90"
          >
            {t('guardian.runCurrentDiff', 'Run Assessment for HEAD')}
          </button>
        </div>
      )}

      {report && (
        <div className="space-y-6">
          {/* Verdict Banner Card */}
          <div className="p-4 sm:p-5 bg-panel border border-line rounded-xl space-y-3">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                {renderVerdictBadge(report.verdict)}
                <span className="text-xs text-muted font-mono">
                  {report.base_provenance.ref_name} → {report.head_provenance.ref_name}
                </span>
              </div>
              <div className="flex items-center gap-2 text-xs">
                {report.should_block_ci ? (
                  <span className="px-2 py-0.5 rounded text-[10px] font-semibold uppercase bg-red-500/15 text-red-600 border border-red-500/30">
                    CI BLOCK (Exit 1)
                  </span>
                ) : (
                  <span className="px-2 py-0.5 rounded text-[10px] font-semibold uppercase bg-blue-500/15 text-blue-600 border border-blue-500/30">
                    CI ADVISORY (Exit 0)
                  </span>
                )}
                <span className="text-muted">{t('guardian.riskScore', 'Risk Score')}:</span>
                <span className="font-bold text-ink">
                  {report.risk_assessment.risk_score} / 100
                </span>
                <span
                  className={`px-2 py-0.5 rounded text-[10px] font-semibold uppercase ${
                    report.risk_assessment.risk_level === 'CRITICAL'
                      ? 'bg-red-500/15 text-red-600'
                      : report.risk_assessment.risk_level === 'HIGH'
                      ? 'bg-amber-500/15 text-amber-600'
                      : 'bg-emerald-500/15 text-emerald-600'
                  }`}
                >
                  {report.risk_assessment.risk_level}
                </span>
              </div>
            </div>

            <p className="text-xs text-ink bg-raised p-2.5 rounded-lg border border-line">
              {report.verdict_reason}
            </p>

            {report.risk_assessment.risk_factors.length > 0 && (
              <div className="text-xs space-y-1 pt-1">
                <div className="text-muted font-medium text-[11px] uppercase tracking-wider">
                  {t('guardian.riskFactors', 'Identified Risk Contributors')}:
                </div>
                <ul className="list-disc list-inside space-y-0.5 text-ink">
                  {report.risk_assessment.risk_factors.map((f, i) => (
                    <li key={i}>{f}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          {/* Vitals Delta Grid */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="p-3 bg-panel border border-line rounded-xl">
              <div className="text-[11px] text-muted">{t('guardian.newCycles', 'New Cycles')}</div>
              <div className="text-xl font-bold mt-1 text-ink flex items-center gap-1.5">
                {report.new_cycles.length > 0 ? (
                  <span className="text-red-500 font-bold">+{report.new_cycles.length}</span>
                ) : (
                  <span className="text-emerald-500 font-medium">0</span>
                )}
                {report.resolved_cycles.length > 0 && (
                  <span className="text-xs text-emerald-500 font-normal">
                    (-{report.resolved_cycles.length} resolved)
                  </span>
                )}
              </div>
            </div>

            <div className="p-3 bg-panel border border-line rounded-xl">
              <div className="text-[11px] text-muted">{t('guardian.contractViolations', 'Contract Violations')}</div>
              <div className="text-xl font-bold mt-1 text-ink flex items-center gap-1.5">
                {report.new_contract_violations.length > 0 ? (
                  <span className="text-red-500 font-bold">+{report.new_contract_violations.length}</span>
                ) : (
                  <span className="text-emerald-500 font-medium">0</span>
                )}
                {report.existing_baseline_violations.length > 0 && (
                  <span className="text-xs text-muted font-normal">
                    ({report.existing_baseline_violations.length} baseline)
                  </span>
                )}
              </div>
            </div>

            <div className="p-3 bg-panel border border-line rounded-xl">
              <div className="text-[11px] text-muted">{t('guardian.healthDelta', 'Health Score')}</div>
              <div className="text-xl font-bold mt-1 text-ink flex items-center gap-1.5">
                <span>{report.health_delta.score_after ?? 'N/A'}</span>
                {report.health_delta.score_delta !== null && (
                  <span
                    className={`text-xs flex items-center ${
                      report.health_delta.score_delta > 0
                        ? 'text-emerald-500'
                        : report.health_delta.score_delta < 0
                        ? 'text-red-500'
                        : 'text-muted'
                    }`}
                  >
                    {report.health_delta.score_delta > 0 ? (
                      <TrendingUp className="w-3 h-3 mr-0.5" />
                    ) : (
                      <TrendingDown className="w-3 h-3 mr-0.5" />
                    )}
                    {report.health_delta.score_delta > 0 ? '+' : ''}
                    {report.health_delta.score_delta}
                  </span>
                )}
              </div>
            </div>

            <div className="p-3 bg-panel border border-line rounded-xl">
              <div className="text-[11px] text-muted">{t('guardian.astCoverage', 'AST LOC Coverage')}</div>
              <div className="text-xl font-bold mt-1 text-ink flex items-center gap-1.5">
                <span>{report.coverage_delta.ast_loc_coverage_after.toFixed(1)}%</span>
                <span className="text-xs text-muted">
                  ({report.coverage_delta.ast_loc_coverage_delta >= 0 ? '+' : ''}
                  {report.coverage_delta.ast_loc_coverage_delta.toFixed(1)}%)
                </span>
              </div>
            </div>
          </div>

          {/* New Violations Table */}
          {report.new_contract_violations.length > 0 && (
            <div className="p-4 bg-panel border border-line rounded-xl space-y-3">
              <h2 className="text-xs font-bold uppercase tracking-wider text-red-500 flex items-center gap-1.5">
                <AlertTriangle className="w-4 h-4" />
                {t('guardian.newViolationsTitle', 'New Architectural Policy Violations')} ({report.new_contract_violations.length})
              </h2>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs border-collapse">
                  <thead>
                    <tr className="border-b border-line text-muted">
                      <th className="py-2 px-2 font-medium">{t('guardian.rule', 'Rule')}</th>
                      <th className="py-2 px-2 font-medium">{t('guardian.source', 'Source Module')}</th>
                      <th className="py-2 px-2 font-medium">{t('guardian.target', 'Target Module')}</th>
                      <th className="py-2 px-2 font-medium">{t('guardian.remediation', 'Remediation')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {report.new_contract_violations.map((v, i) => (
                      <tr key={i} className="border-b border-line/50 hover:bg-raised">
                        <td className="py-2 px-2 font-mono font-bold text-red-500">{v.rule_id}</td>
                        <td className="py-2 px-2 font-mono text-ink">
                          {v.source_file}:{v.line}
                        </td>
                        <td className="py-2 px-2 font-mono text-ink">{v.target_file}</td>
                        <td className="py-2 px-2 text-muted">{v.remediation || v.message}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* New Cycles List */}
          {report.new_cycles.length > 0 && (
            <div className="p-4 bg-panel border border-line rounded-xl space-y-3">
              <h2 className="text-xs font-bold uppercase tracking-wider text-red-500 flex items-center gap-1.5">
                <XCircle className="w-4 h-4" />
                {t('guardian.newCyclesTitle', 'Regressive Circular Dependency Loops')} ({report.new_cycles.length})
              </h2>
              <div className="space-y-2">
                {report.new_cycles.map((c, i) => (
                  <div key={i} className="p-2.5 bg-raised rounded-lg border border-line font-mono text-xs">
                    <span className="font-bold text-red-500 mr-2">[{c.id}]</span>
                    <span className="text-ink">{c.nodes.join(' → ')}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Advanced Mode: Module Changes & Hubs */}
          {workstationMode === 'advanced' && (
            <div className="p-4 bg-panel border border-line rounded-xl space-y-3">
              <h2 className="text-xs font-bold uppercase tracking-wider text-muted">
                {t('guardian.moduleChanges', 'Module Changes & Coupling')}
              </h2>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 text-xs">
                <div className="p-2 bg-raised rounded border border-line">
                  <span className="text-muted">{t('guardian.added', 'Added')}:</span>{' '}
                  <span className="font-bold text-emerald-500">+{report.added_modules.length}</span>
                </div>
                <div className="p-2 bg-raised rounded border border-line">
                  <span className="text-muted">{t('guardian.removed', 'Removed')}:</span>{' '}
                  <span className="font-bold text-red-500">-{report.removed_modules.length}</span>
                </div>
                <div className="p-2 bg-raised rounded border border-line">
                  <span className="text-muted">{t('guardian.renamed', 'Renamed')}:</span>{' '}
                  <span className="font-bold text-ink">{report.renamed_modules.length}</span>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
