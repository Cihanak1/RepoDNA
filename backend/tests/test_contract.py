"""Unit and integration tests for RepoDNA Architecture Contract Engine."""

from __future__ import annotations

import tempfile
from datetime import UTC, datetime
from pathlib import Path

import pytest

from repodna.contract.evaluator import ContractEvaluator
from repodna.contract.loader import (
    find_contract_file,
    init_starter_contract,
    load_contract_file,
    load_contract_from_yaml,
)
from repodna.contract.models import (
    ContractMode,
    ContractSeverity,
    UnknownBehavior,
)
from repodna.schemas.models import (
    AnalysisResult,
    ArchitectureHealthReport,
    DependencyEdge,
    FileNode,
    GitInsights,
    GraphMetrics,
    LanguageBreakdownItem,
    LanguageSupportLevel,
    SourceType,
    TransparencyReport,
    UnresolvedReference,
)
from repodna.security.validators import SecurityValidationError


def _create_mock_analysis(
    files: list[FileNode],
    edges: list[DependencyEdge],
    ast_loc_coverage_pct: float = 100.0,
) -> AnalysisResult:
    return AnalysisResult(
        analysis_id="test_analysis_1",
        repo_name="test-repo",
        source_type=SourceType.LOCAL,
        target_display="./test-repo",
        analyzed_at=datetime.now(UTC),
        duration_ms=42,
        total_files=len(files),
        total_lines_code=sum(f.lines_code for f in files),
        total_lines_all=sum(f.lines_total for f in files),
        total_size_bytes=sum(f.size_bytes for f in files),
        languages=[
            LanguageBreakdownItem(
                language="Python",
                support_level=LanguageSupportLevel.FULL_AST,
                file_count=len(files),
                lines_code=sum(f.lines_code for f in files),
                lines_total=sum(f.lines_total for f in files),
                size_bytes=sum(f.size_bytes for f in files),
                percentage_of_code=100.0,
            )
        ],
        files=files,
        edges=edges,
        cycles=[],
        graph_metrics=GraphMetrics(total_nodes=len(files), total_edges=len(edges)),
        health_report=ArchitectureHealthReport(
            overall_score=95.0,
            grade="A",
            status="evaluated",
            confidence="high",
            methodology="Standard",
        ),
        git_insights=GitInsights(is_git_repo=True),
        transparency=TransparencyReport(
            ast_loc_coverage_pct=ast_loc_coverage_pct,
            supported_languages_detected=["Python"],
        ),
    )


def test_contract_yaml_parsing_and_defaults() -> None:
    yaml_text = """
version: 1
policy:
  mode: advisory
  unknown_behavior: warn
rules:
  - id: LAYER-001
    title: Domain Isolation
    from: "domain/**"
    disallow_imports:
      - "infrastructure/**"
    severity: error
    remediation: Use dependency inversion.
"""
    contract = load_contract_from_yaml(yaml_text)
    assert contract.version == 1
    assert contract.policy.mode == ContractMode.ADVISORY
    assert contract.policy.unknown_behavior == UnknownBehavior.WARN
    assert len(contract.rules) == 1
    r = contract.rules[0]
    assert r.id == "LAYER-001"
    assert r.title == "Domain Isolation"
    assert r.from_patterns == ["domain/**"]
    assert r.disallow_imports == ["infrastructure/**"]
    assert r.severity == ContractSeverity.ERROR


def test_contract_validation_errors() -> None:
    # Unsupported version
    with pytest.raises(ValueError, match="Unsupported contract schema version"):
        load_contract_from_yaml("version: 99\nrules: []")

    # Duplicate rule id
    duplicate_yaml = """
version: 1
rules:
  - id: R1
    title: First
    from: "a/**"
  - id: R1
    title: Second
    from: "b/**"
"""
    with pytest.raises(ValueError, match="Duplicate rule id 'R1'"):
        load_contract_from_yaml(duplicate_yaml)

    # Invalid rule ID syntax
    invalid_id_yaml = """
version: 1
rules:
  - id: "INVALID ID WITH SPACES"
    title: Bad
    from: "a/**"
"""
    with pytest.raises(ValueError, match="must contain only alphanumeric"):
        load_contract_from_yaml(invalid_id_yaml)


def test_contract_size_limit_security() -> None:
    huge_yaml = "version: 1\n# " + ("A" * 600_000)
    with pytest.raises(SecurityValidationError, match="exceeds maximum allowed size"):
        load_contract_from_yaml(huge_yaml)


