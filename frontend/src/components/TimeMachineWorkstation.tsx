import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  AlertCircle,
  ArrowRight,
  Calendar,
  CheckCircle2,
  ChevronRight,
  Clock,
  Copy,
  Database,
  Download,
  FileCode,
  GitCommit,
  GitCompare,
  Layers,
  LineChart,
  RefreshCw,
  Search,
  ShieldAlert,
  Sparkles,
  TrendingDown,
  TrendingUp,
  User,
  X,
} from 'lucide-react';
import {
  fetchHistoricalCommits,
  fetchHistoricalDiff,
  fetchHistoricalEvidenceBlob,
  fetchHistoricalSnapshot,
  fetchHistoricalTimeline,
} from '../api/client';
import type {
  HistoricalCommitItem,
  HistoricalDiffResult,
  HistoricalEvidenceBlobResponse,
  HistoricalSnapshot,
  TimelineEntry,
  TimelineResult,
} from '../types/history';
import type { AnalysisResult } from '../types/repodna';
import type { WorkstationMode } from '../utils/preferences';

type TimeMachineView = 'timeline' | 'diff' | 'trends';

interface TimeMachineWorkstationProps {
  result: AnalysisResult;
  workstationMode?: WorkstationMode;
  onSelectFileInStudio?: (fileId: string) => void;
}

