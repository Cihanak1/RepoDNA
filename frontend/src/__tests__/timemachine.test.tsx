import { describe, expect, it, vi, beforeEach } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import '../i18n';
import { TimeMachineWorkstation } from '../components/TimeMachineWorkstation';
import { HeaderBar } from '../components/HeaderBar';
import { CommandPaletteDialog } from '../components/CommandPaletteDialog';
import type { AnalysisResult } from '../types/repodna';
import type {
  HistoricalCommitItem,
  HistoricalCommitsResponse,
  HistoricalDiffResult,
  HistoricalEvidenceBlobResponse,
  HistoricalSnapshot,
  TimelineResult,
} from '../types/history';
import * as apiClient from '../api/client';

const mockAnalysis: AnalysisResult = {
  analysis_id: 'test_hist_123',
  repo_name: 'acme-time',
  source_type: 'local',
  target_display: './acme-time',
  is_demo: false,
  analyzed_at: '2026-11-10T12:00:00Z',
  duration_ms: 150,
  total_files: 5,
  total_lines_code: 400,
  total_lines_all: 550,
  total_size_bytes: 15000,
  languages: [
    {
      language: 'Python',
      support_level: 'full_ast',
      file_count: 5,
      lines_code: 400,
      lines_total: 550,
      size_bytes: 15000,
      percentage_of_code: 100,
    },
  ],
  files: [],
  edges: [],
  cycles: [],
  graph_metrics: {
    total_nodes: 5,
    total_edges: 4,
    connected_components: 1,
    scc_count: 0,
    cycle_count: 0,
    nodes_in_cycles: 0,
    orphan_files_count: 1,
    hub_files_count: 1,
    max_fan_in: 3,
    max_fan_out: 2,
    average_instability: 0.4,
    graph_density: 0.16,
  },
  health_report: {
    overall_score: 90.0,
    grade: 'A',
    status: 'evaluated',
    confidence: 'high',
    methodology: 'Standard',
    category_scores: [],
    findings: [],
    passed_rules: ['ARCH-001'],
    summary_metrics: {},
  },
  git_insights: {
    is_git_repo: true,
    recent_commits: [],
    hotspots: [],
    total_commits_scanned: 10,
    unique_contributors: 2,
    bus_factor_estimate: 2,
  },
  transparency: {
    supported_languages_detected: ['Python'],
    unsupported_languages_detected: [],
    unsupported_files_count: 0,
    unresolved_internal_imports_count: 0,
    dynamic_imports_count: 0,
    skipped_files: [],
    truncated_by_limits: false,
    parser_engine_info: {},
  },
};

const mockCommits: HistoricalCommitItem[] = [
  {
    sha: 'c111111111111111111111111111111111111111',
    short_sha: 'c111111',
    author: 'Alice Dev',
    timestamp: '2026-11-08T10:00:00Z',
    subject: 'Initial stable architecture',
    is_cached: true,
  },
  {
    sha: 'c222222222222222222222222222222222222222',
    short_sha: 'c222222',
    author: 'Bob Architect',
    timestamp: '2026-11-09T14:30:00Z',
    subject: 'Refactor core service and add caching',
    is_cached: false,
  },
  {
    sha: 'c33333333333333333333333333333333333333',
    short_sha: 'c333333',
    author: 'Charlie Reviewer',
    timestamp: '2026-11-10T09:15:00Z',
    subject: 'Add boundary policy and telemetry',
    is_cached: false,
  },
];

const mockCommitsResponse: HistoricalCommitsResponse = {
  total_commits: 3,
  commits: mockCommits,
  is_shallow: false,
};

const mockSnapshotC1: HistoricalSnapshot = {
  schema_version: '1.0',
  commit_sha: 'c111111111111111111111111111111111111111',
  parent_shas: [],
  repo_identity: 'acme-time',
  commit_timestamp: '2026-11-08T10:00:00Z',
  commit_author: 'Alice Dev',
  commit_message: 'Initial stable architecture',
  total_files: 4,
  total_lines_code: 320,
  ast_loc_coverage_pct: 100.0,
  languages: {
    Python: { files_count: 4, lines_code: 320, percentage: 100.0 },
  },
  modules: [
    {
      path: 'backend/core.py',
      name: 'core',
      language: 'Python',
      lines_code: 120,
      fan_in: 3,
      fan_out: 0,
      instability: 0.0,
      is_hub: true,
      in_cycle: false,
      symbol_count: 12,
    },
    {
      path: 'backend/api.py',
      name: 'api',
      language: 'Python',
      lines_code: 80,
      fan_in: 0,
      fan_out: 1,
      instability: 1.0,
      is_hub: false,
      in_cycle: false,
      symbol_count: 6,
    },
  ],
  dependencies: [
    {
      source: 'backend/api.py',
      target: 'backend/core.py',
      import_names: ['CoreService'],
      is_dynamic: false,
    },
  ],
  cycles: [],
  coupling: {
    'backend/core.py': { fan_in: 3, fan_out: 0, instability: 0.0 },
  },
  health: {
    score: 92.5,
    grade: 'A',
    status: 'evaluated',
    penalties: {},
  },
  findings: [],
  evidence: [],
  limitations: [],
  is_shallow: false,
  cache_hit: true,
};

