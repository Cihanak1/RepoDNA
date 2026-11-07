import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  AlertCircle,
  FolderOpen,
  Github,
  Play,
  ShieldCheck,
  Sparkles,
} from 'lucide-react';
import {
  cancelScanJob,
  fetchBackendHealth,
  fetchJobProgress,
  fetchJobResult,
  startAsyncScanJob,
} from './api/client';
import { DependencyGraph } from './components/DependencyGraph';
import { ExplorerSidebar } from './components/ExplorerSidebar';
import { FolderBrowserDialog } from './components/FolderBrowserDialog';
import { HeaderBar } from './components/HeaderBar';
import { HealthReportView } from './components/HealthReportView';
import { InspectorPanel } from './components/InspectorPanel';
import { SummaryStrip } from './components/SummaryStrip';
import type {
  AnalysisResult,
  ScanLimits,
  ScanProgress,
  SourceType,
} from './types/repodna';
import { filterFiles, type LayoutMode } from './utils/graphLayout';

export const App: React.FC = () => {
  const [defaultWorkspacePath, setDefaultWorkspacePath] = useState<string>('');
  const [sourceType, setSourceType] = useState<SourceType>('local');
  const [targetInput, setTargetInput] = useState<string>('');
  const [branchInput, setBranchInput] = useState<string>('');
  const [limits, setLimits] = useState<ScanLimits>({
    max_files: 2500,
    max_file_size_bytes: 1_048_576,
    max_total_size_bytes: 104_857_600,
    timeout_seconds: 60,
  });

  const [folderDialogOpen, setFolderDialogOpen] = useState(false);
  const [activeJob, setActiveJob] = useState<ScanProgress | null>(null);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [errorBanner, setErrorBanner] = useState<{ code: string; message: string } | null>(null);

  const [activeTab, setActiveTab] = useState<'studio' | 'report'>('studio');
  const [selectedFileId, setSelectedFileId] = useState<string | null>(null);
  const [layoutMode, setLayoutMode] = useState<LayoutMode>('layered');

  // Explorer & Graph Filters
  const [searchQuery, setSearchQuery] = useState('');
  const [languageFilter, setLanguageFilter] = useState('ALL');
  const [supportFilter, setSupportFilter] = useState('ALL');
  const [cyclesOnly, setCyclesOnly] = useState(false);
  const [hubsOnly, setHubsOnly] = useState(false);
  const [orphansOnly, setOrphansOnly] = useState(false);
  const [focusNeighborhood, setFocusNeighborhood] = useState(false);
  const [highlightCycles, setHighlightCycles] = useState(true);

  const pollTimerRef = useRef<number | null>(null);

  // Fetch backend health metadata on mount (does NOT auto-scan any files)
  useEffect(() => {
    let mounted = true;
    fetchBackendHealth()
      .then((info) => {
        if (!mounted) return;
        setDefaultWorkspacePath(info.default_workspace);
        setTargetInput((prev) => prev || info.default_workspace);
      })
      .catch(() => {
        // Backend may still be starting
      });
    return () => {
      mounted = false;
      if (pollTimerRef.current) window.clearInterval(pollTimerRef.current);
    };
  }, []);

  // Update document title dynamically for accessibility
  useEffect(() => {
    if (result) {
      document.title = `${result.repo_name} (${result.health_report.overall_score.toFixed(0)}/100) | RepoDNA`;
    } else {
      document.title = 'RepoDNA — Developer Repository Intelligence Platform';
    }
  }, [result]);

  const stopPolling = () => {
    if (pollTimerRef.current !== null) {
      window.clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
  };

  const handleTriggerScan = async (
    overrideSource?: SourceType,
    overrideTarget?: string
  ) => {
    stopPolling();
    setErrorBanner(null);

    const effSource = overrideSource ?? sourceType;
    const effTarget = (overrideTarget ?? targetInput).trim();

    if (!effTarget) {
      setErrorBanner({
        code: 'EMPTY_TARGET',
        message: 'Please enter a valid local directory path or HTTPS GitHub repository URL.',
      });
      return;
    }

    try {
      const initialJob = await startAsyncScanJob({
        source_type: effSource,
        target: effTarget,
        branch: effSource === 'github' && branchInput.trim() ? branchInput.trim() : null,
        limits,
      });
      setActiveJob(initialJob);

      const poll = async () => {
        try {
          const progress = await fetchJobProgress(initialJob.job_id);
          setActiveJob(progress);

          if (progress.status === 'completed') {
            stopPolling();
            const finalResult = await fetchJobResult(initialJob.job_id);
            setResult(finalResult);
            setActiveJob(null);
            // Select either first cycle file or highest fan-in/out file by default
            const firstCycleFile = finalResult.files.find((f) => f.in_cycle);
            const firstFile =
              firstCycleFile ??
              [...finalResult.files].sort(
                (a, b) => b.fan_in + b.fan_out - (a.fan_in + a.fan_out)
              )[0] ??
              null;
            setSelectedFileId(firstFile ? firstFile.id : null);
          } else if (progress.status === 'failed' || progress.status === 'cancelled') {
            stopPolling();
            setErrorBanner({
              code: progress.error_code || progress.status.toUpperCase(),
              message: progress.error_message || progress.phase_message,
            });
            setActiveJob(null);
          }
        } catch (err) {
          stopPolling();
          setErrorBanner({
            code: 'POLL_ERROR',
            message: err instanceof Error ? err.message : 'Failed to poll scan job status.',
          });
          setActiveJob(null);
        }
      };

      // Run immediate check then poll every 180ms
      await poll();
      if (pollTimerRef.current === null) {
        pollTimerRef.current = window.setInterval(() => {
          void poll();
        }, 180);
      }
    } catch (err: unknown) {
      const code =
        err && typeof err === 'object' && 'code' in err
          ? String((err as { code: string }).code)
          : 'SCAN_REJECTED';
      const message = err instanceof Error ? err.message : 'Failed to initiate repository scan.';
      setErrorBanner({ code, message });
      setActiveJob(null);
    }
  };

  const handleCancelJob = async () => {
    if (!activeJob) return;
    stopPolling();
    try {
      const cancelled = await cancelScanJob(activeJob.job_id);
      setActiveJob(null);
      setErrorBanner({
        code: cancelled.error_code || 'SCAN_CANCELLED',
        message: 'Repository scan was cancelled by user.',
      });
    } catch {
      setActiveJob(null);
    }
  };

  const handleResetFilters = () => {
    setSearchQuery('');
    setLanguageFilter('ALL');
    setSupportFilter('ALL');
    setCyclesOnly(false);
    setHubsOnly(false);
    setOrphansOnly(false);
    setFocusNeighborhood(false);
  };

  const { filteredFiles, filteredEdges, neighborIds } = useMemo(() => {
    if (!result) {
      return { filteredFiles: [], filteredEdges: [], neighborIds: new Set<string>() };
    }
    return filterFiles(result.files, result.edges, {
      searchQuery,
      languageFilter,
      supportFilter,
      cyclesOnly,
      hubsOnly,
      orphansOnly,
      focusSelectedNeighborhood: focusNeighborhood,
      selectedFileId,
      highlightCycles,
    });
  }, [
    result,
    searchQuery,
    languageFilter,
    supportFilter,
    cyclesOnly,
    hubsOnly,
    orphansOnly,
    focusNeighborhood,
    selectedFileId,
    highlightCycles,
  ]);

  const selectedFile = useMemo(() => {
    if (!result || !selectedFileId) return null;
    return result.files.find((f) => f.id === selectedFileId) ?? null;
  }, [result, selectedFileId]);

  const handleSelectFileFromReport = (fileId: string) => {
    setSelectedFileId(fileId);
    setActiveTab('studio');
  };

  return (
    <div className="min-h-screen flex flex-col bg-slate-950 text-slate-100">
      <a href="#main-workspace" className="skip-link visually-hidden">
        Skip to main workspace
      </a>

      <HeaderBar
        sourceType={sourceType}
        onSourceTypeChange={setSourceType}
        targetInput={targetInput}
        onTargetInputChange={setTargetInput}
        branchInput={branchInput}
        onBranchInputChange={setBranchInput}
        limits={limits}
        onLimitsChange={setLimits}
        onTriggerScan={(s, t) => void handleTriggerScan(s, t)}
        onOpenFolderBrowser={() => setFolderDialogOpen(true)}
        activeJob={activeJob}
        onCancelJob={() => void handleCancelJob()}
        result={result}
        activeTab={activeTab}
        onTabChange={setActiveTab}
        defaultWorkspacePath={defaultWorkspacePath}
      />

      {/* Error / Security Rejection Alert */}
      {errorBanner && (
        <div
          role="alert"
          data-testid="error-alert-banner"
          className="bg-red-950/70 border-b border-red-700/70 px-4 py-2.5 flex items-center justify-between gap-3 text-xs text-red-200"
        >
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-red-400 shrink-0" aria-hidden="true" />
            <span>
              <strong className="font-mono">[{errorBanner.code}]</strong> {errorBanner.message}
            </span>
          </div>
          <button
            type="button"
            onClick={() => setErrorBanner(null)}
            className="px-2 py-0.5 rounded bg-red-900/60 hover:bg-red-800 text-red-100 text-[11px] cursor-pointer"
          >
            Dismiss
          </button>
        </div>
      )}

      {result && (
        <SummaryStrip
          result={result}
          cyclesOnly={cyclesOnly}
          onToggleCyclesOnly={() => {
            setCyclesOnly((prev) => !prev);
            setActiveTab('studio');
          }}
          onOpenReportTab={() => setActiveTab('report')}
        />
      )}

      <main id="main-workspace" tabIndex={-1} className="flex-1 flex flex-col overflow-hidden">
        {!result ? (
          /* Explicit Consent Launchpad — Never auto-scans local folders without user action */
          <div
            data-testid="welcome-launchpad"
            className="flex-1 flex items-center justify-center p-6"
          >
            <div className="max-w-3xl w-full bg-slate-900/75 border border-slate-800 rounded-2xl p-6 lg:p-8 shadow-2xl space-y-6">
              <div className="space-y-2">
                <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-sky-500/15 border border-sky-500/30 text-sky-300 text-xs font-medium">
                  <ShieldCheck className="w-3.5 h-3.5" aria-hidden="true" />
                  Zero Unsolicited Scanning &bull; Read-Only Static AST Intelligence
                </div>
                <h2 className="text-2xl font-bold text-slate-100 m-0">
                  Analyze Repository Architecture &amp; Module Health
                </h2>
                <p className="text-xs text-slate-300 leading-relaxed m-0">
                  Select a local source directory, enter a public HTTPS GitHub URL, or inspect the labeled Demo dataset. RepoDNA uses Tree-sitter AST parsing and Tarjan Strongly Connected Components to map internal module relationships, detect circular dependencies, and compute explainable rule-based health scores without executing a single line of repository code.
                </p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-3.5">
                {/* Action 1: Analyze Current Local Workspace */}
                <div className="bg-slate-950/80 border border-slate-800 rounded-xl p-4 flex flex-col justify-between gap-4">
                  <div className="space-y-1.5">
                    <div className="w-8 h-8 rounded-lg bg-sky-500/15 border border-sky-500/30 flex items-center justify-center">
                      <FolderOpen className="w-4 h-4 text-sky-400" aria-hidden="true" />
                    </div>
                    <h3 className="text-sm font-semibold text-slate-100 m-0">
                      Local Repository Scan
                    </h3>
                    <p className="text-[11px] text-slate-400 m-0">
                      Explicitly scan this workspace or browse any local directory on your machine.
                    </p>
                  </div>
                  <div className="flex flex-col gap-1.5">
                    {defaultWorkspacePath && (
                      <button
                        type="button"
                        data-testid="launchpad-scan-workspace-btn"
                        onClick={() => {
                          setSourceType('local');
                          setTargetInput(defaultWorkspacePath);
                          void handleTriggerScan('local', defaultWorkspacePath);
                        }}
                        className="w-full px-3 py-2 rounded-lg bg-sky-600 hover:bg-sky-500 text-white text-xs font-semibold flex items-center justify-center gap-1.5 cursor-pointer"
                      >
                        <Play className="w-3.5 h-3.5" aria-hidden="true" />
                        Analyze Current Workspace
                      </button>
                    )}
                    <button
                      type="button"
                      onClick={() => setFolderDialogOpen(true)}
                      className="w-full px-3 py-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 border border-slate-700 text-xs font-medium text-slate-200 cursor-pointer"
                    >
                      Browse Other Folder...
                    </button>
                  </div>
                </div>

                {/* Action 2: Public HTTPS GitHub Repository */}
                <div className="bg-slate-950/80 border border-slate-800 rounded-xl p-4 flex flex-col justify-between gap-4">
                  <div className="space-y-1.5">
                    <div className="w-8 h-8 rounded-lg bg-indigo-500/15 border border-indigo-500/30 flex items-center justify-center">
                      <Github className="w-4 h-4 text-indigo-400" aria-hidden="true" />
                    </div>
                    <h3 className="text-sm font-semibold text-slate-100 m-0">
                      GitHub HTTPS Clone
                    </h3>
                    <p className="text-[11px] text-slate-400 m-0">
                      Clones into an isolated temporary folder with hooks and symlinks disabled, then cleans up automatically.
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => {
                      setSourceType('github');
                      setTargetInput('https://github.com/Cihanak1/AImage');
                    }}
                    className="w-full px-3 py-2 rounded-lg bg-indigo-600/25 hover:bg-indigo-600/35 border border-indigo-500/40 text-indigo-200 text-xs font-semibold cursor-pointer"
                  >
                    Enter GitHub HTTPS URL
                  </button>
                </div>

                {/* Action 3: Labeled Demo Dataset */}
                <div className="bg-slate-950/80 border border-slate-800 rounded-xl p-4 flex flex-col justify-between gap-4">
                  <div className="space-y-1.5">
                    <div className="w-8 h-8 rounded-lg bg-amber-500/15 border border-amber-500/30 flex items-center justify-center">
                      <Sparkles className="w-4 h-4 text-amber-400" aria-hidden="true" />
                    </div>
                    <h3 className="text-sm font-semibold text-slate-100 m-0">
                      Labeled Demo Showcase
                    </h3>
                    <p className="text-[11px] text-slate-400 m-0">
                      Explore a multi-language architecture with circular dependencies, dynamic imports, and churn hotspots.
                    </p>
                  </div>
                  <button
                    type="button"
                    data-testid="launchpad-demo-btn"
                    onClick={() => {
                      setSourceType('demo');
                      setTargetInput('demo');
                      void handleTriggerScan('demo', 'demo');
                    }}
                    className="w-full px-3 py-2 rounded-lg bg-amber-500/20 hover:bg-amber-500/30 border border-amber-500/40 text-amber-200 text-xs font-semibold cursor-pointer"
                  >
                    Load Labeled Demo Mode
                  </button>
                </div>
              </div>
            </div>
          </div>
        ) : activeTab === 'studio' ? (
          <div className="flex-1 flex flex-col lg:flex-row overflow-hidden">
            <ExplorerSidebar
              allFiles={result.files}
              filteredFiles={filteredFiles}
              selectedFileId={selectedFileId}
              onSelectFile={setSelectedFileId}
              searchQuery={searchQuery}
              onSearchChange={setSearchQuery}
              languageFilter={languageFilter}
              onLanguageFilterChange={setLanguageFilter}
              supportFilter={supportFilter}
              onSupportFilterChange={setSupportFilter}
              cyclesOnly={cyclesOnly}
              onCyclesOnlyChange={setCyclesOnly}
              hubsOnly={hubsOnly}
              onHubsOnlyChange={setHubsOnly}
              orphansOnly={orphansOnly}
              onOrphansOnlyChange={setOrphansOnly}
              onResetFilters={handleResetFilters}
            />

            <DependencyGraph
              files={filteredFiles}
              edges={filteredEdges}
              selectedFileId={selectedFileId}
              neighborIds={neighborIds}
              onSelectFile={setSelectedFileId}
              layoutMode={layoutMode}
              onLayoutModeChange={setLayoutMode}
              focusNeighborhood={focusNeighborhood}
              onToggleFocusNeighborhood={() => setFocusNeighborhood((prev) => !prev)}
              highlightCycles={highlightCycles}
              onToggleHighlightCycles={() => setHighlightCycles((prev) => !prev)}
            />

            <InspectorPanel
              selectedFile={selectedFile}
              allCycles={result.cycles}
              allFindings={result.health_report.findings}
              onSelectFile={setSelectedFileId}
            />
          </div>
        ) : (
          <HealthReportView
            result={result}
            onSelectFileInStudio={handleSelectFileFromReport}
          />
        )}
      </main>

      <FolderBrowserDialog
        isOpen={folderDialogOpen}
        initialPath={targetInput.startsWith('https://') || targetInput === 'demo' ? defaultWorkspacePath : targetInput}
        onClose={() => setFolderDialogOpen(false)}
        onSelectFolder={(chosenPath) => {
          setSourceType('local');
          setTargetInput(chosenPath);
        }}
      />
    </div>
  );
};
