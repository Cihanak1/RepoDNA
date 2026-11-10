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

// ---------------------------------------------------------------------------
// RepoDNA v0.4.0 — Architecture Contract, PR Guardian, and Repository Passport
// ---------------------------------------------------------------------------

export type ContractMode = 'advisory' | 'enforce';
export type UnknownBehavior = 'warn' | 'fail' | 'ignore';
export type GuardianVerdict = 'PASS' | 'WARNING' | 'FAIL' | 'INCONCLUSIVE';
export type RiskLevel = 'LOW' | 'MODERATE' | 'HIGH' | 'CRITICAL';

export interface ContractRule {
  id: string;
  title: string;
  description: string;
  from: string[];
  disallow_imports: string[];
  allow_imports?: string[] | null;
  severity: SeverityLevel;
  remediation: string;
}

export interface ContractPolicy {
  mode: ContractMode;
  unknown_behavior: UnknownBehavior;
}

export interface ArchitectureContract {
  version: number;
  policy: ContractPolicy;
  rules: ContractRule[];
  metadata?: Record<string, unknown>;
}

export interface ContractViolation {
  rule_id: string;
  rule_title: string;
  severity: SeverityLevel;
  source_file: string;
  target_file: string;
  import_names: string[];
  line: number;
  message: string;
  remediation: string;
  is_baseline: boolean;
}

export interface ContractUnknown {
  rule_id: string;
  rule_title: string;
  source_file: string;
  raw_import: string;
  line: number;
  reason: string;
  detail: string;
}

export interface ContractEvaluationReport {
  contract_version: number;
  mode: ContractMode;
  unknown_behavior: UnknownBehavior;
  total_rules: number;
  rules_evaluated: number;
  rules_passed: string[];
  rules_violated: string[];
  rules_unmatched?: string[];
  rules_unknown?: string[];
  violations: ContractViolation[];
  new_violations: ContractViolation[];
  baseline_violations: ContractViolation[];
  unknowns: ContractUnknown[];
  is_compliant: boolean;
  verdict: string;
  summary_text: string;
}

export interface RiskAssessment {
  risk_score: number;
  risk_level: RiskLevel;
  risk_factors: string[];
  mitigation_advice: string[];
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
  severity: SeverityLevel;
  description: string;
}

export interface CouplingDeltaItem {
  file_id: string;
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
  caveats: string[];
}

export interface RevisionProvenance {
  ref_name: string;
  commit_sha?: string | null;
  is_working_tree: boolean;
  analyzed_at: string;
  total_files: number;
  total_lines_code: number;
  ast_coverage_pct: number;
  health_score?: number | null;
  health_grade: string;
}

export interface GuardianReport {
  generated_at: string;
  base_provenance: RevisionProvenance;
  head_provenance: RevisionProvenance;
  verdict: GuardianVerdict;
  verdict_reason: string;
  risk_assessment: RiskAssessment;
  mode: ContractMode;
  should_block_ci?: boolean;
  exit_code?: number;
  added_modules: string[];
  removed_modules: string[];
  renamed_modules: RenamedModule[];
  added_edges: EdgeDiffItem[];
  removed_edges: EdgeDiffItem[];
  new_cycles: CycleDiffItem[];
  resolved_cycles: CycleDiffItem[];
  persisting_cycles_count: number;
  contract_evaluated: boolean;
  contract_version?: number | null;
  new_contract_violations: ContractViolation[];
  resolved_contract_violations: ContractViolation[];
  existing_baseline_violations: ContractViolation[];
  unknown_evaluations: ContractUnknown[];
  base_contract_report?: ContractEvaluationReport | null;
  head_contract_report?: ContractEvaluationReport | null;
  coupling_deltas: CouplingDeltaItem[];
  health_delta: HealthScoreDelta;
  coverage_delta: CoverageDelta;
  diff_summary: string;
  summary_markdown: string;
  metadata: Record<string, unknown>;
}

export interface PassportHubModule {
  file_id: string;
  fan_in: number;
  fan_out: number;
  instability: number;
  is_hub: boolean;
}