def test_contract_evaluation_compliant() -> None:
    yaml_text = """
version: 1
policy:
  mode: enforce
rules:
  - id: DOMAIN-001
    title: Domain Layer Isolation
    from: "domain/**"
    disallow_imports:
      - "infrastructure/**"
    severity: error
"""
    contract = load_contract_from_yaml(yaml_text)
    files = [
        FileNode(
            id="domain/model.py",
            name="model.py",
            directory="domain",
            extension=".py",
            language="Python",
            support_level=LanguageSupportLevel.FULL_AST,
            size_bytes=100,
            lines_total=10,
            lines_code=10,
            lines_comment=0,
            lines_blank=0,
            imports_internal=["domain/types.py"],
        ),
        FileNode(
            id="domain/types.py",
            name="types.py",
            directory="domain",
            extension=".py",
            language="Python",
            support_level=LanguageSupportLevel.FULL_AST,
            size_bytes=80,
            lines_total=8,
            lines_code=8,
            lines_comment=0,
            lines_blank=0,
        ),
        FileNode(
            id="infrastructure/db.py",
            name="db.py",
            directory="infrastructure",
            extension=".py",
            language="Python",
            support_level=LanguageSupportLevel.FULL_AST,
            size_bytes=200,
            lines_total=20,
            lines_code=20,
            lines_comment=0,
            lines_blank=0,
            imports_internal=["domain/model.py"],
        ),
    ]
    edges = [
        DependencyEdge(id="e1", source="domain/model.py", target="domain/types.py"),
        DependencyEdge(id="e2", source="infrastructure/db.py", target="domain/model.py"),
    ]
    analysis = _create_mock_analysis(files, edges)
    evaluator = ContractEvaluator(contract)
    report = evaluator.evaluate(analysis)

    assert report.is_compliant is True
    assert report.verdict == "PASS"
    assert len(report.violations) == 0
    assert "DOMAIN-001" in report.rules_passed


def test_contract_evaluation_violation_advisory_vs_enforce() -> None:
    yaml_text = """
version: 1
policy:
  mode: advisory
rules:
  - id: DOMAIN-001
    title: Domain Layer Isolation
    from: "domain/**"
    disallow_imports:
      - "infrastructure/**"
    severity: error
    remediation: Invert dependency.
"""
    contract = load_contract_from_yaml(yaml_text)
    files = [
        FileNode(
            id="domain/model.py",
            name="model.py",
            directory="domain",
            extension=".py",
            language="Python",
            support_level=LanguageSupportLevel.FULL_AST,
            size_bytes=100,
            lines_total=10,
            lines_code=10,
            lines_comment=0,
            lines_blank=0,
            imports_internal=["infrastructure/db.py"],
        ),
        FileNode(
            id="infrastructure/db.py",
            name="db.py",
            directory="infrastructure",
            extension=".py",
            language="Python",
            support_level=LanguageSupportLevel.FULL_AST,
            size_bytes=200,
            lines_total=20,
            lines_code=20,
            lines_comment=0,
            lines_blank=0,
        ),
    ]
    edges = [
        DependencyEdge(id="e1", source="domain/model.py", target="infrastructure/db.py", line=5),
    ]
    analysis = _create_mock_analysis(files, edges)

    # 1. Advisory mode
    adv_evaluator = ContractEvaluator(contract, mode_override=ContractMode.ADVISORY)
    adv_report = adv_evaluator.evaluate(analysis)
    assert adv_report.verdict == "WARNING"
    assert len(adv_report.new_violations) == 1
    v = adv_report.new_violations[0]
    assert v.rule_id == "DOMAIN-001"
    assert v.source_file == "domain/model.py"
    assert v.target_file == "infrastructure/db.py"
    assert v.line == 5

    # 2. Enforce mode
    enf_evaluator = ContractEvaluator(contract, mode_override=ContractMode.ENFORCE)
    enf_report = enf_evaluator.evaluate(analysis)
    assert enf_report.verdict == "FAIL"
    assert enf_report.is_compliant is False