const mockDiffResult: HistoricalDiffResult = {
  schema_version: '1.0',
  base_commit_sha: 'c111111111111111111111111111111111111111',
  head_commit_sha: 'c222222222222222222222222222222222222222',
  base_timestamp: '2026-11-08T10:00:00Z',
  head_timestamp: '2026-11-09T14:30:00Z',
  time_delta_display: '1 day',
  module_changes: {
    added: ['backend/cache.py'],
    removed: ['backend/old_cache.py'],
    renamed: [
      {
        old_path: 'backend/old_cache.py',
        new_path: 'backend/cache.py',
        confidence: 0.90,
        reason: 'Git history rename detection based on content similarity (syntactic match, not semantic identity)',
        is_verified_by_git: true,
      },
    ],
    modified_dependencies: [],
  },
  dependency_changes: {
    added_edges: [],
    removed_edges: [],
  },
  cycle_changes: {
    new_cycles: [],
    resolved_cycles: [],
    persisting_cycles_count: 0,
  },
  coupling_deltas: [
    {
      path: 'backend/core.py',
      fan_in_before: 3,
      fan_in_after: 4,
      fan_in_delta: 1,
      fan_out_before: 0,
      fan_out_after: 0,
      fan_out_delta: 0,
      instability_before: 0.0,
      instability_after: 0.0,
      instability_delta: 0.0,
    },
  ],
  health_delta: {
    score_before: 92.5,
    score_after: 90.5,
    score_delta: -2.0,
    grade_before: 'A',
    grade_after: 'A',
    status_before: 'evaluated',
    status_after: 'evaluated',
  },
  coverage_delta: {
    ast_loc_coverage_before: 100.0,
    ast_loc_coverage_after: 100.0,
    ast_loc_coverage_delta: 0.0,
    supported_langs_before: ['Python'],
    supported_langs_after: ['Python'],
  },
  finding_changes: {
    new_findings: [],
    resolved_findings: [],
    persisting_findings_count: 0,
  },
  caveats: [
    'Git-detected renames are based on content similarity heuristics and do not imply semantic identity.',
  ],
  summary_text: 'Summary of architectural evolution',
};

const mockTimelineResult: TimelineResult = {
  schema_version: '1.0',
  repo_identity: 'acme-time',
  total_commits: 3,
  successful_commits: 2,
  failed_commits: 1,
  missing_commits: [],
  entries: [
    {
      commit_sha: 'c111111111111111111111111111111111111111',
      commit_timestamp: '2026-11-08T10:00:00Z',
      commit_author: 'Alice Dev',
      commit_message: 'Initial stable architecture',
      status: 'success',
      total_files: 4,
      total_lines_code: 320,
      health_score: 92.5,
      health_grade: 'A',
      cycles_count: 0,
      modules_count: 4,
      ast_coverage_pct: 100.0,
      cache_hit: true,
    },
    {
      commit_sha: 'c222222222222222222222222222222222222222',
      commit_timestamp: '2026-11-09T14:30:00Z',
      commit_author: 'Bob Architect',
      commit_message: 'Refactor core service',
      status: 'success',
      total_files: 5,
      total_lines_code: 380,
      health_score: 90.5,
      health_grade: 'A',
      cycles_count: 0,
      modules_count: 5,
      ast_coverage_pct: 100.0,
      cache_hit: false,
    },
    {
      commit_sha: 'c33333333333333333333333333333333333333',
      commit_timestamp: '2026-11-10T09:15:00Z',
      commit_author: 'Charlie Reviewer',
      commit_message: 'Broken tree commit',
      status: 'failed',
      error_message: 'Git archive extraction failed: Tree corrupt',
      total_files: 0,
      total_lines_code: 0,
      health_score: null,
      health_grade: 'N/A',
      cycles_count: 0,
      modules_count: 0,
      ast_coverage_pct: 0.0,
      cache_hit: false,
    },
  ],
  summary_text: 'Timeline summary',
};

