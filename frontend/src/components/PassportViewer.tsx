import React, { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  AlertCircle,
  Check,
  Copy,
  Download,
  Globe,
  Layers,
  RotateCcw,
} from 'lucide-react';
import { fetchRepositoryPassport } from '../api/client';
import type { AnalysisResult, RepositoryPassport } from '../types/repodna';
import type { WorkstationMode } from '../utils/preferences';

interface PassportViewerProps {
  result: AnalysisResult | null;
  defaultWorkspacePath: string;
  workstationMode?: WorkstationMode;
}

export const PassportViewer: React.FC<PassportViewerProps> = ({
  result,
}) => {
  const { t } = useTranslation();
  const [passport, setPassport] = useState<RepositoryPassport | null>(null);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');

  const analysisId = result?.analysis_id;

  const loadPassport = useCallback(async () => {
    if (!analysisId) return;
    setLoading(true);
    setErrorMsg(null);
    try {
      const data = await fetchRepositoryPassport(analysisId, 200);
      setPassport(data);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setErrorMsg(msg);
    } finally {
      setLoading(false);
    }
  }, [analysisId]);

  useEffect(() => {
    if (analysisId) {
      void loadPassport();
    }
  }, [analysisId, loadPassport]);

  const handleCopyJson = () => {
    if (!passport) return;
    void navigator.clipboard.writeText(JSON.stringify(passport, null, 2));
    setCopied(true);
    window.setTimeout(() => setCopied(false), 2000);
  };

  const handleDownloadJson = () => {
    if (!passport) return;
    const blob = new Blob([JSON.stringify(passport, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `repodna-passport-${passport.repo_name}.json`;
    link.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  };

  if (!result) {
    return (
      <div className="h-full flex items-center justify-center p-8 text-center text-muted text-xs">
        {t('passport.noAnalysis', 'Analyze a repository to view its structural Repository Passport.')}
      </div>
    );
  }

  const filteredInventory = passport?.module_inventory.filter((m) =>
    m.id.toLowerCase().includes(searchTerm.toLowerCase())
  ) || [];

  return (
    <div className="h-full flex flex-col overflow-y-auto bg-canvas text-ink p-4 sm:p-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-line">
        <div>
          <div className="flex items-center gap-2">
            <Globe className="w-5 h-5 text-accent" aria-hidden="true" />
            <h1 className="text-lg font-bold tracking-tight">
              {t('passport.title', 'Repository Passport')}
            </h1>
          </div>
          <p className="text-xs text-muted mt-1">
            {t(
              'passport.subtitle',
              'Portable, verified architectural identity manifest for AI coding agents and engineering teams.'
            )}
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handleCopyJson}
            disabled={!passport}
            className="px-3 py-1.5 rounded-lg bg-panel hover:bg-raised border border-line text-xs font-medium text-ink flex items-center gap-1.5 cursor-pointer shadow-xs disabled:opacity-50"
          >
            {copied ? <Check className="w-3.5 h-3.5 text-emerald-500" /> : <Copy className="w-3.5 h-3.5 text-muted" />}
            {copied ? t('common.copied', 'Copied!') : t('passport.copyJson', 'Copy JSON')}
          </button>
          <button
            type="button"
            onClick={handleDownloadJson}
            disabled={!passport}
            className="px-3 py-1.5 rounded-lg bg-accent-solid text-white text-xs font-medium flex items-center gap-1.5 cursor-pointer shadow-xs hover:opacity-90 disabled:opacity-50"
          >
            <Download className="w-3.5 h-3.5" />
            {t('passport.downloadJson', 'Download Manifest')}
          </button>
        </div>
      </div>

      {errorMsg && (
        <div className="p-3 bg-red-500/10 border border-red-500/20 text-red-600 dark:text-red-400 rounded-lg text-xs flex items-center gap-2">
          <AlertCircle className="w-4 h-4 shrink-0" aria-hidden="true" />
          <span>{errorMsg}</span>
        </div>
      )}

      {loading && (
        <div className="p-8 text-center text-xs text-muted">
          <RotateCcw className="w-6 h-6 animate-spin mx-auto mb-2 text-accent" />
          {t('common.loading', 'Loading passport manifest…')}
        </div>
      )}

      {passport && (
        <div className="space-y-6">
          {/* Passport Identity Card */}
          <div className="p-5 bg-panel border border-line rounded-xl space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div>
                <span className="text-[11px] font-mono uppercase tracking-wider text-muted">
                  Schema v{passport.schema_version} • RepoDNA v{passport.repodna_version}
                </span>
                <h2 className="text-base font-bold text-ink mt-0.5">{passport.repo_name}</h2>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-xs text-muted">{t('passport.confidence', 'Confidence')}:</span>
                <span className="px-2.5 py-0.5 rounded-full text-xs font-bold uppercase bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
                  {passport.confidence}
                </span>
              </div>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs border-t border-line/60 pt-3">
              <div>
                <span className="text-muted">{t('passport.gitRevision', 'Git Revision')}:</span>
                <div className="font-mono font-medium text-ink truncate mt-0.5">{passport.git_revision}</div>
              </div>
              <div>
                <span className="text-muted">{t('passport.astCoverage', 'AST Coverage')}:</span>
                <div className="font-bold text-ink mt-0.5">
                  {passport.ast_coverage.ast_loc_coverage_pct.toFixed(1)}% LOC
                </div>
              </div>
              <div>
                <span className="text-muted">{t('passport.healthGrade', 'Health Grade')}:</span>
                <div className="font-bold text-ink mt-0.5">
                  {passport.architecture_health.score ?? 'N/A'} ({passport.architecture_health.grade})
                </div>
              </div>
              <div>
                <span className="text-muted">{t('passport.modulesCount', 'Total Modules')}:</span>
                <div className="font-bold text-ink mt-0.5">{passport.dependency_summary.total_modules}</div>
              </div>
            </div>

            {passport.identified_boundaries.length > 0 && (
              <div className="border-t border-line/60 pt-3 text-xs">
                <span className="text-muted font-medium mr-2">
                  {t('passport.boundaries', 'Identified Boundaries')}:
                </span>
                <div className="inline-flex flex-wrap gap-1.5 mt-1">
                  {passport.identified_boundaries.map((b, i) => (
                    <span
                      key={i}
                      className="px-2 py-0.5 rounded bg-raised border border-line font-mono text-[11px] text-ink"
                    >
                      {b}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Architectural Hubs Table */}
          {passport.architectural_hubs.length > 0 && (
            <div className="p-4 bg-panel border border-line rounded-xl space-y-3">
              <h2 className="text-xs font-bold uppercase tracking-wider text-muted flex items-center gap-1.5">
                <Layers className="w-4 h-4 text-accent" />
                {t('passport.hubsTitle', 'Architectural Hubs (Highest Fan-In / Impact)')} ({passport.architectural_hubs.length})
              </h2>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs border-collapse">
                  <thead>
                    <tr className="border-b border-line text-muted">
                      <th className="py-2 px-2 font-medium">{t('passport.modulePath', 'Module Path')}</th>
                      <th className="py-2 px-2 font-medium">{t('passport.fanIn', 'Fan-In (Dependents)')}</th>
                      <th className="py-2 px-2 font-medium">{t('passport.fanOut', 'Fan-Out (Imports)')}</th>
                      <th className="py-2 px-2 font-medium">{t('passport.instability', 'Instability (I)')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {passport.architectural_hubs.map((hub, idx) => (
                      <tr key={idx} className="border-b border-line/40 hover:bg-raised">
                        <td className="py-2 px-2 font-mono font-medium text-ink">{hub.file_id}</td>
                        <td className="py-2 px-2 font-bold text-accent">{hub.fan_in}</td>
                        <td className="py-2 px-2 text-muted">{hub.fan_out}</td>
                        <td className="py-2 px-2 font-mono text-muted">{hub.instability.toFixed(2)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Module Inventory */}
          <div className="p-4 bg-panel border border-line rounded-xl space-y-3">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <h2 className="text-xs font-bold uppercase tracking-wider text-muted">
                {t('passport.inventoryTitle', 'Indexed Module Inventory')} ({filteredInventory.length})
              </h2>
              <input
                type="text"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                placeholder={t('passport.searchPlaceholder', 'Filter modules…')}
                className="px-2.5 py-1 rounded-lg bg-raised border border-line text-xs font-mono text-ink placeholder:text-muted focus:outline-none w-48"
              />
            </div>

            <div className="max-h-80 overflow-y-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead className="sticky top-0 bg-panel border-b border-line text-muted">
                  <tr>
                    <th className="py-2 px-2 font-medium">{t('passport.module', 'Module')}</th>
                    <th className="py-2 px-2 font-medium">{t('passport.language', 'Lang')}</th>
                    <th className="py-2 px-2 font-medium">{t('passport.loc', 'LOC')}</th>
                    <th className="py-2 px-2 font-medium">{t('passport.fanIn', 'Fan-In')}</th>
                    <th className="py-2 px-2 font-medium">{t('passport.fanOut', 'Fan-Out')}</th>
                    <th className="py-2 px-2 font-medium">{t('passport.status', 'Status')}</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredInventory.slice(0, 100).map((m, idx) => (
                    <tr key={idx} className="border-b border-line/30 hover:bg-raised">
                      <td className="py-1.5 px-2 font-mono text-ink truncate max-w-xs">{m.id}</td>
                      <td className="py-1.5 px-2 text-muted">{m.language}</td>
                      <td className="py-1.5 px-2 font-mono text-muted">{m.lines_code}</td>
                      <td className="py-1.5 px-2 font-mono text-muted">{m.fan_in}</td>
                      <td className="py-1.5 px-2 font-mono text-muted">{m.fan_out}</td>
                      <td className="py-1.5 px-2">
                        {m.is_hub && (
                          <span className="px-1.5 py-0.5 rounded text-[10px] bg-accent/15 text-accent font-semibold mr-1">
                            HUB
                          </span>
                        )}
                        {m.in_cycle && (
                          <span className="px-1.5 py-0.5 rounded text-[10px] bg-red-500/15 text-red-500 font-semibold">
                            CYCLE
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
