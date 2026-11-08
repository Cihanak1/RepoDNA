import React, { lazy, Suspense, useDeferredValue, useEffect, useMemo, useRef, useState } from 'react';
import {
  AlertCircle,
} from 'lucide-react';
import {
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
import { PanelResizer } from './components/PanelResizer';
import { readPreference, savePreference } from './utils/preferences';
import { SummaryStrip } from './components/SummaryStrip';
import type {
  AnalysisResult,
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
  const [activeJob, setActiveJob] = useState<ScanProgress | null>(null);
  const [scanningTargetLabel, setScanningTargetLabel] = useState<string>('');
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [errorBanner, setErrorBanner] = useState<{ code: string; message: string } | null>(null);

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
        setTargetInput((prev) => prev || info.default_workspace);
      })
      .catch(() => {
        // Backend may still be starting
      });
    return () => {
      mounted = false;
      scanSessionIdRef.current += 1;
      if (pollTimerRef.current !== null) {
        window.clearTimeout(pollTimerRef.current);
        pollTimerRef.current = null;
      }
    };
  }, []);

  // Update document title dynamically for accessibility
  useEffect(() => {
    if (result) {
      const scoreText =
        result.health_report.overall_score !== null
          ? `${result.health_report.overall_score.toFixed(0)}/100`
          : 'N/A';
      document.title = `${result.repo_name} (${scoreText}) | RepoDNA`;
    } else {
      document.title = 'RepoDNA — Developer Repository Intelligence Platform';
    }
  }, [result]);

  const stopPolling = () => {
    if (pollTimerRef.current !== null) {
      window.clearTimeout(pollTimerRef.current);
      pollTimerRef.current = null;
    }
    pollInFlightRef.current = false;
  };

  const handleTriggerScan = async (
    overrideSource?: SourceType,
    overrideTarget?: string
  ) => {
    scanSessionIdRef.current += 1;
    const currentSession = scanSessionIdRef.current;
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

    setScanningTargetLabel(effTarget);

    try {
      const initialJob = await startAsyncScanJob({
        source_type: effSource,
        target: effTarget,
        branch: effSource === 'github' && branchInput.trim() ? branchInput.trim() : null,
        limits,
      });
      if (currentSession !== scanSessionIdRef.current) {
        return;
      }
      setActiveJob(initialJob);

      const pollOnce = async () => {
        if (currentSession !== scanSessionIdRef.current) {
          return;
        }
        if (pollInFlightRef.current) {
          return;
        }
        pollInFlightRef.current = true;
        try {
          const progress = await fetchJobProgress(initialJob.job_id);
          if (currentSession !== scanSessionIdRef.current) {
            return;
          }
          setActiveJob(progress);

          if (progress.status === 'completed') {
            stopPolling();
            const finalResult = await fetchJobResultWithRetry(initialJob.job_id);
            if (currentSession !== scanSessionIdRef.current) {
              return;
            }
            setResult(finalResult);
            setActiveJob(null);
            setActiveTab('studio');
            const firstCycleFile = finalResult.files.find((f) => f.in_cycle);
            const firstFile =
              firstCycleFile ??
              [...finalResult.files].sort(
                (a, b) => b.fan_in + b.fan_out - (a.fan_in + a.fan_out)
              )[0] ??
              null;
            setSelectedFileId(firstFile ? firstFile.id : null);
            return;
          }

          if (progress.status === 'failed' || progress.status === 'cancelled') {
            stopPolling();
            setErrorBanner({
              code: progress.error_code || progress.status.toUpperCase(),
              message: progress.error_message || progress.phase_message,
            });
            setActiveJob(null);
            return;
          }

          // Schedule next single-flight poll only after current poll settles
          pollTimerRef.current = window.setTimeout(() => {
            void pollOnce();
          }, 180);
        } catch (err) {
          if (currentSession !== scanSessionIdRef.current) {
            return;
          }
          stopPolling();
          const code =
            err && typeof err === 'object' && 'code' in err
              ? String((err as { code: string }).code)
              : 'POLL_ERROR';
          setErrorBanner({
            code,
            message: err instanceof Error ? err.message : 'Failed to poll scan job status.',
          });
          setActiveJob(null);
        } finally {
          pollInFlightRef.current = false;
        }
      };

      await pollOnce();
    } catch (err: unknown) {
      if (currentSession !== scanSessionIdRef.current) {
        return;
      }
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
    scanSessionIdRef.current += 1;
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

  const handleToggleThemeFromPalette = () => {
    const meta = document.querySelector<HTMLMetaElement>('meta[name="color-scheme"]');
    const current = meta?.content === 'light' ? 'light' : 'dark';
    const next = current === 'dark' ? 'light' : 'dark';
    try {
      localStorage.setItem('color-scheme', next);
    } catch {
      // ignore
    }
    if (meta) meta.content = next;
    window.dispatchEvent(new StorageEvent('storage', { key: 'color-scheme', newValue: next }));
  };

  const { filteredFiles, filteredEdges, neighborIds } = useMemo(() => {
    if (!result) {
      return { filteredFiles: [], filteredEdges: [], neighborIds: new Set<string>() };
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

  const handleSelectFileFromReport = (fileId: string) => {
    selectFile(fileId);
    setActiveTab('studio');
  };

  return (
    <div className="app-shell flex flex-col bg-canvas text-ink">
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
        onOpenCommandPalette={() => setCommandPaletteOpen(true)}
      />

      {/* Error / Security Rejection Alert */}
      {errorBanner && (
        <div
          role="alert"
          data-testid="error-alert-banner"
          className="bg-danger/10 border-b border-danger/70 px-4 py-2.5 flex items-center justify-between gap-3 text-xs text-danger"
        >
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-danger shrink-0" aria-hidden="true" />
            <span>
              <strong className="font-mono">[{errorBanner.code}]</strong> {errorBanner.message}
            </span>
          </div>
          <button
            type="button"
            onClick={() => setErrorBanner(null)}
            className="px-2 py-0.5 rounded bg-danger-solid hover:bg-danger-solid text-white text-[11px] cursor-pointer"
          >
            Dismiss
          </button>
        </div>
      )}

      {activeJob && result && (
        <div
          role="status"
          data-testid="previous-analysis-banner"
          className="bg-warning/10 border-b border-warning/60 px-4 py-2 flex items-center justify-between gap-3 text-xs text-warning"
        >
          <div>
            <strong className="tracking-wide font-bold text-warning mr-2">
              Previous analysis ({result.repo_name})
            </strong>
            <span>
              Viewing previous snapshot while scanning{' '}
              <code className="font-mono text-warning">{scanningTargetLabel}</code> &mdash;{' '}
              {activeJob.phase_message} ({activeJob.progress_percent.toFixed(0)}%)
            </span>
          </div>
          <span className="text-[11px] font-mono text-warning shrink-0">
            Updating automatically when complete...
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
        />
      )}

      <main id="main-workspace" tabIndex={-1} className="flex-1 flex flex-col overflow-hidden">
        {!result ? (
          <Launchpad workspace={defaultWorkspacePath} scanning={activeJob !== null}
            onWorkspace={() => { setSourceType('local'); setTargetInput(defaultWorkspacePath); void handleTriggerScan('local', defaultWorkspacePath); }}
            onBrowse={() => setFolderDialogOpen(true)}
            onGithub={() => { setSourceType('github'); setTargetInput('https://github.com/'); document.getElementById('repo-target-input')?.focus(); }}
            onDemo={() => { setSourceType('demo'); setTargetInput('demo'); void handleTriggerScan('demo', 'demo'); }} />
        ) : activeTab === 'studio' ? (
          <>
          <div className="workspace-controls" role="toolbar" aria-label="Workspace panels">
            <span className="text-muted text-xs mr-auto hidden sm:block">Architecture / {groupingMode === 'files' ? 'Modules' : 'Packages'}</span>
            {(['files', 'canvas', 'inspector'] as const).map(view => <button key={view} className="mobile-view" aria-pressed={mobileView === view} onClick={() => setMobileView(view)}>{view === 'files' ? 'Files' : view === 'canvas' ? 'Canvas' : 'Inspector'}</button>)}
            <button className="desktop-panel-toggle" aria-pressed={showExplorer && !focusMode} onClick={() => { setFocusMode(false); setShowExplorer(v => !v); }}>Explorer</button>
            <button className="desktop-panel-toggle" aria-pressed={showInspector && !focusMode} title="Toggle inspector (Alt+I)" onClick={() => { setFocusMode(false); setShowInspector(v => !v); }}>Inspector</button>
            <button aria-pressed={focusMode} title="Focus canvas (Alt+F), Escape to exit" onClick={() => { setFocusMode(v => !v); setMobileView('canvas'); }}>{focusMode ? 'Exit focus' : 'Focus canvas'}</button>
          </div>
          <div className="workspace-panels" data-mobile={mobileView} data-explorer={showExplorer && !focusMode} data-inspector={showInspector && !focusMode}
            style={{ '--explorer-width': `${explorerWidth}px`, '--inspector-width': `${inspectorWidth}px` } as React.CSSProperties}>
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

            {showExplorer && !focusMode && <PanelResizer label="Explorer width" value={explorerWidth} min={220} max={400} onChange={setExplorerWidth} />}
            <Suspense fallback={<div className="graph-workspace grid place-content-center" role="status">Loading architecture canvas…</div>}>
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
            />
            </Suspense>

            {showInspector && !focusMode && <PanelResizer label="Inspector width" value={inspectorWidth} min={260} max={460} reverse onChange={setInspectorWidth} />}
            <InspectorPanel
              key={selectedFileId}
              packageFiles={groupingMode === 'directories' && selectedFile ? result.files.filter(file => file.directory === selectedFile.directory) : undefined}
              onExpandPackage={() => setGroupingMode('files')}
              selectedFile={selectedFile}
              allCycles={result.cycles}
              allFindings={result.health_report.findings}
              onSelectFile={selectFile}
            />
          </div>
          </>
        ) : (
          <Suspense fallback={<p role="status" className="p-6">Loading health report…</p>}>
          <HealthReportView
            result={result}
            onSelectFileInStudio={handleSelectFileFromReport}
          />
          </Suspense>
        )}
      </main>

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
    </div>
  );
};
