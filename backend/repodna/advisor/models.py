"""Data models for RepoDNA Refactoring Advisor.

Provides deterministic, evidence-based architectural refactoring recommendations.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class AdvisorCategory(StrEnum):
    """The four core architectural refactoring recommendation categories."""

    CIRCULAR_DEPENDENCY = "circular_dependency_reduction"
    HIGH_COUPLING = "high_coupling_module_review"
    LAYER_BOUNDARY = "layer_boundary_improvement"
    OVERSIZED_HUB = "oversized_architectural_hub_review"


class RefactoringRecommendation(BaseModel):
    """A deterministic, evidence-grounded architectural refactoring recommendation."""

    recommendation_id: str = Field(
        description="Deterministic unique ID, e.g. ref_cycle_<hash>"
    )
    target_module: str = Field(
        description="Normalized POSIX relative file path of primary target module"
    )
    category: AdvisorCategory
    severity: str = Field(description="critical, high, medium, low")
    title: str
    description: str
    evidence_id: str | None = None
    evidence_snippets: list[str] = Field(default_factory=list)
    revision_source: str = "WORKING_TREE"
    affected_modules: list[str] = Field(
        default_factory=list, description="Downstream / dependent modules"
    )
    expected_architectural_benefit: str
    suggested_action_steps: list[str] = Field(default_factory=list)
    risks_and_limitations: str
    support_level: str = Field(
        default="verified", description="verified or candidate"
    )
    metric_delta_preview: dict[str, Any] = Field(default_factory=dict)

    @property
    def target_modules(self) -> list[str]:
        return [self.target_module, *[m for m in self.affected_modules if m != self.target_module]]

    @property
    def action_steps(self) -> list[str]:
        return self.suggested_action_steps

    @property
    def expected_benefit(self) -> str:
        return self.expected_architectural_benefit

    @property
    def impact_description(self) -> str:
        return self.description


class RefactoringAdvisorReport(BaseModel):
    """Aggregated architectural refactoring report for a repository analysis."""

    schema_version: str = "1.0.0"
    repo_identity: str
    total_recommendations: int
    total_modules_analyzed: int = 0
    by_category: dict[str, int]
    by_severity: dict[str, int]
    recommendations: list[RefactoringRecommendation]
    summary_text: str

    @property
    def repo_name(self) -> str:
        return self.repo_identity

    @property
    def summary(self) -> str:
        return self.summary_text

    @property
    def critical_cycles_detected(self) -> int:
        return self.by_category.get(AdvisorCategory.CIRCULAR_DEPENDENCY.value, 0)

    @property
    def high_coupling_modules(self) -> int:
        return self.by_category.get(AdvisorCategory.HIGH_COUPLING.value, 0)

    @property
    def layer_boundary_violations(self) -> int:
        return self.by_category.get(AdvisorCategory.LAYER_BOUNDARY.value, 0)

    @property
    def oversized_hubs(self) -> int:
        return self.by_category.get(AdvisorCategory.OVERSIZED_HUB.value, 0)
