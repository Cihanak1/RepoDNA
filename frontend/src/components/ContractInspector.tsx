import React, { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  AlertTriangle,
  BookOpen,
  RotateCcw,
  Shield,
} from 'lucide-react';
import { fetchArchitectureContract } from '../api/client';
import type { AnalysisResult, ArchitectureContract } from '../types/repodna';
import type { WorkstationMode } from '../utils/preferences';

interface ContractInspectorProps {
  result: AnalysisResult | null;
  defaultWorkspacePath: string;
  workstationMode?: WorkstationMode;
}

export const ContractInspector: React.FC<ContractInspectorProps> = ({
  result,
  defaultWorkspacePath,
}) => {
  const { t } = useTranslation();
  const [contract, setContract] = useState<ArchitectureContract | null>(null);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const targetPath = result?.target_display || defaultWorkspacePath || '.';

  const loadContract = useCallback(async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const data = await fetchArchitectureContract(targetPath);
      setContract(data);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setErrorMsg(msg);
    } finally {
      setLoading(false);
    }
  }, [targetPath]);

  useEffect(() => {
    void loadContract();
  }, [loadContract]);

  return (
    <div className="h-full flex flex-col overflow-y-auto bg-canvas text-ink p-4 sm:p-6 space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-line">
        <div>
          <div className="flex items-center gap-2">
            <Shield className="w-5 h-5 text-accent" aria-hidden="true" />
            <h1 className="text-lg font-bold tracking-tight">
              {t('contract.title', 'Architecture Contract Inspector')}
            </h1>
          </div>
          <p className="text-xs text-muted mt-1">
            {t(
              'contract.subtitle',
              'Declarative boundary policy rules defined in .repodna/architecture.yml for structural integrity.'
            )}
          </p>
        </div>

        <button
          type="button"
          onClick={() => void loadContract()}
          disabled={loading}
          className="px-3 py-1.5 rounded-lg bg-panel hover:bg-raised border border-line text-xs font-medium text-ink flex items-center gap-1.5 cursor-pointer self-start sm:self-auto shadow-xs"
        >
          <RotateCcw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} aria-hidden="true" />
          {t('common.refresh', 'Refresh Contract')}
        </button>
      </div>

      {errorMsg && (
        <div className="p-3 bg-red-500/10 border border-red-500/20 text-red-600 dark:text-red-400 rounded-lg text-xs flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 shrink-0" aria-hidden="true" />
          <span>{errorMsg}</span>
        </div>
      )}

      {loading && (
        <div className="p-8 text-center text-xs text-muted">
          <RotateCcw className="w-6 h-6 animate-spin mx-auto mb-2 text-accent" />
          {t('common.loading', 'Loading contract…')}
        </div>
      )}

      {!loading && !contract && !errorMsg && (
        <div className="p-8 text-center bg-panel border border-line rounded-xl space-y-3">
          <BookOpen className="w-10 h-10 text-muted mx-auto" aria-hidden="true" />
          <h2 className="text-sm font-semibold">
            {t('contract.notFoundTitle', 'No Architecture Contract Found')}
          </h2>
          <p className="text-xs text-muted max-w-md mx-auto">
            {t(
              'contract.notFoundDesc',
              'This repository does not have a .repodna/architecture.yml file yet. Initialize a starter policy to define layer boundaries and prohibited imports.'
            )}
          </p>
          <div className="p-3 bg-raised rounded-lg border border-line max-w-sm mx-auto font-mono text-xs text-ink select-all">
            repodna contract init
          </div>
        </div>
      )}

      {contract && (
        <div className="space-y-6">
          {/* Policy Overview Card */}
          <div className="p-4 bg-panel border border-line rounded-xl space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-2 text-xs">
                <span className="text-muted font-medium">{t('contract.policyMode', 'Policy Mode')}:</span>
                <span
                  className={`px-2.5 py-0.5 rounded-full font-bold uppercase ${
                    contract.policy.mode === 'enforce'
                      ? 'bg-red-500/15 text-red-600 dark:text-red-400 border border-red-500/20'
                      : 'bg-amber-500/15 text-amber-600 dark:text-amber-400 border border-amber-500/20'
                  }`}
                >
                  {contract.policy.mode}
                </span>
                <span className="text-muted ml-2">
                  {t('contract.unknownBehavior', 'Unknown Handling')}:{' '}
                  <strong className="text-ink">{contract.policy.unknown_behavior}</strong>
                </span>
              </div>
              <div className="text-xs text-muted">
                {t('contract.schemaVersion', 'Schema Version')}: <strong>v{contract.version}</strong>
              </div>
            </div>
          </div>

          {/* Rules List */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-xs font-bold uppercase tracking-wider text-muted">
                {t('contract.declaredRules', 'Declared Boundary Rules')} ({contract.rules.length})
              </h2>
            </div>

            {contract.rules.map((rule) => (
              <div
                key={rule.id}
                className="p-4 bg-panel border border-line rounded-xl space-y-3 hover:border-accent/40 transition"
              >
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span className="px-2 py-0.5 rounded text-[11px] font-mono font-bold bg-raised border border-line text-ink">
                      {rule.id}
                    </span>
                    <h3 className="text-sm font-semibold text-ink">{rule.title}</h3>
                  </div>
                  <span
                    className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase self-start sm:self-auto ${
                      rule.severity === 'critical'
                        ? 'bg-red-500/15 text-red-600'
                        : rule.severity === 'warning'
                        ? 'bg-amber-500/15 text-amber-600'
                        : 'bg-blue-500/15 text-blue-600'
                    }`}
                  >
                    {rule.severity}
                  </span>
                </div>

                {rule.description && (
                  <p className="text-xs text-muted">{rule.description}</p>
                )}

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2 text-xs">
                  <div className="p-2.5 bg-raised rounded-lg border border-line space-y-1">
                    <span className="text-[11px] font-semibold text-muted uppercase">
                      {t('contract.fromPatterns', 'Source Files (from)')}:
                    </span>
                    <div className="font-mono text-ink text-[11px] space-y-0.5">
                      {rule.from.map((pat, idx) => (
                        <div key={idx}>• {pat}</div>
                      ))}
                    </div>
                  </div>

                  <div className="p-2.5 bg-raised rounded-lg border border-line space-y-1">
                    <span className="text-[11px] font-semibold text-red-500 uppercase">
                      {t('contract.disallowImports', 'Prohibited Imports')}:
                    </span>
                    <div className="font-mono text-ink text-[11px] space-y-0.5">
                      {rule.disallow_imports.length > 0 ? (
                        rule.disallow_imports.map((pat, idx) => (
                          <div key={idx} className="text-red-600 dark:text-red-400">• {pat}</div>
                        ))
                      ) : (
                        <span className="text-muted">None</span>
                      )}
                    </div>
                  </div>
                </div>

                {rule.remediation && (
                  <div className="text-xs text-muted bg-raised/50 p-2 rounded border border-line/50">
                    <strong className="text-ink">{t('contract.remediation', 'Remediation')}:</strong> {rule.remediation}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
