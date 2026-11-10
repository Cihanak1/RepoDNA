"""Unit tests for RepoDNA Repository Passport v2 schema, generation, validation, and migration."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from repodna.brain.indexer import SymbolIndexer
from repodna.passport.generator import (
    export_passport_to_json,
    export_passport_to_markdown,
    generate_repository_passport,
    generate_repository_passport_v2,
)
from repodna.passport.migrator import migrate_v1_to_v2
from repodna.passport.models import (
    PASSPORT_SCHEMA_VERSION_V1,
    PASSPORT_SCHEMA_VERSION_V2,
    RepositoryPassport,
    RepositoryPassportV2,
)
from repodna.passport.validator import check_passport_privacy, validate_passport_json
from repodna.schemas.models import (
    AnalysisResult,
    ArchitectureHealthReport,
    FileNode,
    GitInsights,
    GraphMetrics,
    LanguageBreakdownItem,
    LanguageSupportLevel,
    SourceType,
    TransparencyReport,
)


@pytest.fixture
def sample_analysis() -> AnalysisResult:
    f1 = FileNode(
        id="repodna/api/app.py",
        name="app.py",
        directory="repodna/api",
        extension=".py",
        language="Python",
        support_level=LanguageSupportLevel.FULL_AST,
        size_bytes=2400,
        lines_total=120,
        lines_code=100,
        lines_comment=10,
        lines_blank=10,
        fan_in=5,
        fan_out=2,
        instability=0.28,
        is_hub=True,
    )
    f2 = FileNode(
        id="repodna/core/analyzer.py",
        name="analyzer.py",
        directory="repodna/core",
        extension=".py",
        language="Python",
        support_level=LanguageSupportLevel.FULL_AST,
        size_bytes=4200,
        lines_total=200,
        lines_code=180,
        lines_comment=10,
        lines_blank=10,
        fan_in=8,
        fan_out=1,
        instability=0.11,
        is_hub=True,
    )
    f3 = FileNode(
        id="repodna/cli/main.py",
        name="main.py",
        directory="repodna/cli",
        extension=".py",
        language="Python",
        support_level=LanguageSupportLevel.FULL_AST,
        size_bytes=1600,
        lines_total=80,
        lines_code=70,
        lines_comment=5,
        lines_blank=5,
        fan_in=1,
        fan_out=4,
        instability=0.8,
    )

    return AnalysisResult(
        analysis_id="test_analysis_p2",
        repo_name="RepoDNA-Test",
        source_type=SourceType.LOCAL,
        target_display="./RepoDNA-Test",
        analyzed_at=datetime.now(UTC),
        duration_ms=45,
        total_files=3,
        total_lines_code=350,
        total_lines_all=400,
        total_size_bytes=12000,
        languages=[
            LanguageBreakdownItem(
                language="Python",
                support_level=LanguageSupportLevel.FULL_AST,
                file_count=3,
                lines_code=350,
                lines_total=400,
                size_bytes=12000,
                percentage_of_code=100.0,
            )

        ],
        files=[f1, f2, f3],
        edges=[],
        cycles=[],
        graph_metrics=GraphMetrics(
            total_nodes=3,
            total_edges=2,
            graph_density=0.1,
            hub_files_count=2,
        ),

        health_report=ArchitectureHealthReport(
            overall_score=94.5,
            grade="A",
            status="evaluated",
            confidence="high",
            confidence_reason="100% Python AST coverage",
            methodology="Static AST graph analysis",
        ),

        git_insights=GitInsights(
            is_git_repo=True,
            default_branch="main",
            total_commits_scanned=12,
        ),

        transparency=TransparencyReport(
            ast_file_coverage_pct=100.0,
            ast_loc_coverage_pct=100.0,
            supported_languages_detected=["Python"],
        ),
    )


def test_passport_v1_and_v2_generation(sample_analysis: AnalysisResult) -> None:
    p1 = generate_repository_passport(sample_analysis, git_revision="81fa9b7")
    assert isinstance(p1, RepositoryPassport)
    assert p1.schema_version == PASSPORT_SCHEMA_VERSION_V1
    assert p1.repo_name == "RepoDNA-Test"
    assert len(p1.architectural_hubs) == 2

    p2 = generate_repository_passport_v2(sample_analysis, git_revision="81fa9b7")
    assert isinstance(p2, RepositoryPassportV2)
    assert p2.schema_version == PASSPORT_SCHEMA_VERSION_V2
    assert p2.repo_name == "RepoDNA-Test"
    assert p2.source_revision == "81fa9b7"
    assert len(p2.architectural_entrypoints) >= 1
    assert len(p2.major_module_roles) >= 1
    assert p2.retrieval_capabilities is not None
    assert p2.retrieval_capabilities.supports_semantic_search is True


def test_passport_v2_with_indexer(sample_analysis: AnalysisResult, tmp_path: Path) -> None:
    # Create simple python source files in tmp_path
    f1_path = tmp_path / "repodna" / "api"
    f1_path.mkdir(parents=True, exist_ok=True)
    (f1_path / "app.py").write_text("class FastApp:\n    def start(self):\n        pass\n")

    indexer = SymbolIndexer(root_path=tmp_path, revision="81fa9b7", analysis=sample_analysis)
    indexer.index_all()

    p2 = generate_repository_passport_v2(sample_analysis, git_revision="81fa9b7", indexer=indexer)
    assert p2.symbol_index_summary is not None
    assert p2.symbol_index_summary.total_symbols >= 1
    assert "Python" in p2.symbol_index_summary.language_counts
    assert p2.evidence_ledger_summary is not None
    assert p2.evidence_ledger_summary.total_evidence >= 1


def test_passport_validation_both_versions(sample_analysis: AnalysisResult) -> None:
    p1 = generate_repository_passport(sample_analysis, git_revision="81fa9b7")
    p1_json = export_passport_to_json(p1)
    validated_1 = validate_passport_json(p1_json)
    assert validated_1.schema_version == "1.0.0"

    p2 = generate_repository_passport_v2(sample_analysis, git_revision="81fa9b7")
    p2_json = export_passport_to_json(p2)
    validated_2 = validate_passport_json(p2_json)
    assert validated_2.schema_version == "2.0.0"


def test_passport_migration_v1_to_v2(sample_analysis: AnalysisResult) -> None:
    p1 = generate_repository_passport(sample_analysis, git_revision="81fa9b7")
    p2 = migrate_v1_to_v2(p1)
    assert isinstance(p2, RepositoryPassportV2)
    assert p2.schema_version == "2.0.0"
    assert p2.repo_name == p1.repo_name
    assert p2.git_revision == p1.git_revision
    assert len(p2.architectural_entrypoints) >= 1
    assert p2.retrieval_capabilities is not None


def test_passport_v2_privacy_guardrails(sample_analysis: AnalysisResult) -> None:
    p2 = generate_repository_passport_v2(sample_analysis, git_revision="81fa9b7")
    leaks = check_passport_privacy(p2)
    assert leaks == []

    # Injecting host leak into major_module_roles
    p2.major_module_roles.append(
        type(p2.major_module_roles[0])(
            file_path="C:/Users/cihan/Desktop/Secret/secret.py",
            role="secret",
            responsibility="Leaked private file",
        )
    )
    leaks_after = check_passport_privacy(p2)
    assert len(leaks_after) >= 1
    assert "Absolute host path in major_module_roles" in leaks_after[0]


def test_passport_v2_markdown_export(sample_analysis: AnalysisResult) -> None:
    p2 = generate_repository_passport_v2(sample_analysis, git_revision="81fa9b7")
    md = export_passport_to_markdown(p2)
    assert "# RepoDNA Repository Passport" in md
    assert "## Architectural Entrypoints" in md
    assert "## Major Module Roles" in md
