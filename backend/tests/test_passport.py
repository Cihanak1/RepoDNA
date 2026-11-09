"""Unit and validation tests for RepoDNA Repository Passport."""

from __future__ import annotations

import tempfile
from datetime import UTC, datetime
from pathlib import Path

import pytest

from repodna.contract.loader import load_contract_from_yaml
from repodna.passport.generator import (
    export_passport_to_json,
    export_passport_to_markdown,
    generate_repository_passport,
)
from repodna.passport.models import PASSPORT_SCHEMA_VERSION, RepositoryPassport
from repodna.passport.validator import (
    validate_passport_file,
    validate_passport_json,
)
from repodna.schemas.models import (
    AnalysisResult,
    ArchitectureHealthReport,
    CycleGroup,
    DependencyEdge,
    FileNode,
    GitInsights,
    GraphMetrics,
    LanguageBreakdownItem,
    LanguageSupportLevel,
    SeverityLevel,
    SourceType,
    TransparencyReport,
)
from repodna.security.validators import SecurityValidationError


def _make_dummy_analysis(num_files: int = 10) -> AnalysisResult:
    files = [
        FileNode(
            id=f"src/module_{i}.py",
            name=f"module_{i}.py",
            directory="src",
            extension=".py",
            language="Python",
            support_level=LanguageSupportLevel.FULL_AST,
            size_bytes=100 + i * 10,
            lines_total=20 + i,
            lines_code=15 + i,
            lines_comment=2,
            lines_blank=3,
            fan_in=i if i % 3 == 0 else 1,
            fan_out=2,
            instability=0.35,
            is_hub=(i == 9),
        )
        for i in range(num_files)
    ]
    edges = [
        DependencyEdge(id="e1", source="src/module_1.py", target="src/module_9.py"),
        DependencyEdge(id="e2", source="src/module_2.py", target="src/module_9.py"),
    ]
    cycles = [
        CycleGroup(
            id="CYC-1",
            nodes=["src/module_1.py", "src/module_2.py", "src/module_1.py"],
            length=2,
            severity=SeverityLevel.CRITICAL,
            description="Cycle between 1 and 2",
        )
    ]
    return AnalysisResult(
        analysis_id="snap_passport",
        repo_name="passport-test-repo",
        source_type=SourceType.LOCAL,
        target_display="./passport-test-repo",
        analyzed_at=datetime.now(UTC),
        duration_ms=45,
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
        cycles=cycles,
        graph_metrics=GraphMetrics(
            total_nodes=len(files),
            total_edges=len(edges),
            cycle_count=len(cycles),
            hub_files_count=1,
            average_instability=0.35,
        ),
        health_report=ArchitectureHealthReport(
            overall_score=88.5,
            grade="B",
            status="evaluated",
            confidence="high",
            confidence_reason="100% full AST python coverage",
            methodology="Standard",
        ),
        git_insights=GitInsights(is_git_repo=True),
        transparency=TransparencyReport(
            ast_loc_coverage_pct=100.0,
            ast_file_coverage_pct=100.0,
            supported_languages_detected=["Python"],
        ),
    )


def test_passport_generation_and_validation() -> None:
    analysis = _make_dummy_analysis(num_files=15)
    passport = generate_repository_passport(analysis, git_revision="abc1234", max_modules=10)

    assert passport.schema_version == PASSPORT_SCHEMA_VERSION
    assert passport.repo_name == "passport-test-repo"
    assert passport.git_revision == "abc1234"
    assert passport.repodna_version == "0.4.0"
    assert passport.confidence == "high"
    assert passport.architecture_health.score == 88.5

    # Check hubs
    assert len(passport.architectural_hubs) >= 1
    assert passport.architectural_hubs[0].file_id == "src/module_9.py"

    # Check truncation
    assert passport.truncation_metadata.is_truncated is True
    assert passport.truncation_metadata.total_inventory_count == 15
    assert passport.truncation_metadata.returned_inventory_count == 10
    assert len(passport.module_inventory) == 10

    # Serialization roundtrip
    json_output = export_passport_to_json(passport)
    validated = validate_passport_json(json_output)
    assert validated.repo_name == passport.repo_name
    assert validated.git_revision == "abc1234"


def test_passport_markdown_export() -> None:
    analysis = _make_dummy_analysis(num_files=5)
    passport = generate_repository_passport(analysis, git_revision="HEAD")
    md = export_passport_to_markdown(passport)

    assert "# RepoDNA Repository Passport — `passport-test-repo`" in md
    assert "Architectural Vitals" in md
    assert "88.5/100 (B)" in md
    assert "Primary Languages" in md
    assert "Architectural Hubs" in md


def test_passport_with_contract_status() -> None:
    contract_yaml = """
version: 1
policy:
  mode: enforce
rules:
  - id: LAYER-001
    title: Clean
    from: "src/**"
    disallow_imports:
      - "forbidden/**"
"""
    contract = load_contract_from_yaml(contract_yaml)
    analysis = _make_dummy_analysis(num_files=5)
    passport = generate_repository_passport(analysis, contract=contract)

    assert passport.contract_status.has_contract is True
    assert passport.contract_status.rules_count == 1
    assert passport.contract_status.is_compliant is True
    assert passport.contract_status.active_violations_count == 0


def test_passport_validation_errors_and_security() -> None:
    # Unsupported version
    bad_version_json = '{"schema_version": "9.9.9", "repo_name": "x"}'
    with pytest.raises(ValueError, match="Unsupported passport schema version"):
        validate_passport_json(bad_version_json)

    # Malformed JSON
    with pytest.raises(ValueError, match="Invalid JSON format"):
        validate_passport_json("{invalid: json}")

    # Exceeding size limit
    huge_json = '{"schema_version": "1.0.0", "blob": "' + ("A" * 2_500_000) + '"}'
    with pytest.raises(SecurityValidationError, match="Passport manifest size exceeds limit"):
        validate_passport_json(huge_json)


def test_passport_file_validation_disk() -> None:
    analysis = _make_dummy_analysis(num_files=3)
    passport = generate_repository_passport(analysis, git_revision="test-sha")

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_file = Path(tmp_dir) / "passport.json"
        tmp_file.write_text(export_passport_to_json(passport), encoding="utf-8")

        loaded = validate_passport_file(tmp_file)
        assert isinstance(loaded, RepositoryPassport)
        assert loaded.git_revision == "test-sha"
