"""Integration tests for RepoDNA Brain REST API endpoints (Search, Symbols, Evidence, Context, Passport v2)."""

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from repodna.api.app import _store_result, app
from repodna.schemas.models import (
    AnalysisResult,
    ArchitectureHealthReport,
    FileNode,
    GitInsights,
    GraphMetrics,
    LanguageBreakdownItem,
    LanguageSupportLevel,
    SourceType,
    SymbolItem,
    TransparencyReport,
)


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def registered_analysis() -> str:
    analysis_id = "test_brain_api_analysis"
    f1 = FileNode(
        id="backend/repodna/api/app.py",
        name="app.py",
        directory="backend/repodna/api",
        extension=".py",
        language="Python",
        support_level=LanguageSupportLevel.FULL_AST,
        size_bytes=2500,
        lines_total=100,
        lines_code=80,
        lines_comment=10,
        lines_blank=10,
        fan_in=3,
        fan_out=2,
        is_hub=True,
        symbols=[
            SymbolItem(name="FastAPIApp", kind="class", line=15),
            SymbolItem(name="search_repository_brain", kind="function", line=45),
        ],
    )
    f2 = FileNode(
        id="backend/repodna/brain/indexer.py",
        name="indexer.py",
        directory="backend/repodna/brain",
        extension=".py",
        language="Python",
        support_level=LanguageSupportLevel.FULL_AST,
        size_bytes=3800,
        lines_total=150,
        lines_code=120,
        lines_comment=15,
        lines_blank=15,
        fan_in=4,
        fan_out=1,
        symbols=[
            SymbolItem(name="SymbolIndexer", kind="class", line=10),
            SymbolItem(name="index_all", kind="function", line=30),
        ],
    )

    analysis = AnalysisResult(
        analysis_id=analysis_id,
        repo_name="RepoDNA",
        source_type=SourceType.LOCAL,
        target_display=".",
        analyzed_at=datetime.now(UTC),
        duration_ms=60,
        total_files=2,
        total_lines_code=200,
        total_lines_all=250,
        total_size_bytes=8000,
        languages=[
            LanguageBreakdownItem(
                language="Python",
                support_level=LanguageSupportLevel.FULL_AST,
                file_count=2,
                lines_code=200,
                lines_total=250,
                size_bytes=8000,
                percentage_of_code=100.0,
            )

        ],
        files=[f1, f2],
        edges=[],
        cycles=[],
        graph_metrics=GraphMetrics(total_nodes=2, total_edges=1, hub_files_count=1),

        health_report=ArchitectureHealthReport(
            overall_score=95.0,
            grade="A",
            status="evaluated",
            confidence="high",
            confidence_reason="100% AST coverage",
            methodology="Static AST graph analysis",
        ),

        git_insights=GitInsights(
            is_git_repo=True,
            default_branch="feat/v0.5-repository-brain",
            total_commits_scanned=20,
        ),

        transparency=TransparencyReport(
            ast_file_coverage_pct=100.0,
            ast_loc_coverage_pct=100.0,
            supported_languages_detected=["Python"],
        ),
    )
    _store_result(analysis)
    return analysis_id


def test_brain_search_endpoint(client: TestClient, registered_analysis: str) -> None:
    resp = client.post(
        f"/api/analyses/{registered_analysis}/brain/search",
        json={"query": "indexer", "limit": 5},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "matches" in data
    assert data["total_matches"] >= 1
    assert any("indexer" in m["file_id"] for m in data["matches"])


def test_brain_symbols_endpoint(client: TestClient, registered_analysis: str) -> None:
    resp = client.get(
        f"/api/analyses/{registered_analysis}/brain/symbols",
        params={"limit": 10},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_symbols"] >= 1
    assert len(data["symbols"]) >= 1


def test_brain_symbols_filter_by_name(client: TestClient, registered_analysis: str) -> None:
    resp = client.get(
        f"/api/analyses/{registered_analysis}/brain/symbols",
        params={"name": "SymbolIndexer"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert any(s["name"] == "SymbolIndexer" for s in data["symbols"])


def test_brain_symbol_trace_endpoint(client: TestClient, registered_analysis: str) -> None:
    # First get a symbol ID
    syms_resp = client.get(f"/api/analyses/{registered_analysis}/brain/symbols?limit=1")
    sym = syms_resp.json()["symbols"][0]
    sym_id = sym["id"]

    trace_resp = client.get(f"/api/analyses/{registered_analysis}/brain/symbols/{sym_id}/trace")
    assert trace_resp.status_code == 200
    data = trace_resp.json()
    assert data["symbol"]["id"] == sym_id
    assert "definition_evidence" in data


def test_brain_evidence_endpoints(client: TestClient, registered_analysis: str) -> None:
    # Query all evidence
    resp = client.get(f"/api/analyses/{registered_analysis}/brain/evidence?limit=10")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_evidence"] >= 1
    ev_item = data["evidence_items"][0]
    ev_id = ev_item["evidence_id"]

    # Query single evidence
    single_resp = client.get(f"/api/analyses/{registered_analysis}/brain/evidence/{ev_id}")
    assert single_resp.status_code == 200
    single_data = single_resp.json()
    assert single_data["evidence_id"] == ev_id
    assert "file_path" in single_data


def test_brain_context_endpoint(client: TestClient, registered_analysis: str) -> None:
    resp = client.post(
        f"/api/analyses/{registered_analysis}/brain/context",
        json={"mode": "focused", "query": "indexer", "max_tokens": 1000},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["mode"] == "focused"
    assert "summary" in data
    assert "estimated_tokens" in data
    assert "token_savings_pct" in data


def test_passport_v2_endpoint(client: TestClient, registered_analysis: str) -> None:
    resp = client.get(f"/api/analyses/{registered_analysis}/passport/v2")
    assert resp.status_code == 200
    data = resp.json()
    assert data["schema_version"] == "2.0.0"
    assert data["repo_name"] == "RepoDNA"
    assert "symbol_index_summary" in data


def test_passport_validate_and_migrate_endpoints(
    client: TestClient, registered_analysis: str
) -> None:
    # 1. Fetch v1 passport
    v1_resp = client.get(f"/api/analyses/{registered_analysis}/passport")
    assert v1_resp.status_code == 200
    v1_manifest = v1_resp.text

    # 2. Validate v1
    val_resp = client.post("/api/passport/validate", json={"manifest_json": v1_manifest})
    assert val_resp.status_code == 200
    assert val_resp.json()["valid"] is True
    assert val_resp.json()["schema_version"] == "1.0.0"

    # 3. Migrate v1 to v2
    mig_resp = client.post("/api/passport/migrate", json={"manifest_json": v1_manifest})
    assert mig_resp.status_code == 200
    v2_data = mig_resp.json()
    assert v2_data["schema_version"] == "2.0.0"

    # 4. Validate migrated v2
    import json
    val_v2_resp = client.post("/api/passport/validate", json={"manifest_json": json.dumps(v2_data)})
    assert val_v2_resp.status_code == 200
    assert val_v2_resp.json()["schema_version"] == "2.0.0"
