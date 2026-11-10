import React, { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  AlertCircle,
  Check,
  Code2,
  Copy,
  Cpu,
  Download,
  Globe,
  Layers,
  RotateCcw,
  Sparkles,
} from 'lucide-react';
import {
  fetchRepositoryPassport,
  fetchRepositoryPassportV2,
  migratePassportV1ToV2,
} from '../api/client';
import type {
  AnalysisResult,
  PassportEntrypoint,
  PassportModuleRole,
  RepositoryPassport,
  RepositoryPassportV2,
} from '../types/repodna';
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
  const [selectedVersion, setSelectedVersion] = useState<'1.0' | '2.0'>('2.0');
  const [passport, setPassport] = useState<RepositoryPassport | RepositoryPassportV2 | null>(null);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [isMigrating, setIsMigrating] = useState(false);

  const analysisId = result?.analysis_id;

  const loadPassport = useCallback(async () => {
    if (!analysisId) return;
    setLoading(true);
    setErrorMsg(null);
    try {
      if (selectedVersion === '2.0') {
        const data = await fetchRepositoryPassportV2(analysisId, 200);
        setPassport(data);
      } else {
        const data = await fetchRepositoryPassport(analysisId, 200);
        setPassport(data);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setErrorMsg(msg);
    } finally {
      setLoading(false);
    }
  }, [analysisId, selectedVersion]);

  useEffect(() => {
    if (analysisId) {
      void loadPassport();
    }
  }, [analysisId, loadPassport]);

  const handleMigrate = async () => {
    if (!passport) return;
    setIsMigrating(true);
    try {
      const v2 = await migratePassportV1ToV2(JSON.stringify(passport));
      setPassport(v2);
      setSelectedVersion('2.0');
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : 'Migration failed.');
    } finally {
      setIsMigrating(false);
    }
  };

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
    link.download = `repodna-passport-${passport.repo_name}-v${passport.schema_version}.json`;
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

  const isV2 = passport?.schema_version === '2.0.0';
  const v2Passport = isV2 ? (passport as RepositoryPassportV2) : null;

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
            <span className="px-2 py-0.5 rounded text-[11px] font-mono font-bold bg-raised border border-line">
              v{passport?.schema_version ?? selectedVersion}
            </span>
          </div>
          <p className="text-xs text-muted mt-1">
            {t(
              'passport.subtitle',
              'Portable, verified architectural identity manifest for AI coding agents and engineering teams.'
            )}
          </p>
        </div>

        {/* Top Controls Bar */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Version Switcher */}
          <div className="flex rounded-md p-0.5 bg-raised border border-line text-xs">
            <button
              type="button"
              onClick={() => setSelectedVersion('1.0')}
              className={`px-2.5 py-1 rounded text-xs font-medium cursor-pointer transition ${
                selectedVersion === '1.0'
                  ? 'bg-panel text-ink shadow-xs font-semibold'
                  : 'text-muted hover:text-ink'
              }`}
            >
              v1.0 (Legacy)
            </button>
            <button
              type="button"
              onClick={() => setSelectedVersion('2.0')}
              className={`px-2.5 py-1 rounded text-xs font-medium cursor-pointer transition ${
                selectedVersion === '2.0'
                  ? 'bg-accent-solid text-white shadow-xs font-semibold'
                  : 'text-muted hover:text-ink'
              }`}
            >
              v2.0 (Brain)
            </button>
          </div>

          {!isV2 && (
            <button
              type="button"
              onClick={handleMigrate}
              disabled={isMigrating || !passport}
              className="px-3 py-1.5 rounded-lg bg-raised hover:bg-panel border border-accent/40 text-xs font-medium text-accent flex items-center gap-1.5 cursor-pointer shadow-xs disabled:opacity-50"
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span>{isMigrating ? 'Migrating…' : 'Migrate to v2'}</span>
            </button>
          )}

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
                <div className="font-mono font-medium text-ink truncate mt-0.5 flex items-center gap-1.5">
                  <span className="truncate">{passport.git_revision}</span>
                  {passport.provenance_verified ? (
                    <span className="text-[9px] px-1 py-0.5 bg-emerald-500/15 text-emerald-600 rounded shrink-0">SHA</span>
                  ) : (
                    <span className="text-[9px] px-1 py-0.5 bg-amber-500/15 text-amber-600 rounded shrink-0">unverified</span>
                  )}
                </div>
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

          {/* v2.0 Additions: Symbol Index Summary */}
          {v2Passport?.symbol_index_summary && (
            <div className="p-5 bg-panel border border-line rounded-xl space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-xs font-bold text-ink uppercase tracking-wider flex items-center gap-2">
                  <Code2 className="w-4 h-4 text-accent" />
                  <span>Symbol Intelligence Summary (Repository Brain)</span>
                </h3>
                <span className="px-2 py-0.5 rounded text-[11px] font-mono bg-raised text-muted">
                  {v2Passport.symbol_index_summary.total_symbols} total symbols
                </span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
                <div className="p-3 rounded bg-canvas border border-line">
                  <span className="text-muted block text-[10px] uppercase font-semibold">Verified References</span>
                  <div className="text-base font-mono font-bold text-success mt-0.5">
                    {v2Passport.symbol_index_summary.total_verified_references}
                  </div>
                  <span className="text-[10px] text-muted">Proven AST edges</span>
                </div>
                <div className="p-3 rounded bg-canvas border border-line">
                  <span className="text-muted block text-[10px] uppercase font-semibold">Candidate References</span>
                  <div className="text-base font-mono font-bold text-warning mt-0.5">
                    {v2Passport.symbol_index_summary.total_candidate_references}
                  </div>
                  <span className="text-[10px] text-muted">Potential call sites</span>
                </div>
                <div className="p-3 rounded bg-canvas border border-line">
                  <span className="text-muted block text-[10px] uppercase font-semibold">Unresolved References</span>
                  <div className="text-base font-mono font-bold text-muted mt-0.5">
                    {v2Passport.symbol_index_summary.total_unresolved_references}
                  </div>
                  <span className="text-[10px] text-muted">External or dynamic</span>
                </div>
              </div>

              {Object.keys(v2Passport.symbol_index_summary.symbols_by_kind).length > 0 && (
                <div className="flex flex-wrap gap-2 pt-2 border-t border-line/60 text-xs">
                  <span className="text-muted text-[11px] self-center">Symbols by Kind:</span>
                  {Object.entries(v2Passport.symbol_index_summary.symbols_by_kind).map(([k, count]) => (
                    <span key={k} className="px-2 py-0.5 rounded bg-raised border border-line font-mono text-[11px] text-ink">
                      <span className="text-muted uppercase font-semibold">{k}:</span> {count}
                    </span>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* v2.0 Additions: Architectural Entrypoints */}
          {v2Passport?.architectural_entrypoints && v2Passport.architectural_entrypoints.length > 0 && (
            <div className="p-5 bg-panel border border-line rounded-xl space-y-3">
              <h3 className="text-xs font-bold text-ink uppercase tracking-wider flex items-center gap-2">
                <Layers className="w-4 h-4 text-accent" />
                <span>Architectural Entrypoints</span>
              </h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2">
                {v2Passport.architectural_entrypoints.map((ep: PassportEntrypoint, i: number) => (
                  <div key={i} className="p-3 rounded bg-canvas border border-line flex flex-col gap-1 text-xs">
                    <div className="flex items-center justify-between">
                      <span className="px-1.5 py-0.5 rounded text-[10px] font-mono uppercase bg-accent/15 text-accent font-bold">
                        {ep.role}
                      </span>
                      {ep.evidence_id && (
                        <span className="text-[10px] font-mono text-muted">{ep.evidence_id}</span>
                      )}
                    </div>
                    <div className="font-mono text-ink text-xs truncate mt-0.5">{ep.file_path}</div>
                    {ep.primary_symbol && (
                      <div className="text-[10px] font-mono text-muted truncate">
                        Primary: <span className="text-ink font-semibold">{ep.primary_symbol}</span>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* v2.0 Additions: Major Module Roles */}
          {v2Passport?.major_module_roles && v2Passport.major_module_roles.length > 0 && (
            <div className="p-5 bg-panel border border-line rounded-xl space-y-3">
              <h3 className="text-xs font-bold text-ink uppercase tracking-wider flex items-center gap-2">
                <Cpu className="w-4 h-4 text-accent" />
                <span>Major Module Roles</span>
              </h3>
              <div className="space-y-1.5">
                {v2Passport.major_module_roles.map((mr: PassportModuleRole, i: number) => (
                  <div key={i} className="p-2.5 rounded bg-canvas border border-line flex items-center justify-between gap-3 text-xs">
                    <div className="flex items-center gap-2 min-w-0">
                      <span className="px-1.5 py-0.5 rounded text-[10px] font-mono uppercase bg-raised text-muted font-bold shrink-0">
                        {mr.role}
                      </span>
                      <span className="font-mono text-ink font-semibold truncate">{mr.file_path}</span>
                    </div>
                    <span className="text-[11px] text-muted shrink-0 max-w-[50%] text-right truncate">
                      {mr.responsibility}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Primary Languages Table */}
          <div className="p-5 bg-panel border border-line rounded-xl space-y-3">
            <h3 className="text-xs font-bold text-ink uppercase tracking-wider">
              {t('passport.languages', 'Primary Languages')}
            </h3>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="border-b border-line text-muted">
                    <th className="py-2 pr-4">{t('passport.language', 'Language')}</th>
                    <th className="py-2 pr-4">{t('passport.supportLevel', 'Support Level')}</th>
                    <th className="py-2 pr-4 text-right">{t('passport.files', 'Files')}</th>
                    <th className="py-2 pr-4 text-right">{t('passport.loc', 'LOC')}</th>
                    <th className="py-2 text-right">{t('passport.share', 'Code %')}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line/60">
                  {passport.primary_languages.map((l, i) => (
                    <tr key={i} className="hover:bg-raised/40">
                      <td className="py-2 pr-4 font-medium text-ink">{l.language}</td>
                      <td className="py-2 pr-4">
                        <span className="font-mono text-[11px] px-1.5 py-0.5 rounded bg-raised text-muted">
                          {l.support_level}
                        </span>
                      </td>
                      <td className="py-2 pr-4 text-right font-mono text-muted">{l.file_count}</td>
                      <td className="py-2 pr-4 text-right font-mono text-muted">{l.lines_code.toLocaleString()}</td>
                      <td className="py-2 text-right font-mono font-medium text-ink">{l.percentage}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Architectural Hubs (High Fan-In) */}
          <div className="p-5 bg-panel border border-line rounded-xl space-y-3">
            <h3 className="text-xs font-bold text-ink uppercase tracking-wider">
              {t('passport.hubs', 'Architectural Hubs (Highest Fan-In / Impact)')}
            </h3>
            {passport.architectural_hubs.length > 0 ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2">
                {passport.architectural_hubs.slice(0, 12).map((h, i) => (
                  <div key={i} className="p-3 bg-canvas border border-line rounded-lg text-xs space-y-1">
                    <div className="font-mono font-medium text-ink truncate">{h.file_id}</div>
                    <div className="flex items-center justify-between text-[11px] text-muted">
                      <span>Fan-In: <strong className="text-ink">{h.fan_in}</strong></span>
                      <span>Fan-Out: <strong className="text-ink">{h.fan_out}</strong></span>
                      <span>Instability: <strong className="text-ink">{h.instability.toFixed(2)}</strong></span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-muted">{t('passport.noHubs', 'No architectural hubs detected.')}</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
