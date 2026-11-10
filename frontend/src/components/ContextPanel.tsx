import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  Copy,
  Cpu,
  Download,
  Sparkles,
} from 'lucide-react';
import { buildBrainContext } from '../api/client';
import type { AgentContextResponse, AnalysisResult } from '../types/repodna';

interface ContextPanelProps {
  analysisId: string;
  result?: AnalysisResult | null;
}

export const ContextPanel: React.FC<ContextPanelProps> = ({ analysisId }) => {
  const { t } = useTranslation();
  const [mode, setMode] = useState<'compact' | 'focused' | 'deep'>('focused');
  const [query, setQuery] = useState('');
  const [maxTokens, setMaxTokens] = useState<number>(2000);
  const [minimalContract, setMinimalContract] = useState(false);
  const [selectedFiles] = useState<string[]>([]);
  const [viewFormat, setViewFormat] = useState<'markdown' | 'json'>('markdown');
  const [contextResponse, setContextResponse] = useState<AgentContextResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const handleGenerate = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    setIsLoading(true);
    setErrorMsg(null);
    try {
      const resp = await buildBrainContext(analysisId, {
        mode,
        query: mode === 'focused' ? query.trim() || undefined : undefined,
        target_files: selectedFiles.length > 0 ? selectedFiles : undefined,
        max_tokens: maxTokens,
        minimal_contract: minimalContract,
      });
      setContextResponse(resp);
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : 'Failed to generate agent context.');
    } finally {
      setIsLoading(false);
    }
  };

  const copyOutput = () => {
    if (!contextResponse) return;
    const text =
      viewFormat === 'json'
        ? JSON.stringify(contextResponse, null, 2)
        : contextResponse.summary +
          '\n\n' +
          (contextResponse.evidence || []).map((e) => `- ${e}`).join('\n');
    void navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  };

  const downloadOutput = () => {
    if (!contextResponse) return;
    const isJson = viewFormat === 'json';
    const text = isJson
      ? JSON.stringify(contextResponse, null, 2)
      : contextResponse.summary +
        '\n\n' +
        (contextResponse.evidence || []).map((e) => `- ${e}`).join('\n');
    const blob = new Blob([text], { type: isJson ? 'application/json' : 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `repodna-context-${mode}.${isJson ? 'json' : 'md'}`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const tokenPresets = [500, 1000, 2000, 4000, 8000];

  return (
    <div className="flex flex-col h-full bg-canvas overflow-y-auto">
      {/* Configuration Header */}
      <div className="p-4 bg-panel border-b border-line shadow-xs shrink-0">
        <form onSubmit={handleGenerate} className="flex flex-col gap-4 max-w-5xl mx-auto">
          {/* Mode Selector */}
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-sm font-bold text-ink flex items-center gap-2">
                <Cpu className="w-4 h-4 text-accent" />
                <span>{t('intelligence.contextPanelTitle', 'AI Agent Architecture Context Generator')}</span>
              </h2>
              <p className="text-xs text-muted mt-0.5">
                {t(
                  'intelligence.contextSubtitle',
                  'Controlled, deterministic architectural context with token budgeting and verifiable evidence ledger.'
                )}
              </p>
            </div>

            {/* Mode Pills */}
            <div className="flex rounded-md p-1 bg-raised border border-line">
              <button
                type="button"
                data-testid="context-mode-compact-btn"
                onClick={() => setMode('compact')}
                className={`px-3 py-1 rounded text-xs font-medium transition cursor-pointer ${
                  mode === 'compact'
                    ? 'bg-accent-solid text-white shadow-xs'
                    : 'text-muted hover:text-ink'
                }`}
              >
                {t('intelligence.modeCompact', 'Compact')}
              </button>
              <button
                type="button"
                data-testid="context-mode-focused-btn"
                onClick={() => setMode('focused')}
                className={`px-3 py-1 rounded text-xs font-medium transition cursor-pointer ${
                  mode === 'focused'
                    ? 'bg-accent-solid text-white shadow-xs'
                    : 'text-muted hover:text-ink'
                }`}
              >
                {t('intelligence.modeFocused', 'Focused')}
              </button>
              <button
                type="button"
                data-testid="context-mode-deep-btn"
                onClick={() => setMode('deep')}
                className={`px-3 py-1 rounded text-xs font-medium transition cursor-pointer ${
                  mode === 'deep'
                    ? 'bg-accent-solid text-white shadow-xs'
                    : 'text-muted hover:text-ink'
                }`}
              >
                {t('intelligence.modeDeep', 'Deep')}
              </button>
            </div>
          </div>

          {/* Focused Query Input */}
          {mode === 'focused' && (
            <div>
              <label className="block text-xs font-medium text-ink mb-1">
                {t('intelligence.targetQuery', 'Target Query / Task Scope')}
              </label>
              <input
                type="text"
                data-testid="context-query-input"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder={t(
                  'intelligence.queryContextPlaceholder',
                  'e.g. "auth session token validation", "Tarjan circular dependency detector", "fastapi routes"'
                )}
                className="w-full px-3 py-1.5 bg-canvas border border-line rounded text-xs text-ink placeholder:text-muted focus:outline-hidden focus:border-accent"
              />
            </div>
          )}

          {/* Token Budget Controls */}
          <div className="flex flex-wrap items-center justify-between gap-3 text-xs">
            <div className="flex items-center gap-2">
              <span className="font-medium text-ink">{t('intelligence.tokenBudget', 'Token Budget')}:</span>
              <div className="flex items-center gap-1">
                {tokenPresets.map((preset) => (
                  <button
                    key={preset}
                    type="button"
                    data-testid={`preset-${preset}-btn`}
                    onClick={() => setMaxTokens(preset)}
                    className={`px-2 py-0.5 rounded font-mono text-[11px] transition cursor-pointer border ${
                      maxTokens === preset
                        ? 'bg-accent/15 border-accent text-accent font-bold'
                        : 'bg-canvas border-line text-muted hover:text-ink'
                    }`}
                  >
                    {preset}
                  </button>
                ))}
              </div>
              <input
                type="number"
                min={50}
                max={32000}
                step={100}
                value={maxTokens}
                onChange={(e) => setMaxTokens(parseInt(e.target.value, 10) || 1000)}
                className="w-20 px-2 py-0.5 bg-canvas border border-line rounded text-xs font-mono text-ink text-center"
              />
            </div>

            <div className="flex items-center gap-3">
              <label className="flex items-center gap-1.5 text-xs text-ink cursor-pointer">
                <input
                  type="checkbox"
                  data-testid="minimal-contract-checkbox"
                  checked={minimalContract}
                  onChange={(e) => setMinimalContract(e.target.checked)}
                  className="rounded border-line text-accent cursor-pointer"
                />
                <span>{t('intelligence.minimalContract', 'Minimal Response Contract')}</span>
              </label>

              <button
                type="submit"
                data-testid="generate-context-btn"
                onClick={(e) => {
                  e.preventDefault();
                  void handleGenerate();
                }}
                disabled={isLoading}
                className="px-4 py-1.5 bg-accent-solid text-white text-xs font-medium rounded hover:opacity-90 transition cursor-pointer flex items-center gap-1.5"
              >
                <Sparkles className="w-3.5 h-3.5" />
                <span>{isLoading ? t('common.generating', 'Generating…') : t('intelligence.generateContext', 'Build Context')}</span>
              </button>
            </div>
          </div>
        </form>
      </div>

      {/* Main Results Container */}
      <div className="flex-1 p-4 max-w-5xl mx-auto w-full flex flex-col gap-4">
        {errorMsg && (
          <div className="p-3 rounded bg-danger/10 border border-danger/30 text-danger text-xs flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{errorMsg}</span>
          </div>
        )}

        {contextResponse ? (
          <div className="flex flex-col gap-3">
            {/* Vitals & Token Honesty Disclosure Strip */}
            <div className="p-3 rounded-lg bg-panel border border-line shadow-xs flex flex-wrap items-center justify-between gap-3 text-xs">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-semibold text-ink">
                  {t('intelligence.contextOutputTokens', 'Context Size')}:
                </span>
                <span className="px-2 py-0.5 rounded font-mono font-bold bg-raised border border-line text-ink">
                  {contextResponse.estimated_tokens?.toLocaleString()} tokens
                </span>
                <span className="text-[11px] text-muted">
                  ({contextResponse.token_counting_method === 'tiktoken_cl100k'
                    ? 'tiktoken cl100k'
                    : 'heuristic ~4 chars/tok'}
                  )
                </span>
                {contextResponse.token_savings_pct !== undefined && contextResponse.token_savings_pct > 0 && (
                  <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-success/15 text-success border border-success/30">
                    {contextResponse.token_savings_pct.toFixed(1)}% {t('intelligence.tokenReduction', 'reduction vs codebase')}
                  </span>
                )}
              </div>

              {/* Budget Compliance Badges */}
              <div className="flex items-center gap-2">
                {contextResponse.truncated ? (
                  <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-warning/15 text-warning border border-warning/30 flex items-center gap-1">
                    <AlertTriangle className="w-3 h-3" />
                    <span>TRUNCATED TO FIT BUDGET</span>
                  </span>
                ) : (
                  <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-success/15 text-success border border-success/30 flex items-center gap-1">
                    <CheckCircle2 className="w-3 h-3" />
                    <span>BUDGET COMPLIANT</span>
                  </span>
                )}
                {contextResponse.continuation_token && (
                  <span className="text-[10px] font-mono text-muted">
                    Next: {contextResponse.continuation_token}
                  </span>
                )}
              </div>
            </div>

            {/* Truncation / Overflow Warnings */}
            {contextResponse.limitations.some((l) => l.includes('exceeds requested budget')) && (
              <div className="p-3 rounded bg-danger/10 border border-danger/30 text-danger text-xs flex items-center gap-2">
                <AlertCircle className="w-4 h-4 shrink-0" />
                <span>
                  {t(
                    'intelligence.metadataOverflowAlert',
                    'Minimal metadata envelope exceeds requested budget. Increase token budget to fit full headers.'
                  )}
                </span>
              </div>
            )}

            {/* Output View Tabs & Action Bar */}
            <div className="flex items-center justify-between pt-1">
              <div className="flex rounded p-0.5 bg-raised border border-line text-xs">
                <button
                  type="button"
                  onClick={() => setViewFormat('markdown')}
                  className={`px-3 py-1 rounded text-xs font-medium cursor-pointer transition ${
                    viewFormat === 'markdown'
                      ? 'bg-panel text-ink shadow-xs'
                      : 'text-muted hover:text-ink'
                  }`}
                >
                  Markdown
                </button>
                <button
                  type="button"
                  onClick={() => setViewFormat('json')}
                  className={`px-3 py-1 rounded text-xs font-medium cursor-pointer transition ${
                    viewFormat === 'json'
                      ? 'bg-panel text-ink shadow-xs'
                      : 'text-muted hover:text-ink'
                  }`}
                >
                  JSON
                </button>
              </div>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={downloadOutput}
                  className="px-2.5 py-1 rounded bg-raised border border-line hover:border-accent text-xs font-medium text-ink cursor-pointer flex items-center gap-1 transition"
                >
                  <Download className="w-3.5 h-3.5" />
                  <span>Download</span>
                </button>
                <button
                  type="button"
                  onClick={copyOutput}
                  className="px-3 py-1 rounded bg-accent-solid text-white text-xs font-medium cursor-pointer hover:opacity-90 flex items-center gap-1.5 transition"
                >
                  {copied ? (
                    <>
                      <CheckCircle2 className="w-3.5 h-3.5 text-success" />
                      <span>Copied!</span>
                    </>
                  ) : (
                    <>
                      <Copy className="w-3.5 h-3.5" />
                      <span>Copy Context</span>
                    </>
                  )}
                </button>
              </div>
            </div>

            {/* Rendered Output Display Box */}
            <div className="rounded-lg bg-panel border border-line shadow-xs p-4 font-mono text-xs overflow-x-auto max-h-[550px] overflow-y-auto">
              <pre className="text-ink leading-relaxed whitespace-pre-wrap">
                {viewFormat === 'json'
                  ? JSON.stringify(contextResponse, null, 2)
                  : contextResponse.summary +
                    '\n\n' +
                    (contextResponse.relevant_modules && contextResponse.relevant_modules.length > 0
                      ? '### Relevant Modules\n' +
                        contextResponse.relevant_modules
                          .map((m) => `- **${m.id}** (${m.language || 'code'}): Fan-In ${m.fan_in}, Fan-Out ${m.fan_out}`)
                          .join('\n') +
                        '\n\n'
                      : '') +
                    (contextResponse.evidence && contextResponse.evidence.length > 0
                      ? '### Architectural Evidence Citations\n' +
                        contextResponse.evidence.map((e) => `- ${e}`).join('\n')
                      : '')}
              </pre>
            </div>
          </div>
        ) : !isLoading ? (
          <div className="p-12 text-center bg-panel/50 rounded-lg border border-dashed border-line text-muted my-auto">
            <Cpu className="w-10 h-10 mx-auto mb-2 text-accent opacity-70" />
            <p className="text-xs font-medium text-ink mb-1">
              {t('intelligence.contextEmptyTitle', 'Configure mode & token budget and click "Build Context".')}
            </p>
            <p className="text-[11px] max-w-md mx-auto">
              {t(
                'intelligence.contextEmptyDesc',
                'Outputs bounded, deterministic architectural knowledge for LLMs without flooding token windows.'
              )}
            </p>
          </div>
        ) : null}
      </div>
    </div>
  );
};
