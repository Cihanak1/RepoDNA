"""Typed Pydantic v2 models for RepoDNA Architecture Contracts."""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

RULE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_\-\.]+$")


class ContractMode(StrEnum):
    ADVISORY = "advisory"
    ENFORCE = "enforce"


class UnknownBehavior(StrEnum):
    WARN = "warn"
    FAIL = "fail"
    IGNORE = "ignore"


class ContractSeverity(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class ContractPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: ContractMode = Field(
        default=ContractMode.ADVISORY,
        description="Whether contract violations are advisory warnings or enforced failures.",
    )
    unknown_behavior: UnknownBehavior = Field(
        default=UnknownBehavior.WARN,
        description="How to handle unresolved imports or unsupported language files matching rules.",
    )


class ContractRule(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: str = Field(description="Unique rule identifier, e.g. 'LAYER-001'.")
    title: str = Field(min_length=1, max_length=256, description="Human-readable rule title.")
    description: str = Field(default="", max_length=2048, description="Detailed explanation of the rule.")
    from_patterns: list[str] = Field(
        alias="from",
        description="POSIX glob patterns matching source files governed by this rule.",
    )
    disallow_imports: list[str] = Field(
        default_factory=list,
        description="POSIX glob patterns matching imported modules that are prohibited.",
    )
    allow_imports: list[str] | None = Field(
        default=None,
        description="Optional exclusive whitelist of permitted imports. If specified, any import not matching is prohibited.",
    )
    severity: ContractSeverity = Field(
        default=ContractSeverity.WARNING,
        description="Severity level of violations.",
    )
    remediation: str = Field(
        default="",
        max_length=1024,
        description="Actionable steps to resolve violations.",
    )

    @field_validator("id")
    @classmethod
    def validate_rule_id(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Rule ID cannot be empty.")
        if not RULE_ID_PATTERN.match(cleaned):
            raise ValueError(f"Rule ID '{cleaned}' must contain only alphanumeric characters, underscores, dashes, or dots.")
        return cleaned

    @field_validator("from_patterns", mode="before")
    @classmethod
    def normalize_from_patterns(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            return [v.strip()]
        if isinstance(v, (list, tuple)):
            return [str(item).strip() for item in v if str(item).strip()]
        raise ValueError("'from' must be a glob string or list of glob strings.")

    @field_validator("disallow_imports", mode="before")
    @classmethod
    def normalize_disallow_imports(cls, v: Any) -> list[str]:
        if v is None:
            return []
        if isinstance(v, str):
            return [v.strip()]
        if isinstance(v, (list, tuple)):
            return [str(item).strip() for item in v if str(item).strip()]
        raise ValueError("'disallow_imports' must be a string or list of strings.")

    @field_validator("allow_imports", mode="before")
    @classmethod
    def normalize_allow_imports(cls, v: Any) -> list[str] | None:
        if v is None:
            return None
        if isinstance(v, str):
            return [v.strip()]
        if isinstance(v, (list, tuple)):
            return [str(item).strip() for item in v if str(item).strip()]
        raise ValueError("'allow_imports' must be a string or list of strings.")


class ArchitectureContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = Field(default=1, description="Schema version of the architecture contract.")
    policy: ContractPolicy = Field(default_factory=ContractPolicy)
    rules: list[ContractRule] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("version")
    @classmethod
    def validate_version(cls, v: int) -> int:
        if v != 1:
            raise ValueError(f"Unsupported contract schema version: {v}. Supported versions: [1]")
        return v

    @field_validator("rules")
    @classmethod
    def validate_unique_rule_ids(cls, rules: list[ContractRule]) -> list[ContractRule]:
        seen: set[str] = set()
        for r in rules:
            if r.id in seen:
                raise ValueError(f"Duplicate rule id '{r.id}' found in contract.")
            seen.add(r.id)
        return rules


class ContractViolation(BaseModel):
    rule_id: str
    rule_title: str
    severity: ContractSeverity
    source_file: str
    target_file: str
    import_names: list[str] = Field(default_factory=list)
    line: int = 1
    message: str
    remediation: str = ""
    is_baseline: bool = False


class ContractUnknown(BaseModel):
    rule_id: str
    rule_title: str
    source_file: str
    raw_import: str
    line: int = 1
    reason: str
    detail: str


class ContractEvaluationReport(BaseModel):
    contract_version: int
    mode: ContractMode
    unknown_behavior: UnknownBehavior
    total_rules: int
    rules_evaluated: int
    rules_passed: list[str] = Field(default_factory=list)
    rules_violated: list[str] = Field(default_factory=list)
    violations: list[ContractViolation] = Field(default_factory=list)
    new_violations: list[ContractViolation] = Field(default_factory=list)
    baseline_violations: list[ContractViolation] = Field(default_factory=list)
    unknowns: list[ContractUnknown] = Field(default_factory=list)
    is_compliant: bool
    verdict: str = Field(description="PASS, WARNING, FAIL, or INCONCLUSIVE")
    summary_text: str
