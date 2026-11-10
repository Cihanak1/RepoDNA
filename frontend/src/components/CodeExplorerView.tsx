import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  AlertCircle,
  ArrowRight,
  CheckCircle2,
  Code2,
  Copy,
  ExternalLink,
  Filter,
  Layers,
  Search,
  ShieldCheck,
  Sparkles,
} from 'lucide-react';
import { searchBrainCode } from '../api/client';
import type { CodeSearchResult, SearchResponse, SymbolDefinition } from '../types/repodna';

interface CodeExplorerViewProps {
  analysisId: string;
  onSelectFileInStudio?: (fileId: string) => void;
  onSelectSymbolForTrace?: (symbolId: string) => void;
  onSelectEvidence?: (evidenceId: string) => void;
}

export const CodeExplorerView: React.FC<CodeExplorerViewProps> = ({
  analysisId,
  onSelectFileInStudio,
  onSelectSymbolForTrace,
  onSelectEvidence,
}) => {
  const { t } = useTranslation();
  const [query, setQuery] = useState('');
  const [languageFilter, setLanguageFilter] = useState('');
  const [kindFilter, setKindFilter] = useState<string>('');
  const [pathFilter, setPathFilter] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [searchResponse, setSearchResponse] = useState<SearchResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [copiedSnippetId, setCopiedSnippetId] = useState<string | null>(null);

  const handleSearch = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!query.trim()) return;

    setIsLoading(true);
    setErrorMsg(null);
    try {
      const resp = await searchBrainCode(analysisId, {
        query: query.trim(),
        limit: 15,
        kind: kindFilter || undefined,
        path_filter: pathFilter.trim() || undefined,
        language: languageFilter || undefined,
      });
      setSearchResponse(resp);
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : t('intelligence.searchFailed', 'Search failed.'));
    } finally {
      setIsLoading(false);
    }
  };

  const copyToClipboard = (text: string, id: string) => {
    void navigator.clipboard.writeText(text);
    setCopiedSnippetId(id);
    setTimeout(() => setCopiedSnippetId(null), 1800);
  };

  const getTierColor = (tier: 'HIGH' | 'MEDIUM' | 'LOW') => {
    switch (tier) {
      case 'HIGH':
        return 'bg-success/15 text-success border-success/30';
      case 'MEDIUM':
        return 'bg-warning/15 text-warning border-warning/30';
      case 'LOW':
      default:
        return 'bg-muted/15 text-muted border-line';
    }
  };

  return (
    <div className="flex flex-col h-full bg-canvas overflow-y-auto">
      {/* Search Header Banner */}
      <div className="p-4 bg-panel border-b border-line shadow-xs shrink-0">
        <form onSubmit={handleSearch} className="flex flex-col gap-3 max-w-5xl mx-auto">
          <div className="flex items-center gap-2">
            <div className="relative flex-1">
              <Search className="w-4 h-4 text-muted absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder={t(
                  'intelligence.searchPlaceholder',
                  'Search symbols, services, controllers, or architectural roles (e.g. "auth session token", "Tarjan cycles")…'
                )}
                className="w-full pl-9 pr-4 py-2 bg-canvas border border-line rounded-md text-xs text-ink placeholder:text-muted focus:outline-hidden focus:border-accent"
              />
            </div>
            <button
              type="submit"
              disabled={isLoading || !query.trim()}
              className="px-4 py-2 bg-accent-solid text-white text-xs font-medium rounded-md hover:opacity-90 transition cursor-pointer flex items-center gap-1.5 shrink-0"
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span>{isLoading ? t('common.searching', 'Searching…') : t('common.search', 'Search')}</span>
            </button>
          </div>

          {/* Filters Bar */}
          <div className="flex flex-wrap items-center gap-2 text-xs text-muted">
            <span className="flex items-center gap-1 font-medium text-ink">
              <Filter className="w-3 h-3" />
              <span>{t('intelligence.filters', 'Filters')}:</span>
            </span>

            {/* Language filter */}
            <select
              value={languageFilter}
              onChange={(e) => setLanguageFilter(e.target.value)}
              className="bg-canvas border border-line rounded px-2 py-1 text-xs text-ink cursor-pointer"
              aria-label={t('intelligence.filterLanguage', 'Filter by language')}
            >
              <option value="">{t('intelligence.allLanguages', 'All Languages')}</option>
              <option value="Python">Python</option>
              <option value="TypeScript">TypeScript</option>
              <option value="JavaScript">JavaScript</option>
              <option value="Go">Go</option>
            </select>

            {/* Symbol Kind filter */}
            <select
              value={kindFilter}
              onChange={(e) => setKindFilter(e.target.value)}
              className="bg-canvas border border-line rounded px-2 py-1 text-xs text-ink cursor-pointer"
              aria-label={t('intelligence.filterKind', 'Filter by symbol kind')}
            >
              <option value="">{t('intelligence.allKinds', 'All Symbol Kinds')}</option>
              <option value="class">{t('intelligence.class', 'Class')}</option>
              <option value="function">{t('intelligence.function', 'Function')}</option>
              <option value="method">{t('intelligence.method', 'Method')}</option>
              <option value="interface">{t('intelligence.interface', 'Interface')}</option>
              <option value="type">{t('intelligence.type', 'Type')}</option>
              <option value="struct">{t('intelligence.struct', 'Struct')}</option>
            </select>

            {/* Path filter */}
            <input
              type="text"
              value={pathFilter}
              onChange={(e) => setPathFilter(e.target.value)}
              placeholder={t('intelligence.pathFilterPlaceholder', 'Path prefix (e.g. backend/api)')}
              className="bg-canvas border border-line rounded px-2 py-1 text-xs text-ink placeholder:text-muted max-w-[180px]"
            />

            {(languageFilter || kindFilter || pathFilter) && (
              <button
                type="button"
                onClick={() => {
                  setLanguageFilter('');
                  setKindFilter('');
                  setPathFilter('');
                }}
                className="text-xs text-accent hover:underline cursor-pointer ml-1"
              >
                {t('common.reset', 'Reset filters')}
              </button>
            )}
          </div>
        </form>
      </div>

      {/* Main Results Container */}
      <div className="flex-1 p-4 max-w-5xl mx-auto w-full">
        {errorMsg && (
          <div className="p-3 mb-4 rounded-md bg-danger/10 border border-danger/30 text-danger text-xs flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{errorMsg}</span>
          </div>
        )}

        {searchResponse && (
          <div className="mb-4 flex flex-wrap items-center justify-between gap-2 pb-2 border-b border-line text-xs">
            <div className="flex items-center gap-2">
              <span className="font-semibold text-ink">
                {t('intelligence.resultsFound', 'Found {{count}} matching modules', {
                  count: searchResponse.total_matches,
                })}
              </span>
              <span className="px-2 py-0.5 rounded-full text-[11px] font-mono bg-raised border border-line text-muted">
                {t('intelligence.intent', 'Intent')}: {searchResponse.query_intent}
              </span>
            </div>
            {searchResponse.tokens_evaluated.length > 0 && (
              <div className="flex items-center gap-1 text-[11px] text-muted">
                <span>{t('intelligence.evaluatedTerms', 'Terms')}:</span>
                <span className="font-mono text-ink">
                  {searchResponse.tokens_evaluated.slice(0, 6).join(', ')}
                  {searchResponse.tokens_evaluated.length > 6 ? '…' : ''}
                </span>
              </div>
            )}
          </div>
        )}

        {/* Results List */}
        {searchResponse?.matches && searchResponse.matches.length > 0 ? (
          <div className="space-y-4">
            {searchResponse.matches.map((res: CodeSearchResult, idx: number) => (
              <div
                key={res.file_id}
                className="p-4 rounded-lg bg-panel border border-line shadow-xs hover:border-accent/50 transition flex flex-col gap-3"
              >
                {/* Result Card Header */}
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span className="w-5 h-5 rounded-full bg-raised border border-line flex items-center justify-center text-[10px] font-mono text-muted">
                      {idx + 1}
                    </span>
                    <button
                      type="button"
                      onClick={() => onSelectFileInStudio?.(res.file_id)}
                      className="font-mono font-semibold text-xs text-ink hover:text-accent hover:underline text-left cursor-pointer flex items-center gap-1.5"
                    >
                      <span>{res.file_id}</span>
                      <ExternalLink className="w-3 h-3 text-muted" />
                    </button>
                    <span className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-raised text-muted">
                      {res.language}
                    </span>
                    {res.is_hub && (
                      <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-accent/15 text-accent border border-accent/30">
                        {t('intelligence.hubModule', 'Hub')}
                      </span>
                    )}
                    {res.in_cycle && (
                      <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-danger/15 text-danger border border-danger/30">
                        {t('intelligence.cycle', 'Cyclic')}
                      </span>
                    )}
                  </div>

                  <div className="flex items-center gap-2">
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-bold border uppercase ${getTierColor(
                        res.relevance_tier
                      )}`}
                    >
                      {res.relevance_tier}
                    </span>
                    <div className="text-right">
                      <div className="text-xs font-mono font-bold text-ink">{res.score.toFixed(1)} pts</div>
                      <div className="w-16 h-1.5 bg-raised rounded-full overflow-hidden mt-0.5 border border-line">
                        <div
                          className="h-full bg-accent-solid rounded-full"
                          style={{ width: `${Math.min(100, (res.score / 60) * 100)}%` }}
                        />
                      </div>
                    </div>
                  </div>
                </div>

                {/* Match Reasons */}
                {res.match_reasons.length > 0 && (
                  <div className="bg-canvas p-2.5 rounded border border-line text-xs">
                    <div className="text-[11px] font-medium text-muted mb-1 flex items-center gap-1">
                      <ShieldCheck className="w-3 h-3 text-accent" />
                      <span>{t('intelligence.matchEvidence', 'Scoring & Retrieval Rationale')}:</span>
                    </div>
                    <ul className="space-y-0.5 pl-4 list-disc text-ink text-[11px]">
                      {res.match_reasons.map((reason: string, rIdx: number) => (
                        <li key={rIdx}>{reason}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Matched Symbols Chips */}
                {res.matched_symbols.length > 0 && (
                  <div className="flex flex-wrap items-center gap-1.5">
                    <span className="text-[11px] text-muted flex items-center gap-1">
                      <Code2 className="w-3 h-3" />
                      <span>{t('intelligence.matchedSymbols', 'Matched Symbols')}:</span>
                    </span>
                    {res.matched_symbols.map((sym: SymbolDefinition) => (
                      <button
                        key={sym.id}
                        type="button"
                        onClick={() => onSelectSymbolForTrace?.(sym.id)}
                        className="px-2 py-1 rounded-md text-[11px] font-mono bg-raised border border-line hover:border-accent text-ink hover:text-accent cursor-pointer flex items-center gap-1 transition"
                        title={t('intelligence.clickToTrace', 'Click to trace callers and blast radius')}
                      >
                        <span className="text-muted text-[10px] uppercase font-semibold">[{sym.kind}]</span>
                        <span>{sym.name}</span>
                        <span className="text-muted text-[10px]">L{sym.line_start}</span>
                        <ArrowRight className="w-2.5 h-2.5 text-muted" />
                      </button>
                    ))}
                  </div>
                )}

                {/* Snippet Preview */}
                {res.snippet && (
                  <div className="relative group rounded bg-canvas border border-line p-2 text-xs font-mono overflow-x-auto">
                    <div className="absolute right-2 top-2 opacity-0 group-hover:opacity-100 transition">
                      <button
                        type="button"
                        onClick={() => copyToClipboard(res.snippet || '', res.file_id)}
                        className="p-1 rounded bg-panel border border-line hover:bg-raised text-muted hover:text-ink cursor-pointer"
                        title={t('common.copy', 'Copy snippet')}
                      >
                        {copiedSnippetId === res.file_id ? (
                          <CheckCircle2 className="w-3.5 h-3.5 text-success" />
                        ) : (
                          <Copy className="w-3.5 h-3.5" />
                        )}
                      </button>
                    </div>
                    <pre className="text-ink text-[11px] leading-relaxed whitespace-pre-wrap">
                      {res.snippet}
                    </pre>
                  </div>
                )}

                {/* Card Footer Actions */}
                <div className="flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-line text-xs">
                  <div className="flex items-center gap-3 text-muted text-[11px]">
                    <span>{t('intelligence.loc', '{{count}} LOC', { count: res.lines_code })}</span>
                    <span>Fan-In: {res.fan_in}</span>
                    <span>Fan-Out: {res.fan_out}</span>
                  </div>

                  <div className="flex items-center gap-2">
                    {res.evidence_items.length > 0 && onSelectEvidence && (
                      <button
                        type="button"
                        onClick={() => onSelectEvidence(res.evidence_items[0].evidence_id)}
                        className="px-2.5 py-1 rounded bg-raised border border-line hover:border-accent text-ink text-xs font-medium cursor-pointer flex items-center gap-1 transition"
                      >
                        <ShieldCheck className="w-3 h-3 text-accent" />
                        <span>{t('intelligence.inspectEvidence', 'Evidence ({{count}})', { count: res.evidence_items.length })}</span>
                      </button>
                    )}
                    <button
                      type="button"
                      onClick={() => onSelectFileInStudio?.(res.file_id)}
                      className="px-2.5 py-1 rounded bg-accent-solid text-white text-xs font-medium cursor-pointer hover:opacity-90 flex items-center gap-1 transition"
                    >
                      <Layers className="w-3 h-3" />
                      <span>{t('intelligence.viewInStudio', 'View in Studio')}</span>
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : searchResponse && !isLoading ? (
          <div className="p-8 text-center bg-panel rounded-lg border border-line text-muted">
            <Search className="w-8 h-8 mx-auto mb-2 opacity-50" />
            <p className="text-xs font-medium text-ink mb-1">{t('intelligence.noResults', 'No matching modules found.')}</p>
            <p className="text-[11px]">{searchResponse.summary_text}</p>
          </div>
        ) : (
          !isLoading && (
            <div className="p-8 text-center bg-panel/50 rounded-lg border border-dashed border-line text-muted">
              <Sparkles className="w-8 h-8 mx-auto mb-2 text-accent opacity-70" />
              <p className="text-xs font-medium text-ink mb-1">
                {t('intelligence.emptyPrompt', 'Enter a natural language or symbol query to explore the repository brain.')}
              </p>
              <p className="text-[11px] max-w-md mx-auto">
                {t(
                  'intelligence.emptyHint',
                  'Examples: "PR architecture guardian rules", "fastapi app routing endpoints", "tarjan circular dependency detector"'
                )}
              </p>
            </div>
          )
        )}
      </div>
    </div>
  );
};
