import React, { useCallback, useEffect, useState } from 'react';
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Copy,
  Check,
  Filter,
  Layers,
  Network,
  RefreshCw,
  Sparkles,
  Split,
  Workflow,
  ShieldCheck,
  FileCode,
} from 'lucide-react';
import { fetchRefactoringRecommendations } from '../api/client';
import type {
  AdvisorCategory,
  AdvisorSeverity,
  RefactoringAdvisorReport,
  RefactoringRecommendation,
} from '../types/advisor';
import type { AnalysisResult } from '../types/repodna';
import type { WorkstationMode } from '../utils/preferences';

interface RefactoringAdvisorViewProps {
  result: AnalysisResult | null;
  workstationMode?: WorkstationMode;
  onSelectFileInStudio: (fileId: string) => void;
  onNavigateTab?: (tab: string) => void;
}

export const RefactoringAdvisorView: React.FC<RefactoringAdvisorViewProps> = ({
  result,
  onSelectFileInStudio,
  onNavigateTab,
}) => {
  const [report, setReport] = useState<RefactoringAdvisorReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [selectedCategory, setSelectedCategory] = useState<AdvisorCategory | 'all'>('all');
  const [selectedSeverity, setSelectedSeverity] = useState<AdvisorSeverity | 'all'>('all');
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [checkedSteps, setCheckedSteps] = useState<Record<string, Record<number, boolean>>>({});

  const analysisId = result?.analysis_id;

  const loadRecommendations = useCallback(async () => {
    if (!analysisId) return;
    setLoading(true);
    setErrorMsg(null);
    try {
      const catParam = selectedCategory === 'all' ? undefined : selectedCategory;
      const sevParam = selectedSeverity === 'all' ? undefined : selectedSeverity;
      const data = await fetchRefactoringRecommendations(analysisId, catParam, sevParam);
      setReport(data);
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : 'Failed to load refactoring advice');
    } finally {
      setLoading(false);
    }
  }, [analysisId, selectedCategory, selectedSeverity]);

  useEffect(() => {
    loadRecommendations();
  }, [loadRecommendations]);

  const handleCopyMarkdown = (rec: RefactoringRecommendation) => {
    const md = [
      `### [${rec.severity.toUpperCase()}] ${rec.title}`,
      `**Category**: \`${rec.category}\``,
      `**Target Module**: \`${rec.target_module}\``,
      `**Impact**: ${rec.description}`,
      '',
      '**Action Steps**:',
      ...rec.suggested_action_steps.map((s, idx) => `${idx + 1}. ${s}`),
      '',
      `**Expected Benefit**: ${rec.expected_architectural_benefit}`,
      `**Risks**: ${rec.risks_and_limitations}`,
    ].join('\n');

    navigator.clipboard.writeText(md).then(() => {
      setCopiedId(rec.recommendation_id);
      setTimeout(() => setCopiedId(null), 2000);
    });
  };

  const toggleStep = (recId: string, stepIndex: number) => {
    setCheckedSteps((prev) => ({
      ...prev,
      [recId]: {
        ...(prev[recId] || {}),
        [stepIndex]: !prev[recId]?.[stepIndex],
      },
    }));
  };

  const getSeverityBadge = (severity: string) => {
    switch (severity) {
      case 'critical':
        return (
          <span className="px-2 py-0.5 rounded text-xs font-semibold bg-rose-500/20 text-rose-400 border border-rose-500/30 flex items-center gap-1">
            <AlertTriangle className="w-3 h-3" /> Critical
          </span>
        );
      case 'high':
        return (
          <span className="px-2 py-0.5 rounded text-xs font-semibold bg-amber-500/20 text-amber-400 border border-amber-500/30 flex items-center gap-1">
            <AlertTriangle className="w-3 h-3" /> High
          </span>
        );
      case 'medium':
        return (
          <span className="px-2 py-0.5 rounded text-xs font-semibold bg-blue-500/20 text-blue-400 border border-blue-500/30">
            Medium
          </span>
        );
      default:
        return (
          <span className="px-2 py-0.5 rounded text-xs font-semibold bg-slate-500/20 text-slate-400 border border-slate-500/30">
            Low
          </span>
        );
    }
  };

  const getCategoryIcon = (category: AdvisorCategory) => {
    switch (category) {
      case 'circular_dependency_reduction':
        return <RotateCcwIcon className="w-4 h-4 text-rose-400" />;
      case 'high_coupling_module_review':
        return <Split className="w-4 h-4 text-amber-400" />;
      case 'layer_boundary_improvement':
        return <Layers className="w-4 h-4 text-indigo-400" />;
      case 'oversized_architectural_hub_review':
        return <Network className="w-4 h-4 text-purple-400" />;
      default:
        return <Workflow className="w-4 h-4 text-emerald-400" />;
    }
  };

  const getCategoryLabel = (category: AdvisorCategory) => {
    switch (category) {
      case 'circular_dependency_reduction':
        return 'Circular Dependency';
      case 'high_coupling_module_review':
        return 'High Coupling Review';
      case 'layer_boundary_improvement':
        return 'Layer Inversion';
      case 'oversized_architectural_hub_review':
        return 'Oversized Hub';
      default:
        return category;
    }
  };

  return (
    <div className="flex-1 overflow-y-auto p-6 bg-slate-950 text-slate-100 flex flex-col gap-6">
      {/* Header Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-5 rounded-xl bg-slate-900 border border-slate-800 shadow-sm">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Sparkles className="w-5 h-5 text-indigo-400" />
            <h1 className="text-xl font-bold tracking-tight text-white">
              Architecture Refactoring Advisor
            </h1>
            <span className="px-2 py-0.5 text-xs font-semibold rounded-full bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
              v0.7.0 Portfolio Release
            </span>
          </div>
          <p className="text-xs text-slate-400 max-w-3xl">
            Deterministic, evidence-grounded architectural recommendations to break cycles, decouple high-fanout modules, eliminate layer inversions, and decompose oversized hubs.
          </p>
        </div>

        <button
          type="button"
          onClick={loadRecommendations}
          disabled={loading || !analysisId}
          data-testid="refresh-advisor-btn"
          className="self-start md:self-auto px-3.5 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-xs font-medium text-white flex items-center gap-1.5 transition cursor-pointer shadow-sm"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          {loading ? 'Analyzing...' : 'Re-evaluate Advice'}
        </button>
      </div>

      {/* Summary KPI Strip */}
      {report && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3.5">
          <div className="p-4 rounded-xl bg-slate-900/90 border border-slate-800 flex flex-col gap-1">
            <span className="text-xs text-slate-400">Total Recommendations</span>
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-bold text-white">{report.total_recommendations}</span>
              <span className="text-xs text-slate-500">
                / {report.total_modules_analyzed} modules
              </span>
            </div>
          </div>

          <div className="p-4 rounded-xl bg-slate-900/90 border border-slate-800 flex flex-col gap-1">
            <span className="text-xs text-slate-400 flex items-center gap-1.5">
              <RotateCcwIcon className="w-3.5 h-3.5 text-rose-400" /> Critical Cycles
            </span>
            <div className="flex items-baseline gap-2">
              <span className={`text-2xl font-bold ${report.by_category.circular_dependency_reduction > 0 ? 'text-rose-400' : 'text-slate-300'}`}>
                {report.by_category.circular_dependency_reduction || 0}
              </span>
            </div>
          </div>

          <div className="p-4 rounded-xl bg-slate-900/90 border border-slate-800 flex flex-col gap-1">
            <span className="text-xs text-slate-400 flex items-center gap-1.5">
              <Split className="w-3.5 h-3.5 text-amber-400" /> High Coupling
            </span>
            <div className="flex items-baseline gap-2">
              <span className={`text-2xl font-bold ${report.by_category.high_coupling_module_review > 0 ? 'text-amber-400' : 'text-slate-300'}`}>
                {report.by_category.high_coupling_module_review || 0}
              </span>
            </div>
          </div>

          <div className="p-4 rounded-xl bg-slate-900/90 border border-slate-800 flex flex-col gap-1">
            <span className="text-xs text-slate-400 flex items-center gap-1.5">
              <Layers className="w-3.5 h-3.5 text-indigo-400" /> Layer Inversions
            </span>
            <div className="flex items-baseline gap-2">
              <span className={`text-2xl font-bold ${report.by_category.layer_boundary_improvement > 0 ? 'text-indigo-400' : 'text-slate-300'}`}>
                {report.by_category.layer_boundary_improvement || 0}
              </span>
            </div>
          </div>

          <div className="p-4 rounded-xl bg-slate-900/90 border border-slate-800 flex flex-col gap-1">
            <span className="text-xs text-slate-400 flex items-center gap-1.5">
              <Network className="w-3.5 h-3.5 text-purple-400" /> Oversized Hubs
            </span>
            <div className="flex items-baseline gap-2">
              <span className={`text-2xl font-bold ${report.by_category.oversized_architectural_hub_review > 0 ? 'text-purple-400' : 'text-slate-300'}`}>
                {report.by_category.oversized_architectural_hub_review || 0}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Filter Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-3 p-3.5 rounded-xl bg-slate-900/80 border border-slate-800 text-xs">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-slate-400 font-medium flex items-center gap-1 mr-1">
            <Filter className="w-3.5 h-3.5" /> Category:
          </span>
          {(
            [
              { id: 'all', label: 'All' },
              { id: 'circular_dependency_reduction', label: 'Cycles' },
              { id: 'high_coupling_module_review', label: 'Coupling' },
              { id: 'layer_boundary_improvement', label: 'Layers' },
              { id: 'oversized_architectural_hub_review', label: 'Hubs' },
            ] as const
          ).map((c) => (
            <button
              key={c.id}
              type="button"
              data-testid={`filter-cat-${c.id}`}
              onClick={() => setSelectedCategory(c.id)}
              className={`px-2.5 py-1 rounded-md font-medium transition cursor-pointer ${
                selectedCategory === c.id
                  ? 'bg-indigo-600 text-white'
                  : 'bg-slate-800/80 text-slate-300 hover:bg-slate-800'
              }`}
            >
              {c.label}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-2">
          <span className="text-slate-400 font-medium">Min Severity:</span>
          {(['all', 'critical', 'high', 'medium', 'low'] as const).map((sev) => (
            <button
              key={sev}
              type="button"
              data-testid={`filter-sev-${sev}`}
              onClick={() => setSelectedSeverity(sev)}
              className={`px-2 py-0.5 rounded text-xs capitalize transition cursor-pointer ${
                selectedSeverity === sev
                  ? 'bg-slate-200 text-slate-950 font-semibold'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              {sev}
            </button>
          ))}
        </div>
      </div>

      {/* Main Content / Error / Empty States */}
      {errorMsg ? (
        <div className="p-6 rounded-xl bg-rose-950/40 border border-rose-800/60 text-rose-300 text-sm flex items-center gap-3">
          <AlertTriangle className="w-5 h-5 flex-shrink-0" />
          <span>{errorMsg}</span>
        </div>
      ) : loading && !report ? (
        <div className="p-12 text-center text-slate-400 text-sm flex flex-col items-center gap-3">
          <RefreshCw className="w-6 h-6 animate-spin text-indigo-400" />
          <span>Generating architectural refactoring recommendations...</span>
        </div>
      ) : report?.recommendations.length === 0 ? (
        <div className="p-12 text-center rounded-xl bg-slate-900 border border-slate-800 flex flex-col items-center gap-3">
          <ShieldCheck className="w-10 h-10 text-emerald-400" />
          <h2 className="text-base font-semibold text-white">Clean Architectural Baseline</h2>
          <p className="text-xs text-slate-400 max-w-lg">
            No actionable architectural refactoring recommendations were triggered for the selected filters.
            Dependency graph couplings, cycle counts, and layer boundaries meet configured thresholds.
          </p>
        </div>
      ) : (
        <div className="flex flex-col gap-4">
          {report?.recommendations.map((rec) => {
            const stepsDone = Object.values(checkedSteps[rec.recommendation_id] || {}).filter(
              Boolean
            ).length;
            const totalSteps = rec.suggested_action_steps.length;

            return (
              <div
                key={rec.recommendation_id}
                data-testid={`advisor-card-${rec.recommendation_id}`}
                className="p-5 rounded-xl bg-slate-900/90 border border-slate-800 hover:border-slate-700/80 transition flex flex-col gap-4 shadow-sm"
              >
                {/* Header Row */}
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="flex items-start gap-3">
                    <div className="p-2 rounded-lg bg-slate-800/80 border border-slate-700/60 mt-0.5">
                      {getCategoryIcon(rec.category)}
                    </div>
                    <div>
                      <div className="flex items-center gap-2 mb-1">
                        {getSeverityBadge(rec.severity)}
                        <span className="text-xs text-slate-400 font-mono">
                          {getCategoryLabel(rec.category)}
                        </span>
                        <span className="text-xs text-slate-600 font-mono">
                          #{rec.recommendation_id.slice(-6)}
                        </span>
                      </div>
                      <h3 className="text-sm font-semibold text-white">{rec.title}</h3>
                      <button
                        type="button"
                        onClick={() => onSelectFileInStudio(rec.target_module)}
                        className="text-xs font-mono text-indigo-400 hover:text-indigo-300 hover:underline flex items-center gap-1 mt-0.5 text-left"
                      >
                        <FileCode className="w-3.5 h-3.5" />
                        {rec.target_module}
                      </button>
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => handleCopyMarkdown(rec)}
                      title="Copy recommendation markdown"
                      className="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-xs text-slate-300 flex items-center gap-1.5 transition cursor-pointer"
                    >
                      {copiedId === rec.recommendation_id ? (
                        <>
                          <Check className="w-3.5 h-3.5 text-emerald-400" /> Copied
                        </>
                      ) : (
                        <>
                          <Copy className="w-3.5 h-3.5" /> Copy Prompt
                        </>
                      )}
                    </button>

                    <button
                      type="button"
                      onClick={() => onSelectFileInStudio(rec.target_module)}
                      data-testid={`inspect-graph-btn-${rec.recommendation_id}`}
                      className="px-2.5 py-1 rounded bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-300 border border-indigo-500/30 text-xs font-medium flex items-center gap-1 transition cursor-pointer"
                    >
                      Inspect in Graph <ArrowRight className="w-3 h-3" />
                    </button>

                    {onNavigateTab && (
                      <button
                        type="button"
                        onClick={() => onNavigateTab('history')}
                        className="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-xs text-slate-300 flex items-center gap-1 transition cursor-pointer"
                        title="View evolution in Time Machine"
                      >
                        History
                      </button>
                    )}
                  </div>
                </div>

                {/* Description & Impact */}
                <div className="p-3 rounded-lg bg-slate-950/60 border border-slate-800 text-xs text-slate-300 leading-relaxed">
                  {rec.description}
                </div>

                {/* Metric Preview Delta */}
                {Object.keys(rec.metric_delta_preview).length > 0 && (
                  <div className="flex flex-wrap items-center gap-3 text-xs bg-slate-950/40 p-2.5 rounded-lg border border-slate-800/80 font-mono">
                    <span className="text-slate-400 font-sans font-medium text-[11px]">
                      METRICS DELTA:
                    </span>
                    {Object.entries(rec.metric_delta_preview).map(([k, v]) => (
                      <span key={k} className="px-2 py-0.5 rounded bg-slate-800/90 text-slate-200">
                        <strong className="text-slate-400">{k}:</strong> {String(v)}
                      </span>
                    ))}
                  </div>
                )}

                {/* Suggested Action Checklist */}
                <div className="flex flex-col gap-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-slate-300">
                      Action Checklist ({stepsDone}/{totalSteps} complete)
                    </span>
                  </div>
                  <div className="flex flex-col gap-1.5">
                    {rec.suggested_action_steps.map((step, sIdx) => {
                      const isDone = !!checkedSteps[rec.recommendation_id]?.[sIdx];
                      return (
                        <div
                          key={sIdx}
                          onClick={() => toggleStep(rec.recommendation_id, sIdx)}
                          className={`p-2 rounded-lg text-xs flex items-start gap-2.5 transition cursor-pointer select-none border ${
                            isDone
                              ? 'bg-emerald-950/20 border-emerald-900/40 text-emerald-300 line-through'
                              : 'bg-slate-950/40 border-slate-800/80 text-slate-300 hover:border-slate-700'
                          }`}
                        >
                          <input
                            type="checkbox"
                            checked={isDone}
                            onChange={() => {}}
                            className="mt-0.5 rounded border-slate-700 text-emerald-500 focus:ring-0 cursor-pointer"
                          />
                          <span className="leading-snug flex-1">{step}</span>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Expected Architectural Benefit */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs pt-1 border-t border-slate-800/60">
                  <div className="flex items-start gap-2">
                    <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0 mt-0.5" />
                    <div>
                      <span className="font-semibold text-emerald-400">Expected Benefit:</span>
                      <p className="text-slate-300 mt-0.5">{rec.expected_architectural_benefit}</p>
                    </div>
                  </div>

                  <div className="flex items-start gap-2">
                    <AlertTriangle className="w-4 h-4 text-amber-400 flex-shrink-0 mt-0.5" />
                    <div>
                      <span className="font-semibold text-amber-400">Risks & Considerations:</span>
                      <p className="text-slate-300 mt-0.5">{rec.risks_and_limitations}</p>
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

function RotateCcwIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg
      {...props}
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      viewBox="0 0 24 24"
    >
      <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" />
      <path d="M3 3v5h5" />
    </svg>
  );
}
