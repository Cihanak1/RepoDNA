"""Typed Pydantic v2 schemas for RepoDNA PR Architecture Guardian."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from repodna.contract.models import (
    ContractEvaluationReport,
    ContractMode,
    ContractUnknown,
    ContractViolation,
)
from repodna.diff.models import (
    CouplingDeltaItem,
    CoverageDelta,
    CycleDiffItem,
    EdgeDiffItem,
    HealthScoreDelta,
    RenamedModule,
    RevisionProvenance,
)


class GuardianVerdict(StrEnum):
    PASS = "PASS"
    WARNING = "WARNING"
    FAIL = "FAIL"
    INCONCLUSIVE = "INCONCLUSIVE"


class RiskLevel(StrEnum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class RiskAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    risk_score: float = Field(ge=0.0, le=100.0, description="Deterministic risk score from 0.0 to 100.0.")
    risk_level: RiskLevel
    risk_factors: list[str] = Field(default_factory=list, description="Explicit breakdown of risk contributors.")
    mitigation_advice: list[str] = Field(default_factory=list)


class GuardianReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    generated_at: datetime
    base_provenance: RevisionProvenance
    head_provenance: RevisionProvenance
    verdict: GuardianVerdict
    verdict_reason: str
    risk_assessment: RiskAssessment
    mode: ContractMode = ContractMode.ADVISORY

    # Module changes
    added_modules: list[str] = Field(default_factory=list)
    removed_modules: list[str] = Field(default_factory=list)
    renamed_modules: list[RenamedModule] = Field(default_factory=list)

    # Dependency changes
    added_edges: list[EdgeDiffItem] = Field(default_factory=list)
    removed_edges: list[EdgeDiffItem] = Field(default_factory=list)

    # Circular dependencies
    new_cycles: list[CycleDiffItem] = Field(default_factory=list)
    resolved_cycles: list[CycleDiffItem] = Field(default_factory=list)
    persisting_cycles_count: int = 0

    # Architecture contract deltas
    contract_evaluated: bool = False
    contract_version: int | None = None
    new_contract_violations: list[ContractViolation] = Field(default_factory=list)
    resolved_contract_violations: list[ContractViolation] = Field(default_factory=list)
    existing_baseline_violations: list[ContractViolation] = Field(default_factory=list)
    unknown_evaluations: list[ContractUnknown] = Field(default_factory=list)
    base_contract_report: ContractEvaluationReport | None = None
    head_contract_report: ContractEvaluationReport | None = None

    # Coupling and health
    coupling_deltas: list[CouplingDeltaItem] = Field(default_factory=list)
    health_delta: HealthScoreDelta
    coverage_delta: CoverageDelta

    # Policy and CI gate execution
    should_block_ci: bool = Field(
        default=False,
        description="Whether this assessment warrants failing CI (exit code 1) under active policy mode.",
    )
    exit_code: int = Field(
        default=0,
        description="Recommended process exit code (0: clean/advisory, 1: policy block/fail, 2: inconclusive/error).",
    )

    # Raw diff reference
    diff_summary: str
    summary_markdown: str
    metadata: dict[str, Any] = Field(default_factory=dict)