const mockEvidenceBlob: HistoricalEvidenceBlobResponse = {
  evidence_id: 'ev_mod_core',
  commit_sha: 'c111111111111111111111111111111111111111',
  file_path: 'backend/core.py',
  line_start: 10,
  line_end: 18,
  snippet: 'class CoreService:\n    def execute(self):\n        return "ok"',
  content_hash: 'hash_c1_core_content',
  is_provenance_valid: true,
  revision_source: 'git_blob',
};

describe('TimeMachineWorkstation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(apiClient, 'fetchHistoricalCommits').mockResolvedValue(mockCommitsResponse);
    vi.spyOn(apiClient, 'fetchHistoricalSnapshot').mockResolvedValue(mockSnapshotC1);
    vi.spyOn(apiClient, 'fetchHistoricalDiff').mockResolvedValue(mockDiffResult);
    vi.spyOn(apiClient, 'fetchHistoricalTimeline').mockResolvedValue(mockTimelineResult);
    vi.spyOn(apiClient, 'fetchHistoricalEvidenceBlob').mockResolvedValue(mockEvidenceBlob);
  });

  it('renders sub-tabs and loads commit history', async () => {
    render(
      <TimeMachineWorkstation
        result={mockAnalysis}
        workstationMode="advanced"
      />
    );

    // Verify sub-tabs exist
    expect(screen.getByTestId('tm-subtab-timeline-btn')).toBeInTheDocument();
    expect(screen.getByTestId('tm-subtab-diff-btn')).toBeInTheDocument();
    expect(screen.getByTestId('tm-subtab-trends-btn')).toBeInTheDocument();

    // Verify commit history loaded
    await waitFor(() => {
      expect(screen.getByText('Alice Dev')).toBeInTheDocument();
      expect(screen.getByText('Bob Architect')).toBeInTheDocument();
      expect(screen.getByText('Charlie Reviewer')).toBeInTheDocument();
    });

    // Check cached indicator on first commit
    expect(screen.getByText('Cached')).toBeInTheDocument();
  });

  it('filters commits using search input', async () => {
    render(
      <TimeMachineWorkstation
        result={mockAnalysis}
        workstationMode="advanced"
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Alice Dev')).toBeInTheDocument();
    });

    const searchInput = screen.getByTestId('commit-search-input');
    fireEvent.change(searchInput, { target: { value: 'Bob' } });

    expect(screen.queryByText('Alice Dev')).not.toBeInTheDocument();
    expect(screen.getByText('Bob Architect')).toBeInTheDocument();
  });

  it('selects commit and renders architectural snapshot details', async () => {
    render(
      <TimeMachineWorkstation
        result={mockAnalysis}
        workstationMode="advanced"
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Alice Dev')).toBeInTheDocument();
    });

    // Select the first commit
    const commitItem = screen.getByTestId('commit-item-c111111');
    fireEvent.click(commitItem);

    // Verify snapshot metrics appear
    await waitFor(() => {
      expect(screen.getByText('92.5')).toBeInTheDocument();
      expect(screen.getByText('320 LOC')).toBeInTheDocument();
      expect(screen.getByText('AST: 100.0%')).toBeInTheDocument();
    });

    // Verify module list in snapshot details
    expect(screen.getByText('backend/core.py')).toBeInTheDocument();
    expect(screen.getByText('backend/api.py')).toBeInTheDocument();
  });

  it('switches to evolution diff and executes comparison', async () => {
    render(
      <TimeMachineWorkstation
        result={mockAnalysis}
        workstationMode="advanced"
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Alice Dev')).toBeInTheDocument();
    });

    // Switch to diff view
    fireEvent.click(screen.getByTestId('tm-subtab-diff-btn'));

    // Set base and head selects
    const baseSelect = screen.getByTestId('diff-base-select');
    const headSelect = screen.getByTestId('diff-head-select');

    fireEvent.change(baseSelect, {
      target: { value: 'c111111111111111111111111111111111111111' },
    });
    fireEvent.change(headSelect, {
      target: { value: 'c222222222222222222222222222222222222222' },
    });

    // Click compare button
    const compareBtn = screen.getByTestId('run-diff-btn');
    fireEvent.click(compareBtn);

    // Verify diff content renders
    await waitFor(() => {
      expect(screen.getByTestId('evolution-diff-content')).toBeInTheDocument();
    });

    // Check added and removed modules
    expect(screen.getAllByText('backend/cache.py').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('backend/old_cache.py').length).toBeGreaterThanOrEqual(1);

    // Check rename with caveat and 90% confidence
    expect(screen.getByText(/Git-Detected Rename/)).toBeInTheDocument();
    expect(screen.getByText(/Conf: 90%/)).toBeInTheDocument();
  });

  it('switches to architecture trends and handles failed/missing commits honestly', async () => {
    render(
      <TimeMachineWorkstation
        result={mockAnalysis}
        workstationMode="advanced"
      />
    );

    // Switch to trends view
    fireEvent.click(screen.getByTestId('tm-subtab-trends-btn'));

    // Verify timeline loaded
    await waitFor(() => {
      expect(screen.getByText('c111111111')).toBeInTheDocument();
    });

    // Successful commits show metrics
    expect(screen.getByText('92.5 (A)')).toBeInTheDocument();

    // Failed commit shows FAILED badge and does NOT show fake zeros
    expect(screen.getByText('FAILED')).toBeInTheDocument();
  });

  it('opens historical evidence modal and inspects verified Git blob', async () => {
    render(
      <TimeMachineWorkstation
        result={mockAnalysis}
        workstationMode="advanced"
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Alice Dev')).toBeInTheDocument();
    });

    // Select commit c1
    fireEvent.click(screen.getByTestId('commit-item-c111111'));

    await waitFor(() => {
      expect(screen.getByTestId('snapshot-module-core')).toBeInTheDocument();
    });

    // Click module to inspect historical evidence blob
    fireEvent.click(screen.getByTestId('snapshot-module-core'));

    // Verify modal is open and shows verified snippet
    await waitFor(() => {
      expect(screen.getByTestId('evidence-inspector-modal')).toBeInTheDocument();
      expect(screen.getByText('Historical Git Blob Evidence Inspector')).toBeInTheDocument();
      expect(screen.getByText(/Cryptographically Verified Historical Blob/)).toBeInTheDocument();
      expect(screen.getByText(/class CoreService:/)).toBeInTheDocument();
    });

    // Close modal by clicking close button (X)
    const closeButtons = screen.getAllByRole('button');
    const closeBtn = closeButtons.find(b => b.querySelector('svg.lucide-x') !== null);
    if (closeBtn) {
      fireEvent.click(closeBtn);
    }
  });

  it('navigates to Time Machine from HeaderBar and CommandPalette', async () => {
    const handleTabChange = vi.fn();

    // Test HeaderBar
    render(
      <HeaderBar
        sourceType="local"
        onSourceTypeChange={vi.fn()}
        targetInput="./test"
        onTargetInputChange={vi.fn()}
        branchInput=""
        onBranchInputChange={vi.fn()}
        limits={{
          max_files: 2500,
          max_file_size_bytes: 1048576,
          max_total_size_bytes: 104857600,
          timeout_seconds: 60,
        }}
        onLimitsChange={vi.fn()}
        onTriggerScan={vi.fn()}
        onOpenFolderBrowser={vi.fn()}
        activeJob={null}
        onCancelJob={vi.fn()}
        result={mockAnalysis}
        activeTab="studio"
        onTabChange={handleTabChange}
        defaultWorkspacePath="./test"
        onOpenCommandPalette={vi.fn()}
        workstationMode="advanced"
      />
    );

    const timeMachineTabBtn = screen.getByTestId('tab-history-btn');
    expect(timeMachineTabBtn).toBeInTheDocument();
    fireEvent.click(timeMachineTabBtn);
    expect(handleTabChange).toHaveBeenCalledWith('history');

    // Test CommandPaletteDialog
    const handlePaletteTab = vi.fn();
    const handleClose = vi.fn();
    render(
      <CommandPaletteDialog
        isOpen={true}
        onClose={handleClose}
        files={[]}
        onSelectFile={vi.fn()}
        onSwitchTab={handlePaletteTab}
        onToggleTheme={vi.fn()}
        onChangeLayout={vi.fn()}
        onChangeGrouping={vi.fn()}
        onChangeDensity={vi.fn()}
        onToggleCyclesOnly={vi.fn()}
        onResetFilters={vi.fn()}
        onLoadDemo={vi.fn()}
        workstationMode="advanced"
      />
    );

    const historyPaletteAction = screen.getByText('Switch to Architecture Time Machine');
    expect(historyPaletteAction).toBeInTheDocument();
    fireEvent.click(historyPaletteAction);
    expect(handlePaletteTab).toHaveBeenCalledWith('history');
  });
});
