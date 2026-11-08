import React, { useEffect, useRef, useState } from 'react';
import {
  Activity,
  Command,
  Download,
  FileCode2,
  FolderOpen,
  GitBranch,
  Github,
  Moon,
  Play,
  Settings2,
  ShieldCheck,
  Sparkles,
  Square,
  Sun,
  X,
} from 'lucide-react';
import { getExportUrl } from '../api/client';
import type { AnalysisResult, ScanLimits, ScanProgress, SourceType } from '../types/repodna';

interface HeaderBarProps {
  sourceType: SourceType;
  onSourceTypeChange: (st: SourceType) => void;
  targetInput: string;
  onTargetInputChange: (val: string) => void;
  branchInput: string;
  onBranchInputChange: (val: string) => void;
  limits: ScanLimits;
  onLimitsChange: (limits: ScanLimits) => void;
  onTriggerScan: (overrideSource?: SourceType, overrideTarget?: string) => void;
  onOpenFolderBrowser: () => void;
  activeJob: ScanProgress | null;
  onCancelJob: () => void;
  result: AnalysisResult | null;
  activeTab: 'studio' | 'report';
  onTabChange: (tab: 'studio' | 'report') => void;
  defaultWorkspacePath: string;
  onOpenCommandPalette: () => void;
}