export const TimeMachineWorkstation: React.FC<TimeMachineWorkstationProps> = ({
  result,
}) => {
  const { t } = useTranslation();
  const [activeView, setActiveView] = useState<TimeMachineView>('timeline');

  // Commits list
  const [commits, setCommits] = useState<HistoricalCommitItem[]>([]);
  const [loadingCommits, setLoadingCommits] = useState(false);
  const [commitsError, setCommitsError] = useState<string | null>(null);
  const [commitSearch, setCommitSearch] = useState('');
  const [selectedCommitSha, setSelectedCommitSha] = useState<string | null>(null);

  // Snapshot for selected commit
  const [snapshot, setSnapshot] = useState<HistoricalSnapshot | null>(null);
  const [loadingSnapshot, setLoadingSnapshot] = useState(false);
  const [snapshotError, setSnapshotError] = useState<string | null>(null);

  // Timeline
  const [timeline, setTimeline] = useState<TimelineResult | null>(null);
  const [loadingTimeline, setLoadingTimeline] = useState(false);
  const [timelineError, setTimelineError] = useState<string | null>(null);

  // Diff comparison
  const [baseCommitSha, setBaseCommitSha] = useState<string>('');
  const [headCommitSha, setHeadCommitSha] = useState<string>('');
  const [diffResult, setDiffResult] = useState<HistoricalDiffResult | null>(null);
  const [loadingDiff, setLoadingDiff] = useState(false);
  const [diffError, setDiffError] = useState<string | null>(null);

  // Historical Evidence modal
  const [evidenceModalOpen, setEvidenceModalOpen] = useState(false);
  const [selectedEvidence, setSelectedEvidence] =
    useState<HistoricalEvidenceBlobResponse | null>(null);
  const [loadingEvidence, setLoadingEvidence] = useState(false);
  const [evidenceError, setEvidenceError] = useState<string | null>(null);
  const [copiedLink, setCopiedLink] = useState(false);

  // Notification / toast status
  const [statusMsg, setStatusMsg] = useState<string | null>(null);

  const showStatus = (msg: string) => {
    setStatusMsg(msg);
    window.setTimeout(() => setStatusMsg(null), 3000);
  };

  // Load commit list on mount or when analysisId changes
  const loadCommits = useCallback(async () => {
    setLoadingCommits(true);
    setCommitsError(null);
    try {
      const resp = await fetchHistoricalCommits(result.analysis_id, 100, 0);
      setCommits(resp.commits);
      if (resp.commits.length > 0 && !selectedCommitSha) {
        setSelectedCommitSha(resp.commits[0].sha);
        if (resp.commits.length > 1) {
          setBaseCommitSha(resp.commits[resp.commits.length - 1].sha);
          setHeadCommitSha(resp.commits[0].sha);
        }
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to fetch commits.';
      setCommitsError(msg);
    } finally {
      setLoadingCommits(false);
    }
  }, [result.analysis_id, selectedCommitSha]);

  useEffect(() => {
    void loadCommits();
  }, [loadCommits]);

  // Load snapshot when selected commit changes
  useEffect(() => {
    if (!selectedCommitSha) return;
    let isCancelled = false;

    const loadSnapshot = async () => {
      setLoadingSnapshot(true);
      setSnapshotError(null);
      try {
        const snap = await fetchHistoricalSnapshot(
          result.analysis_id,
          selectedCommitSha,
          true
        );
        if (!isCancelled) {
          setSnapshot(snap);
        }
      } catch (err: unknown) {
        if (!isCancelled) {
          const msg = err instanceof Error ? err.message : 'Snapshot analysis failed.';
          setSnapshotError(msg);
        }
      } finally {
        if (!isCancelled) setLoadingSnapshot(false);
      }
    };

    void loadSnapshot();
    return () => {
      isCancelled = true;
    };
  }, [result.analysis_id, selectedCommitSha]);

  // Load timeline on demand
  const handleLoadTimeline = useCallback(async () => {
    if (timeline || loadingTimeline) return;
    setLoadingTimeline(true);
    setTimelineError(null);
    try {
      const res = await fetchHistoricalTimeline(result.analysis_id, 30);
      setTimeline(res);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to generate timeline.';
      setTimelineError(msg);
    } finally {
      setLoadingTimeline(false);
    }
  }, [result.analysis_id, timeline, loadingTimeline]);

  useEffect(() => {
    if (activeView === 'trends') {
      void handleLoadTimeline();
    }
  }, [activeView, handleLoadTimeline]);

  // Run Evolution Diff
  const handleRunDiff = async () => {
    if (!baseCommitSha || !headCommitSha) return;
    setLoadingDiff(true);
    setDiffError(null);
    try {
      const res = await fetchHistoricalDiff(
        result.analysis_id,
        baseCommitSha,
        headCommitSha
      );
      setDiffResult(res);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Diff calculation failed.';
      setDiffError(msg);
    } finally {
      setLoadingDiff(false);
    }
  };

  // Inspect Historical Evidence
  const handleInspectEvidence = async (
    commitSha: string,
    filePath: string,
    lineStart: number = 1,
    lineEnd: number = 50,
    evidenceId: string = 'ev_inspect'
  ) => {
    setEvidenceModalOpen(true);
    setLoadingEvidence(true);
    setEvidenceError(null);
    try {
      const blob = await fetchHistoricalEvidenceBlob(
        result.analysis_id,
        evidenceId,
        commitSha,
        filePath,
        lineStart,
        lineEnd
      );
      setSelectedEvidence(blob);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to read historical Git blob.';
      setEvidenceError(msg);
    } finally {
      setLoadingEvidence(false);
    }
  };

  // Copy text to clipboard
  const handleCopy = (text: string, label: string) => {
    void navigator.clipboard.writeText(text);
    showStatus(`${label} copied to clipboard!`);
  };

  // Export Diff
  const handleExportDiff = (format: 'json' | 'markdown') => {
    if (!diffResult) return;
    const content =
      format === 'json'
        ? JSON.stringify(diffResult, null, 2)
        : diffResult.summary_text;
    const blob = new Blob([content], {
      type: format === 'json' ? 'application/json' : 'text/markdown',
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `repodna-evolution-diff-${diffResult.base_commit_sha.slice(0, 7)}-to-${diffResult.head_commit_sha.slice(0, 7)}.${format === 'json' ? 'json' : 'md'}`;
    a.click();
    URL.revokeObjectURL(url);
    showStatus(`Exported diff as ${format.toUpperCase()}`);
  };

  // Filtered commits for sidebar
  const filteredCommits = useMemo(() => {
    if (!commitSearch.trim()) return commits;
    const q = commitSearch.toLowerCase();
    return commits.filter(
      (c) =>
        c.subject.toLowerCase().includes(q) ||
        c.author.toLowerCase().includes(q) ||
        c.sha.toLowerCase().includes(q)
    );
  }, [commits, commitSearch]);

  const selectedIndex = useMemo(() => {
    return commits.findIndex((c) => c.sha === selectedCommitSha);
  }, [commits, selectedCommitSha]);

  return (
    <div
      data-testid="time-machine-workstation"
      className="flex flex-col h-full bg-canvas overflow-hidden"
    >
      {/* Sub-Navigation Header Bar */}
      <div className="px-4 py-2 bg-panel border-b border-line flex items-center justify-between gap-3 shrink-0">
        <div className="flex items-center gap-1.5 overflow-x-auto">
          <button
            type="button"
            data-testid="tm-subtab-timeline-btn"
            onClick={() => setActiveView('timeline')}
            className={`px-3 py-1.5 rounded-md text-xs font-medium flex items-center gap-1.5 transition cursor-pointer ${
              activeView === 'timeline'
                ? 'bg-accent-solid text-white shadow-xs'
                : 'text-muted hover:text-ink hover:bg-raised'
            }`}
          >
            <Clock className="w-3.5 h-3.5" />
            <span>{t('history.timelineTab', 'Commit Timeline & Scrubber')}</span>
          </button>

          <button
            type="button"
            data-testid="tm-subtab-diff-btn"
            onClick={() => setActiveView('diff')}
            className={`px-3 py-1.5 rounded-md text-xs font-medium flex items-center gap-1.5 transition cursor-pointer ${
              activeView === 'diff'
                ? 'bg-accent-solid text-white shadow-xs'
                : 'text-muted hover:text-ink hover:bg-raised'
            }`}
          >
            <GitCompare className="w-3.5 h-3.5" />
            <span>{t('history.diffTab', 'Evolution Diff')}</span>
          </button>

          <button
            type="button"
            data-testid="tm-subtab-trends-btn"
            onClick={() => setActiveView('trends')}
            className={`px-3 py-1.5 rounded-md text-xs font-medium flex items-center gap-1.5 transition cursor-pointer ${
              activeView === 'trends'
                ? 'bg-accent-solid text-white shadow-xs'
                : 'text-muted hover:text-ink hover:bg-raised'
            }`}
          >
            <LineChart className="w-3.5 h-3.5" />
            <span>{t('history.trendsTab', 'Architecture Trends')}</span>
          </button>
        </div>

        <div className="flex items-center gap-2">
          {statusMsg && (
            <span
              role="status"
              className="text-xs px-2 py-0.5 rounded bg-accent/15 border border-accent/30 text-accent font-medium animate-fade"
            >
              {statusMsg}
            </span>
          )}
          <button
            type="button"
            onClick={() => void loadCommits()}
            disabled={loadingCommits}
            className="p-1 rounded-md text-muted hover:text-ink hover:bg-raised transition cursor-pointer"
            title="Refresh commit history"
          >
            <RefreshCw
              className={`w-3.5 h-3.5 ${loadingCommits ? 'animate-spin' : ''}`}
            />
          </button>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 overflow-hidden flex flex-col md:flex-row">
        {/* ========================================================================= */}
        {/* VIEW 1: TIMELINE & SCRUBBER */}
        {/* ========================================================================= */}
        {activeView === 'timeline' && (
          <div className="flex-1 flex flex-col md:flex-row overflow-hidden">
            {/* Left Rail: Commit History List */}
            <div className="w-full md:w-80 border-r border-line bg-panel flex flex-col shrink-0 overflow-hidden">
              <div className="p-3 border-b border-line flex flex-col gap-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-ink uppercase tracking-wider flex items-center gap-1.5">
                    <GitCommit className="w-3.5 h-3.5 text-accent" />
                    <span>{t('history.commitHistory', 'Git Commits')}</span>
                  </span>
                  <span className="text-[11px] font-mono text-muted">
                    {filteredCommits.length} / {commits.length}
                  </span>
                </div>
                <div className="relative">
                  <Search className="w-3 h-3 text-muted absolute left-2.5 top-1/2 -translate-y-1/2" />
                  <input
                    type="text"
                    data-testid="commit-search-input"
                    value={commitSearch}
                    onChange={(e) => setCommitSearch(e.target.value)}
                    placeholder={t('history.searchPlaceholder', 'Filter commits or authors...')}
                    className="w-full pl-7 pr-3 py-1 bg-canvas border border-line rounded text-xs text-ink placeholder:text-muted focus:outline-none focus:border-accent"
                  />
                </div>
              </div>

              {/* Scrubber slider */}
              {commits.length > 1 && (
                <div className="px-3 py-2 bg-raised border-b border-line flex flex-col gap-1">
                  <div className="flex items-center justify-between text-[11px] text-muted">
                    <span>{t('history.scrubber', 'Time Scrubber')}</span>
                    <span className="font-mono">
                      #{selectedIndex >= 0 ? commits.length - selectedIndex : 1} of{' '}
                      {commits.length}
                    </span>
                  </div>
                  <input
                    type="range"
                    min={0}
                    max={commits.length - 1}
                    value={selectedIndex >= 0 ? selectedIndex : 0}
                    onChange={(e) => {
                      const idx = parseInt(e.target.value, 10);
                      if (commits[idx]) {
                        setSelectedCommitSha(commits[idx].sha);
                      }
                    }}
                    className="w-full accent-accent cursor-pointer h-1.5 bg-line rounded-lg"
                  />
                  <div className="flex justify-between text-[10px] text-muted font-mono">
                    <span>Latest (HEAD)</span>
                    <span>Oldest</span>
                  </div>
                </div>
              )}

              {/* Commit Items Scrollable List */}
              <div
                data-testid="commit-list-container"
                className="flex-1 overflow-y-auto divide-y divide-line/60"
              >
                {loadingCommits ? (
                  <div className="p-6 text-center text-xs text-muted">
                    <RefreshCw className="w-4 h-4 animate-spin mx-auto mb-2 text-accent" />
                    <span>{t('history.loadingCommits', 'Reading Git commit history...')}</span>
                  </div>
                ) : commitsError ? (
                  <div className="p-4 text-xs text-danger bg-danger/10 m-3 rounded border border-danger/30">
                    <AlertCircle className="w-4 h-4 mb-1" />
                    <p>{commitsError}</p>
                  </div>
                ) : filteredCommits.length === 0 ? (
                  <div className="p-6 text-center text-xs text-muted">
                    {t('history.noCommitsFound', 'No matching commits.')}
                  </div>
                ) : (
                  filteredCommits.map((c) => {
                    const isSelected = c.sha === selectedCommitSha;
                    return (
                      <div
                        key={c.sha}
                        data-testid={`commit-item-${c.short_sha}`}
                        onClick={() => setSelectedCommitSha(c.sha)}
                        className={`p-3 transition cursor-pointer text-left flex flex-col gap-1 ${
                          isSelected
                            ? 'bg-accent/10 border-l-4 border-accent pl-2'
                            : 'hover:bg-raised'
                        }`}
                      >
                        <div className="flex items-center justify-between gap-1 text-[11px]">
                          <span className="font-mono font-bold text-accent flex items-center gap-1">
                            <GitCommit className="w-3 h-3" />
                            {c.short_sha}
                          </span>
                          <span className="text-[10px] text-muted flex items-center gap-1">
                            <Calendar className="w-2.5 h-2.5" />
                            {c.timestamp ? c.timestamp.slice(0, 10) : ''}
                          </span>
                        </div>
                        <p className="text-xs text-ink font-medium line-clamp-2 leading-relaxed">
                          {c.subject}
                        </p>
                        <div className="flex items-center justify-between text-[10px] text-muted mt-0.5">
                          <span className="flex items-center gap-1 truncate max-w-[130px]">
                            <User className="w-2.5 h-2.5" />
                            {c.author}
                          </span>
                          {c.is_cached ? (
                            <span className="px-1.5 py-0.2 rounded bg-success/15 border border-success/30 text-success font-medium">
                              {t('history.cached', 'Cached')}
                            </span>
                          ) : (
                            <span className="text-muted/70">Unanalyzed</span>
                          )}
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
            </div>

            {/* Right Pane: Historical Snapshot Details */}
            <div className="flex-1 flex flex-col overflow-y-auto bg-canvas p-4 md:p-6">
              {loadingSnapshot ? (
                <div
                  data-testid="snapshot-loading-indicator"
                  className="flex-1 flex flex-col items-center justify-center text-xs text-muted gap-2"
                >
                  <RefreshCw className="w-6 h-6 animate-spin text-accent" />
                  <p className="font-medium text-ink">
                    {t(
                      'history.extractingSnapshot',
                      'Extracting and analyzing historical Git snapshot...'
                    )}
                  </p>
                  <p className="text-muted text-[11px]">
                    Using safe sandbox extraction. Active working tree remains untouched.
                  </p>
                </div>
              ) : snapshotError ? (
                <div className="p-4 bg-danger/10 border border-danger/30 rounded-lg text-xs text-danger flex flex-col gap-2">
                  <div className="flex items-center gap-2 font-bold">
                    <ShieldAlert className="w-4 h-4" />
                    <span>Snapshot Analysis Failed</span>
                  </div>
                  <p>{snapshotError}</p>
                </div>
              ) : snapshot ? (
                <div className="flex flex-col gap-6 max-w-5xl mx-auto w-full">
                  {/* Top Commit Banner */}
                  <div className="p-4 rounded-xl bg-panel border border-line shadow-xs flex flex-col gap-3">
                    <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line pb-3">
                      <div className="flex items-center gap-2">
                        <span className="px-2 py-0.5 rounded bg-accent-solid text-white font-mono text-xs font-bold">
                          {snapshot.commit_sha.slice(0, 10)}
                        </span>
                        <button
                          type="button"
                          onClick={() => handleCopy(snapshot.commit_sha, 'Commit SHA')}
                          className="text-muted hover:text-ink text-xs flex items-center gap-1 cursor-pointer"
                          title="Copy full 40-char SHA"
                        >
                          <Copy className="w-3 h-3" />
                          <span className="font-mono text-[11px]">
                            {snapshot.commit_sha.slice(0, 20)}...
                          </span>
                        </button>
                      </div>

                      <div className="flex items-center gap-2">
                        {snapshot.cache_hit ? (
                          <span
                            data-testid="snapshot-cache-hit-badge"
                            className="px-2 py-0.5 rounded bg-success/15 border border-success/30 text-success text-xs font-medium flex items-center gap-1"
                          >
                            <Database className="w-3 h-3" />
                            <span>Cache Hit (Instant)</span>
                          </span>
                        ) : (
                          <span className="px-2 py-0.5 rounded bg-raised border border-line text-muted text-xs font-medium">
                            Fresh Analysis
                          </span>
                        )}

                        <span className="text-xs text-muted font-mono">
                          {snapshot.commit_timestamp ? snapshot.commit_timestamp.slice(0, 10) : ''}
                        </span>
                      </div>
                    </div>

                    <div className="flex flex-col gap-1">
                      <h3 className="text-base font-bold text-ink leading-snug">
                        {snapshot.commit_message || 'Commit with no message'}
                      </h3>
                      <p className="text-xs text-muted flex items-center gap-1.5">
                        <User className="w-3 h-3 text-accent" />
                        <span>Author: {snapshot.commit_author}</span>
                        <span>•</span>
                        <span>Repo: {snapshot.repo_identity}</span>
                      </p>
                    </div>

                    {/* Limitations & Shallow Notice */}
                    {snapshot.is_shallow && (
                      <div className="p-2.5 rounded bg-warning/10 border border-warning/30 text-warning text-xs flex items-center gap-2">
                        <AlertCircle className="w-4 h-4 shrink-0" />
                        <span>
                          {t(
                            'history.shallowWarning',
                            'Repository is a shallow clone; parent lineage is truncated.'
                          )}
                        </span>
                      </div>
                    )}
                  </div>

                  {/* Architecture Metrics Grid */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                    <div className="p-3.5 rounded-lg bg-panel border border-line flex flex-col gap-1">
                      <span className="text-[11px] font-medium text-muted">
                        Health Score
                      </span>
                      <div className="flex items-baseline gap-2">
                        <span className="text-xl font-bold font-mono text-ink">
                          {snapshot.health.score !== null
                            ? snapshot.health.score.toFixed(1)
                            : 'N/A'}
                        </span>
                        <span className="px-1.5 py-0.5 rounded bg-accent/15 text-accent font-bold text-xs">
                          {snapshot.health.grade}
                        </span>
                      </div>
                      <span className="text-[10px] text-muted">
                        Status: {snapshot.health.status}
                      </span>
                    </div>

                    <div className="p-3.5 rounded-lg bg-panel border border-line flex flex-col gap-1">
                      <span className="text-[11px] font-medium text-muted">
                        Total Modules
                      </span>
                      <div className="flex items-baseline gap-2">
                        <span className="text-xl font-bold font-mono text-ink">
                          {snapshot.total_files}
                        </span>
                        <span className="text-xs text-muted font-mono">
                          {snapshot.total_lines_code.toLocaleString()} LOC
                        </span>
                      </div>
                      <span className="text-[10px] text-muted">
                        AST: {snapshot.ast_loc_coverage_pct.toFixed(1)}%
                      </span>
                    </div>

                    <div className="p-3.5 rounded-lg bg-panel border border-line flex flex-col gap-1">
                      <span className="text-[11px] font-medium text-muted">
                        Dependencies
                      </span>
                      <div className="flex items-baseline gap-2">
                        <span className="text-xl font-bold font-mono text-ink">
                          {snapshot.dependencies.length}
                        </span>
                        <span className="text-xs text-muted">edges</span>
                      </div>
                      <span className="text-[10px] text-muted">
                        Cross-module linkages
                      </span>
                    </div>

                    <div className="p-3.5 rounded-lg bg-panel border border-line flex flex-col gap-1">
                      <span className="text-[11px] font-medium text-muted">
                        Architectural Cycles
                      </span>
                      <div className="flex items-baseline gap-2">
                        <span
                          className={`text-xl font-bold font-mono ${
                            snapshot.cycles.length > 0
                              ? 'text-danger'
                              : 'text-success'
                          }`}
                        >
                          {snapshot.cycles.length}
                        </span>
                        <span className="text-xs text-muted">detected</span>
                      </div>
                      <span className="text-[10px] text-muted">
                        {snapshot.cycles.length === 0
                          ? 'Zero circular dependencies'
                          : 'Circular dependencies present'}
                      </span>
                    </div>
                  </div>

                  {/* Modules & Evidence Table */}
                  <div className="p-4 rounded-xl bg-panel border border-line flex flex-col gap-3">
                    <div className="flex items-center justify-between border-b border-line pb-2.5">
                      <h4 className="text-xs font-bold text-ink uppercase tracking-wider flex items-center gap-2">
                        <FileCode className="w-3.5 h-3.5 text-accent" />
                        <span>Module Inventory & Evidence ({snapshot.modules.length})</span>
                      </h4>
                      <span className="text-xs text-muted">
                        Click module to inspect historical Git blob
                      </span>
                    </div>

                    <div className="divide-y divide-line/60 max-h-80 overflow-y-auto">
                      {snapshot.modules.map((m) => (
                        <div
                          key={m.path}
                          data-testid={`snapshot-module-${m.name}`}
                          onClick={() =>
                            void handleInspectEvidence(
                              snapshot.commit_sha,
                              m.path,
                              1,
                              40,
                              `ev_mod_${m.name}`
                            )
                          }
                          className="py-2.5 px-2 hover:bg-raised transition flex items-center justify-between gap-3 text-xs cursor-pointer rounded"
                        >
                          <div className="flex flex-col min-w-0">
                            <span className="font-mono font-medium text-ink truncate">
                              {m.path}
                            </span>
                            <span className="text-[11px] text-muted">
                              {m.language} • {m.lines_code} LOC • {m.symbol_count} symbols
                            </span>
                          </div>

                          <div className="flex items-center gap-2 shrink-0">
                            {m.in_cycle && (
                              <span className="px-1.5 py-0.5 rounded bg-danger/15 text-danger font-medium text-[10px]">
                                In Cycle
                              </span>
                            )}
                            {m.is_hub && (
                              <span className="px-1.5 py-0.5 rounded bg-warning/15 text-warning font-medium text-[10px]">
                                Hub
                              </span>
                            )}
                            <span className="font-mono text-muted text-[11px]">
                              In: {m.fan_in} / Out: {m.fan_out}
                            </span>
                            <ChevronRight className="w-3.5 h-3.5 text-muted" />
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              ) : null}
            </div>
          </div>
        )}

        {/* ========================================================================= */}
        {/* VIEW 2: EVOLUTION DIFF VIEWER */}
        {/* ========================================================================= */}
        {activeView === 'diff' && (
          <div className="flex-1 flex flex-col p-4 md:p-6 overflow-y-auto bg-canvas">
            <div className="max-w-5xl mx-auto w-full flex flex-col gap-6">
              {/* Diff Controls Bar */}
              <div className="p-4 rounded-xl bg-panel border border-line shadow-xs flex flex-col md:flex-row items-center justify-between gap-4">
                <div className="flex flex-wrap items-center gap-3 w-full md:w-auto">
                  <div className="flex flex-col gap-1">
                    <label className="text-[11px] font-bold text-muted uppercase">
                      Base Commit (Older)
                    </label>
                    <select
                      data-testid="diff-base-select"
                      value={baseCommitSha}
                      onChange={(e) => setBaseCommitSha(e.target.value)}
                      className="px-2.5 py-1.5 bg-canvas border border-line rounded text-xs font-mono text-ink focus:outline-none focus:border-accent"
                    >
                      {commits.map((c) => (
                        <option key={`base-${c.sha}`} value={c.sha}>
                          {c.short_sha} — {c.subject ? c.subject.slice(0, 36) : ''} ({c.timestamp ? c.timestamp.slice(0, 10) : ''})
                        </option>
                      ))}
                    </select>
                  </div>

                  <ArrowRight className="w-4 h-4 text-muted hidden md:block mt-4" />

                  <div className="flex flex-col gap-1">
                    <label className="text-[11px] font-bold text-muted uppercase">
                      Head Commit (Newer)
                    </label>
                    <select
                      data-testid="diff-head-select"
                      value={headCommitSha}
                      onChange={(e) => setHeadCommitSha(e.target.value)}
                      className="px-2.5 py-1.5 bg-canvas border border-line rounded text-xs font-mono text-ink focus:outline-none focus:border-accent"
                    >
                      {commits.map((c) => (
                        <option key={`head-${c.sha}`} value={c.sha}>
                          {c.short_sha} — {c.subject ? c.subject.slice(0, 36) : ''} ({c.timestamp ? c.timestamp.slice(0, 10) : ''})
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  <button
                    type="button"
                    data-testid="run-diff-btn"
                    onClick={() => void handleRunDiff()}
                    disabled={loadingDiff || !baseCommitSha || !headCommitSha}
                    className="px-4 py-2 bg-accent-solid text-white font-medium text-xs rounded-lg shadow-xs hover:opacity-95 transition flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
                  >
                    <GitCompare
                      className={`w-3.5 h-3.5 ${loadingDiff ? 'animate-spin' : ''}`}
                    />
                    <span>
                      {loadingDiff
                        ? t('history.calculatingDiff', 'Comparing...')
                        : t('history.compareCommits', 'Compare Architecture')}
                    </span>
                  </button>

                  {diffResult && (
                    <div className="flex items-center gap-1 border-l border-line pl-2">
                      <button
                        type="button"
                        onClick={() => handleExportDiff('json')}
                        className="px-2 py-1.5 rounded bg-raised hover:bg-line text-ink text-xs font-medium transition cursor-pointer flex items-center gap-1"
                        title="Download Diff JSON"
                      >
                        <Download className="w-3 h-3 text-accent" />
                        <span>JSON</span>
                      </button>
                      <button
                        type="button"
                        onClick={() => handleExportDiff('markdown')}
                        className="px-2 py-1.5 rounded bg-raised hover:bg-line text-ink text-xs font-medium transition cursor-pointer flex items-center gap-1"
                        title="Download Diff Markdown"
                      >
                        <Download className="w-3 h-3 text-accent" />
                        <span>MD</span>
                      </button>
                    </div>
                  )}
                </div>
              </div>

              {/* Diff Result Breakdown */}
              {loadingDiff ? (
                <div className="p-12 text-center text-xs text-muted flex flex-col items-center gap-2">
                  <RefreshCw className="w-6 h-6 animate-spin text-accent" />
                  <p className="font-bold text-ink">
                    Analyzing architectural evolution between revisions...
                  </p>
                </div>
              ) : diffError ? (
                <div className="p-4 bg-danger/10 border border-danger/30 rounded-lg text-xs text-danger flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 shrink-0" />
                  <p>{diffError}</p>
                </div>
              ) : diffResult ? (
                <div
                  data-testid="evolution-diff-content"
                  className="flex flex-col gap-6"
                >
                  {/* Summary Delta Banner */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                    <div className="p-3.5 rounded-lg bg-panel border border-line flex flex-col gap-1">
                      <span className="text-[11px] font-medium text-muted">
                        Health Score Delta
                      </span>
                      <div className="flex items-baseline gap-2">
                        <span className="text-xl font-bold font-mono text-ink">
                          {diffResult.health_delta.score_after !== null
                            ? diffResult.health_delta.score_after.toFixed(1)
                            : 'N/A'}
                        </span>
                        {diffResult.health_delta.score_delta !== null && (
                          <span
                            className={`text-xs font-bold font-mono flex items-center ${
                              diffResult.health_delta.score_delta >= 0
                                ? 'text-success'
                                : 'text-danger'
                            }`}
                          >
                            {diffResult.health_delta.score_delta >= 0 ? '+' : ''}
                            {diffResult.health_delta.score_delta.toFixed(1)}
                          </span>
                        )}
                      </div>
                      <span className="text-[10px] text-muted">
                        {diffResult.health_delta.grade_before} →{' '}
                        {diffResult.health_delta.grade_after}
                      </span>
                    </div>

                    <div className="p-3.5 rounded-lg bg-panel border border-line flex flex-col gap-1">
                      <span className="text-[11px] font-medium text-muted">
                        Modules Churn
                      </span>
                      <div className="flex items-baseline gap-2 text-xs font-mono font-bold">
                        <span className="text-success">
                          +{diffResult.module_changes.added.length}
                        </span>
                        <span>/</span>
                        <span className="text-danger">
                          -{diffResult.module_changes.removed.length}
                        </span>
                        <span>/</span>
                        <span className="text-accent">
                          ~{diffResult.module_changes.renamed.length}
                        </span>
                      </div>
                      <span className="text-[10px] text-muted">
                        Added / Removed / Renamed
                      </span>
                    </div>

                    <div className="p-3.5 rounded-lg bg-panel border border-line flex flex-col gap-1">
                      <span className="text-[11px] font-medium text-muted">
                        Dependencies
                      </span>
                      <div className="flex items-baseline gap-2 text-xs font-mono font-bold">
                        <span className="text-success">
                          +{diffResult.dependency_changes.added_edges.length}
                        </span>
                        <span>/</span>
                        <span className="text-danger">
                          -{diffResult.dependency_changes.removed_edges.length}
                        </span>
                      </div>
                      <span className="text-[10px] text-muted">Added / Removed Edges</span>
                    </div>

                    <div className="p-3.5 rounded-lg bg-panel border border-line flex flex-col gap-1">
                      <span className="text-[11px] font-medium text-muted">
                        Cycle Progression
                      </span>
                      <div className="flex items-baseline gap-2 text-xs font-mono font-bold">
                        <span className="text-danger">
                          +{diffResult.cycle_changes.new_cycles.length} new
                        </span>
                        <span>•</span>
                        <span className="text-success">
                          -{diffResult.cycle_changes.resolved_cycles.length} resolved
                        </span>
                      </div>
                      <span className="text-[10px] text-muted">
                        Persisting: {diffResult.cycle_changes.persisting_cycles_count}
                      </span>
                    </div>
                  </div>

                  {/* Caveats alert */}
                  {diffResult.caveats.length > 0 && (
                    <div className="p-3 rounded-lg bg-raised border border-line text-xs text-muted flex flex-col gap-1">
                      <span className="font-bold text-ink flex items-center gap-1.5">
                        <AlertCircle className="w-3.5 h-3.5 text-accent" />
                        <span>Honest Evaluation Caveats:</span>
                      </span>
                      <ul className="list-disc list-inside text-[11px] space-y-0.5">
                        {diffResult.caveats.map((cav) => (
                          <li key={cav}>{cav}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Renamed modules section with candidate vs git verified distinction */}
                  {diffResult.module_changes.renamed.length > 0 && (
                    <div className="p-4 rounded-xl bg-panel border border-line flex flex-col gap-2.5">
                      <h4 className="text-xs font-bold text-ink uppercase tracking-wider flex items-center gap-1.5">
                        <Sparkles className="w-3.5 h-3.5 text-accent" />
                        <span>
                          Renamed / Moved Modules (
                          {diffResult.module_changes.renamed.length})
                        </span>
                      </h4>
                      <div className="divide-y divide-line/60">
                        {diffResult.module_changes.renamed.map((ren) => (
                          <div
                            key={`${ren.old_path}->${ren.new_path}`}
                            className="py-2 flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs"
                          >
                            <div className="flex items-center gap-1.5 font-mono">
                              <span className="text-muted line-through">
                                {ren.old_path}
                              </span>
                              <ArrowRight className="w-3.5 h-3.5 text-accent shrink-0" />
                              <span className="text-ink font-medium">
                                {ren.new_path}
                              </span>
                            </div>
                            <div className="flex items-center gap-2 shrink-0">
                              {ren.is_verified_by_git ? (
                                <span className="px-2 py-0.5 rounded bg-success/15 border border-success/30 text-success text-[10px] font-medium flex items-center gap-1">
                                  <CheckCircle2 className="w-3 h-3" />
                                  <span>Git-Detected Rename</span>
                                </span>
                              ) : (
                                <span className="px-2 py-0.5 rounded bg-warning/15 border border-warning/30 text-warning text-[10px] font-medium">
                                  Candidate Heuristic Match
                                </span>
                              )}
                              <span className="text-[10px] font-mono text-muted">
                                Conf: {(ren.confidence * 100).toFixed(0)}%
                              </span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Added & Removed Modules Grid */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {/* Added */}
                    <div className="p-4 rounded-xl bg-panel border border-line flex flex-col gap-2">
                      <h4 className="text-xs font-bold text-success uppercase tracking-wider flex items-center gap-1.5">
                        <TrendingUp className="w-3.5 h-3.5" />
                        <span>Added Modules ({diffResult.module_changes.added.length})</span>
                      </h4>
                      <div className="max-h-60 overflow-y-auto divide-y divide-line/40 text-xs font-mono">
                        {diffResult.module_changes.added.length === 0 ? (
                          <span className="text-muted text-[11px]">No new modules added.</span>
                        ) : (
                          diffResult.module_changes.added.map((m) => (
                            <div
                              key={`add-${m}`}
                              onClick={() =>
                                void handleInspectEvidence(
                                  headCommitSha,
                                  m,
                                  1,
                                  40,
                                  `ev_add_${m}`
                                )
                              }
                              className="py-1.5 px-1 hover:bg-raised text-ink cursor-pointer truncate flex items-center justify-between"
                            >
                              <span>{m}</span>
                              <ChevronRight className="w-3 h-3 text-muted" />
                            </div>
                          ))
                        )}
                      </div>
                    </div>

                    {/* Removed */}
                    <div className="p-4 rounded-xl bg-panel border border-line flex flex-col gap-2">
                      <h4 className="text-xs font-bold text-danger uppercase tracking-wider flex items-center gap-1.5">
                        <TrendingDown className="w-3.5 h-3.5" />
                        <span>
                          Removed Modules ({diffResult.module_changes.removed.length})
                        </span>
                      </h4>
                      <div className="max-h-60 overflow-y-auto divide-y divide-line/40 text-xs font-mono">
                        {diffResult.module_changes.removed.length === 0 ? (
                          <span className="text-muted text-[11px]">No modules removed.</span>
                        ) : (
                          diffResult.module_changes.removed.map((m) => (
                            <div
                              key={`rem-${m}`}
                              onClick={() =>
                                void handleInspectEvidence(
                                  baseCommitSha,
                                  m,
                                  1,
                                  40,
                                  `ev_rem_${m}`
                                )
                              }
                              className="py-1.5 px-1 hover:bg-raised text-muted line-through cursor-pointer truncate flex items-center justify-between"
                            >
                              <span>{m}</span>
                              <ChevronRight className="w-3 h-3 text-muted" />
                            </div>
                          ))
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Coupling Deltas Table */}
                  {diffResult.coupling_deltas.length > 0 && (
                    <div className="p-4 rounded-xl bg-panel border border-line flex flex-col gap-2.5">
                      <h4 className="text-xs font-bold text-ink uppercase tracking-wider flex items-center gap-1.5">
                        <Layers className="w-3.5 h-3.5 text-accent" />
                        <span>Coupling Hotspot Shifts ({diffResult.coupling_deltas.length})</span>
                      </h4>
                      <div className="overflow-x-auto">
                        <table className="w-full text-left text-xs font-mono">
                          <thead>
                            <tr className="border-b border-line text-[11px] text-muted">
                              <th className="py-2 px-2">Module</th>
                              <th className="py-2 px-2 text-right">Fan-In (Ca)</th>
                              <th className="py-2 px-2 text-right">Fan-Out (Ce)</th>
                              <th className="py-2 px-2 text-right">Instability (I)</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-line/40">
                            {diffResult.coupling_deltas.slice(0, 10).map((cd) => (
                              <tr key={cd.path} className="hover:bg-raised">
                                <td className="py-2 px-2 font-medium text-ink truncate max-w-xs">
                                  {cd.path}
                                </td>
                                <td className="py-2 px-2 text-right">
                                  {cd.fan_in_before} → {cd.fan_in_after}{' '}
                                  <span
                                    className={
                                      cd.fan_in_delta > 0
                                        ? 'text-accent'
                                        : cd.fan_in_delta < 0
                                          ? 'text-muted'
                                          : ''
                                    }
                                  >
                                    ({cd.fan_in_delta >= 0 ? '+' : ''}
                                    {cd.fan_in_delta})
                                  </span>
                                </td>
                                <td className="py-2 px-2 text-right">
                                  {cd.fan_out_before} → {cd.fan_out_after}{' '}
                                  <span
                                    className={
                                      cd.fan_out_delta > 0
                                        ? 'text-danger'
                                        : cd.fan_out_delta < 0
                                          ? 'text-success'
                                          : ''
                                    }
                                  >
                                    ({cd.fan_out_delta >= 0 ? '+' : ''}
                                    {cd.fan_out_delta})
                                  </span>
                                </td>
                                <td className="py-2 px-2 text-right">
                                  {cd.instability_before.toFixed(2)} →{' '}
                                  {cd.instability_after.toFixed(2)}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <div className="p-12 text-center text-xs text-muted border border-dashed border-line rounded-xl">
                  Select two commits above and click &quot;Compare Architecture&quot; to inspect structural differences.
                </div>
              )}
            </div>
          </div>
        )}

        {/* ========================================================================= */}
        {/* VIEW 3: ARCHITECTURE TRENDS */}
        {/* ========================================================================= */}
        {activeView === 'trends' && (
          <div className="flex-1 flex flex-col p-4 md:p-6 overflow-y-auto bg-canvas">
            <div className="max-w-5xl mx-auto w-full flex flex-col gap-6">
              <div className="p-4 rounded-xl bg-panel border border-line shadow-xs flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-bold text-ink">
                    Historical Architectural Progression
                  </h3>
                  <p className="text-xs text-muted">
                    Trace health scores, modular scale, and cycles across commit sequence.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    setTimeline(null);
                    void handleLoadTimeline();
                  }}
                  disabled={loadingTimeline}
                  className="px-3 py-1.5 rounded bg-raised hover:bg-line text-ink text-xs font-medium transition cursor-pointer flex items-center gap-1.5"
                >
                  <RefreshCw
                    className={`w-3.5 h-3.5 ${loadingTimeline ? 'animate-spin' : ''}`}
                  />
                  <span>Re-evaluate</span>
                </button>
              </div>

              {loadingTimeline ? (
                <div className="p-12 text-center text-xs text-muted flex flex-col items-center gap-2">
                  <RefreshCw className="w-6 h-6 animate-spin text-accent" />
                  <p className="font-bold text-ink">
                    Building chronological architecture progression...
                  </p>
                </div>
              ) : timelineError ? (
                <div className="p-4 bg-danger/10 border border-danger/30 rounded text-xs text-danger">
                  {timelineError}
                </div>
              ) : timeline ? (
                <div className="flex flex-col gap-4">
                  {timeline.failed_commits > 0 && (
                    <div className="p-3 bg-warning/10 border border-warning/30 rounded text-xs text-warning flex items-center gap-2">
                      <AlertCircle className="w-4 h-4 shrink-0" />
                      <span>
                        {timeline.failed_commits} commit(s) failed extraction and are marked as
                        UNAVAILABLE rather than reporting fake zeros.
                      </span>
                    </div>
                  )}

                  {/* Progression Table */}
                  <div className="rounded-xl bg-panel border border-line overflow-hidden shadow-xs">
                    <div className="overflow-x-auto">
                      <table className="w-full text-left text-xs font-mono">
                        <thead className="bg-raised border-b border-line text-muted text-[11px]">
                          <tr>
                            <th className="py-2.5 px-3">Commit</th>
                            <th className="py-2.5 px-3">Date</th>
                            <th className="py-2.5 px-3">Author</th>
                            <th className="py-2.5 px-3">Status</th>
                            <th className="py-2.5 px-3 text-right">Health Score</th>
                            <th className="py-2.5 px-3 text-right">Modules</th>
                            <th className="py-2.5 px-3 text-right">Lines Code</th>
                            <th className="py-2.5 px-3 text-right">Cycles</th>
                            <th className="py-2.5 px-3 text-right">AST Cov</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-line/50">
                          {timeline.entries.map((e: TimelineEntry) => {
                            const isFailed = e.status === 'failed';
                            return (
                              <tr
                                key={e.commit_sha}
                                className={`hover:bg-raised transition ${
                                  isFailed ? 'bg-danger/5' : ''
                                }`}
                              >
                                <td className="py-2 px-3 font-bold text-accent">
                                  {e.commit_sha.slice(0, 10)}
                                </td>
                                <td className="py-2 px-3 text-muted">
                                  {e.commit_timestamp
                                    ? e.commit_timestamp.slice(0, 10)
                                    : 'N/A'}
                                </td>
                                <td className="py-2 px-3 text-ink truncate max-w-[120px]">
                                  {e.commit_author}
                                </td>
                                <td className="py-2 px-3">
                                  {isFailed ? (
                                    <span className="px-1.5 py-0.5 rounded bg-danger/15 text-danger font-bold text-[10px]">
                                      FAILED
                                    </span>
                                  ) : (
                                    <span className="px-1.5 py-0.5 rounded bg-success/15 text-success font-bold text-[10px]">
                                      SUCCESS
                                    </span>
                                  )}
                                </td>
                                <td className="py-2 px-3 text-right font-bold text-ink">
                                  {isFailed || e.health_score === null
                                    ? 'N/A'
                                    : `${e.health_score.toFixed(1)} (${e.health_grade})`}
                                </td>
                                <td className="py-2 px-3 text-right text-ink">
                                  {isFailed ? 'N/A' : e.modules_count}
                                </td>
                                <td className="py-2 px-3 text-right text-muted">
                                  {isFailed ? 'N/A' : e.total_lines_code.toLocaleString()}
                                </td>
                                <td className="py-2 px-3 text-right">
                                  {isFailed ? (
                                    'N/A'
                                  ) : e.cycles_count > 0 ? (
                                    <span className="text-danger font-bold">
                                      {e.cycles_count}
                                    </span>
                                  ) : (
                                    <span className="text-success">0</span>
                                  )}
                                </td>
                                <td className="py-2 px-3 text-right text-muted">
                                  {isFailed ? 'N/A' : `${e.ast_coverage_pct.toFixed(1)}%`}
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>
              ) : null}
            </div>
          </div>
        )}
      </div>

      {/* ========================================================================= */}
      {/* HISTORICAL EVIDENCE INSPECTOR MODAL */}
      {/* ========================================================================= */}
      {evidenceModalOpen && (
        <div
          data-testid="evidence-inspector-modal"
          className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4 animate-fade"
        >
          <div className="bg-panel border border-line rounded-xl max-w-3xl w-full max-h-[85vh] flex flex-col shadow-2xl overflow-hidden">
            {/* Modal Header */}
            <div className="p-4 border-b border-line flex items-center justify-between bg-raised">
              <div className="flex items-center gap-2">
                <FileCode className="w-4 h-4 text-accent" />
                <h3 className="text-sm font-bold text-ink">
                  Historical Git Blob Evidence Inspector
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setEvidenceModalOpen(false)}
                className="p-1 rounded text-muted hover:text-ink cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-5 flex-1 overflow-y-auto flex flex-col gap-4">
              {/* Provenance Alert */}
              <div className="p-3 rounded-lg bg-accent/10 border border-accent/30 text-xs text-accent flex items-start gap-2">
                <Database className="w-4 h-4 shrink-0 mt-0.5" />
                <div>
                  <p className="font-bold">Cryptographically Verified Historical Blob</p>
                  <p className="text-[11px] text-muted">
                    This file snippet is read directly from Git commit blob storage. It reflects the
                    code as it existed at the specified revision, entirely isolated from your active
                    working tree.
                  </p>
                </div>
              </div>

              {loadingEvidence ? (
                <div className="p-8 text-center text-xs text-muted flex flex-col items-center gap-2">
                  <RefreshCw className="w-5 h-5 animate-spin text-accent" />
                  <span>Loading source from historical Git object...</span>
                </div>
              ) : evidenceError ? (
                <div className="p-4 bg-danger/10 border border-danger/30 rounded text-xs text-danger">
                  {evidenceError}
                </div>
              ) : selectedEvidence ? (
                <div className="flex flex-col gap-3">
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs font-mono">
                    <div className="p-2 bg-canvas border border-line rounded">
                      <span className="text-[10px] text-muted block">Commit SHA</span>
                      <span className="font-bold text-ink truncate block">
                        {selectedEvidence.commit_sha.slice(0, 10)}
                      </span>
                    </div>
                    <div className="p-2 bg-canvas border border-line rounded">
                      <span className="text-[10px] text-muted block">File Path</span>
                      <span className="font-bold text-ink truncate block">
                        {selectedEvidence.file_path}
                      </span>
                    </div>
                    <div className="p-2 bg-canvas border border-line rounded">
                      <span className="text-[10px] text-muted block">Line Range</span>
                      <span className="font-bold text-ink">
                        L{selectedEvidence.line_start} - L{selectedEvidence.line_end}
                      </span>
                    </div>
                    <div className="p-2 bg-canvas border border-line rounded">
                      <span className="text-[10px] text-muted block">Source</span>
                      <span className="font-bold text-success truncate block">
                        {selectedEvidence.revision_source}
                      </span>
                    </div>
                  </div>

                  {/* Code snippet display */}
                  <div className="rounded-lg bg-canvas border border-line overflow-hidden font-mono text-xs">
                    <div className="px-3 py-1.5 bg-raised border-b border-line flex items-center justify-between text-[11px] text-muted">
                      <span>{selectedEvidence.file_path}</span>
                      <button
                        type="button"
                        onClick={() => {
                          void navigator.clipboard.writeText(selectedEvidence.snippet);
                          setCopiedLink(true);
                          window.setTimeout(() => setCopiedLink(false), 2000);
                        }}
                        className="flex items-center gap-1 hover:text-ink cursor-pointer"
                      >
                        <Copy className="w-3 h-3" />
                        <span>{copiedLink ? 'Copied!' : 'Copy Code'}</span>
                      </button>
                    </div>
                    <pre className="p-4 overflow-x-auto text-ink leading-relaxed">
                      <code>{selectedEvidence.snippet}</code>
                    </pre>
                  </div>
                </div>
              ) : null}
            </div>

            {/* Modal Footer */}
            <div className="p-3 border-t border-line bg-raised flex justify-end">
              <button
                type="button"
                onClick={() => setEvidenceModalOpen(false)}
                className="px-4 py-1.5 rounded-lg bg-panel hover:bg-canvas border border-line text-xs font-medium text-ink cursor-pointer"
              >
                Close Inspector
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