export interface PassportModuleItem {
  id: string;
  language: string;
  lines_code: number;
  fan_in: number;
  fan_out: number;
  instability: number;
  in_cycle: boolean;
  is_hub: boolean;
}

export interface PassportLanguageItem {
  language: string;
  support_level: string;
  file_count: number;
  lines_code: number;
  percentage: number;
}

export interface PassportCoverage {
  ast_file_coverage_pct: number;
  ast_loc_coverage_pct: number;
  supported_languages: string[];
  partial_static_languages: string[];
  unsupported_languages: string[];
}

export interface PassportDependencySummary {
  total_modules: number;
  total_internal_edges: number;
  cycle_count: number;
  cyclic_scc_count: number;
  orphan_modules_count: number;
  hub_modules_count: number;
  average_instability: number;
}

export interface PassportHealth {
  score?: number | null;
  grade: string;
  status: string;
  confidence: string;
  confidence_reason: string;
}

export interface PassportContractStatus {
  has_contract: boolean;
  contract_version?: number | null;
  mode?: string | null;
  rules_count: number;
  is_compliant?: boolean | null;
  active_violations_count: number;
}

export interface PassportTruncation {
  is_truncated: boolean;
  total_inventory_count: number;
  returned_inventory_count: number;
  reason?: string | null;
}

export interface RepositoryPassport {
  schema_version: string;
  repo_name: string;
  git_revision: string;
  provenance_verified?: boolean;
  revision_status?: string;
  analyzed_at: string;
  repodna_version: string;
  primary_languages: PassportLanguageItem[];
  ast_coverage: PassportCoverage;
  confidence: string;
  architectural_hubs: PassportHubModule[];
  module_inventory: PassportModuleItem[];
  dependency_summary: PassportDependencySummary;
  identified_boundaries: string[];
  architecture_health: PassportHealth;
  verified_findings: string[];
  unknown_unverified: string[];
  contract_status: PassportContractStatus;
  evidence_references: string[];
  truncation_metadata: PassportTruncation;
  metadata?: Record<string, unknown>;
}

// ----------------------------------------------------------------------------
// Repository Brain & Code Intelligence Types (v0.5.0)
// ----------------------------------------------------------------------------

export type SymbolKind =
  | 'function'
  | 'class'
  | 'method'
  | 'interface'
  | 'type'
  | 'import'
  | 'export'
  | 'struct'
  | 'variable'
  | 'constant';

export type ReferenceKind =
  | 'import'
  | 'call'
  | 'type_usage'
  | 'inheritance'
  | 'access'
  | 'reexport';

export type ResolutionStatus = 'verified' | 'candidate' | 'unresolved';

export type StalenessReason =
  | 'fresh'
  | 'revision_mismatch'
  | 'content_changed'
  | 'line_shift'
  | 'file_deleted';

export type EvidenceType =
  | 'symbol_definition'
  | 'symbol_reference'
  | 'import_statement'
  | 'export_statement'
  | 'dependency_edge'
  | 'architectural_hub'
  | 'contract_violation'
  | 'cycle_participation';

export interface SymbolReference {
  file_path: string;
  line: number;
  column?: number;
  symbol_name: string;
  reference_kind: ReferenceKind;
  source_symbol_name?: string | null;
  is_verified: boolean;
  resolution_status: ResolutionStatus;
  target_symbol_id?: string | null;
  target_file_path?: string | null;
  alias_name?: string | null;
  module_specifier?: string | null;
  qualifier?: string | null;
  confidence_reason: string;
}

export interface SymbolDefinition {
  id: string;
  name: string;
  kind: SymbolKind;
  file_path: string;
  line_start: number;
  line_end: number;
  column_start?: number;
  column_end?: number;
  language: string;
  container_name?: string | null;
  signature?: string | null;
  docstring?: string | null;
  is_exported: boolean;
  evidence_id: string;
  verified_references?: SymbolReference[];
  candidate_references?: SymbolReference[];
}

