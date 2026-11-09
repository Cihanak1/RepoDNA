"""Comprehensive unit and scenario tests for PR Architecture Guardian."""

from __future__ import annotations

from datetime import UTC, datetime

from repodna.contract.loader import load_contract_from_yaml
from repodna.guardian.engine import PRArchitectureGuardian
from repodna.guardian.models import GuardianVerdict, RiskLevel
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


def _build_analysis(
    files: list[FileNode],
    edges: list[DependencyEdge],
    cycles: list[CycleGroup] | None = None,
    overall_score: float = 90.0,
    ast_loc_cov: float = 100.0,
) -> AnalysisResult:
    cyc = cycles or []
    return AnalysisResult(
        analysis_id=f"snap_{len(files)}_{len(edges)}",
        repo_name="demo-repo",
        source_type=SourceType.LOCAL,
        target_display="./demo-repo",
        analyzed_at=datetime.now(UTC),
        duration_ms=50,
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
        cycles=cyc,
        graph_metrics=GraphMetrics(
            total_nodes=len(files),
            total_edges=len(edges),
            cycle_count=len(cyc),
        ),
        health_report=ArchitectureHealthReport(
            overall_score=overall_score,
            grade="A" if overall_score >= 90 else "B",
            status="evaluated",
            confidence="high",
            methodology="Standard",
        ),
        git_insights=GitInsights(is_git_repo=True),
        transparency=TransparencyReport(
            ast_loc_coverage_pct=ast_loc_cov,
            supported_languages_detected=["Python"],
        ),
    )


def _make_node(fid: str, fan_in: int = 0, fan_out: int = 0, is_hub: bool = False) -> FileNode:
    return FileNode(
        id=fid,
        name=fid.split("/")[-1],
        directory="/".join(fid.split("/")[:-1]),
        extension=".py",
        language="Python",
        support_level=LanguageSupportLevel.FULL_AST,
        size_bytes=100,
        lines_total=10,
        lines_code=10,
        lines_comment=0,
        lines_blank=0,
        fan_in=fan_in,
        fan_out=fan_out,
        is_hub=is_hub,
    )


def test_guardian_clean_pass() -> None:
    base_files = [_make_node("core/a.py"), _make_node("core/b.py")]
    base_edges = [DependencyEdge(id="e1", source="core/a.py", target="core/b.py")]
    base = _build_analysis(base_files, base_edges)

    # Head adds a harmless module core/c.py
    head_files = [_make_node("core/a.py"), _make_node("core/b.py"), _make_node("core/c.py")]
    head_edges = [
        DependencyEdge(id="e1", source="core/a.py", target="core/b.py"),
        DependencyEdge(id="e2", source="core/a.py", target="core/c.py"),
    ]
    head = _build_analysis(head_files, head_edges)

    guardian = PRArchitectureGuardian()
    report = guardian.assess(base, head, base_ref="main", head_ref="feat/c")

    assert report.verdict == GuardianVerdict.PASS
    assert report.risk_assessment.risk_level == RiskLevel.LOW
    assert len(report.new_cycles) == 0
    assert "clean" in report.verdict_reason.lower()
    assert "+1" in report.summary_markdown  # Added module


def test_guardian_fails_on_new_circular_dependency() -> None:
    base_files = [_make_node("core/a.py"), _make_node("core/b.py")]
    base_edges = [DependencyEdge(id="e1", source="core/a.py", target="core/b.py")]
    base = _build_analysis(base_files, base_edges)

    # Head creates a cycle: b -> a
    head_files = [_make_node("core/a.py"), _make_node("core/b.py")]
    head_edges = [
        DependencyEdge(id="e1", source="core/a.py", target="core/b.py"),
        DependencyEdge(id="e2", source="core/b.py", target="core/a.py"),
    ]
    head_cycles = [
        CycleGroup(
            id="CYC-001",
            nodes=["core/a.py", "core/b.py", "core/a.py"],
            length=2,
            severity=SeverityLevel.CRITICAL,
            description="Circular loop",
        )
    ]
    head = _build_analysis(head_files, head_edges, cycles=head_cycles, overall_score=75.0)

    guardian = PRArchitectureGuardian()
    report = guardian.assess(base, head)

    assert report.verdict == GuardianVerdict.FAIL
    assert len(report.new_cycles) == 1
    assert report.risk_assessment.risk_level in (RiskLevel.MODERATE, RiskLevel.HIGH)
    assert any("circular dependency" in f for f in report.risk_assessment.risk_factors)


