"""Typed Pydantic v2 schemas for RepoDNA Repository Passport."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

PASSPORT_SCHEMA_VERSION = "1.0.0"
PASSPORT_SCHEMA_VERSION_V1 = "1.0.0"
PASSPORT_SCHEMA_VERSION_V2 = "2.0.0"



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
    provenance_verified: bool = Field(
        default=False,
        description="Whether git_revision was verified as an immutable hexadecimal commit SHA.",
    )
    revision_status: str = Field(
        default="unresolved_ref",
        description="'verified_commit_sha' or 'unresolved_symbolic_ref'.",
    )
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


class PassportSymbolSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_symbols: int = 0
    language_counts: dict[str, int] = Field(default_factory=dict)
    symbols_by_kind: dict[str, int] = Field(default_factory=dict)
    total_verified_references: int = 0
    total_candidate_references: int = 0
    total_unresolved_references: int = 0


class PassportEntrypoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_path: str
    role: str = Field(description="Role classification: cli, api, main, worker, web, etc.")
    primary_symbol: str | None = None
    evidence_id: str | None = None
    source: str = "ast_verified"


class PassportModuleRole(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_path: str
    role: str = Field(description="Role: core, api, brain, cli, guardian, contract, passport, storage, util, etc.")
    responsibility: str
    source: str = "ast_verified"
    evidence_id: str | None = None


class PassportEvidenceSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_evidence: int = 0
    fresh_count: int = 0
    stale_count: int = 0
    evidence_by_type: dict[str, int] = Field(default_factory=dict)


class PassportRetrievalCapabilities(BaseModel):
    model_config = ConfigDict(extra="forbid")

    supports_semantic_search: bool = True
    supports_symbol_resolution: bool = True
    supports_cross_module_trace: bool = True
    supports_blast_radius: bool = True
    token_budgeting: bool = True


class RepositoryPassportV2(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = PASSPORT_SCHEMA_VERSION_V2
    repo_name: str
    git_revision: str
    provenance_verified: bool = Field(
        default=False,
        description="Whether git_revision was verified as an immutable hexadecimal commit SHA.",
    )
    revision_status: str = Field(
        default="unresolved_ref",
        description="'verified_commit_sha' or 'unresolved_symbolic_ref'.",
    )
    analyzed_at: datetime
    repodna_version: str = "0.5.0"
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

    # v2.0 additions
    symbol_index_summary: PassportSymbolSummary | None = None
    architectural_entrypoints: list[PassportEntrypoint] = Field(default_factory=list)
    major_module_roles: list[PassportModuleRole] = Field(default_factory=list)
    verified_reference_counts: int | None = None
    candidate_unresolved_counts: dict[str, int] = Field(default_factory=dict)
    evidence_ledger_summary: PassportEvidenceSummary | None = None
    retrieval_capabilities: PassportRetrievalCapabilities | None = None
    analysis_limitations: list[str] = Field(default_factory=list)
    source_revision: str | None = None

