"""Typed Pydantic v2 schemas for RepoDNA Repository Brain."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from repodna.schemas.models import LanguageSupportLevel


class SymbolKind(StrEnum):
    FUNCTION = "function"
    CLASS = "class"
    METHOD = "method"
    INTERFACE = "interface"
    TYPE = "type"
    IMPORT = "import"
    EXPORT = "export"
    STRUCT = "struct"
    VARIABLE = "variable"
    CONSTANT = "constant"


class ReferenceKind(StrEnum):
    IMPORT = "import"
    CALL = "call"
    TYPE_USAGE = "type_usage"
    INHERITANCE = "inheritance"
    ACCESS = "access"


class ResolutionStatus(StrEnum):
    VERIFIED = "verified"
    CANDIDATE = "candidate"
    UNRESOLVED = "unresolved"


class StalenessReason(StrEnum):
    FRESH = "fresh"
    REVISION_MISMATCH = "revision_mismatch"
    CONTENT_CHANGED = "content_changed"
    LINE_SHIFT = "line_shift"
    FILE_DELETED = "file_deleted"


class EvidenceType(StrEnum):
    SYMBOL_DEFINITION = "symbol_definition"
    SYMBOL_REFERENCE = "symbol_reference"
    IMPORT_STATEMENT = "import_statement"
    EXPORT_STATEMENT = "export_statement"
    DEPENDENCY_EDGE = "dependency_edge"
    ARCHITECTURAL_HUB = "architectural_hub"
    CONTRACT_VIOLATION = "contract_violation"
    CYCLE_PARTICIPATION = "cycle_participation"


class SymbolReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_path: str = Field(description="Repository-relative path of the referencing file.")
    line: int = Field(ge=1, description="1-indexed line number where reference occurs.")
    column: int = Field(default=0, ge=0, description="0-indexed column offset.")
    symbol_name: str = Field(description="Name of the referenced symbol.")
    reference_kind: ReferenceKind = Field(default=ReferenceKind.IMPORT)
    source_symbol_name: str | None = Field(
        default=None, description="Enclosing function or class containing this reference, if any."
    )
    is_verified: bool = Field(
        default=False, description="True if AST proves this reference links to target definition."
    )
    resolution_status: ResolutionStatus = Field(
        default=ResolutionStatus.UNRESOLVED,
        description="Resolution certainty: verified, candidate, or unresolved.",
    )
    target_symbol_id: str | None = Field(
        default=None, description="Deterministic ID of resolved target symbol, if any."
    )
    target_file_path: str | None = Field(
        default=None, description="File path of resolved target definition, if any."
    )
    alias_name: str | None = Field(
        default=None, description="Local alias name if imported with alias."
    )
    module_specifier: str | None = Field(
        default=None, description="Import module specifier (e.g. 'utils' or './service')."
    )
    qualifier: str | None = Field(
        default=None, description="Namespace or object qualifier (e.g. 'math' in 'math.sqrt')."
    )
    confidence_reason: str = Field(
        default="Unresolved reference", description="Explanation of resolution status."
    )


class SymbolDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(description="Deterministic symbol identifier, e.g. sym_<hash>.")
    name: str = Field(description="Symbol identifier name.")
    kind: SymbolKind = Field(description="Kind of symbol: class, function, method, interface, etc.")
    file_path: str = Field(description="Repository-relative path where symbol is defined.")
    line_start: int = Field(ge=1, description="1-indexed starting line.")
    line_end: int = Field(ge=1, description="1-indexed ending line.")
    column_start: int = Field(default=0, ge=0)
    column_end: int = Field(default=0, ge=0)
    language: str = Field(description="Source language, e.g. Python, TypeScript.")
    container_name: str | None = Field(
        default=None, description="Parent class or namespace name containing this symbol."
    )
    signature: str | None = Field(default=None, description="Declaration signature or header.")
    docstring: str | None = Field(default=None, description="Associated docstring or summary.")
    is_exported: bool = Field(default=True, description="Whether symbol is exported or public.")
    evidence_id: str = Field(description="ID of associated EvidenceReference.")
    verified_references: list[SymbolReference] = Field(default_factory=list)
    candidate_references: list[SymbolReference] = Field(default_factory=list)

    @classmethod
    def generate_id(
        cls, file_path: str, name: str, kind: str, line_start: int, container_name: str | None = None
    ) -> str:
        raw = f"{file_path}:{container_name or ''}:{kind}:{name}:{line_start}"
        h = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
        return f"sym_{h}"


class EvidenceReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_id: str = Field(description="Deterministic unique evidence identifier (e.g. ev_<hash>).")
    repository_revision: str = Field(
        description="Git commit SHA or 'WORKING_TREE' for uncommitted workspace."
    )
    file_path: str = Field(description="Repository-relative normalized POSIX path.")
    line_start: int = Field(ge=1, description="1-indexed starting line.")
    line_end: int = Field(ge=1, description="1-indexed ending line.")
    evidence_type: EvidenceType = Field(description="Category of architectural evidence.")
    symbol_name: str | None = Field(default=None, description="Target symbol name if applicable.")
    symbol_kind: SymbolKind | None = Field(default=None)
    support_level: LanguageSupportLevel = Field(default=LanguageSupportLevel.FULL_AST)
    confidence_reason: str = Field(description="Explicit reason explaining validity of evidence.")
    code_snippet: str | None = Field(
        default=None, max_length=2000, description="Bounded source code snippet."
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    is_stale: bool = Field(
        default=False, description="Flagged true if underlying file changed since evidence creation."
    )
    staleness_reason: StalenessReason = Field(
        default=StalenessReason.FRESH, description="Detailed category of staleness (e.g. line_shift, content_changed, revision_mismatch)."
    )
    staleness_details: str | None = Field(
        default=None, description="Human/agent-readable explanation of why evidence was invalidated."
    )
    line_shift_delta: int | None = Field(
        default=None, description="Number of lines the snippet shifted (+/-) if code moved without modification."
    )
    content_hash: str | None = Field(
        default=None, description="Blake2b or SHA256 of the normalized file snippet when evidence was gathered."
    )

    @classmethod
    def generate_id(
        cls,
        revision: str,
        file_path: str,
        line_start: int,
        line_end: int,
        evidence_type: str,
        symbol_name: str | None = None,
    ) -> str:
        raw = f"{revision}:{file_path}:{line_start}:{line_end}:{evidence_type}:{symbol_name or ''}"
        h = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
        return f"ev_{h}"


class CodeSearchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_id: str = Field(description="Repository-relative file path.")
    score: float = Field(ge=0.0, description="Deterministic composite relevance score.")
    relevance_tier: str = Field(description="HIGH, MEDIUM, or LOW relevance tier.")
    match_reasons: list[str] = Field(default_factory=list, description="Explainable scoring reasons.")
    matched_symbols: list[SymbolDefinition] = Field(default_factory=list)
    evidence_items: list[EvidenceReference] = Field(default_factory=list)
    language: str
    lines_code: int = 0
    fan_in: int = 0
    fan_out: int = 0
    is_hub: bool = False
    in_cycle: bool = False
    is_comment_only_match: bool = Field(
        default=False,
        description="True if query terms matched exclusively in comments/docstrings with no code symbols.",
    )
    snippet: str | None = None


class SearchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str
    total_matches: int
    matches: list[CodeSearchResult] = Field(default_factory=list)
    summary_text: str
    query_intent: str = Field(
        default="general_search", description="Classified intent (e.g. where_is, trace, find_symbol)."
    )
    tokens_evaluated: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class SymbolQueryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_symbols: int
    symbols: list[SymbolDefinition] = Field(default_factory=list)
    summary_text: str
    filter_criteria: dict[str, Any] = Field(default_factory=dict)


class SymbolTraceResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: SymbolDefinition
    definition_evidence: EvidenceReference
    references: list[SymbolReference] = Field(default_factory=list)
    candidate_references: list[SymbolReference] = Field(default_factory=list)
    importing_modules: list[str] = Field(default_factory=list)
    calling_modules: list[str] = Field(default_factory=list)
    downstream_dependents: list[str] = Field(default_factory=list)
    downstream_impact_count: int = 0
    cycle_warning: str | None = None
    is_ambiguous: bool = Field(default=False)
    ambiguity_candidates: list[SymbolDefinition] = Field(default_factory=list)
    summary_text: str


class EvidenceLedgerResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_evidence: int
    stale_count: int = 0
    evidence_items: list[EvidenceReference] = Field(default_factory=list)
    summary_text: str
