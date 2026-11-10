"""Typed Pydantic models for RepoDNA Historical Architecture Snapshot Engine."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from repodna.diff.models import (
    CouplingDeltaItem,
    CoverageDelta,
    CycleChanges,
    DependencyChanges,
    HealthScoreDelta,
    ModuleChanges,
    RuleFindingChanges,
)
from repodna.schemas.models import RuleFinding, SeverityLevel

SNAPSHOT_SCHEMA_VERSION = "1.0.0"
CACHE_SCHEMA_VERSION = "1.0.0"


class HistoricalModuleSummary(BaseModel):
    """Summary of a module (file) in a historical snapshot."""

    path: str
    name: str
    language: str
    lines_code: int = 0
    fan_in: int = 0
    fan_out: int = 0
    instability: float = 0.0
    is_hub: bool = False
    in_cycle: bool = False
    symbol_count: int = 0


class HistoricalDependencyEdge(BaseModel):
    """Dependency relationship between two modules at a specific historical commit."""

    source: str
    target: str
    import_names: list[str] = Field(default_factory=list)
    is_dynamic: bool = False


class HistoricalCycle(BaseModel):
    """Architectural cyclic dependency detected in a historical commit."""

    id: str
    nodes: list[str]
    length: int
    severity: SeverityLevel
    description: str


class HistoricalCouplingMetrics(BaseModel):
    """Fan-in, fan-out, and instability metrics for a module."""

    fan_in: int = 0
    fan_out: int = 0
    instability: float = 0.0


class HistoricalHealthMetrics(BaseModel):
    """Architecture health metrics and grade for a historical commit."""

    score: float | None = None
    grade: str = "N/A"
    status: str = "UNKNOWN"
    penalties: dict[str, float] = Field(default_factory=dict)


class HistoricalEvidenceItem(BaseModel):
    """Immutable evidence citation tied to a specific historical Git commit."""

    evidence_id: str
    commit_sha: str
    file_path: str
    line_start: int
    line_end: int
    evidence_type: str
    symbol_name: str | None = None
    code_snippet: str
    content_hash: str
    support_level: str
    snapshot_identity: str


class HistoricalLanguageSummary(BaseModel):
    """Language breakdown in a historical snapshot."""

    files_count: int = 0
    lines_code: int = 0
    percentage: float = 0.0


class HistoricalSnapshot(BaseModel):
    """Immutable architectural snapshot of a repository at a specific Git commit SHA."""

    schema_version: str = SNAPSHOT_SCHEMA_VERSION
    commit_sha: str = Field(description="Full 40-character Git commit SHA.")
    parent_shas: list[str] = Field(default_factory=list, description="Parent commit SHAs.")
    repo_identity: str = Field(description="Canonical repository identity.")
    commit_timestamp: str = Field(description="ISO-8601 commit timestamp.")
    commit_author: str = Field(default="unknown")
    commit_message: str = Field(default="")
    analyzed_at: str = Field(description="ISO-8601 timestamp when analysis was performed.")
    analyzer_version: str = Field(default="0.6.0")

    total_files: int = 0
    total_lines_code: int = 0
    ast_loc_coverage_pct: float = 0.0

    languages: dict[str, HistoricalLanguageSummary] = Field(default_factory=dict)
    modules: list[HistoricalModuleSummary] = Field(default_factory=list)
    dependencies: list[HistoricalDependencyEdge] = Field(default_factory=list)
    cycles: list[HistoricalCycle] = Field(default_factory=list)
    coupling: dict[str, HistoricalCouplingMetrics] = Field(default_factory=dict)
    health: HistoricalHealthMetrics = Field(default_factory=HistoricalHealthMetrics)
    findings: list[RuleFinding] = Field(default_factory=list)
    evidence: list[HistoricalEvidenceItem] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)

    is_shallow: bool = False
    cache_hit: bool = False


class HistoricalDiffResult(BaseModel):
    """Architectural evolution diff between two historical snapshots."""

    schema_version: str = SNAPSHOT_SCHEMA_VERSION
    base_commit_sha: str
    head_commit_sha: str
    base_timestamp: str
    head_timestamp: str
    time_delta_display: str = ""

    module_changes: ModuleChanges = Field(default_factory=ModuleChanges)
    dependency_changes: DependencyChanges = Field(default_factory=DependencyChanges)
    cycle_changes: CycleChanges = Field(default_factory=CycleChanges)
    coupling_deltas: list[CouplingDeltaItem] = Field(default_factory=list)
    health_delta: HealthScoreDelta
    coverage_delta: CoverageDelta
    finding_changes: RuleFindingChanges = Field(default_factory=RuleFindingChanges)

    caveats: list[str] = Field(default_factory=list)
    summary_text: str = ""


class TimelineEntry(BaseModel):
    """A single chronological point in the architectural evolution timeline."""

    commit_sha: str
    commit_timestamp: str
    commit_author: str
    commit_message: str
    total_files: int
    total_lines_code: int
    health_score: float | None
    health_grade: str
    cycles_count: int
    modules_count: int
    ast_coverage_pct: float


class TimelineResult(BaseModel):
    """Architectural evolution timeline across multiple historical commits."""

    schema_version: str = SNAPSHOT_SCHEMA_VERSION
    repo_identity: str
    total_commits: int
    entries: list[TimelineEntry] = Field(default_factory=list)
    summary_text: str = ""


class CacheEnvelope(BaseModel):
    """On-disk safe serialization envelope with corruption detection."""

    schema_version: str = CACHE_SCHEMA_VERSION
    cache_key: str
    created_at: str
    commit_sha: str
    analyzer_version: str
    checksum: str
    payload: dict[str, Any]
