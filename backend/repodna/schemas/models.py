"""Typed Pydantic v2 schemas for RepoDNA."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SourceType(StrEnum):
    LOCAL = "local"
    GITHUB = "github"
    DEMO = "demo"


class ScanStatus(StrEnum):
    QUEUED = "queued"
    CLONING = "cloning"
    DISCOVERING = "discovering"
    PARSING = "parsing"
    BUILDING_GRAPH = "building_graph"
    ANALYZING_GIT = "analyzing_git"
    EVALUATING_RULES = "evaluating_rules"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class LanguageSupportLevel(StrEnum):
    FULL_AST = "full_ast"          # Tree-sitter + static AST import & symbol extraction
    PARTIAL_STATIC = "partial_static"  # Static pattern import extraction
    UNSUPPORTED = "unsupported"    # Tracked for LOC/distribution, explicitly marked unsupported for imports


class SeverityLevel(StrEnum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class ScanLimits(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_files: int = Field(default=2500, ge=10, le=20000, description="Maximum number of files to scan.")
    max_file_size_bytes: int = Field(
        default=1_048_576, ge=4096, le=10_485_760, description="Max single file size in bytes (default 1 MB)."
    )
    max_total_size_bytes: int = Field(
        default=104_857_600, ge=65536, le=524_288_000, description="Max total scanned bytes (default 100 MB)."
    )
    timeout_seconds: float = Field(default=60.0, ge=5.0, le=300.0, description="Overall scan timeout in seconds.")


class ScanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_type: SourceType = Field(description="Whether scanning a local path, GitHub URL, or explicit demo.")
    target: str = Field(min_length=1, max_length=1024, description="Local filesystem path, HTTPS GitHub URL, or 'demo'.")
    branch: str | None = Field(default=None, max_length=128, description="Optional branch/tag for GitHub clone.")
    limits: ScanLimits = Field(default_factory=ScanLimits)


class ScanProgress(BaseModel):
    job_id: str
    status: ScanStatus
    phase_message: str
    progress_percent: float = Field(ge=0.0, le=100.0)
    files_discovered: int = 0
    files_processed: int = 0
    started_at: datetime
    updated_at: datetime
    error_code: str | None = None
    error_message: str | None = None


class UnresolvedReference(BaseModel):
    source_file: str
    raw_import: str
    line: int
    reason: str = Field(description="Why this import was not linked to an internal file (e.g., external_package, dynamic_import, unresolvable_path).")


class SymbolItem(BaseModel):
    name: str
    kind: str  # "class", "function", "interface", "type", "struct"
    line: int


class FileNode(BaseModel):
    id: str = Field(description="Normalized POSIX relative path within repository.")
    name: str
    directory: str
    extension: str
    language: str
    support_level: LanguageSupportLevel
    size_bytes: int
    lines_total: int
    lines_code: int
    lines_comment: int
    lines_blank: int
    imports_internal: list[str] = Field(default_factory=list, description="Resolved internal file IDs.")
    imported_by: list[str] = Field(default_factory=list, description="Internal file IDs that import this file.")
    imports_external: list[str] = Field(default_factory=list, description="External library/package names.")
    unresolved_imports: list[UnresolvedReference] = Field(default_factory=list)
    symbols: list[SymbolItem] = Field(default_factory=list)
    fan_in: int = 0
    fan_out: int = 0
    instability: float = Field(default=0.0, description="Robert C. Martin Instability metric I = Ce / (Ca + Ce).")
    in_cycle: bool = False
    cycle_ids: list[str] = Field(default_factory=list)
    is_orphan: bool = False
    is_hub: bool = False
    git_commits: int = 0
    git_last_author: str | None = None
    git_last_modified: str | None = None
    secret_warnings: list[str] = Field(default_factory=list)


class DependencyEdge(BaseModel):
    id: str
    source: str
    target: str
    import_names: list[str] = Field(default_factory=list)
    line: int = 1
    in_cycle: bool = False


class CycleGroup(BaseModel):
    id: str
    nodes: list[str] = Field(description="Ordered cycle path of file IDs, e.g. [A, B, C, A].")
    length: int
    severity: SeverityLevel
    description: str


class LanguageBreakdownItem(BaseModel):
    language: str
    support_level: LanguageSupportLevel
    file_count: int
    lines_code: int
    lines_total: int
    size_bytes: int
    percentage_of_code: float


class SkippedItem(BaseModel):
    path: str
    reason: str  # "symlink_blocked", "file_size_limit", "binary_file", "max_files_limit", "ignored_directory", "path_traversal_blocked"
    detail: str


class TransparencyReport(BaseModel):
    supported_languages_detected: list[str] = Field(default_factory=list)
    partial_static_languages_detected: list[str] = Field(default_factory=list)
    partial_static_files_count: int = 0
    unsupported_languages_detected: list[str] = Field(default_factory=list)
    unsupported_files_count: int = 0
    unresolved_internal_imports_count: int = 0
    dynamic_imports_count: int = 0
    skipped_files: list[SkippedItem] = Field(default_factory=list)
    truncated_by_limits: bool = False
    truncation_reason: str | None = None
    parser_engine_info: dict[str, str] = Field(default_factory=dict)


class GitCommitSummary(BaseModel):
    sha: str
    author: str
    date: str
    subject: str


class GitHotspot(BaseModel):
    path: str
    commits: int
    authors_count: int
    lines_code: int
    churn_risk_score: float = Field(description="Normalized product of commit frequency and file complexity.")


class GitInsights(BaseModel):
    is_git_repo: bool
    default_branch: str | None = None
    total_commits_scanned: int = 0
    unique_contributors: int = 0
    first_commit_date: str | None = None
    latest_commit_date: str | None = None
    recent_commits: list[GitCommitSummary] = Field(default_factory=list)
    hotspots: list[GitHotspot] = Field(default_factory=list)
    bus_factor_estimate: int = 1
    note: str | None = None


class RuleFinding(BaseModel):
    rule_id: str
    title: str
    category: str  # "cycles", "coupling", "complexity", "hygiene", "security"
    severity: SeverityLevel
    score_deduction: float
    max_deduction: float
    formula_explanation: str
    threshold_description: str
    affected_files: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    remediation: str


class CategoryScore(BaseModel):
    category: str
    label: str
    score: float | None = Field(default=None, ge=0.0, le=100.0)
    weight: float
    deductions: float
    findings_count: int


class ArchitectureHealthReport(BaseModel):
    overall_score: float | None = Field(default=None, ge=0.0, le=100.0)
    grade: str  # "A", "B", "C", "D", "F", "N/A"
    status: str = Field(default="evaluated", description="Either 'evaluated' or 'insufficient_data'.")
    methodology: str
    category_scores: list[CategoryScore] = Field(default_factory=list)
    findings: list[RuleFinding] = Field(default_factory=list)
    passed_rules: list[str] = Field(default_factory=list)
    summary_metrics: dict[str, Any] = Field(default_factory=dict)


class GraphMetrics(BaseModel):
    total_nodes: int = 0
    total_edges: int = 0
    connected_components: int = 0
    scc_count: int = 0
    cycle_count: int = 0
    nodes_in_cycles: int = 0
    cycles_truncated: bool = False
    cycle_truncation_reason: str | None = None
    orphan_files_count: int = 0
    hub_files_count: int = 0
    max_fan_in: int = 0
    max_fan_out: int = 0
    average_instability: float = 0.0
    graph_density: float = 0.0


class AnalysisResult(BaseModel):
    analysis_id: str
    repo_name: str
    source_type: SourceType
    target_display: str
    is_demo: bool = False
    analyzed_at: datetime
    duration_ms: int
    total_files: int
    total_lines_code: int
    total_lines_all: int
    total_size_bytes: int
    languages: list[LanguageBreakdownItem]
    files: list[FileNode]
    edges: list[DependencyEdge]
    cycles: list[CycleGroup]
    graph_metrics: GraphMetrics
    health_report: ArchitectureHealthReport
    git_insights: GitInsights
    transparency: TransparencyReport
