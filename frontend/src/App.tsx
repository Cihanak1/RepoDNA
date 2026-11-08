import React, { lazy, Suspense, useDeferredValue, useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  AlertCircle,
} from 'lucide-react';
import {
  ApiError,
  cancelScanJob,
  fetchBackendHealth,
  fetchJobProgress,
  fetchJobResultWithRetry,
  getExportUrl,
  startAsyncScanJob,
} from './api/client';
import { CommandPaletteDialog } from './components/CommandPaletteDialog';
import { ExplorerSidebar } from './components/ExplorerSidebar';
import { FolderBrowserDialog } from './components/FolderBrowserDialog';
import { HeaderBar } from './components/HeaderBar';
import { InspectorPanel } from './components/InspectorPanel';
import { Launchpad } from './components/Launchpad';
import { OnboardingTour } from './components/OnboardingTour';
import { PanelResizer } from './components/PanelResizer';
import { readPreference, savePreference, type WorkstationMode } from './utils/preferences';
import { SummaryStrip } from './components/SummaryStrip';
import type {
  AnalysisResult,
  DependencyEdge,
  FileNode,
  ScanLimits,
  ScanProgress,
  SourceType,
} from './types/repodna';
import {
  filterFiles,
  type GraphDensityMode,
  type GraphGroupingMode,
  type LayoutMode,
} from './utils/graphLayout';

const DependencyGraph = lazy(() => import('./components/DependencyGraph').then(module => ({ default: module.DependencyGraph })));
const HealthReportView = lazy(() => import('./components/HealthReportView').then(module => ({ default: module.HealthReportView })));

