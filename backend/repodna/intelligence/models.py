"""Typed Pydantic v2 schemas for RepoDNA AI Repository Intelligence."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from repodna.schemas.models import LanguageSupportLevel, RuleFinding, SeverityLevel, SymbolItem


class ModuleOverviewItem(BaseModel):
    id: str
    name: str
    directory: str
    language: str
    support_level: LanguageSupportLevel
    lines_code: int
    fan_in: int
    fan_out: int
    instability: float
    in_cycle: bool
    is_hub: bool


class RepositoryOverview(BaseModel):
    repo_name: str
    target_display: str
    analyzed_at: datetime
    analysis_version: str = "0.3.0"
    total_files: int
    total_lines_code: int
    total_size_bytes: int
    health_score: float | None = None
    health_grade: str
    health_status: str
    confidence: str
    ast_loc_coverage_pct: float
    ast_file_coverage_pct: float
    cycle_count: int
    cyclic_scc_count: int
    hub_modules_count: int
    primary_languages: list[str]
    unverified_rules: list[str]
    key_architectural_hubs: list[str]
    summary_text: str


class PackageCluster(BaseModel):
    name: str
    file_count: int
    files: list[str]
    external_dependencies: list[str] = Field(default_factory=list)


class ArchitectureMap(BaseModel):
    level: str  # "overview", "clusters", "full"
    total_modules: int
    total_clusters: int
    clusters: list[PackageCluster]
    inter_cluster_edges: list[dict[str, Any]] = Field(default_factory=list)
    summary_text: str


class RelevantModuleMatch(BaseModel):
    file_id: str
    language: str
    support_level: LanguageSupportLevel
    relevance_score: float
    match_reasons: list[str]
    matching_symbols: list[SymbolItem] = Field(default_factory=list)
    fan_in: int = 0
    fan_out: int = 0
    in_cycle: bool = False
    is_hub: bool = False


class RelevantModulesResponse(BaseModel):
    query: str
    total_matches: int
    matches: list[RelevantModuleMatch]
    summary_text: str


class ModuleDetails(BaseModel):
    file_id: str
    name: str
    directory: str
    language: str
    support_level: LanguageSupportLevel
    size_bytes: int
    lines_total: int
    lines_code: int
    lines_comment: int
    fan_in: int
    fan_out: int
    instability: float
    in_cycle: bool
    cycle_ids: list[str] = Field(default_factory=list)
    is_hub: bool
    is_orphan: bool
    symbols: list[SymbolItem] = Field(default_factory=list)
    dependencies_internal: list[str] = Field(default_factory=list)
    dependents_internal: list[str] = Field(default_factory=list)
    external_packages: list[str] = Field(default_factory=list)
    health_findings: list[RuleFinding] = Field(default_factory=list)
    secret_warnings: list[str] = Field(default_factory=list)
    analysis_limitations: list[str] = Field(default_factory=list)
    summary_text: str


class DependencyTraceItem(BaseModel):
    source: str
    target: str
    import_names: list[str] = Field(default_factory=list)
    line: int = 1
    depth: int = 1
    in_cycle: bool = False


class DependencyQueryResponse(BaseModel):
    root_file: str
    direction: str  # "outgoing", "incoming", "both"
    depth: int
    total_items: int
    items: list[DependencyTraceItem]
    summary_text: str


class ArchitectureFindingsResponse(BaseModel):
    total_findings: int
    critical_count: int
    warning_count: int
    info_count: int
    findings: list[RuleFinding]
    unverified_rules: list[str]
    summary_text: str


class AnalysisCoverageReport(BaseModel):
    confidence: str
    confidence_reason: str
    ast_file_coverage_pct: float
    ast_loc_coverage_pct: float
    supported_languages: list[str]
    partial_static_languages: list[str]
    partial_static_files_count: int
    unsupported_languages: list[str]
    unsupported_files_count: int
    skipped_files_count: int
    unverified_rules: list[str]
    honest_coverage_guarantee: str
    summary_text: str


class ChangeImpactResponse(BaseModel):
    target_files: list[str]
    direct_dependents: list[str]
    transitive_dependents: list[str]
    impacted_cycles: list[str]
    impact_severity: SeverityLevel
    risk_factors: list[str]
    affected_hubs: list[str]
    summary_text: str
