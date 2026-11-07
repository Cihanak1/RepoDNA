export type SourceType = 'local' | 'github' | 'demo';

export type ScanStatus =
  | 'queued'
  | 'cloning'
  | 'discovering'
  | 'parsing'
  | 'building_graph'
  | 'analyzing_git'
  | 'evaluating_rules'
  | 'completed'
  | 'cancelled'
  | 'failed';

export type LanguageSupportLevel = 'full_ast' | 'partial_static' | 'unsupported';

export type SeverityLevel = 'critical' | 'warning' | 'info';

export interface ScanLimits {
  max_files: number;
  max_file_size_bytes: number;
  max_total_size_bytes: number;
  timeout_seconds: number;
}

export interface ScanRequest {
  source_type: SourceType;
  target: string;
  branch?: string | null;
  limits?: ScanLimits;
}

export interface ScanProgress {
  job_id: string;
  status: ScanStatus;
  phase_message: string;
  progress_percent: number;
  files_discovered: number;
  files_processed: number;
  started_at: string;
  updated_at: string;
  error_code?: string | null;
  error_message?: string | null;
}

export interface UnresolvedReference {
  source_file: string;
  raw_import: string;
  line: number;
  reason: string;
}

export interface SymbolItem {
  name: string;
  kind: string;
  line: number;
}

export interface FileNode {
  id: string;
  name: string;
  directory: string;
  extension: string;
  language: string;
  support_level: LanguageSupportLevel;
  size_bytes: number;
  lines_total: number;
  lines_code: number;
  lines_comment: number;
  lines_blank: number;
  imports_internal: string[];
  imported_by: string[];
  imports_external: string[];
  unresolved_imports: UnresolvedReference[];
  symbols: SymbolItem[];
  fan_in: number;
  fan_out: number;
  instability: number;
  in_cycle: boolean;
  cycle_ids: string[];
  is_orphan: boolean;
  is_hub: boolean;
  git_commits: number;
  git_last_author?: string | null;
  git_last_modified?: string | null;
  secret_warnings: string[];
}

export interface DependencyEdge {
  id: string;
  source: string;
  target: string;
  import_names: string[];
  line: number;
  in_cycle: boolean;
}

export interface CycleGroup {
  id: string;
  nodes: string[];
  length: number;
  severity: SeverityLevel;
  description: string;
}

export interface LanguageBreakdownItem {
  language: string;
  support_level: LanguageSupportLevel;
  file_count: number;
  lines_code: number;
  lines_total: number;
  size_bytes: number;
  percentage_of_code: number;
}

export interface SkippedItem {
  path: string;
  reason: string;
  detail: string;
}

export interface TransparencyReport {
  supported_languages_detected: string[];
  partial_static_languages_detected?: string[];
  partial_static_files_count?: number;
  unsupported_languages_detected: string[];
  unsupported_files_count: number;
  ast_file_coverage_pct?: number;
  ast_loc_coverage_pct?: number;
  partial_static_file_coverage_pct?: number;
  partial_static_loc_coverage_pct?: number;
  unsupported_file_coverage_pct?: number;
  unsupported_loc_coverage_pct?: number;
  analysis_confidence?: string;
  dependency_graph_evaluated?: boolean;
  unresolved_internal_imports_count: number;
  dynamic_imports_count: number;
  skipped_files: SkippedItem[];
  truncated_by_limits: boolean;
  truncation_reason?: string | null;
  parser_engine_info: Record<string, string>;
}

export interface GitCommitSummary {
  sha: string;
  author: string;
  date: string;
  subject: string;
}

export interface GitHotspot {
  path: string;
  commits: number;
  authors_count: number;
  lines_code: number;
  churn_risk_score: number;
}

export interface GitInsights {
  is_git_repo: boolean;
  default_branch?: string | null;
  total_commits_scanned: number;
  unique_contributors: number;
  first_commit_date?: string | null;
  latest_commit_date?: string | null;
  recent_commits: GitCommitSummary[];
  hotspots: GitHotspot[];
  bus_factor_estimate: number;
  note?: string | null;
}

export interface RuleFinding {
  rule_id: string;
  title: string;
  category: string;
  severity: SeverityLevel;
  score_deduction: number;
  max_deduction: number;
  formula_explanation: string;
  threshold_description: string;
  affected_files: string[];
  evidence: string[];
  remediation: string;
}

export interface CategoryScore {
  category: string;
  label: string;
  score: number | null;
  status?: string;
  weight: number;
  deductions: number;
  findings_count: number;
}

export interface ArchitectureHealthReport {
  overall_score: number | null;
  grade: string;
  status?: string;
  confidence?: string;
  confidence_reason?: string;
  ast_file_coverage_pct?: number;
  ast_loc_coverage_pct?: number;
  dependency_graph_evaluated?: boolean;
  cycle_analysis_summary?: string;
  methodology: string;
  category_scores: CategoryScore[];
  findings: RuleFinding[];
  passed_rules: string[];
  unverified_rules?: string[];
  summary_metrics: Record<string, number>;
}

export interface GraphMetrics {
  total_nodes: number;
  total_edges: number;
  connected_components: number;
  scc_count: number;
  cycle_count: number;
  nodes_in_cycles: number;
  cycles_truncated?: boolean;
  cycle_truncation_reason?: string | null;
  orphan_files_count: number;
  hub_files_count: number;
  max_fan_in: number;
  max_fan_out: number;
  average_instability: number;
  graph_density: number;
}

export interface AnalysisResult {
  analysis_id: string;
  repo_name: string;
  source_type: SourceType;
  target_display: string;
  is_demo: boolean;
  analyzed_at: string;
  duration_ms: number;
  total_files: number;
  total_lines_code: number;
  total_lines_all: number;
  total_size_bytes: number;
  languages: LanguageBreakdownItem[];
  files: FileNode[];
  edges: DependencyEdge[];
  cycles: CycleGroup[];
  graph_metrics: GraphMetrics;
  health_report: ArchitectureHealthReport;
  git_insights: GitInsights;
  transparency: TransparencyReport;
}

export interface DirectoryEntryItem {
  name: string;
  path: string;
  is_git_repo: boolean;
}

export interface DirectoryBrowseResponse {
  current_path: string;
  parent_path: string | null;
  directories: DirectoryEntryItem[];
}

export interface HealthCheckResponse {
  status: string;
  version: string;
  parsers: Record<string, string>;
  default_workspace: string;
}
