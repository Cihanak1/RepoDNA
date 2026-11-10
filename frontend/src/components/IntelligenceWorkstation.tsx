import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Code2,
  Cpu,
  Search,
  ShieldCheck,
} from 'lucide-react';
import { CodeExplorerView } from './CodeExplorerView';
import { ContextPanel } from './ContextPanel';
import { EvidenceInspectorView } from './EvidenceInspectorView';
import { SymbolRelationshipView } from './SymbolRelationshipView';
import type { AnalysisResult } from '../types/repodna';
import type { WorkstationMode } from '../utils/preferences';

export type IntelligenceSubTab = 'search' | 'symbols' | 'evidence' | 'context';

interface IntelligenceWorkstationProps {
  result: AnalysisResult;
  onSelectFileInStudio: (fileId: string) => void;
  workstationMode?: WorkstationMode;
}

export const IntelligenceWorkstation: React.FC<IntelligenceWorkstationProps> = ({
  result,
  onSelectFileInStudio,
}) => {
  const { t } = useTranslation();
  const [activeSubTab, setActiveSubTab] = useState<IntelligenceSubTab>('search');
  const [activeSymbolId, setActiveSymbolId] = useState<string | null>(null);
  const [activeEvidenceId, setActiveEvidenceId] = useState<string | null>(null);

  const handleSelectSymbolForTrace = (symbolId: string) => {
    setActiveSymbolId(symbolId);
    setActiveSubTab('symbols');
  };

  const handleSelectEvidence = (evidenceId: string) => {
    setActiveEvidenceId(evidenceId);
    setActiveSubTab('evidence');
  };

  return (
    <div className="flex flex-col h-full bg-canvas overflow-hidden">
      {/* Sub-Navigation Header Bar */}
      <div className="px-4 py-2 bg-panel border-b border-line flex items-center justify-between gap-3 shrink-0">
        <div className="flex items-center gap-1.5 overflow-x-auto">
          <button
            type="button"
            onClick={() => setActiveSubTab('search')}
            className={`px-3 py-1.5 rounded-md text-xs font-medium flex items-center gap-1.5 transition cursor-pointer ${
              activeSubTab === 'search'
                ? 'bg-accent-solid text-white shadow-xs'
                : 'text-muted hover:text-ink hover:bg-raised'
            }`}
          >
            <Search className="w-3.5 h-3.5" />
            <span>{t('intelligence.tabSearch', 'Smart Search')}</span>
          </button>

          <button
            type="button"
            onClick={() => setActiveSubTab('symbols')}
            className={`px-3 py-1.5 rounded-md text-xs font-medium flex items-center gap-1.5 transition cursor-pointer ${
              activeSubTab === 'symbols'
                ? 'bg-accent-solid text-white shadow-xs'
                : 'text-muted hover:text-ink hover:bg-raised'
            }`}
          >
            <Code2 className="w-3.5 h-3.5" />
            <span>{t('intelligence.tabSymbols', 'Symbol Relations')}</span>
          </button>

          <button
            type="button"
            onClick={() => setActiveSubTab('evidence')}
            className={`px-3 py-1.5 rounded-md text-xs font-medium flex items-center gap-1.5 transition cursor-pointer ${
              activeSubTab === 'evidence'
                ? 'bg-accent-solid text-white shadow-xs'
                : 'text-muted hover:text-ink hover:bg-raised'
            }`}
          >
            <ShieldCheck className="w-3.5 h-3.5" />
            <span>{t('intelligence.tabEvidence', 'Evidence Ledger')}</span>
          </button>

          <button
            type="button"
            onClick={() => setActiveSubTab('context')}
            className={`px-3 py-1.5 rounded-md text-xs font-medium flex items-center gap-1.5 transition cursor-pointer ${
              activeSubTab === 'context'
                ? 'bg-accent-solid text-white shadow-xs'
                : 'text-muted hover:text-ink hover:bg-raised'
            }`}
          >
            <Cpu className="w-3.5 h-3.5" />
            <span>{t('intelligence.tabContext', 'Agent Context')}</span>
          </button>
        </div>

        <div className="hidden sm:flex items-center gap-2 text-xs text-muted">
          <span className="font-mono text-ink font-semibold">{result.repo_name}</span>
          <span>•</span>
          <span>{result.total_files} files</span>
          <span>•</span>
          <span>v0.5.0 Brain</span>
        </div>
      </div>

      {/* View Content */}
      <div className="flex-1 overflow-hidden">
        {activeSubTab === 'search' && (
          <CodeExplorerView
            analysisId={result.analysis_id}
            onSelectFileInStudio={onSelectFileInStudio}
            onSelectSymbolForTrace={handleSelectSymbolForTrace}
            onSelectEvidence={handleSelectEvidence}
          />
        )}

        {activeSubTab === 'symbols' && (
          <SymbolRelationshipView
            analysisId={result.analysis_id}
            initialSymbolId={activeSymbolId}
            onSelectFileInStudio={onSelectFileInStudio}
            onSelectEvidence={handleSelectEvidence}
          />
        )}

        {activeSubTab === 'evidence' && (
          <EvidenceInspectorView
            analysisId={result.analysis_id}
            initialEvidenceId={activeEvidenceId}
            onSelectFileInStudio={onSelectFileInStudio}
            onSelectSymbolForTrace={() => {
              setActiveSubTab('symbols');
            }}
          />
        )}

        {activeSubTab === 'context' && (
          <ContextPanel analysisId={result.analysis_id} result={result} />
        )}
      </div>
    </div>
  );
};
