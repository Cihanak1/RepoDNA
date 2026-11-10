"""Pydantic v2 schemas for RepoDNA Code Intelligence Retrieval & Fidelity Benchmark."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class QueryCategory(StrEnum):
    SYMBOL_LOOKUP = "symbol_lookup"
    FEATURE_LOCATION = "feature_location"
    DEPENDENCY_TRACE = "dependency_trace"
    IMPACT_ANALYSIS = "impact_analysis"
    NEGATIVE = "negative"
    AMBIGUOUS = "ambiguous"


class Difficulty(StrEnum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class SplitType(StrEnum):
    DEV = "dev"
    HOLDOUT = "holdout"


class FailureCategory(StrEnum):
    MISSING_SYMBOL = "missing_symbol"
    INCORRECT_IMPORT_RESOLUTION = "incorrect_import_resolution"
    FALSE_REFERENCE_VERIFICATION = "false_reference_verification"
    RANKING_FAILURE = "ranking_failure"
    SYNONYM_EXPANSION_ERROR = "synonym_expansion_error"
    TOKEN_BUDGET_TRUNCATION = "token_budget_truncation"
    UNSUPPORTED_LANGUAGE = "unsupported_language"
    AMBIGUOUS_QUERY = "ambiguous_query"
    INSUFFICIENT_SOURCE_EVIDENCE = "insufficient_source_evidence"
    NONE = "none"


class BenchmarkQuery(BaseModel):
    model_config = ConfigDict(extra="ignore")

    query_id: str = Field(description="Unique identifier, e.g. Q01, Q02.")
    query: str = Field(description="Natural language or identifier query.")
    repository: str = Field(default="RepoDNA", description="Target repository name.")
    revision_sha: str = Field(default="head", description="Target git commit SHA or 'head'.")
    language: str = Field(description="Target language: python, typescript, javascript, multi.")
    expected_files: list[str] = Field(
        default_factory=list, description="Ground truth target files (empty for negative queries)."
    )
    expected_symbols: list[str] = Field(
        default_factory=list, description="Ground truth target symbol names or IDs."
    )
    expected_evidence: list[str] = Field(
        default_factory=list, description="Ground truth expected keywords or snippets."
    )
    query_category: QueryCategory = Field(description="Category of developer intent.")
    difficulty: Difficulty = Field(description="Difficulty level: easy, medium, hard.")
    split: SplitType = Field(default=SplitType.DEV, description="Dataset split: dev or holdout.")
    notes: str | None = Field(default=None, description="Explanation or test criteria.")


class SingleQueryEvaluation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query_id: str
    query: str
    method: str  # filename_only, symbol_only, repository_brain
    split: SplitType
    returned_files: list[str]
    hit_at_1: bool
    hit_at_3: bool
    hit_at_5: bool
    reciprocal_rank: float
    precision_at_1: float
    precision_at_3: float
    precision_at_5: float
    recall_at_1: float
    recall_at_3: float
    recall_at_5: float
    ndcg_at_5: float
    latency_ms: float
    is_negative: bool
    abstained: bool
    false_positive_on_negative: bool
    failure_category: FailureCategory = FailureCategory.NONE
    failure_notes: str | None = None


class MethodMetricsSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    method: str
    split: str  # all, dev, holdout
    total_queries: int
    positive_queries: int
    negative_queries: int
    hit_at_1: float
    hit_at_3: float
    hit_at_5: float
    mrr: float
    precision_at_1: float
    precision_at_3: float
    precision_at_5: float
    recall_at_1: float
    recall_at_3: float
    recall_at_5: float
    ndcg_at_5: float
    negative_abstention_rate: float
    negative_false_positive_rate: float
    p50_latency_ms: float
    p95_latency_ms: float
    mean_latency_ms: float


class FailureReportItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query_id: str
    query: str
    category: FailureCategory
    split: SplitType
    expected_files: list[str]
    actual_files: list[str]
    root_cause: str
    proposed_fix: str


class BudgetComplianceResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_tokens: int
    counted_tokens: int
    counting_method: str
    termination_success: bool = True
    budget_compliant: bool
    metadata_overflow: bool = False
    truncated: bool
    estimated_token_count: int
    tokenizer_method: str
    is_compliant: bool
    is_truncated: bool
    contract: str = "standard"
    iterations: int = 1
    duration_ms: float
    is_deterministic: bool
    notes: str


class ScalabilityScaleResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scale_tier: str  # small, medium, large
    file_count: int
    loc: int
    symbol_count: int
    cold_indexing_ms: float
    warm_query_p50_ms: float
    warm_query_p95_ms: float
    repeated_query_ms: float
    peak_memory_mb: float
    memory_growth_mb: float
    status: str  # ok, timeout, error


class BenchmarkRunReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    benchmark_version: str = "v1.0"
    timestamp: str
    commit_sha: str
    environment: dict[str, Any]
    dataset_path: str
    dataset_total: int
    dataset_dev_count: int
    dataset_holdout_count: int
    cold_indexing_time_ms: float
    warm_indexing_time_ms: float
    peak_memory_mb: float
    verified_reference_precision: float
    false_verified_count: int
    unresolved_reference_count: int
    token_budget_compliance_pct: float
    baselines: dict[str, MethodMetricsSummary]
    dev_split_metrics: dict[str, MethodMetricsSummary]
    holdout_split_metrics: dict[str, MethodMetricsSummary]
    failure_analysis: list[FailureReportItem]
    budget_benchmarks: list[BudgetComplianceResult]
    scalability_results: list[ScalabilityScaleResult]
    query_evaluations: list[SingleQueryEvaluation]