def test_contract_baseline_suppression() -> None:
    yaml_text = """
version: 1
policy:
  mode: enforce
rules:
  - id: DOMAIN-001
    title: Domain Layer Isolation
    from: "domain/**"
    disallow_imports:
      - "infrastructure/**"
    severity: error
"""
    contract = load_contract_from_yaml(yaml_text)
    files = [
        FileNode(
            id="domain/model.py",
            name="model.py",
            directory="domain",
            extension=".py",
            language="Python",
            support_level=LanguageSupportLevel.FULL_AST,
            size_bytes=100,
            lines_total=10,
            lines_code=10,
            lines_comment=0,
            lines_blank=0,
            imports_internal=["infrastructure/db.py"],
        ),
        FileNode(
            id="infrastructure/db.py",
            name="db.py",
            directory="infrastructure",
            extension=".py",
            language="Python",
            support_level=LanguageSupportLevel.FULL_AST,
            size_bytes=200,
            lines_total=20,
            lines_code=20,
            lines_comment=0,
            lines_blank=0,
        ),
    ]
    edges = [
        DependencyEdge(id="e1", source="domain/model.py", target="infrastructure/db.py"),
    ]
    analysis = _create_mock_analysis(files, edges)

    # Baseline suppresses known violation
    baseline = {("DOMAIN-001", "domain/model.py", "infrastructure/db.py")}
    evaluator = ContractEvaluator(contract, baseline=baseline)
    report = evaluator.evaluate(analysis)

    assert len(report.violations) == 1
    assert len(report.new_violations) == 0
    assert len(report.baseline_violations) == 1
    assert report.verdict == "PASS"
    assert report.is_compliant is True


def test_contract_allow_imports_whitelist() -> None:
    yaml_text = """
version: 1
rules:
  - id: STRICT-001
    title: Strict Whitelist
    from: "domain/**"
    allow_imports:
      - "domain/**"
      - "shared/kernel/**"
    severity: error
"""
    contract = load_contract_from_yaml(yaml_text)
    files = [
        FileNode(
            id="domain/model.py",
            name="model.py",
            directory="domain",
            extension=".py",
            language="Python",
            support_level=LanguageSupportLevel.FULL_AST,
            size_bytes=100,
            lines_total=10,
            lines_code=10,
            lines_comment=0,
            lines_blank=0,
            imports_internal=["other/module.py"],
        ),
        FileNode(
            id="other/module.py",
            name="module.py",
            directory="other",
            extension=".py",
            language="Python",
            support_level=LanguageSupportLevel.FULL_AST,
            size_bytes=100,
            lines_total=10,
            lines_code=10,
            lines_comment=0,
            lines_blank=0,
        ),
    ]
    edges = [DependencyEdge(id="e1", source="domain/model.py", target="other/module.py")]
    analysis = _create_mock_analysis(files, edges)
    report = ContractEvaluator(contract).evaluate(analysis)

    assert len(report.new_violations) == 1
    assert "not in the allowed imports whitelist" in report.new_violations[0].message


def test_contract_unknown_handling_unsupported_and_unresolved() -> None:
    yaml_text = """
version: 1
policy:
  mode: advisory
  unknown_behavior: warn
rules:
  - id: DOMAIN-001
    title: Domain Isolation
    from: "domain/**"
    disallow_imports:
      - "infra/**"
"""
    contract = load_contract_from_yaml(yaml_text)
    files = [
        # 1. Unsupported language file matching rule
        FileNode(
            id="domain/legacy.cob",
            name="legacy.cob",
            directory="domain",
            extension=".cob",
            language="COBOL",
            support_level=LanguageSupportLevel.UNSUPPORTED,
            size_bytes=500,
            lines_total=50,
            lines_code=50,
            lines_comment=0,
            lines_blank=0,
        ),
        # 2. File with suspicious unresolved reference
        FileNode(
            id="domain/service.py",
            name="service.py",
            directory="domain",
            extension=".py",
            language="Python",
            support_level=LanguageSupportLevel.FULL_AST,
            size_bytes=200,
            lines_total=20,
            lines_code=20,
            lines_comment=0,
            lines_blank=0,
            unresolved_imports=[
                UnresolvedReference(
                    source_file="domain/service.py",
                    raw_import="infra.database",
                    line=3,
                    reason="unresolvable_path",
                )
            ],
        ),
    ]
    analysis = _create_mock_analysis(files, [])
    report = ContractEvaluator(contract).evaluate(analysis)

    assert len(report.unknowns) >= 2
    reasons = {u.reason for u in report.unknowns}
    assert "unsupported_language" in reasons
    assert "unresolvable_path" in reasons
    # Should not report passed falsely
    assert report.verdict == "WARNING"


def test_contract_init_and_loader_filesystem() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        # Init starter contract
        created_file = init_starter_contract(tmp_path)
        assert created_file.exists()
        assert created_file.name == "architecture.yml"

        # Discovered contract
        found = find_contract_file(tmp_path)
        assert found == created_file

        # Load file
        contract = load_contract_file(created_file)
        assert contract.version == 1
        assert len(contract.rules) >= 2

        # Overwrite protection
        with pytest.raises(FileExistsError):
            init_starter_contract(tmp_path, overwrite=False)
