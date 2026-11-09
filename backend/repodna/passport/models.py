"""Typed Pydantic v2 schemas for RepoDNA Repository Passport."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

PASSPORT_SCHEMA_VERSION = "1.0.0"


class PassportHubModule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_id: str
    fan_in: int
    fan_out: int
    instability: float
    is_hub: bool = True


class PassportModuleItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    language: str
    lines_code: int
    fan_in: int
    fan_out: int
    instability: float
    in_cycle: bool
    is_hub: bool


class PassportLanguageItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    language: str
    support_level: str
    file_count: int
    lines_code: int
    percentage: float


class PassportCoverage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ast_file_coverage_pct: float
    ast_loc_coverage_pct: float
    supported_languages: list[str] = Field(default_factory=list)
    partial_static_languages: list[str] = Field(default_factory=list)
    unsupported_languages: list[str] = Field(default_factory=list)


class PassportDependencySummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_modules: int
    total_internal_edges: int
    cycle_count: int
    cyclic_scc_count: int
    orphan_modules_count: int
    hub_modules_count: int
    average_instability: float


class PassportHealth(BaseModel):
    model_config = ConfigDict(extra="forbid")

    score: float | None = None
    grade: str
    status: str
    confidence: str
    confidence_reason: str = ""


class PassportContractStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    has_contract: bool
    contract_version: int | None = None
    mode: str | None = None
    rules_count: int = 0
    is_compliant: bool | None = None
    active_violations_count: int = 0


class PassportTruncation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_truncated: bool = False
    total_inventory_count: int = 0
    returned_inventory_count: int = 0
    reason: str | None = None


class RepositoryPassport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = PASSPORT_SCHEMA_VERSION
    repo_name: str
    git_revision: str
    analyzed_at: datetime
    repodna_version: str = "0.4.0"
    primary_languages: list[PassportLanguageItem] = Field(default_factory=list)
    ast_coverage: PassportCoverage
    confidence: str
    architectural_hubs: list[PassportHubModule] = Field(default_factory=list)
    module_inventory: list[PassportModuleItem] = Field(default_factory=list)
    dependency_summary: PassportDependencySummary
    identified_boundaries: list[str] = Field(default_factory=list)
    architecture_health: PassportHealth
    verified_findings: list[str] = Field(default_factory=list)
    unknown_unverified: list[str] = Field(default_factory=list)
    contract_status: PassportContractStatus
    evidence_references: list[str] = Field(default_factory=list)
    truncation_metadata: PassportTruncation
    metadata: dict[str, Any] = Field(default_factory=dict)
