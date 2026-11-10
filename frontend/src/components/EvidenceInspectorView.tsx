import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Code2,
  Copy,
  ExternalLink,
  FileCode,
  FileX,
  GitCommit,
  RefreshCw,
  Search,
  ShieldCheck,
} from 'lucide-react';
import { fetchBrainEvidence, fetchBrainEvidenceItem } from '../api/client';
import type {
  EvidenceLedgerResponse,
  EvidenceReference,
  StalenessReason,
} from '../types/repodna';

interface EvidenceInspectorViewProps {
  analysisId: string;
  initialEvidenceId?: string | null;
  onSelectFileInStudio?: (fileId: string) => void;
  onSelectSymbolForTrace?: (symbolName: string) => void;
}

export const EvidenceInspectorView: React.FC<EvidenceInspectorViewProps> = ({
  analysisId,
  initialEvidenceId,
  onSelectFileInStudio,
  onSelectSymbolForTrace,
}) => {
  const { t } = useTranslation();
  const [filePathFilter, setFilePathFilter] = useState('');
  const [symbolFilter, setSymbolFilter] = useState('');
  const [stalenessFilter, setStalenessFilter] = useState<string>('');
  const [evidenceTypeFilter, setEvidenceTypeFilter] = useState<string>('');
  const [ledgerResponse, setLedgerResponse] = useState<EvidenceLedgerResponse | null>(null);
  const [selectedEvidence, setSelectedEvidence] = useState<EvidenceReference | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [copiedSnippet, setCopiedSnippet] = useState(false);

  const loadLedger = async () => {
    setIsLoading(true);
    setErrorMsg(null);
    try {
      const resp = await fetchBrainEvidence(analysisId, {
        file_path: filePathFilter.trim() || undefined,
        symbol_name: symbolFilter.trim() || undefined,
        evidence_type: evidenceTypeFilter || undefined,
        check_staleness: true,
        limit: 100,
      });
      setLedgerResponse(resp);
      if (resp.evidence_items.length > 0 && !selectedEvidence) {
        setSelectedEvidence(resp.evidence_items[0]);
      }
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : 'Failed to load evidence ledger.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    void loadLedger();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [analysisId, evidenceTypeFilter]);

  useEffect(() => {
    if (!initialEvidenceId) return;
    void fetchBrainEvidenceItem(analysisId, initialEvidenceId, true)
      .then((item) => setSelectedEvidence(item))
      .catch(() => {});
  }, [analysisId, initialEvidenceId]);

  const copySnippet = (code: string) => {
    void navigator.clipboard.writeText(code);
    setCopiedSnippet(true);
    setTimeout(() => setCopiedSnippet(false), 1800);
  };

  const renderStalenessBadge = (reason: StalenessReason) => {
    switch (reason) {
      case 'fresh':
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-success/15 text-success border border-success/30 flex items-center gap-1">
            <CheckCircle2 className="w-3 h-3" />
            <span>FRESH</span>
          </span>
        );
      case 'line_shift':
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-warning/15 text-warning border border-warning/30 flex items-center gap-1">
            <Clock className="w-3 h-3" />
            <span>LINE SHIFT</span>
          </span>
        );
      case 'content_changed':
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-danger/15 text-danger border border-danger/30 flex items-center gap-1">
            <AlertTriangle className="w-3 h-3" />
            <span>CONTENT CHANGED</span>
          </span>
        );
      case 'revision_mismatch':
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-accent/15 text-accent border border-accent/30 flex items-center gap-1">
            <GitCommit className="w-3 h-3" />
            <span>REVISION MISMATCH</span>
          </span>
        );
      case 'file_deleted':
      default:
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-muted/20 text-muted border border-line flex items-center gap-1">
            <FileX className="w-3 h-3" />
            <span>FILE DELETED</span>
          </span>
        );
    }
  };

  const filteredItems = (ledgerResponse?.evidence_items || []).filter((item) => {
    if (stalenessFilter && item.staleness_reason !== stalenessFilter) return false;
    return true;
  });

  return (
    <div className="flex flex-col h-full bg-canvas overflow-hidden">
      {/* Search & Filter Header */}
      <div className="p-4 bg-panel border-b border-line shadow-xs shrink-0">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void loadLedger();
          }}
          className="flex flex-col gap-3 max-w-7xl mx-auto"
        >
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-accent" />
              <h2 className="text-sm font-bold text-ink">
                {t('intelligence.evidenceLedger', 'Architectural Evidence Ledger')}
              </h2>
              {ledgerResponse && (
                <span className="px-2 py-0.5 rounded-full text-[11px] font-mono bg-raised border border-line text-muted">
                  {ledgerResponse.total_evidence} total citations ({ledgerResponse.stale_count} stale)
                </span>
              )}
            </div>

            <button
              type="button"
              data-testid="verify-staleness-btn"
              onClick={() => void loadLedger()}
              className="px-3 py-1.5 rounded-md bg-raised border border-line hover:border-accent text-xs font-medium text-ink cursor-pointer flex items-center gap-1.5 transition"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
              <span>{t('intelligence.verifyStaleness', 'Verify Staleness')}</span>
            </button>
          </div>

          <div className="flex flex-wrap items-center gap-2 text-xs">
            <div className="relative min-w-[200px] flex-1">
              <Search className="w-3.5 h-3.5 text-muted absolute left-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
              <input
                type="text"
                value={filePathFilter}
                onChange={(e) => setFilePathFilter(e.target.value)}
                placeholder={t('intelligence.filterByFilePath', 'Filter by file path (e.g. backend/api)…')}
                className="w-full pl-8 pr-3 py-1.5 bg-canvas border border-line rounded text-xs text-ink placeholder:text-muted"
              />
            </div>

            <input
              type="text"
              value={symbolFilter}
              onChange={(e) => setSymbolFilter(e.target.value)}
              placeholder={t('intelligence.filterBySymbol', 'Symbol name…')}
              className="px-3 py-1.5 bg-canvas border border-line rounded text-xs text-ink placeholder:text-muted max-w-[160px]"
            />

            <select
              value={stalenessFilter}
              onChange={(e) => setStalenessFilter(e.target.value)}
              className="bg-canvas border border-line rounded px-2.5 py-1.5 text-xs text-ink cursor-pointer"
            >
              <option value="">{t('intelligence.allStaleness', 'All Staleness Statuses')}</option>
              <option value="fresh">Fresh (Verified)</option>
              <option value="line_shift">Line Shift</option>
              <option value="content_changed">Content Changed</option>
              <option value="revision_mismatch">Revision Mismatch</option>
              <option value="file_deleted">File Deleted</option>
            </select>

            <select
              value={evidenceTypeFilter}
              onChange={(e) => setEvidenceTypeFilter(e.target.value)}
              className="bg-canvas border border-line rounded px-2.5 py-1.5 text-xs text-ink cursor-pointer"
            >
              <option value="">{t('intelligence.allEvidenceTypes', 'All Evidence Types')}</option>
              <option value="symbol_definition">Symbol Definition</option>
              <option value="symbol_reference">Symbol Reference</option>
              <option value="import_statement">Import Statement</option>
              <option value="dependency_edge">Dependency Edge</option>
              <option value="architectural_hub">Architectural Hub</option>
              <option value="contract_violation">Contract Violation</option>
              <option value="cycle_participation">Cycle Participation</option>
            </select>

            <button
              type="submit"
              className="px-3 py-1.5 bg-accent-solid text-white text-xs font-medium rounded hover:opacity-90 transition cursor-pointer"
            >
              {t('common.filter', 'Filter')}
            </button>
          </div>
        </form>
      </div>

      {/* Two-Pane Master Detail Layout */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Pane: Evidence Items List */}
        <div className="w-1/2 border-r border-line bg-canvas overflow-y-auto p-3 space-y-2">
          {errorMsg && (
            <div className="p-3 mb-2 rounded bg-danger/10 border border-danger/30 text-danger text-xs flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{errorMsg}</span>
            </div>
          )}

          {filteredItems.map((ev) => (
            <button
              key={ev.evidence_id}
              type="button"
              data-testid="evidence-item-btn"
              onClick={() => setSelectedEvidence(ev)}
              className={`w-full p-3 rounded-lg border text-left transition cursor-pointer flex flex-col gap-1.5 ${
                selectedEvidence?.evidence_id === ev.evidence_id
                  ? 'bg-panel border-accent shadow-xs'
                  : 'bg-panel/70 border-line hover:border-line-hover hover:bg-panel'
              }`}
            >
              <div className="flex items-center justify-between text-xs font-mono">
                <span className="font-semibold text-ink flex items-center gap-1.5">
                  <ShieldCheck className="w-3.5 h-3.5 text-accent" />
                  <span>{ev.evidence_id}</span>
                </span>
                {renderStalenessBadge(ev.staleness_reason)}
              </div>

              <div className="text-xs font-mono text-ink truncate">
                {ev.file_path}:{ev.line_start}–{ev.line_end}
              </div>

              <div className="flex items-center justify-between text-[11px] text-muted">
                <span className="uppercase text-[10px] font-semibold text-muted">
                  {ev.evidence_type.replace(/_/g, ' ')}
                </span>
                {ev.symbol_name && (
                  <span className="font-mono text-accent">sym: {ev.symbol_name}</span>
                )}
              </div>
            </button>
          ))}

          {filteredItems.length === 0 && !isLoading && (
            <div className="p-8 text-center text-muted text-xs">
              {t('intelligence.noEvidenceFound', 'No evidence citations match current filters.')}
            </div>
          )}
        </div>

        {/* Right Pane: Detailed Inspection Drawer */}
        <div className="w-1/2 bg-panel overflow-y-auto p-4 flex flex-col gap-4">
          {selectedEvidence ? (
            <>
              {/* Evidence Detail Header */}
              <div className="flex items-start justify-between pb-3 border-b border-line gap-2">
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="text-sm font-mono font-bold text-ink">
                      {selectedEvidence.evidence_id}
                    </h3>
                    {renderStalenessBadge(selectedEvidence.staleness_reason)}
                  </div>
                  <div className="text-xs font-mono text-muted mt-0.5">
                    Git Revision: <span className="text-ink font-semibold">{selectedEvidence.repository_revision}</span>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  {selectedEvidence.symbol_name && onSelectSymbolForTrace && (
                    <button
                      type="button"
                      onClick={() => onSelectSymbolForTrace(selectedEvidence.symbol_name || '')}
                      className="px-2.5 py-1 rounded bg-raised border border-line hover:border-accent text-xs font-medium text-ink cursor-pointer flex items-center gap-1 transition"
                    >
                      <Code2 className="w-3 h-3" />
                      <span>{t('intelligence.traceSymbol', 'Trace Symbol')}</span>
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={() => onSelectFileInStudio?.(selectedEvidence.file_path)}
                    className="px-2.5 py-1 rounded bg-accent-solid text-white text-xs font-medium cursor-pointer hover:opacity-90 flex items-center gap-1 transition"
                  >
                    <ExternalLink className="w-3 h-3" />
                    <span>{t('intelligence.viewInStudio', 'View in Studio')}</span>
                  </button>
                </div>
              </div>

              {/* Staleness Explanation Details */}
              {selectedEvidence.staleness_details && (
                <div
                  className={`p-3 rounded text-xs border ${
                    selectedEvidence.is_stale
                      ? 'bg-warning/10 border-warning/30 text-warning'
                      : 'bg-success/10 border-success/30 text-success'
                  }`}
                >
                  <div className="font-semibold mb-0.5">{t('intelligence.stalenessCheck', 'Staleness Verification')}:</div>
                  <div>{selectedEvidence.staleness_details}</div>
                  {selectedEvidence.line_shift_delta !== null && selectedEvidence.line_shift_delta !== undefined && selectedEvidence.line_shift_delta !== 0 && (
                    <div className="mt-1 font-mono text-[11px]">
                      Shift delta: {selectedEvidence.line_shift_delta > 0 ? `+${selectedEvidence.line_shift_delta}` : selectedEvidence.line_shift_delta} lines
                    </div>
                  )}
                </div>
              )}

              {/* Coordinates & Metadata */}
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div className="p-2.5 rounded bg-canvas border border-line">
                  <span className="text-muted block text-[10px] uppercase font-semibold">{t('intelligence.filePath', 'File Path')}</span>
                  <span className="font-mono text-ink text-xs truncate block">{selectedEvidence.file_path}</span>
                  <span className="text-muted text-[11px]">Lines {selectedEvidence.line_start}–{selectedEvidence.line_end}</span>
                </div>
                <div className="p-2.5 rounded bg-canvas border border-line">
                  <span className="text-muted block text-[10px] uppercase font-semibold">{t('intelligence.evidenceType', 'Evidence Type')}</span>
                  <span className="font-mono text-ink text-xs capitalize">{selectedEvidence.evidence_type.replace(/_/g, ' ')}</span>
                  <span className="text-muted text-[11px] block">{selectedEvidence.support_level}</span>
                </div>
              </div>

              {/* Confidence Reason */}
              <div className="p-3 rounded bg-canvas border border-line text-xs">
                <div className="text-[11px] font-semibold text-muted uppercase mb-1">{t('intelligence.confidenceReason', 'Validity Proof & Rationale')}</div>
                <div className="text-ink leading-relaxed">{selectedEvidence.confidence_reason}</div>
              </div>

              {/* Code Snippet Box */}
              {selectedEvidence.code_snippet ? (
                <div className="flex flex-col gap-1.5">
                  <div className="flex items-center justify-between text-xs text-muted">
                    <span className="font-semibold text-ink flex items-center gap-1">
                      <FileCode className="w-3.5 h-3.5" />
                      <span>{t('intelligence.sourceSnippet', 'Source Code Snippet')}</span>
                    </span>
                    <button
                      type="button"
                      onClick={() => copySnippet(selectedEvidence.code_snippet || '')}
                      className="px-2 py-0.5 rounded bg-raised border border-line hover:border-accent text-[11px] text-ink cursor-pointer flex items-center gap-1 transition"
                    >
                      {copiedSnippet ? (
                        <>
                          <CheckCircle2 className="w-3 h-3 text-success" />
                          <span>Copied</span>
                        </>
                      ) : (
                        <>
                          <Copy className="w-3 h-3" />
                          <span>Copy</span>
                        </>
                      )}
                    </button>
                  </div>

                  <div className="rounded bg-canvas border border-line p-3 font-mono text-xs overflow-x-auto">
                    <pre className="text-ink leading-relaxed whitespace-pre-wrap">
                      {selectedEvidence.code_snippet}
                    </pre>
                  </div>
                </div>
              ) : (
                <div className="p-4 rounded bg-canvas border border-dashed border-line text-xs text-muted text-center">
                  {t('intelligence.noSnippetAvailable', 'No snippet captured for this evidence citation.')}
                </div>
              )}
            </>
          ) : (
            <div className="p-8 text-center text-muted text-xs my-auto">
              {t('intelligence.selectEvidencePrompt', 'Select an evidence reference from the left pane to view details and live staleness verification.')}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
