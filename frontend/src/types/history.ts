import type { RuleFinding, SeverityLevel } from './repodna';

export interface HistoricalCommitItem {
  sha: string;
  short_sha: string;
  author: string;
  timestamp: string;
  subject: string;
  is_cached: boolean;
}

export interface HistoricalCommitsResponse {
  total_commits: number;
  commits: HistoricalCommitItem[];
  is_shallow: boolean;
}

export interface HistoricalModuleSummary {
  path: string;
  name: string;
  language: string;
  lines_code: number;
  fan_in: number;
  fan_out: number;
  instability: number;
  is_hub: boolean;
  in_cycle: boolean;
  symbol_count: number;
}

export interface HistoricalDependencyEdge {
  source: string;
  target: string;
  import_names: string[];
  is_dynamic: boolean;
}

export interface HistoricalCycle {
  id: string;
  nodes: string[];
  length: number;
  severity: SeverityLevel;
  description: string;
}

export interface HistoricalCouplingMetrics {
  fan_in: number;
  fan_out: number;
  instability: number;
}

export interface HistoricalHealthMetrics {
  score: number | null;
  grade: string;
  status: string;
  penalties: Record<string, number>;
}

export interface HistoricalEvidenceItem {
  evidence_id: string;
  commit_sha: string;
  file_path: string;
  line_start: number;
  line_end: number;
  evidence_type: string;
  symbol_name?: string | null;
  code_snippet: string;
  content_hash: string;
  support_level: string;
  snapshot_identity: string;
}

export interface HistoricalLanguageSummary {
  files_count: number;
  lines_code: number;
  percentage: number;
}

export interface SnapshotRuntimeMetadata {
  analyzed_at: string;
  analysis_duration_ms: number;
  cache_hit: boolean;
  analyzer_version: string;
  parser_version: string;
  config_fingerprint: string;
}

export interface HistoricalSnapshot {
  schema_version: string;
  commit_sha: string;
  parent_shas: string[];
  repo_identity: string;
  commit_timestamp: string;
  commit_author: string;
  commit_message: string;
  total_files: number;
  total_lines_code: number;
  ast_loc_coverage_pct: number;
  languages: Record<string, HistoricalLanguageSummary>;
  modules: HistoricalModuleSummary[];
  dependencies: HistoricalDependencyEdge[];
  cycles: HistoricalCycle[];
  coupling: Record<string, HistoricalCouplingMetrics>;
  health: HistoricalHealthMetrics;
  findings: RuleFinding[];
  evidence: HistoricalEvidenceItem[];
  limitations: string[];
  is_shallow: boolean;
  cache_hit: boolean;
  analyzed_at?: string;
  analyzer_version?: string;
}

export interface RenamedModule {
  old_path: string;
  new_path: string;
  confidence: number;
  reason: string;
  is_verified_by_git: boolean;
}

export interface EdgeDiffItem {
  source: string;
  target: string;
  import_names: string[];
}

export interface CycleDiffItem {
  id: string;
  nodes: string[];
  length: number;
}

export interface CouplingDeltaItem {
  path: string;
  fan_in_before: number;
  fan_in_after: number;
  fan_in_delta: number;
  fan_out_before: number;
  fan_out_after: number;
  fan_out_delta: number;
  instability_before: number;
  instability_after: number;
  instability_delta: number;
}

export interface HealthScoreDelta {
  score_before: number | null;
  score_after: number | null;
  score_delta: number | null;
  grade_before: string;
  grade_after: string;
  status_before: string;
  status_after: string;
}

export interface CoverageDelta {
  ast_loc_coverage_before: number;
  ast_loc_coverage_after: number;
  ast_loc_coverage_delta: number;
  supported_langs_before: string[];
  supported_langs_after: string[];
}

export interface RuleFindingChanges {
  new_findings: RuleFinding[];
  resolved_findings: RuleFinding[];
  persisting_findings_count: number;
}

export interface HistoricalDiffResult {
  schema_version: string;
  base_commit_sha: string;
  head_commit_sha: string;
  base_timestamp: string;
  head_timestamp: string;
  time_delta_display: string;
  module_changes: {
    added: string[];
    removed: string[];
    renamed: RenamedModule[];
    modified_dependencies: string[];
  };
  dependency_changes: {
    added_edges: EdgeDiffItem[];
    removed_edges: EdgeDiffItem[];
  };
  cycle_changes: {
    new_cycles: CycleDiffItem[];
    resolved_cycles: CycleDiffItem[];
    persisting_cycles_count: number;
  };
  coupling_deltas: CouplingDeltaItem[];
  health_delta: HealthScoreDelta;
  coverage_delta: CoverageDelta;
  finding_changes: RuleFindingChanges;
  caveats: string[];
  summary_text: string;
}

export interface TimelineEntry {
  commit_sha: string;
  commit_timestamp: string;
  commit_author: string;
  commit_message: string;
  status: 'success' | 'failed' | 'partial';
  error_message?: string | null;
  total_files: number;
  total_lines_code: number;
  health_score: number | null;
  health_grade: string;
  cycles_count: number;
  modules_count: number;
  ast_coverage_pct: number;
  cache_hit: boolean;
}

export interface TimelineResult {
  schema_version: string;
  repo_identity: string;
  total_commits: number;
  successful_commits: number;
  failed_commits: number;
  missing_commits: string[];
  entries: TimelineEntry[];
  summary_text: string;
}

export interface HistoricalEvidenceBlobResponse {
  evidence_id: string;
  commit_sha: string;
  file_path: string;
  line_start: number;
  line_end: number;
  snippet: string;
  content_hash: string;
  is_provenance_valid: boolean;
  revision_source: string;
}