export interface EvidenceReference {
  evidence_id: string;
  repository_revision: string;
  file_path: string;
  line_start: number;
  line_end: number;
  evidence_type: EvidenceType;
  symbol_name?: string | null;
  symbol_kind?: SymbolKind | null;
  support_level: LanguageSupportLevel;
  confidence_reason: string;
  code_snippet?: string | null;
  created_at: string;
  is_stale: boolean;
  staleness_reason: StalenessReason;
  staleness_details?: string | null;
  line_shift_delta?: number | null;
  content_hash?: string | null;
}

export interface CodeSearchResult {
  file_id: string;
  score: number;
  relevance_tier: 'HIGH' | 'MEDIUM' | 'LOW';
  match_reasons: string[];
  matched_symbols: SymbolDefinition[];
  evidence_items: EvidenceReference[];
  language: string;
  lines_code: number;
  fan_in: number;
  fan_out: number;
  is_hub: boolean;
  in_cycle: boolean;
  is_comment_only_match?: boolean;
  snippet?: string | null;
}

export interface SearchResponse {
  query: string;
  total_matches: number;
  matches: CodeSearchResult[];
  summary_text: string;
  query_intent: string;
  tokens_evaluated: string[];
  limitations?: string[];
}

export interface SymbolQueryResponse {
  total_symbols: number;
  symbols: SymbolDefinition[];
  summary_text: string;
  filter_criteria?: Record<string, unknown>;
}

export interface SymbolTraceResult {
  symbol: SymbolDefinition;
  definition_evidence: EvidenceReference;
  references: SymbolReference[];
  candidate_references: SymbolReference[];
  importing_modules: string[];
  calling_modules: string[];
  downstream_dependents: string[];
  downstream_impact_count: number;
  cycle_warning?: string | null;
  is_ambiguous: boolean;
  ambiguity_candidates?: SymbolDefinition[];
  summary_text: string;
}

export interface EvidenceLedgerResponse {
  total_evidence: number;
  stale_count: number;
  evidence_items: EvidenceReference[];
  summary_text: string;
}

export interface AgentContextResponse {
  repository: string;
  revision: string;
  generated_at: string;
  analysis_version: string;
  mode: string;
  analysis_coverage: Record<string, unknown>;
  confidence_level: string;
  requested_scope: Record<string, unknown>;
  summary: string;
  relevant_modules: Array<Record<string, unknown>>;
  evidence: string[];
  evidence_records?: Array<Record<string, unknown>>;
  limitations: string[];
  truncated: boolean;
  continuation_token?: string | null;
  minimal_contract?: boolean;
  estimated_tokens?: number;
  raw_tokens_estimate?: number;
  token_savings_pct?: number;
  estimated_savings_pct?: number;
  is_savings_estimated?: boolean;
  token_counting_method?: string;
}

export interface PassportSymbolSummary {
  total_symbols: number;
  language_counts: Record<string, number>;
  symbols_by_kind: Record<string, number>;
  total_verified_references: number;
  total_candidate_references: number;
  total_unresolved_references: number;
}

export interface PassportEntrypoint {
  file_path: string;
  role: string;
  primary_symbol?: string | null;
  evidence_id?: string | null;
}

export interface PassportModuleRole {
  file_path: string;
  role: string;
  responsibility: string;
}

export interface PassportEvidenceSummary {
  total_evidence: number;
  fresh_count: number;
  stale_count: number;
  evidence_by_type: Record<string, number>;
}

export interface PassportRetrievalCapabilities {
  supports_semantic_search: boolean;
  supports_symbol_resolution: boolean;
  supports_cross_module_trace: boolean;
  supports_blast_radius: boolean;
  token_budgeting: boolean;
}

export interface RepositoryPassportV2 extends RepositoryPassport {
  symbol_index_summary?: PassportSymbolSummary | null;
  architectural_entrypoints: PassportEntrypoint[];
  major_module_roles: PassportModuleRole[];
  verified_reference_counts: number;
  candidate_unresolved_counts: Record<string, number>;
  evidence_ledger_summary?: PassportEvidenceSummary | null;
  retrieval_capabilities?: PassportRetrievalCapabilities | null;
  analysis_limitations: string[];
  source_revision?: string | null;
}