def test_guardian_resolves_circular_dependency() -> None:
    # Base has cycle
    base_files = [_make_node("core/a.py"), _make_node("core/b.py")]
    base_edges = [
        DependencyEdge(id="e1", source="core/a.py", target="core/b.py"),
        DependencyEdge(id="e2", source="core/b.py", target="core/a.py"),
    ]
    base_cycles = [
        CycleGroup(
            id="CYC-001",
            nodes=["core/a.py", "core/b.py", "core/a.py"],
            length=2,
            severity=SeverityLevel.CRITICAL,
            description="Circular loop",
        )
    ]
    base = _build_analysis(base_files, base_edges, cycles=base_cycles, overall_score=75.0)

    # Head removes the reverse edge b -> a
    head_files = [_make_node("core/a.py"), _make_node("core/b.py")]
    head_edges = [DependencyEdge(id="e1", source="core/a.py", target="core/b.py")]
    head = _build_analysis(head_files, head_edges, cycles=[], overall_score=95.0)

    guardian = PRArchitectureGuardian()
    report = guardian.assess(base, head)

    assert report.verdict == GuardianVerdict.PASS
    assert len(report.new_cycles) == 0
    assert len(report.resolved_cycles) == 1
    assert "Resolved **1** circular dependency loop" in report.summary_markdown


def test_guardian_contract_evaluation_new_vs_baseline() -> None:
    contract_yaml = """
version: 1
policy:
  mode: enforce
rules:
  - id: DOMAIN-001
    title: Domain Isolation
    from: "domain/**"
    disallow_imports:
      - "infra/**"
    severity: error
"""
    contract = load_contract_from_yaml(contract_yaml)

    # Base already has one legacy violation: domain/old.py -> infra/db.py
    base_files = [
        _make_node("domain/old.py"),
        _make_node("domain/clean.py"),
        _make_node("infra/db.py"),
    ]
    base_edges = [
        DependencyEdge(id="e1", source="domain/old.py", target="infra/db.py"),
        DependencyEdge(id="e2", source="domain/clean.py", target="domain/old.py"),
    ]
    base = _build_analysis(base_files, base_edges)

    # Scenario 1: Head keeps old.py violation, but introduces NO new violations
    head_files = [
        _make_node("domain/old.py"),
        _make_node("domain/clean.py"),
        _make_node("domain/new_feature.py"),
        _make_node("infra/db.py"),
    ]
    head_edges = [
        DependencyEdge(id="e1", source="domain/old.py", target="infra/db.py"),
        DependencyEdge(id="e2", source="domain/clean.py", target="domain/old.py"),
        DependencyEdge(id="e3", source="domain/new_feature.py", target="domain/clean.py"),
    ]
    head = _build_analysis(head_files, head_edges)

    guardian = PRArchitectureGuardian(contract=contract)
    report = guardian.assess(base, head)

    # Invariant: PR does not fail on existing base violation!
    assert report.verdict == GuardianVerdict.PASS
    assert len(report.new_contract_violations) == 0
    assert len(report.existing_baseline_violations) == 1
    assert report.existing_baseline_violations[0].source_file == "domain/old.py"

    # Scenario 2: Head introduces a NEW violation: domain/new_feature.py -> infra/db.py
    head_bad_edges = list(head_edges) + [
        DependencyEdge(id="e4", source="domain/new_feature.py", target="infra/db.py")
    ]
    head_bad = _build_analysis(head_files, head_bad_edges)

    bad_report = guardian.assess(base, head_bad)
    # In enforce mode, new violation causes FAIL!
    assert bad_report.verdict == GuardianVerdict.FAIL
    assert len(bad_report.new_contract_violations) == 1
    assert bad_report.new_contract_violations[0].source_file == "domain/new_feature.py"
    assert len(bad_report.existing_baseline_violations) == 1


def test_guardian_inconclusive_on_coverage_collapse_or_empty() -> None:
    base_files = [_make_node(f"core/mod_{i}.py") for i in range(20)]
    base = _build_analysis(base_files, [], ast_loc_cov=90.0)

    # Head coverage collapsed to 10%
    head_files = [_make_node(f"core/mod_{i}.py") for i in range(20)]
    head = _build_analysis(head_files, [], ast_loc_cov=10.0)

    guardian = PRArchitectureGuardian()
    report = guardian.assess(base, head)

    assert report.verdict == GuardianVerdict.INCONCLUSIVE
    assert "coverage collapse" in report.verdict_reason.lower()
