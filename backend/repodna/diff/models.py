"""Typed Pydantic schemas for the RepoDNA Architecture Diff Engine."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from repodna.schemas.models import RuleFinding, SeverityLevel


class RevisionProvenance(BaseModel):
    ref_name: str
    commit_sha: str | None = None
    commit_date: str | None = None
    commit_author: str | None = None
    is_working_tree: bool = False
    analyzed_at: datetime
    analysis_version: str = "0.3.0"
    total_files: int
    total_lines_code: int
    ast_coverage_pct: float
    health_score: float | None = None
    health_grade: str


class RenamedModule(BaseModel):
    old_path: str
    new_path: str
    confidence: float
    reason: str


class ModuleChanges(BaseModel):
    added: list[str] = Field(default_factory=list)
    removed: list[str] = Field(default_factory=list)
    renamed: list[RenamedModule] = Field(default_factory=list)
    modified_dependencies: list[str] = Field(default_factory=list)


class EdgeDiffItem(BaseModel):
    source: str
    target: str
    import_names: list[str] = Field(default_factory=list)


class DependencyChanges(BaseModel):
    added_edges: list[EdgeDiffItem] = Field(default_factory=list)
    removed_edges: list[EdgeDiffItem] = Field(default_factory=list)


class CycleDiffItem(BaseModel):
    id: str
    nodes: list[str]
    length: int
    severity: SeverityLevel
    description: str


class CycleChanges(BaseModel):
    new_cycles: list[CycleDiffItem] = Field(default_factory=list)
    resolved_cycles: list[CycleDiffItem] = Field(default_factory=list)
    persisting_cycles: int = 0


class CouplingDeltaItem(BaseModel):
    file_id: str
    fan_in_before: int
    fan_in_after: int
    fan_in_delta: int
    fan_out_before: int
    fan_out_after: int
    fan_out_delta: int
    instability_before: float
    instability_after: float
    instability_delta: float


class HealthScoreDelta(BaseModel):
    score_before: float | None = None
    score_after: float | None = None
    score_delta: float | None = None
    grade_before: str
    grade_after: str
    status_before: str
    status_after: str


class RuleFindingChanges(BaseModel):
    new_findings: list[RuleFinding] = Field(default_factory=list)
    resolved_findings: list[RuleFinding] = Field(default_factory=list)
    persisting_findings_count: int = 0


class CoverageDelta(BaseModel):
    ast_loc_coverage_before: float
    ast_loc_coverage_after: float
    ast_loc_coverage_delta: float
    supported_langs_before: list[str]
    supported_langs_after: list[str]
    caveats: list[str] = Field(default_factory=list)


class ArchitectureDiffResult(BaseModel):
    base_provenance: RevisionProvenance
    head_provenance: RevisionProvenance
    generated_at: datetime
    verdict: str  # "improved", "neutral", "degraded", "regressive_cycles"
    module_changes: ModuleChanges
    dependency_changes: DependencyChanges
    cycle_changes: CycleChanges
    significant_coupling_deltas: list[CouplingDeltaItem] = Field(default_factory=list)
    health_delta: HealthScoreDelta
    finding_changes: RuleFindingChanges
    coverage_delta: CoverageDelta
    summary_text: str
