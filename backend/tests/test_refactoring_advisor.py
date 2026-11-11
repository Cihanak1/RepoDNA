"""Unit and integration tests for RepoDNA Architecture Refactoring Advisor (v0.7.0).

Tests engine deterministic recommendations across all 4 categories, REST API endpoint,
MCP tool registration/dispatch, and CLI commands.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from repodna.advisor import (
    AdvisorCategory,
    RefactoringAdvisorEngine,
)
from repodna.api.app import _store_result, app
from repodna.cli.main import main
from repodna.mcp.server import RepoDNAMCPServer
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


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _make_sample_analysis(
    files: list[FileNode] | None = None,
    edges: list[DependencyEdge] | None = None,
    cycles: list[CycleGroup] | None = None,
    target: str = "demo-advisor",
    analysis_id: str = "test-analysis-id",
) -> AnalysisResult:
    if files is None:
        files = []
    if edges is None:
        edges = []
    if cycles is None:
        cycles = []

    return AnalysisResult(
        analysis_id=analysis_id,
        repo_name="demo-advisor",
        source_type=SourceType.DEMO,
        target_display=target,
        is_demo=True,
        analyzed_at=datetime.now(UTC),
        duration_ms=15,
        total_files=len(files),
        total_lines_code=sum(f.lines_code for f in files) or 100,
        total_lines_all=sum(f.lines_total for f in files) or 100,
        total_size_bytes=sum(f.size_bytes for f in files) or 1000,
        languages=[
            LanguageBreakdownItem(
                language="Python",
                support_level=LanguageSupportLevel.FULL_AST,
                file_count=len(files),
                lines_code=100,
                lines_total=100,
                size_bytes=1000,
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
        ),
        health_report=ArchitectureHealthReport(
            overall_score=75.0,
            grade="B",
            status="evaluated",
            confidence="high",
            methodology="Static AST graph analysis",
        ),
        git_insights=GitInsights(
            is_git_repo=True,
            commit_sha="abcd1234ef567890abcd1234ef567890abcd1234",
            default_branch="main",
            snapshot_identity="repo-snapshot-v1",
        ),
        transparency=TransparencyReport(
            ast_file_coverage_pct=100.0,
            ast_loc_coverage_pct=100.0,
            supported_languages_detected=["Python"],
        ),
    )


# -----------------------------------------------------------------------------
# 1. Engine Category Tests
# -----------------------------------------------------------------------------


def test_advisor_circular_dependency_reduction() -> None:
    f_a = FileNode(
        id="src/service_a.py",
        name="service_a.py",
        directory="src",
        extension=".py",
        language="Python",
        support_level=LanguageSupportLevel.FULL_AST,
        size_bytes=1200,
        lines_total=60,
        lines_code=50,
        lines_comment=5,
        lines_blank=5,
        fan_in=1,
        fan_out=1,
        is_hub=False,
    )
    f_b = FileNode(
        id="src/service_b.py",
        name="service_b.py",
        directory="src",
        extension=".py",
        language="Python",
        support_level=LanguageSupportLevel.FULL_AST,
        size_bytes=1500,
        lines_total=70,
        lines_code=60,
        lines_comment=5,
        lines_blank=5,
        fan_in=1,
        fan_out=1,
        is_hub=False,
    )
    e1 = DependencyEdge(id="e1", source="src/service_a.py", target="src/service_b.py", import_names=["HelperClass"])
    e2 = DependencyEdge(id="e2", source="src/service_b.py", target="src/service_a.py", import_names=["ProcessClass"])
    cycle = CycleGroup(
        id="cycle-1",
        nodes=["src/service_a.py", "src/service_b.py", "src/service_a.py"],
        length=2,
        severity=SeverityLevel.CRITICAL,
        description="Cycle between A and B",
    )

    analysis = _make_sample_analysis(files=[f_a, f_b], edges=[e1, e2], cycles=[cycle])
    engine = RefactoringAdvisorEngine(analysis=analysis)
    report = engine.generate_report()

    assert report.total_recommendations >= 1
    cycle_recs = [r for r in report.recommendations if r.category == AdvisorCategory.CIRCULAR_DEPENDENCY]
    assert len(cycle_recs) >= 1
    rec = cycle_recs[0]
    assert rec.severity == "critical"
    assert "Break circular dependency" in rec.title
    assert len(rec.suggested_action_steps) >= 3
    assert "expected_architectural_benefit" in rec.model_dump()
    assert rec.expected_architectural_benefit != ""
    assert rec.metric_delta_preview.get("cycle_reduction") == 1


def test_advisor_high_coupling_module_review() -> None:
    # Module with fan_out = 9, fan_in = 1 -> high efferent coupling, Instability ~ 0.9
    f_coupled = FileNode(
        id="src/orchestrator.py",
        name="orchestrator.py",
        directory="src",
        extension=".py",
        language="Python",
        support_level=LanguageSupportLevel.FULL_AST,
        size_bytes=3000,
        lines_total=150,
        lines_code=120,
        lines_comment=15,
        lines_blank=15,
        fan_in=1,
        fan_out=9,
        is_hub=False,
    )
    analysis = _make_sample_analysis(files=[f_coupled])
    engine = RefactoringAdvisorEngine(analysis=analysis)
    report = engine.generate_report()

    coupling_recs = [r for r in report.recommendations if r.category == AdvisorCategory.HIGH_COUPLING]
    assert len(coupling_recs) == 1
    rec = coupling_recs[0]
    assert rec.target_module == "src/orchestrator.py"
    assert "efferent coupling" in rec.title.lower()
    assert "Facade" in " ".join(rec.suggested_action_steps)


def test_advisor_layer_boundary_improvement() -> None:
    # Domain tier importing API/presentation tier
    f_domain = FileNode(
        id="backend/domain/model.py",
        name="model.py",
        directory="backend/domain",
        extension=".py",
        language="Python",
        support_level=LanguageSupportLevel.FULL_AST,
        size_bytes=2000,
        lines_total=80,
        lines_code=70,
        lines_comment=5,
        lines_blank=5,
        fan_in=2,
        fan_out=1,
        is_hub=False,
    )
    f_api = FileNode(
        id="backend/api/routes.py",
        name="routes.py",
        directory="backend/api",
        extension=".py",
        language="Python",
        support_level=LanguageSupportLevel.FULL_AST,
        size_bytes=2000,
        lines_total=80,
        lines_code=70,
        lines_comment=5,
        lines_blank=5,
        fan_in=1,
        fan_out=2,
        is_hub=False,
    )
    edge = DependencyEdge(
        id="e_layer",
        source="backend/domain/model.py",
        target="backend/api/routes.py",
        import_names=["APIRouter"],
    )

    analysis = _make_sample_analysis(files=[f_domain, f_api], edges=[edge])
    engine = RefactoringAdvisorEngine(analysis=analysis)
    report = engine.generate_report()

    layer_recs = [r for r in report.recommendations if r.category == AdvisorCategory.LAYER_BOUNDARY]
    assert len(layer_recs) >= 1
    rec = layer_recs[0]
    assert rec.target_module == "backend/domain/model.py"
    assert "layer boundary inversion" in rec.title.lower()
    assert "backend/api/routes.py" in rec.affected_modules


def test_advisor_oversized_hub_review() -> None:
    f_hub = FileNode(
        id="backend/core/giant_hub.py",
        name="giant_hub.py",
        directory="backend/core",
        extension=".py",
        language="Python",
        support_level=LanguageSupportLevel.FULL_AST,
        size_bytes=10000,
        lines_total=450,
        lines_code=380,
        lines_comment=40,
        lines_blank=30,
        fan_in=9,
        fan_out=8,
        is_hub=True,
    )
    analysis = _make_sample_analysis(files=[f_hub])
    engine = RefactoringAdvisorEngine(analysis=analysis)
    report = engine.generate_report()

    hub_recs = [r for r in report.recommendations if r.category == AdvisorCategory.OVERSIZED_HUB]
    assert len(hub_recs) >= 1
    rec = hub_recs[0]
    assert rec.target_module == "backend/core/giant_hub.py"
    assert "Decompose oversized architectural hub" in rec.title
    assert rec.severity in ("critical", "high")


def test_advisor_filtering_and_sorting() -> None:
    f_hub = FileNode(
        id="backend/core/hub.py",
        name="hub.py",
        directory="backend/core",
        extension=".py",
        language="Python",
        support_level=LanguageSupportLevel.FULL_AST,
        size_bytes=5000,
        lines_total=350,
        lines_code=300,
        lines_comment=25,
        lines_blank=25,
        fan_in=8,
        fan_out=8,
        is_hub=True,
    )
    f_coupled = FileNode(
        id="src/coupled.py",
        name="coupled.py",
        directory="src",
        extension=".py",
        language="Python",
        support_level=LanguageSupportLevel.FULL_AST,
        size_bytes=2000,
        lines_total=100,
        lines_code=80,
        lines_comment=10,
        lines_blank=10,
        fan_in=1,
        fan_out=8,
        is_hub=False,
    )
    analysis = _make_sample_analysis(files=[f_hub, f_coupled])
    engine = RefactoringAdvisorEngine(analysis=analysis)

    # Category filter
    rep_hub_only = engine.generate_report(category_filter=AdvisorCategory.OVERSIZED_HUB)
    assert all(r.category == AdvisorCategory.OVERSIZED_HUB for r in rep_hub_only.recommendations)

    # Severity filter
    rep_crit = engine.generate_report(min_severity="critical")
    assert all(r.severity == "critical" for r in rep_crit.recommendations)


# -----------------------------------------------------------------------------
# 2. REST API Endpoint Tests
# -----------------------------------------------------------------------------


def test_advisor_rest_api_endpoint(client: TestClient) -> None:
    f1 = FileNode(
        id="api_test/module.py",
        name="module.py",
        directory="api_test",
        extension=".py",
        language="Python",
        support_level=LanguageSupportLevel.FULL_AST,
        size_bytes=2000,
        lines_total=100,
        lines_code=90,
        lines_comment=5,
        lines_blank=5,
        fan_in=1,
        fan_out=8,
        is_hub=False,
    )
    analysis_id = "test-advisor-analysis-id"
    analysis = _make_sample_analysis(files=[f1], target="api-test-repo", analysis_id=analysis_id)
    _store_result(analysis)

    # Happy path
    resp = client.get(f"/api/analyses/{analysis_id}/advisor")
    assert resp.status_code == 200
    data = resp.json()
    assert data["schema_version"] == "1.0.0"
    assert "total_recommendations" in data
    assert "recommendations" in data
    assert "summary_text" in data

    # Category filter query param
    resp_filtered = client.get(f"/api/analyses/{analysis_id}/advisor?category=high_coupling_module_review")
    assert resp_filtered.status_code == 200
    data_filtered = resp_filtered.json()
    for rec in data_filtered["recommendations"]:
        assert rec["category"] == "high_coupling_module_review"

    # Invalid category 400
    resp_invalid_cat = client.get(f"/api/analyses/{analysis_id}/advisor?category=non_existent_category")
    assert resp_invalid_cat.status_code == 400
    assert resp_invalid_cat.json()["detail"]["code"] == "INVALID_ADVISOR_CATEGORY"

    # Invalid min_severity 400
    resp_invalid_sev = client.get(f"/api/analyses/{analysis_id}/advisor?min_severity=super_critical")
    assert resp_invalid_sev.status_code == 400
    assert resp_invalid_sev.json()["detail"]["code"] == "INVALID_MIN_SEVERITY"

    # Non-existent analysis 404
    resp_404 = client.get("/api/analyses/unknown-analysis-9999/advisor")
    assert resp_404.status_code == 404


# -----------------------------------------------------------------------------
# 3. MCP Tool Tests
# -----------------------------------------------------------------------------


def test_advisor_mcp_tool_dispatch() -> None:
    server = RepoDNAMCPServer()
    # Test tool schema registration
    tools = server.get_tools_list()
    tool_names = [t["name"] for t in tools]
    assert "repodna_refactoring_advisor" in tool_names
    assert len(tool_names) == 23

    # Dispatch to demo target
    res = server.call_tool(
        "repodna_refactoring_advisor",
        {"target": "demo", "format": "json"},
    )
    assert not res.get("isError", False)
    content = json.loads(res["content"][0]["text"])
    assert "schema_version" in content
    assert "recommendations" in content

    # Test format="text"
    res_text = server.call_tool(
        "repodna_refactoring_advisor",
        {"target": "demo", "format": "text"},
    )
    assert not res_text.get("isError", False)
    text_content = res_text["content"][0]["text"]
    assert "Refactoring Advisor" in text_content or "Refactoring Advisory" in text_content


# -----------------------------------------------------------------------------
# 4. CLI Command Tests
# -----------------------------------------------------------------------------


def test_advisor_cli_commands(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    # Table format
    rc = main(["advisor", "demo", "--format", "table"])
    assert rc == 0
    captured = capsys.readouterr()
    assert "RepoDNA Architecture Refactoring Advisor" in captured.out

    # JSON format
    rc_json = main(["advisor", "demo", "--format", "json"])
    assert rc_json == 0
    captured_json = capsys.readouterr()
    parsed = json.loads(captured_json.out)
    assert parsed["schema_version"] == "1.0.0"

    # Markdown format with file output
    out_file = tmp_path / "advisor_report.md"
    rc_md = main(["advisor", "demo", "--format", "markdown", "--output", str(out_file)])
    assert rc_md == 0
    assert out_file.exists()
    content = out_file.read_text(encoding="utf-8")
    assert "# RepoDNA Refactoring Advisor" in content