export const HeaderBar: React.FC<HeaderBarProps> = ({
  sourceType,
  onSourceTypeChange,
  targetInput,
  onTargetInputChange,
  branchInput,
  onBranchInputChange,
  limits,
  onLimitsChange,
  onTriggerScan,
  onOpenFolderBrowser,
  activeJob,
  onCancelJob,
  result,
  activeTab,
  onTabChange,
  defaultWorkspacePath,
  onOpenCommandPalette,
}) => {
  const limitsDialogRef = useRef<HTMLDialogElement | null>(null);
  const [sourceOpen, setSourceOpen] = useState(false);
  const [limitsOpen, setLimitsOpen] = useState(false);
  const [renderedScheme, setRenderedScheme] = useState<'light' | 'dark'>('dark');
  const [exportStatusMsg, setExportStatusMsg] = useState<string | null>(null);

  const handleExportClick = async (event: React.MouseEvent<HTMLAnchorElement>, fmt: 'json' | 'html') => {
    event.preventDefault();
    if (!result) return;
    setExportStatusMsg(`Preparing ${fmt.toUpperCase()} report…`);
    try {
      const response = await fetch(getExportUrl(result.analysis_id, fmt));
      if (!response.ok) throw new Error('Export failed');
      const url = URL.createObjectURL(await response.blob());
      const link = document.createElement('a');
      link.href = url;
      link.download = `repodna-${result.repo_name}.${fmt}`;
      link.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
      setExportStatusMsg(`Exported ${fmt.toUpperCase()} report — download started`);
    } catch {
      setExportStatusMsg('Export failed. Check the backend connection and try again.');
    }
  };

  // Synchronize theme toggle with <meta name="color-scheme"> and OS preference per modern-web-guidance
  useEffect(() => {
    const computeCurrentRendered = (): 'light' | 'dark' => {
      const explicit = document.querySelector<HTMLMetaElement>('meta[name="color-scheme"]')?.content;
      if (explicit === 'light' || explicit === 'dark') return explicit;
      try {
        const stored = localStorage.getItem('color-scheme');
        if (stored === 'light' || stored === 'dark') return stored;
      } catch {
        // ignore storage errors
      }
      if (typeof window !== 'undefined' && typeof window.matchMedia === 'function') {
        return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
      }
      return 'dark';
    };

    setRenderedScheme(computeCurrentRendered());

    const mql =
      typeof window !== 'undefined' && typeof window.matchMedia === 'function'
        ? window.matchMedia('(prefers-color-scheme: dark)')
        : null;

    const handleChange = () => {
      setRenderedScheme(computeCurrentRendered());
    };

    const handleStorage = (e: StorageEvent) => {
      if (e.key === 'color-scheme' || e.key === null) {
        const meta = document.querySelector<HTMLMetaElement>('meta[name="color-scheme"]');
        if (meta) {
          meta.content = e.newValue ?? 'light dark';
        }
        setRenderedScheme(computeCurrentRendered());
      }
    };

    mql?.addEventListener('change', handleChange);
    window.addEventListener('storage', handleStorage);
    return () => {
      mql?.removeEventListener('change', handleChange);
      window.removeEventListener('storage', handleStorage);
    };
  }, []);

  const handleToggleTheme = () => {
    const targetScheme: 'light' | 'dark' = renderedScheme === 'dark' ? 'light' : 'dark';

    const meta = document.querySelector<HTMLMetaElement>('meta[name="color-scheme"]');
    try {
      localStorage.setItem('color-scheme', targetScheme);
      if (meta) meta.content = targetScheme;
    } catch {
      if (meta) meta.content = targetScheme;
    }
    setRenderedScheme(targetScheme);
  };

  // Limits modal light-dismiss fallback
  useEffect(() => {
    const dialog = limitsDialogRef.current;
    if (!dialog) return;
    if (limitsOpen && !dialog.open) {
      dialog.showModal();
    } else if (!limitsOpen && dialog.open) {
      dialog.close();
    }
  }, [limitsOpen]);

  useEffect(() => {
    const dialog = limitsDialogRef.current;
    if (!dialog) return;
    const onClose = () => {
      dialog.returnValue = '';
      setLimitsOpen(false);
    };
    dialog.addEventListener('close', onClose);

    let onBackdropClick: ((e: MouseEvent) => void) | null = null;
    if (!('closedBy' in HTMLDialogElement.prototype)) {
      onBackdropClick = (event: MouseEvent) => {
        if (event.target !== dialog) return;
        const rect = dialog.getBoundingClientRect();
        const inside =
          rect.top <= event.clientY &&
          event.clientY <= rect.top + rect.height &&
          rect.left <= event.clientX &&
          event.clientX <= rect.left + rect.width;
        if (!inside) dialog.close();
      };
      dialog.addEventListener('click', onBackdropClick);
    }
    return () => {
      dialog.removeEventListener('close', onClose);
      if (onBackdropClick) dialog.removeEventListener('click', onBackdropClick);
    };
  }, []);

  const isScanning =
    activeJob !== null &&
    !['completed', 'cancelled', 'failed'].includes(activeJob.status);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onTriggerScan();
  };

  return (
    <header className="app-header border-b border-line bg-canvas  px-4 py-2.5 flex flex-col gap-2">
      <div className="flex flex-wrap items-center justify-between gap-3">
        {/* Brand Identity */}
        <div className="flex items-center gap-3">
          <div className="brand-symbol">
            <Activity className="w-5 h-5 text-white" aria-hidden="true" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-base font-bold tracking-tight m-0 text-ink">RepoDNA</h1>
              <span className="text-[11px] font-mono tracking-wide px-2 py-0.5 rounded-full bg-accent/15 text-accent border border-accent/30">
                v0.1.1
              </span>
              {result?.is_demo && (
                <span
                  data-testid="demo-mode-badge"
                  className="text-[11px] font-semibold tracking-wide px-2.5 py-0.5 rounded-full bg-warning/20 text-warning border border-warning/40"
                >
                  Demo Mode — Sample Dataset
                </span>
              )}
            </div>
            <p className="header-description text-[11px] text-muted m-0">
              Repository intelligence workstation
            </p>
          </div>
        </div>

        {/* Navigation & Export Controls */}
        <div className="flex items-center gap-2 flex-wrap">
          <nav aria-label="Workspace views" className="flex items-center bg-panel p-1 rounded-lg border border-line">
            <button
              type="button"
              onClick={() => onTabChange('studio')}
              aria-pressed={activeTab === 'studio'}
              className={`px-3 py-1 rounded-md text-xs font-medium flex items-center gap-1.5 transition cursor-pointer ${
                activeTab === 'studio'
                  ? 'bg-accent-solid text-white shadow-sm'
                  : 'text-muted hover:text-ink'
              }`}
            >
              <FileCode2 className="w-3.5 h-3.5" aria-hidden="true" />
              Architecture Studio
            </button>
            <button
              type="button"
              onClick={() => onTabChange('report')}
              aria-pressed={activeTab === 'report'}
              className={`px-3 py-1 rounded-md text-xs font-medium flex items-center gap-1.5 transition cursor-pointer ${
                activeTab === 'report'
                  ? 'bg-accent-solid text-white shadow-sm'
                  : 'text-muted hover:text-ink'
              }`}
            >
              <ShieldCheck className="w-3.5 h-3.5" aria-hidden="true" />
              Health &amp; Transparency Report
            </button>
          </nav>

          <button
            type="button"
            data-testid="open-command-palette-btn"
            onClick={onOpenCommandPalette}
            aria-label="Open Command Palette (Ctrl+K)"
            className="px-2.5 py-1.5 rounded-lg bg-panel hover:bg-raised border border-line text-xs font-medium text-ink flex items-center gap-1.5 cursor-pointer"
          >
            <Command className="w-3.5 h-3.5 text-accent" aria-hidden="true" />
            <span>Command Palette</span>
            <kbd className="px-1.5 py-0.5 rounded bg-raised text-[11px] font-mono text-muted border border-line">
              Ctrl+K
            </kbd>
          </button>

          {result && (
            <div className="flex items-center gap-1.5">
              <a
                href={getExportUrl(result.analysis_id, 'json')}
                download={`repodna-${result.repo_name}.json`}
                onClick={event => void handleExportClick(event, 'json')}
                className="px-2.5 py-1.5 rounded-lg bg-panel hover:bg-raised border border-line text-xs font-medium text-ink flex items-center gap-1.5 no-underline"
              >
                <Download className="w-3.5 h-3.5 text-accent" aria-hidden="true" />
                Export JSON
              </a>
              <a
                href={getExportUrl(result.analysis_id, 'html')}
                download={`repodna-${result.repo_name}.html`}
                onClick={event => void handleExportClick(event, 'html')}
                className="px-2.5 py-1.5 rounded-lg bg-panel hover:bg-raised border border-line text-xs font-medium text-ink flex items-center gap-1.5 no-underline"
              >
                <Download className="w-3.5 h-3.5 text-success" aria-hidden="true" />
                Export HTML
              </a>
              {exportStatusMsg && (
                <span
                  role="status"
                  data-testid="export-status-badge"
                  className="px-2 py-1 rounded-md bg-success/20 border border-success/40 text-success text-[11px] font-medium"
                >
                  {exportStatusMsg}
                </span>
              )}
            </div>
          )}

          <button
            type="button"
            data-testid="theme-toggle-btn"
            onClick={handleToggleTheme}
            className="p-2 rounded-lg bg-panel hover:bg-raised border border-line text-ink cursor-pointer flex items-center gap-1.5 text-xs"
          >
            {renderedScheme === 'dark' ? (
              <>
                <Sun className="w-4 h-4 text-warning" aria-hidden="true" />
                <span className="visually-hidden">Switch to light theme</span>
              </>
            ) : (
              <>
                <Moon className="w-4 h-4 text-accent" aria-hidden="true" />
                <span className="visually-hidden">Switch to dark theme</span>
              </>
            )}
          </button>
        </div>
      </div>

      {result && <div className="repository-identity">
        <GitBranch size={15} aria-hidden="true" className="text-accent shrink-0" />
        <strong title={result.repo_name}>{result.repo_name}</strong>
        <span>{isScanning ? 'Analysis in progress' : result.is_demo ? 'Sample analysis' : 'Analysis complete'}</span>
        <button type="button" className="ml-auto text-xs text-accent cursor-pointer" aria-expanded={sourceOpen} onClick={() => setSourceOpen(v => !v)}>{sourceOpen ? 'Hide source controls' : 'Change repository'}</button>
      </div>}
      {/* Repository Target Acquisition Bar */}
      {(!result || sourceOpen || isScanning) && (
      <form onSubmit={handleSubmit} className="flex flex-wrap items-center gap-2 pt-1">
        <div role="group" aria-label="Source type" className="flex items-center bg-panel p-0.5 rounded-lg border border-line">
          <button
            type="button"
            onClick={() => {
              onSourceTypeChange('local');
              if (targetInput === 'demo' || targetInput.startsWith('https://')) {
                onTargetInputChange(defaultWorkspacePath);
              }
            }}
            aria-pressed={sourceType === 'local'}
            className={`px-2.5 py-1 rounded-md text-xs font-medium flex items-center gap-1 cursor-pointer ${
              sourceType === 'local' ? 'bg-raised text-accent border border-line' : 'text-muted hover:text-ink'
            }`}
          >
            <FolderOpen className="w-3.5 h-3.5" aria-hidden="true" />
            Local Folder
          </button>
          <button
            type="button"
            onClick={() => {
              onSourceTypeChange('github');
              if (!targetInput.startsWith('https://github.com/')) {
                onTargetInputChange('https://github.com/Cihanak1/AImage');
              }
            }}
            aria-pressed={sourceType === 'github'}
            className={`px-2.5 py-1 rounded-md text-xs font-medium flex items-center gap-1 cursor-pointer ${
              sourceType === 'github' ? 'bg-raised text-accent border border-line' : 'text-muted hover:text-ink'
            }`}
          >
            <Github className="w-3.5 h-3.5" aria-hidden="true" />
            GitHub HTTPS
          </button>
          <button
            type="button"
            onClick={() => {
              onSourceTypeChange('demo');
              onTargetInputChange('demo');
              onTriggerScan('demo', 'demo');
            }}
            aria-pressed={sourceType === 'demo'}
            className={`px-2.5 py-1 rounded-md text-xs font-medium flex items-center gap-1 cursor-pointer ${
              sourceType === 'demo' ? 'bg-warning/20 text-warning border border-warning/40' : 'text-muted hover:text-ink'
            }`}
          >
            <Sparkles className="w-3.5 h-3.5" aria-hidden="true" />
            Demo Dataset
          </button>
        </div>

        <div className="flex-1 min-w-0 flex items-center gap-1.5">
          <label htmlFor="repo-target-input" className="visually-hidden">
            {sourceType === 'github' ? 'Public HTTPS GitHub Repository URL' : 'Local Repository Directory Path'}
          </label>
          <input
            id="repo-target-input"
            name="repository" autoComplete="off" spellCheck={false}
            type="text"
            value={targetInput}
            onChange={(e) => onTargetInputChange(e.target.value)}
            placeholder={
              sourceType === 'github'
                ? 'https://github.com/owner/repository'
                : 'Enter local repository directory path...'
            }
            className="flex-1 bg-panel border border-line rounded-lg px-3 py-1.5 text-xs font-mono text-ink placeholder:text-muted"
          />

          {sourceType === 'local' && (
            <button
              type="button"
              onClick={onOpenFolderBrowser}
              className="px-2.5 py-1.5 rounded-lg bg-panel hover:bg-raised border border-line text-xs font-medium text-ink flex items-center gap-1 shrink-0 cursor-pointer"
            >
              <FolderOpen className="w-3.5 h-3.5 text-accent" aria-hidden="true" />
              Browse...
            </button>
          )}

          {sourceType === 'github' && (
            <div className="flex items-center gap-1">
              <label htmlFor="repo-branch-input" className="visually-hidden">
                Git Branch (optional)
              </label>
              <GitBranch className="w-3.5 h-3.5 text-muted" aria-hidden="true" />
              <input
                id="repo-branch-input"
                type="text"
                value={branchInput}
                onChange={(e) => onBranchInputChange(e.target.value)}
                placeholder="branch (optional)"
                className="w-28 bg-panel border border-line rounded-lg px-2 py-1.5 text-xs font-mono text-ink placeholder:text-muted"
              />
            </div>
          )}
        </div>

        <button
          type="button"
          onClick={() => setLimitsOpen(true)}
          className="px-2.5 py-1.5 rounded-lg bg-panel hover:bg-raised border border-line text-xs font-medium text-muted flex items-center gap-1.5 cursor-pointer"
        >
          <Settings2 className="w-3.5 h-3.5 text-muted" aria-hidden="true" />
          Guardrails ({limits.max_files} files / {limits.timeout_seconds}s)
        </button>

        {isScanning ? (
          <button
            type="button"
            onClick={onCancelJob}
            className="px-3.5 py-1.5 rounded-lg bg-danger-solid hover:bg-danger-solid text-white text-xs font-semibold flex items-center gap-1.5 cursor-pointer"
          >
            <Square className="w-3.5 h-3.5" aria-hidden="true" />
            Cancel Scan
          </button>
        ) : (
          <button
            type="submit"
            data-testid="analyze-submit-btn"
            className="px-4 py-1.5 rounded-lg bg-accent-solid hover:bg-accent-solid text-white text-xs font-semibold flex items-center gap-1.5 shadow-sm shadow-sky-500/20 cursor-pointer"
          >
            <Play className="w-3.5 h-3.5" aria-hidden="true" />
            Analyze Repository
          </button>
        )}
      </form>
      )}

      {/* Active Scan Progress Bar */}
      {isScanning && activeJob && (
        <div className="flex items-center gap-3 bg-panel border border-accent/30 rounded-lg px-3 py-1.5 text-xs">
          <progress
            value={activeJob.progress_percent}
            max={100}
            aria-label="Repository scan progress"
            className="w-40 h-2 rounded overflow-hidden accent-sky-500"
          />
          <span className="font-mono text-accent font-semibold">
            {activeJob.progress_percent.toFixed(0)}%
          </span>
          <span className="text-muted truncate flex-1">{activeJob.phase_message}</span>
          {activeJob.files_discovered > 0 && (
            <span className="text-muted font-mono">
              {activeJob.files_processed}/{activeJob.files_discovered} files
            </span>
          )}
        </div>
      )}

      {/* Scan Limits & Safety Guardrails Modal */}
      <dialog
        ref={limitsDialogRef}
        {...({ closedby: 'any' } as React.DialogHTMLAttributes<HTMLDialogElement>)}
        aria-labelledby="limits-dialog-title"
      >
        <div className="p-5 flex flex-col gap-4">
          <div className="flex items-center justify-between border-b border-line pb-3">
            <h2 id="limits-dialog-title" className="text-base font-semibold m-0 flex items-center gap-2">
              <Settings2 className="w-4 h-4 text-accent" aria-hidden="true" />
              Scan Safety Limits &amp; Timeout Guardrails
            </h2>
            <button
              type="button"
              onClick={() => limitsDialogRef.current?.close()}
              aria-label="Close limits dialog"
              className="p-1 rounded-lg hover:bg-raised text-muted cursor-pointer"
            >
              <X className="w-4 h-4" aria-hidden="true" />
            </button>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
            <div className="flex flex-col gap-1">
              <label htmlFor="limit-max-files" className="font-medium text-muted">
                Max Files Limit
              </label>
              <input
                id="limit-max-files"
                type="number"
                min={10}
                max={20000}
                value={limits.max_files}
                onChange={(e) =>
                  onLimitsChange({
                    ...limits,
                    max_files: Math.max(10, Math.min(20000, Number(e.target.value) || 2500)),
                  })
                }
                className="bg-panel border border-line rounded-lg px-2.5 py-1.5 font-mono text-ink"
              />
            </div>

            <div className="flex flex-col gap-1">
              <label htmlFor="limit-max-file-bytes" className="font-medium text-muted">
                Max Single File Size (KB)
              </label>
              <input
                id="limit-max-file-bytes"
                type="number"
                min={16}
                max={10240}
                value={Math.round(limits.max_file_size_bytes / 1024)}
                onChange={(e) =>
                  onLimitsChange({
                    ...limits,
                    max_file_size_bytes: Math.max(16, Math.min(10240, Number(e.target.value) || 1024)) * 1024,
                  })
                }
                className="bg-panel border border-line rounded-lg px-2.5 py-1.5 font-mono text-ink"
              />
            </div>

            <div className="flex flex-col gap-1">
              <label htmlFor="limit-timeout-sec" className="font-medium text-muted">
                Timeout (Seconds)
              </label>
              <input
                id="limit-timeout-sec"
                type="number"
                min={5}
                max={300}
                value={limits.timeout_seconds}
                onChange={(e) =>
                  onLimitsChange({
                    ...limits,
                    timeout_seconds: Math.max(5, Math.min(300, Number(e.target.value) || 60)),
                  })
                }
                className="bg-panel border border-line rounded-lg px-2.5 py-1.5 font-mono text-ink"
              />
            </div>
          </div>

          <div className="flex justify-end pt-2 border-t border-line">
            <button
              type="button"
              onClick={() => limitsDialogRef.current?.close()}
              className="px-4 py-1.5 rounded-lg bg-accent-solid hover:bg-accent-solid text-white text-xs font-semibold cursor-pointer"
            >
              Done
            </button>
          </div>
        </div>
      </dialog>
    </header>
  );
};
