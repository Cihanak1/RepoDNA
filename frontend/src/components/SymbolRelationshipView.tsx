import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  Code2,
  ExternalLink,
  Layers,
  Search,
  ShieldAlert,
  ShieldCheck,
  Split,
} from 'lucide-react';
import { fetchBrainSymbols, traceBrainSymbol } from '../api/client';
import type {
  ResolutionStatus,
  SymbolDefinition,
  SymbolReference,
  SymbolTraceResult,
} from '../types/repodna';

interface SymbolRelationshipViewProps {
  analysisId: string;
  initialSymbolId?: string | null;
  onSelectFileInStudio?: (fileId: string) => void;
  onSelectEvidence?: (evidenceId: string) => void;
}

export const SymbolRelationshipView: React.FC<SymbolRelationshipViewProps> = ({
  analysisId,
  initialSymbolId,
  onSelectFileInStudio,
  onSelectEvidence,
}) => {
  const { t } = useTranslation();
  const [searchName, setSearchName] = useState('');
  const [kindFilter, setKindFilter] = useState('');
  const [candidates, setCandidates] = useState<SymbolDefinition[]>([]);
  const [selectedSymbolId, setSelectedSymbolId] = useState<string | null>(initialSymbolId ?? null);
  const [traceResult, setTraceResult] = useState<SymbolTraceResult | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Load symbol trace whenever selectedSymbolId changes
  useEffect(() => {
    if (!selectedSymbolId) return;

    let isMounted = true;
    setIsLoading(true);
    setErrorMsg(null);

    void traceBrainSymbol(analysisId, selectedSymbolId)
      .then((res) => {
        if (isMounted) {
          setTraceResult(res);
          setIsLoading(false);
        }
      })
      .catch((err: unknown) => {
        if (isMounted) {
          setErrorMsg(err instanceof Error ? err.message : 'Failed to trace symbol.');
          setIsLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [analysisId, selectedSymbolId]);

  const handleSearchSymbols = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!searchName.trim()) return;

    setIsLoading(true);
    setErrorMsg(null);
    try {
      const resp = await fetchBrainSymbols(analysisId, {
        name: searchName.trim(),
        kind: kindFilter || undefined,
        limit: 30,
      });
      setCandidates(resp.symbols);
      if (resp.symbols.length === 1) {
        setSelectedSymbolId(resp.symbols[0].id);
      } else if (resp.symbols.length === 0) {
        setErrorMsg(t('intelligence.noSymbolsFound', 'No symbols found matching query.'));
      }
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : 'Failed to search symbols.');
    } finally {
      setIsLoading(false);
    }
  };

  const renderStatusBadge = (status: ResolutionStatus) => {
    switch (status) {
      case 'verified':
        return (
          <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-success/15 text-success border border-success/30 flex items-center gap-1">
            <CheckCircle2 className="w-2.5 h-2.5" />
            <span>{t('intelligence.verified', 'VERIFIED')}</span>
          </span>
        );
      case 'candidate':
        return (
          <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-warning/15 text-warning border border-warning/30 flex items-center gap-1">
            <AlertTriangle className="w-2.5 h-2.5" />
            <span>{t('intelligence.candidate', 'CANDIDATE')}</span>
          </span>
        );
      case 'unresolved':
      default:
        return (
          <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-muted/20 text-muted border border-line flex items-center gap-1">
            <AlertCircle className="w-2.5 h-2.5" />
            <span>{t('intelligence.unresolved', 'UNRESOLVED')}</span>
          </span>
        );
    }
  };

  return (
    <div className="flex flex-col h-full bg-canvas overflow-y-auto">
      {/* Header Search & Disambiguation Controls */}
      <div className="p-4 bg-panel border-b border-line shadow-xs shrink-0">
        <form onSubmit={handleSearchSymbols} className="flex flex-col gap-3 max-w-5xl mx-auto">
          <div className="flex items-center gap-2">
            <div className="relative flex-1">
              <Search className="w-4 h-4 text-muted absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
              <input
                type="text"
                value={searchName}
                onChange={(e) => setSearchName(e.target.value)}
                placeholder={t(
                  'intelligence.symbolSearchPlaceholder',
                  'Search symbol by identifier name (e.g. "SmartRetrievalEngine", "build_context", "execute")…'
                )}
                className="w-full pl-9 pr-4 py-2 bg-canvas border border-line rounded-md text-xs text-ink placeholder:text-muted focus:outline-hidden focus:border-accent"
              />
            </div>
            <select
              value={kindFilter}
              onChange={(e) => setKindFilter(e.target.value)}
              className="bg-canvas border border-line rounded px-2.5 py-2 text-xs text-ink cursor-pointer"
            >
              <option value="">{t('intelligence.allKinds', 'All Kinds')}</option>
              <option value="class">Class</option>
              <option value="function">Function</option>
              <option value="method">Method</option>
              <option value="interface">Interface</option>
              <option value="type">Type</option>
            </select>
            <button
              type="submit"
              disabled={isLoading || !searchName.trim()}
              className="px-4 py-2 bg-accent-solid text-white text-xs font-medium rounded-md hover:opacity-90 transition cursor-pointer flex items-center gap-1.5 shrink-0"
            >
              <Code2 className="w-3.5 h-3.5" />
              <span>{t('intelligence.lookupSymbol', 'Lookup Symbol')}</span>
            </button>
          </div>

          {/* Ambiguity Disambiguation Selector */}
          {candidates.length > 1 && (
            <div className="p-3 rounded-lg bg-raised border border-accent/40 flex flex-col gap-2">
              <div className="flex items-center gap-1.5 text-xs font-semibold text-accent">
                <Split className="w-3.5 h-3.5" />
                <span>
                  {t(
                    'intelligence.ambiguousMatches',
                    'Multiple symbols match "{{name}}" ({{count}} found). Disambiguate below:',
                    { name: searchName, count: candidates.length }
                  )}
                </span>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                {candidates.map((cand) => (
                  <button
                    key={cand.id}
                    type="button"
                    onClick={() => setSelectedSymbolId(cand.id)}
                    className={`p-2 rounded text-left border transition cursor-pointer flex flex-col gap-0.5 ${
                      selectedSymbolId === cand.id
                        ? 'bg-accent/15 border-accent text-ink'
                        : 'bg-panel border-line hover:border-accent/50 text-muted'
                    }`}
                  >
                    <div className="flex items-center justify-between text-xs font-mono">
                      <span className="font-semibold text-ink">
                        [{cand.kind}] {cand.name}
                      </span>
                      <span className="text-[10px] text-muted">L{cand.line_start}-{cand.line_end}</span>
                    </div>
                    <div className="text-[11px] font-mono text-muted truncate">{cand.file_path}</div>
                    {cand.container_name && (
                      <div className="text-[10px] text-accent">
                        {t('intelligence.inClass', 'in class {{container}}', { container: cand.container_name })}
                      </div>
                    )}
                  </button>
                ))}
              </div>
            </div>
          )}
        </form>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 p-4 max-w-5xl mx-auto w-full">
        {errorMsg && (
          <div className="p-3 mb-4 rounded-md bg-danger/10 border border-danger/30 text-danger text-xs flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{errorMsg}</span>
          </div>
        )}

        {traceResult ? (
          <div className="space-y-4">
            {/* Symbol Definition Card */}
            <div className="p-4 rounded-lg bg-panel border border-line shadow-xs flex flex-col gap-3">
              <div className="flex flex-wrap items-start justify-between gap-2 pb-3 border-b border-line">
                <div className="flex items-center gap-2">
                  <span className="px-2 py-0.5 rounded text-[11px] font-mono uppercase bg-raised text-muted font-bold">
                    {traceResult.symbol.kind}
                  </span>
                  <span className="text-sm font-mono font-bold text-ink">
                    {traceResult.symbol.name}
                  </span>
                  {traceResult.symbol.container_name && (
                    <span className="text-xs text-muted font-mono">
                      ({t('intelligence.memberOf', 'member of')} <span className="text-accent font-semibold">{traceResult.symbol.container_name}</span>)
                    </span>
                  )}
                  {traceResult.symbol.is_exported && (
                    <span className="px-1.5 py-0.2 rounded text-[10px] font-medium bg-accent/15 text-accent border border-accent/30">
                      Exported
                    </span>
                  )}
                </div>

                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => onSelectEvidence?.(traceResult.definition_evidence.evidence_id)}
                    className="px-2 py-1 rounded bg-raised border border-line hover:border-accent text-[11px] font-mono text-ink cursor-pointer flex items-center gap-1 transition"
                  >
                    <ShieldCheck className="w-3 h-3 text-accent" />
                    <span>{traceResult.definition_evidence.evidence_id}</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => onSelectFileInStudio?.(traceResult.symbol.file_path)}
                    className="px-2.5 py-1 rounded bg-accent-solid text-white text-xs font-medium cursor-pointer hover:opacity-90 flex items-center gap-1 transition"
                  >
                    <Layers className="w-3 h-3" />
                    <span>{t('intelligence.openFileInStudio', 'Studio')}</span>
                  </button>
                </div>
              </div>

              {/* Location info */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-2 text-xs">
                <div className="p-2 rounded bg-canvas border border-line">
                  <span className="text-muted block text-[10px] uppercase font-semibold">{t('intelligence.fileLocation', 'File Location')}</span>
                  <span className="font-mono text-ink truncate block">{traceResult.symbol.file_path}</span>
                  <span className="text-muted text-[11px]">Lines {traceResult.symbol.line_start}–{traceResult.symbol.line_end}</span>
                </div>
                <div className="p-2 rounded bg-canvas border border-line">
                  <span className="text-muted block text-[10px] uppercase font-semibold">{t('intelligence.downstreamImpact', 'Downstream Impact')}</span>
                  <span className="text-ink font-semibold text-xs">
                    {t('intelligence.modulesCount', '{{count}} dependent modules', { count: traceResult.downstream_impact_count })}
                  </span>
                  <div className="text-[10px] text-muted">
                    {traceResult.calling_modules.length} direct caller module(s)
                  </div>
                </div>
                <div className="p-2 rounded bg-canvas border border-line">
                  <span className="text-muted block text-[10px] uppercase font-semibold">{t('intelligence.language', 'Language')}</span>
                  <span className="text-ink font-medium">{traceResult.symbol.language}</span>
                  {traceResult.symbol.signature && (
                    <div className="font-mono text-[10px] text-muted truncate mt-0.5">
                      {traceResult.symbol.signature}
                    </div>
                  )}
                </div>
              </div>

              {/* Cycle Warning Alert */}
              {traceResult.cycle_warning && (
                <div className="p-3 rounded bg-danger/10 border border-danger/30 text-danger text-xs flex items-center gap-2">
                  <ShieldAlert className="w-4 h-4 shrink-0" />
                  <span>{traceResult.cycle_warning}</span>
                </div>
              )}
            </div>

            {/* Cross-Module Verified Callers & Usages */}
            <div className="p-4 rounded-lg bg-panel border border-line shadow-xs flex flex-col gap-3">
              <div className="flex items-center justify-between pb-2 border-b border-line">
                <div className="flex items-center gap-2">
                  <h3 className="text-xs font-bold text-ink uppercase tracking-wider">
                    {t('intelligence.verifiedCallers', 'Verified Usages & Callers (AST Proven)')}
                  </h3>
                  <span className="px-1.5 py-0.2 rounded text-[10px] font-mono bg-success/15 text-success border border-success/30 font-bold">
                    {traceResult.references.length}
                  </span>
                </div>
              </div>

              {traceResult.references.length > 0 ? (
                <div className="space-y-2">
                  {traceResult.references.map((ref: SymbolReference, idx: number) => (
                    <div
                      key={idx}
                      className="p-2.5 rounded-md bg-canvas border border-success/30 flex items-center justify-between gap-2 text-xs"
                    >
                      <div className="flex items-center gap-2">
                        {renderStatusBadge(ref.resolution_status)}
                        <span className="px-1.5 py-0.5 rounded text-[10px] font-mono uppercase bg-raised text-muted">
                          {ref.reference_kind}
                        </span>
                        <span className="font-mono text-ink font-medium">
                          {ref.file_path}:{ref.line}
                        </span>
                        {ref.source_symbol_name && (
                          <span className="text-muted text-[11px]">
                            {t('intelligence.inSymbol', 'in')} <code className="text-ink">{ref.source_symbol_name}</code>
                          </span>
                        )}
                      </div>
                      <span className="text-[11px] text-muted">{ref.confidence_reason}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-muted py-2">
                  {t('intelligence.noVerifiedCallers', 'No verified internal callers detected across repository AST.')}
                </p>
              )}
            </div>

            {/* Candidate / Unresolved References */}
            {traceResult.candidate_references.length > 0 && (
              <div className="p-4 rounded-lg bg-panel border border-line shadow-xs flex flex-col gap-3">
                <div className="flex items-center justify-between pb-2 border-b border-line">
                  <div className="flex items-center gap-2">
                    <h3 className="text-xs font-bold text-ink uppercase tracking-wider">
                      {t('intelligence.candidateReferences', 'Candidate / Potential Usages')}
                    </h3>
                    <span className="px-1.5 py-0.2 rounded text-[10px] font-mono bg-warning/15 text-warning border border-warning/30 font-bold">
                      {traceResult.candidate_references.length}
                    </span>
                  </div>
                </div>

                <div className="space-y-2">
                  {traceResult.candidate_references.map((ref: SymbolReference, idx: number) => (
                    <div
                      key={idx}
                      className="p-2.5 rounded-md bg-canvas border border-warning/30 border-dashed flex items-center justify-between gap-2 text-xs"
                    >
                      <div className="flex items-center gap-2">
                        {renderStatusBadge(ref.resolution_status)}
                        <span className="px-1.5 py-0.5 rounded text-[10px] font-mono uppercase bg-raised text-muted">
                          {ref.reference_kind}
                        </span>
                        <span className="font-mono text-ink">
                          {ref.file_path}:{ref.line}
                        </span>
                      </div>
                      <span className="text-[11px] text-muted">{ref.confidence_reason}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Downstream Blast Radius Module Grid */}
            {traceResult.downstream_dependents.length > 0 && (
              <div className="p-4 rounded-lg bg-panel border border-line shadow-xs flex flex-col gap-3">
                <h3 className="text-xs font-bold text-ink uppercase tracking-wider pb-2 border-b border-line">
                  {t('intelligence.blastRadiusModules', 'Downstream Blast Radius Modules ({{count}})', {
                    count: traceResult.downstream_dependents.length,
                  })}
                </h3>
                <div className="flex flex-wrap gap-1.5">
                  {traceResult.downstream_dependents.map((depMod, dIdx) => (
                    <button
                      key={dIdx}
                      type="button"
                      onClick={() => onSelectFileInStudio?.(depMod)}
                      className="px-2 py-1 rounded bg-canvas border border-line hover:border-accent text-ink hover:text-accent font-mono text-xs cursor-pointer flex items-center gap-1 transition"
                    >
                      <span>{depMod}</span>
                      <ExternalLink className="w-2.5 h-2.5 text-muted" />
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : !isLoading ? (
          <div className="p-8 text-center bg-panel/50 rounded-lg border border-dashed border-line text-muted">
            <Code2 className="w-8 h-8 mx-auto mb-2 text-accent opacity-70" />
            <p className="text-xs font-medium text-ink mb-1">
              {t('intelligence.symbolEmptyPrompt', 'Search for a symbol name or select one from Smart Search to inspect its relationship graph.')}
            </p>
            <p className="text-[11px] max-w-md mx-auto">
              {t(
                'intelligence.symbolEmptyHint',
                'RepoDNA proves caller-callee links via AST and distinguishes verified edges from candidate and unresolved usages.'
              )}
            </p>
          </div>
        ) : null}
      </div>
    </div>
  );
};