export const App: React.FC = () => {
  const { t, i18n } = useTranslation();
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
  const [commandPaletteOpen, setCommandPaletteOpen] = useState(false);
  const [tourOpen, setTourOpen] = useState(false);
  const [activeJob, setActiveJob] = useState<ScanProgress | null>(null);
  const [scanningTargetLabel, setScanningTargetLabel] = useState<string>('');
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [errorBanner, setErrorBanner] = useState<{ code: string; message: string } | null>(null);

  // Workstation Mode (Simple vs Advanced)
  const [workstationMode, setWorkstationMode] = useState<WorkstationMode>(() =>
    readPreference<WorkstationMode>('mode', 'simple', (v): v is WorkstationMode => v === 'simple' || v === 'advanced')
  );
  useEffect(() => { savePreference('mode', workstationMode); }, [workstationMode]);

  const [activeTab, setActiveTab] = useState<'studio' | 'report'>('studio');
  const [selectedFileId, setSelectedFileId] = useState<string | null>(null);
  const [layoutMode, setLayoutMode] = useState(() => readPreference<LayoutMode>('layout', 'layered', (v): v is LayoutMode => v === 'layered' || v === 'cluster' || v === 'radial'));
  const [densityMode, setDensityMode] = useState(() => readPreference<GraphDensityMode>('density', 'balanced', (v): v is GraphDensityMode => v === 'compact' || v === 'balanced' || v === 'spacious'));
  const [groupingMode, setGroupingMode] = useState(() => readPreference<GraphGroupingMode>('grouping', 'files', (v): v is GraphGroupingMode => v === 'files' || v === 'directories'));
  useEffect(() => { savePreference('layout', layoutMode); }, [layoutMode]);
  useEffect(() => { savePreference('density', densityMode); }, [densityMode]);
  useEffect(() => { savePreference('grouping', groupingMode); }, [groupingMode]);

  const [explorerWidth, setExplorerWidth] = useState(() => readPreference('explorerWidth', 260, (v): v is number => typeof v === 'number' && v >= 220 && v <= 400));
  const [inspectorWidth, setInspectorWidth] = useState(() => readPreference('inspectorWidth', 320, (v): v is number => typeof v === 'number' && v >= 260 && v <= 460));
  const [showExplorer, setShowExplorer] = useState(true);
  const [showInspector, setShowInspector] = useState(true);
  const [focusMode, setFocusMode] = useState(false);
  const [mobileView, setMobileView] = useState<'files' | 'canvas' | 'inspector'>('canvas');
  useEffect(() => { savePreference('explorerWidth', explorerWidth); }, [explorerWidth]);
  useEffect(() => { savePreference('inspectorWidth', inspectorWidth); }, [inspectorWidth]);
  useEffect(() => {
    const shortcut = (event: KeyboardEvent) => {
      if (event.target instanceof HTMLElement && (event.target.closest('input,textarea,select,[contenteditable=true],dialog[open]'))) return;
      if (event.key === 'Escape') setFocusMode(false);
      if (event.altKey && event.key.toLowerCase() === 'f') { event.preventDefault(); setFocusMode(v => !v); setMobileView('canvas'); }
      if (event.altKey && event.key.toLowerCase() === 'i') { event.preventDefault(); setShowInspector(v => !v); }
      if (event.altKey && event.key.toLowerCase() === 'm') {
        event.preventDefault();
        setWorkstationMode(v => (v === 'simple' ? 'advanced' : 'simple'));
      }
      if (event.key === '/') { event.preventDefault(); setShowExplorer(true); setMobileView('files'); requestAnimationFrame(() => document.getElementById('explorer-search-input')?.focus()); }
    };
    window.addEventListener('keydown', shortcut);
    return () => window.removeEventListener('keydown', shortcut);
  }, []);
  const selectFile = (id: string) => { setSelectedFileId(id); setMobileView('inspector'); setShowInspector(true); };

  // Explorer & Graph Filters
  const [searchQuery, setSearchQuery] = useState('');
  const deferredSearchQuery = useDeferredValue(searchQuery);
  const [languageFilter, setLanguageFilter] = useState('ALL');
  const [supportFilter, setSupportFilter] = useState('ALL');
  const [cyclesOnly, setCyclesOnly] = useState(false);
  const [hubsOnly, setHubsOnly] = useState(false);
  const [orphansOnly, setOrphansOnly] = useState(false);
  const [focusNeighborhood, setFocusNeighborhood] = useState(false);
  const [highlightCycles, setHighlightCycles] = useState(true);

  const pollTimerRef = useRef<number | null>(null);
  const pollInFlightRef = useRef<boolean>(false);
  const scanSessionIdRef = useRef<number>(0);

  // Global keyboard shortcut Ctrl+K / Cmd+K for Command Palette
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setCommandPaletteOpen((prev) => !prev);
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, []);

  // Fetch backend health metadata on mount (does NOT auto-scan any files)
  useEffect(() => {
    let mounted = true;
    fetchBackendHealth()
      .then((info) => {
        if (!mounted) return;
        setDefaultWorkspacePath(info.default_workspace);
        setTargetInput((prev) => (prev ? prev : info.default_workspace));
      })
      .catch((err) => {
        if (!mounted) return;
        console.warn('Backend /api/health unavailable on mount:', err);
      });
    return () => {
      mounted = false;
    };
  }, []);

  // Clean up any polling timer on unmount
  useEffect(() => {
    return () => {
      if (pollTimerRef.current !== null) {
        window.clearTimeout(pollTimerRef.current);
        pollTimerRef.current = null;
      }
    };
  }, []);

  const handleCancelJob = async () => {
    scanSessionIdRef.current += 1;
    pollInFlightRef.current = false;
    if (pollTimerRef.current !== null) {
      window.clearTimeout(pollTimerRef.current);
      pollTimerRef.current = null;
    }

    if (!activeJob) return;
    try {
      await cancelScanJob(activeJob.job_id);
    } catch (err) {
      console.warn('Failed to request scan cancellation:', err);
    } finally {
      setActiveJob(null);
    }
  };

  const handleTriggerScan = async (
    overrideSource?: SourceType,
    overrideTarget?: string
  ) => {
    const activeSource = overrideSource ?? sourceType;
    const activeTarget = (overrideTarget ?? targetInput).trim();

    if (!activeTarget) {
      setErrorBanner({
        code: 'EMPTY_TARGET',
        message: 'Please enter a valid local directory path or HTTPS GitHub repository URL.',
      });
      return;
    }

    setErrorBanner(null);
    setScanningTargetLabel(activeTarget);

    scanSessionIdRef.current += 1;
    const currentSessionId = scanSessionIdRef.current;
    pollInFlightRef.current = false;
    if (pollTimerRef.current !== null) {
      window.clearTimeout(pollTimerRef.current);
      pollTimerRef.current = null;
    }

    try {
      const job = await startAsyncScanJob({
        source_type: activeSource,
        target: activeTarget,
        branch: activeSource === 'github' && branchInput.trim() ? branchInput.trim() : undefined,
        limits,
      });

      setActiveJob(job);

      if (job.status === 'completed') {
        const fullResult = await fetchJobResultWithRetry(job.job_id);
        setResult(fullResult);
        setActiveJob(null);
        setSelectedFileId(fullResult.files[0]?.id ?? null);
        return;
      }

      const schedulePoll = (jobId: string, delayMs: number) => {
        if (scanSessionIdRef.current !== currentSessionId) return;
        pollTimerRef.current = window.setTimeout(async () => {
          if (scanSessionIdRef.current !== currentSessionId) return;
          if (pollInFlightRef.current) {
            schedulePoll(jobId, 400);
            return;
          }

          pollInFlightRef.current = true;
          try {
            const status = await fetchJobProgress(jobId);
            if (scanSessionIdRef.current !== currentSessionId) return;

            setActiveJob(status);

            if (status.status === 'completed') {
              pollInFlightRef.current = false;
              const fullResult = await fetchJobResultWithRetry(jobId);
              setResult(fullResult);
              setActiveTab('studio');
              setSelectedFileId(fullResult.files[0]?.id ?? null);
              setActiveJob(null);
              return;
            }

            if (status.status === 'failed') {
              pollInFlightRef.current = false;
              setErrorBanner({
                code: status.error_code ?? 'SCAN_FAILED',
                message: status.error_message ?? 'Scan failed without a detailed error message.',
              });
              setActiveJob(null);
              return;
            }

            if (status.status === 'cancelled') {
              pollInFlightRef.current = false;
              setActiveJob(null);
              return;
            }

            pollInFlightRef.current = false;
            schedulePoll(jobId, 500);
          } catch (pollErr: unknown) {
            pollInFlightRef.current = false;
            if (scanSessionIdRef.current !== currentSessionId) return;

            const isConflict409 =
              pollErr instanceof Error && pollErr.message.includes('409');
            if (isConflict409) {
              schedulePoll(jobId, 1000);
              return;
            }

            setErrorBanner({
              code: 'NETWORK_ERROR',
              message:
                pollErr instanceof Error
                  ? pollErr.message
                  : 'Failed to poll scan job status from backend.',
            });
            setActiveJob(null);
          }
        }, delayMs);
      };

      schedulePoll(job.job_id, 300);
    } catch (err: unknown) {
      if (scanSessionIdRef.current !== currentSessionId) return;
      setErrorBanner({
        code: err instanceof ApiError ? err.code : 'SCAN_INIT_FAILED',
        message: err instanceof Error ? err.message : 'Failed to start scan job.',
      });
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

  const handleSelectFileFromReport = (fileId: string) => {
    setSelectedFileId(fileId);
    setActiveTab('studio');
    setMobileView('inspector');
    setShowInspector(true);
  };

  const handleToggleThemeFromPalette = () => {
    const themeBtn = document.querySelector<HTMLButtonElement>('[data-testid="theme-toggle-btn"]');
    themeBtn?.click();
  };

  const { filteredFiles, filteredEdges, neighborIds } = useMemo(() => {
    if (!result) {
      return {
        filteredFiles: [] as FileNode[],
        filteredEdges: [] as DependencyEdge[],
        neighborIds: new Set<string>(),
      };
    }
    return filterFiles(result.files, result.edges, {
      searchQuery: deferredSearchQuery,
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
    deferredSearchQuery,
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

  return (
    <div className="app-shell flex flex-col bg-canvas text-ink font-sans selection:bg-accent/20">
      <a
        href="#main-workspace"
        className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-50 focus:px-3 focus:py-1.5 focus:bg-accent focus:text-white focus:rounded focus:outline-none"
      >
        Skip to main content
      </a>

      {/* Workstation Header Bar */}
      <HeaderBar
        sourceType={sourceType}
        onSourceTypeChange={setSourceType}
        targetInput={targetInput}
        onTargetInputChange={setTargetInput}
        branchInput={branchInput}
        onBranchInputChange={setBranchInput}
        limits={limits}
        onLimitsChange={setLimits}
        onTriggerScan={handleTriggerScan}
        onOpenFolderBrowser={() => setFolderDialogOpen(true)}
        activeJob={activeJob}
        onCancelJob={handleCancelJob}
        result={result}
        activeTab={activeTab}
        onTabChange={setActiveTab}
        defaultWorkspacePath={defaultWorkspacePath}
        onOpenCommandPalette={() => setCommandPaletteOpen(true)}
        workstationMode={workstationMode}
        onWorkstationModeChange={setWorkstationMode}
        onOpenTour={() => setTourOpen(true)}
      />

      {errorBanner && (
        <div
          role="alert"
          data-testid="error-alert-banner"
          className="bg-danger/10 border-b border-danger/70 px-4 py-2 flex items-center justify-between gap-3 text-xs text-danger"
        >
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-danger shrink-0" aria-hidden="true" />
            <span>
              <strong className="font-mono">[{errorBanner.code}]</strong>{' '}
              {t(`errors.${errorBanner.code}`, errorBanner.message)}
            </span>
          </div>
          <button
            type="button"
            onClick={() => setErrorBanner(null)}
            className="px-2 py-0.5 rounded bg-danger-solid hover:bg-danger-solid text-white text-[11px] cursor-pointer"
          >
            {t('common.dismiss')}
          </button>
        </div>
      )}

      {activeJob && result && (
        <div
          role="status"
          data-testid="previous-analysis-banner"
          className="bg-warning/10 border-b border-warning/60 px-4 py-1.5 flex items-center justify-between gap-3 text-xs text-warning"
        >
          <div>
            <strong className="tracking-wide font-bold text-warning mr-2">
              {t('common.previousAnalysis')} ({result.repo_name})
            </strong>
            <span>
              {t('header.viewingPreviousSnapshot')}{' '}
              <code className="font-mono text-warning">{scanningTargetLabel}</code> &mdash;{' '}
              {activeJob.phase_message} ({activeJob.progress_percent.toFixed(0)}%)
            </span>
          </div>
          <span className="text-[11px] font-mono text-warning shrink-0">
            {t('header.updatingAutomatically')}
          </span>
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
          isPreviousAnalysis={activeJob !== null}
          workstationMode={workstationMode}
        />
      )}

      <main id="main-workspace" tabIndex={-1} className="flex-1 flex flex-col overflow-hidden">
        {!result ? (
          <Launchpad
            workspace={defaultWorkspacePath}
            scanning={activeJob !== null}
            onWorkspace={() => {
              setSourceType('local');
              setTargetInput(defaultWorkspacePath);
              void handleTriggerScan('local', defaultWorkspacePath);
            }}
            onBrowse={() => setFolderDialogOpen(true)}
            onGithub={() => {
              setSourceType('github');
              setTargetInput('https://github.com/');
              document.getElementById('repo-target-input')?.focus();
            }}
            onDemo={() => {
              setSourceType('demo');
              setTargetInput('demo');
              void handleTriggerScan('demo', 'demo');
            }}
          />
        ) : activeTab === 'studio' ? (
          <>
            <div className="workspace-controls" role="toolbar" aria-label="Workspace panels">
              <span className="text-muted text-xs mr-auto hidden sm:block">
                Architecture / {groupingMode === 'files' ? t('workspace.modulesLabel') : t('workspace.packagesLabel')}
              </span>
              {(['files', 'canvas', 'inspector'] as const).map((view) => (
                <button
                  key={view}
                  className="mobile-view"
                  aria-pressed={mobileView === view}
                  onClick={() => setMobileView(view)}
                >
                  {view === 'files'
                    ? t('workspace.filesView')
                    : view === 'canvas'
                    ? t('workspace.canvasView')
                    : t('workspace.inspectorView')}
                </button>
              ))}
              <button
                className="desktop-panel-toggle"
                aria-pressed={showExplorer && !focusMode}
                onClick={() => {
                  setFocusMode(false);
                  setShowExplorer((v) => !v);
                }}
              >
                {t('workspace.explorerToggle')}
              </button>
              <button
                className="desktop-panel-toggle"
                aria-pressed={showInspector && !focusMode}
                title="Toggle inspector (Alt+I)"
                onClick={() => {
                  setFocusMode(false);
                  setShowInspector((v) => !v);
                }}
              >
                {t('workspace.inspectorToggle')}
              </button>
              <button
                aria-pressed={focusMode}
                title="Focus canvas (Alt+F), Escape to exit"
                onClick={() => {
                  setFocusMode((v) => !v);
                  setMobileView('canvas');
                }}
              >
                {focusMode ? t('workspace.exitFocus') : t('workspace.focusCanvas')}
              </button>
            </div>

            <div
              className="workspace-panels"
              data-mobile={mobileView}
              data-explorer={showExplorer && !focusMode}
              data-inspector={showInspector && !focusMode}
              style={
                {
                  '--explorer-width': `${explorerWidth}px`,
                  '--inspector-width': `${inspectorWidth}px`,
                } as React.CSSProperties
              }
            >
              <ExplorerSidebar
                allFiles={result.files}
                filteredFiles={filteredFiles}
                selectedFileId={selectedFileId}
                onSelectFile={selectFile}
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

              {showExplorer && !focusMode && (
                <PanelResizer
                  label={t('workspace.resizeExplorer')}
                  value={explorerWidth}
                  min={220}
                  max={400}
                  onChange={setExplorerWidth}
                />
              )}

              <Suspense
                fallback={
                  <div className="graph-workspace grid place-content-center text-xs text-muted" role="status">
                    {t('graph.loading')}
                  </div>
                }
              >
                <DependencyGraph
                  files={filteredFiles}
                  edges={filteredEdges}
                  selectedFileId={selectedFileId}
                  neighborIds={neighborIds}
                  onSelectFile={selectFile}
                  layoutMode={layoutMode}
                  onLayoutModeChange={setLayoutMode}
                  densityMode={densityMode}
                  onDensityModeChange={setDensityMode}
                  groupingMode={groupingMode}
                  onGroupingModeChange={setGroupingMode}
                  focusNeighborhood={focusNeighborhood}
                  onToggleFocusNeighborhood={() => setFocusNeighborhood((prev) => !prev)}
                  highlightCycles={highlightCycles}
                  onToggleHighlightCycles={() => setHighlightCycles((prev) => !prev)}
                  workstationMode={workstationMode}
                />
              </Suspense>

              {showInspector && !focusMode && (
                <PanelResizer
                  label={t('workspace.resizeInspector')}
                  value={inspectorWidth}
                  min={260}
                  max={460}
                  reverse
                  onChange={setInspectorWidth}
                />
              )}

              <InspectorPanel
                key={selectedFileId}
                packageFiles={
                  groupingMode === 'directories' && selectedFile
                    ? result.files.filter((file) => file.directory === selectedFile.directory)
                    : undefined
                }
                onExpandPackage={() => setGroupingMode('files')}
                selectedFile={selectedFile}
                allCycles={result.cycles}
                allFindings={result.health_report.findings}
                onSelectFile={selectFile}
                workstationMode={workstationMode}
              />
            </div>
          </>
        ) : (
          <Suspense fallback={<p role="status" className="p-6 text-xs text-muted">{t('report.loading')}</p>}>
            <HealthReportView
              result={result}
              onSelectFileInStudio={handleSelectFileFromReport}
              workstationMode={workstationMode}
            />
          </Suspense>
        )}
      </main>

      {/* Modals & Dialogs */}
      <FolderBrowserDialog
        isOpen={folderDialogOpen}
        initialPath={
          targetInput.startsWith('https://') || targetInput === 'demo'
            ? defaultWorkspacePath
            : targetInput
        }
        onClose={() => setFolderDialogOpen(false)}
        onSelectFolder={(chosenPath) => {
          setSourceType('local');
          setTargetInput(chosenPath);
        }}
      />

      <CommandPaletteDialog
        isOpen={commandPaletteOpen}
        onClose={() => setCommandPaletteOpen(false)}
        files={result ? result.files : []}
        onSelectFile={selectFile}
        onSwitchTab={setActiveTab}
        onToggleTheme={handleToggleThemeFromPalette}
        onChangeLayout={setLayoutMode}
        onChangeGrouping={setGroupingMode}
        onChangeDensity={setDensityMode}
        onToggleCyclesOnly={() => setCyclesOnly((prev) => !prev)}
        onResetFilters={handleResetFilters}
        workstationMode={workstationMode}
        onToggleMode={() => setWorkstationMode((v) => (v === 'simple' ? 'advanced' : 'simple'))}
        onToggleLanguage={() => {
          const next = i18n.language.startsWith('tr') ? 'en' : 'tr';
          void i18n.changeLanguage(next);
          if (typeof document !== 'undefined') {
            document.documentElement.lang = next;
          }
          savePreference('locale', next);
        }}
        onOpenTour={() => setTourOpen(true)}
        onExportReport={
          result
            ? (fmt) => {
                window.open(getExportUrl(result.analysis_id, fmt), '_blank', 'noopener');
              }
            : undefined
        }
        onLoadDemo={() => {
          setSourceType('demo');
          setTargetInput('demo');
          void handleTriggerScan('demo', 'demo');
        }}
      />

      {/* Guided First-Run Tour */}
      <OnboardingTour
        isOpen={tourOpen}
        onClose={() => {
          setTourOpen(false);
          savePreference('onboardingDismissed', true);
        }}
        onTryDemo={() => {
          setSourceType('demo');
          setTargetInput('demo');
          void handleTriggerScan('demo', 'demo');
        }}
      />
    </div>
  );
};
