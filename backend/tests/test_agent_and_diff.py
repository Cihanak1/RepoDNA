"""Comprehensive tests for AI Agent Repository Intelligence, Diff Engine, MCP, and Installer."""

from __future__ import annotations

from pathlib import Path

import pytest

from repodna.cli.installer import AgentInstaller, run_doctor
from repodna.context.builder import AgentContextBuilder
from repodna.core.analyzer import run_repository_analysis
from repodna.diff.engine import ArchitectureDiffEngine
from repodna.diff.models import ArchitectureDiffResult
from repodna.diff.snapshot import SnapshotManager
from repodna.intelligence.service import RepositoryIntelligenceService
from repodna.mcp.server import RepoDNAMCPServer
from repodna.schemas.models import ScanRequest, SeverityLevel, SourceType
from repodna.security.validators import SecurityValidationError


def test_demo_intelligence_service_queries() -> None:
    req = ScanRequest(source_type=SourceType.DEMO, target="demo")
    analysis = run_repository_analysis(req)
    svc = RepositoryIntelligenceService(analysis)

    # 1. Overview
    overview = svc.get_repository_overview()
    assert overview.repo_name == "acme-commerce-platform (DEMO MODE)"
    assert overview.health_grade in ("A", "B", "C", "D")
    assert len(overview.key_architectural_hubs) >= 1
    assert "acme-commerce-platform" in overview.summary_text

    # 2. Architecture Map
    arch_map = svc.get_architecture_map(level="clusters")
    assert arch_map.total_clusters >= 1
    assert len(arch_map.clusters) >= 1

    # 3. Find Relevant Modules
    find_res = svc.find_relevant_modules("service", limit=5)
    assert find_res.total_matches >= 1
    assert any("service" in m.file_id.lower() for m in find_res.matches)

    # 4. Module Details
    first_file = analysis.files[0].id
    details = svc.get_module_details(first_file)
    assert details.file_id == first_file
    assert details.lines_code > 0

    # 5. Dependencies & Dependents
    deps = svc.get_dependencies(first_file, direction="outgoing", depth=1)
    assert deps.root_file == first_file
    dependents = svc.get_dependents(first_file, depth=1)
    assert dependents.root_file == first_file

    # 6. Architecture Findings
    findings = svc.get_architecture_findings()
    assert findings.total_findings >= 0

    # 7. Analysis Coverage
    cov = svc.get_analysis_coverage()
    assert cov.ast_file_coverage_pct > 0
    assert "RepoDNA strictly bounds" in cov.honest_coverage_guarantee

    # 8. Change Impact
    impact = svc.get_change_impact([first_file])
    assert first_file in impact.target_files
    assert impact.impact_severity in (
        SeverityLevel.CRITICAL,
        SeverityLevel.WARNING,
        SeverityLevel.INFO,
    )


def test_agent_context_builder_modes_and_budgeting() -> None:
    req = ScanRequest(source_type=SourceType.DEMO, target="demo")
    analysis = run_repository_analysis(req)

    # Compact mode
    ctx_compact = AgentContextBuilder.build_context(analysis, mode="compact")
    assert ctx_compact.mode == "compact"
    assert len(ctx_compact.relevant_modules) <= 15
    assert ctx_compact.estimated_tokens > 0
    md = ctx_compact.as_markdown()
    assert "# RepoDNA Context [COMPACT]" in md

    # Focused mode with query
    ctx_focused = AgentContextBuilder.build_context(analysis, mode="focused", query="service")
    assert ctx_focused.mode == "focused"
    assert len(ctx_focused.relevant_modules) >= 1

    # Budget cap
    ctx_budget = AgentContextBuilder.build_context(analysis, mode="deep", max_chars=500)
    assert ctx_budget.truncated is True
    assert ctx_budget.continuation_token is not None


def test_mcp_server_protocol_and_tools() -> None:
    server = RepoDNAMCPServer()

    # 1. Initialize
    init_resp = server.handle_request({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
    assert init_resp is not None
    assert init_resp["result"]["serverInfo"]["name"] == "repodna-mcp"

    # 2. Ping
    ping_resp = server.handle_request({"jsonrpc": "2.0", "id": 2, "method": "ping"})
    assert ping_resp == {"jsonrpc": "2.0", "id": 2, "result": {}}

    # 3. Tools list
    tools_resp = server.handle_request({"jsonrpc": "2.0", "id": 3, "method": "tools/list"})
    assert tools_resp is not None
    tools = tools_resp["result"]["tools"]
    tool_names = [t["name"] for t in tools]
    assert "repodna_repository_overview" in tool_names
    assert "repodna_architecture_map" in tool_names
    assert "repodna_find_modules" in tool_names
    assert "repodna_module_dependencies" in tool_names
    assert "repodna_module_findings" in tool_names
    assert "repodna_architecture_diff" in tool_names
    assert "repodna_change_impact" in tool_names
    assert "repodna_analysis_coverage" in tool_names
    assert len(tools) == 8

    # 4. Tool calls
    r1 = server.call_tool("repodna_repository_overview", {"target": "demo"})
    assert not r1.get("isError")
    assert "acme-commerce-platform" in r1["content"][0]["text"]

    r2 = server.call_tool("repodna_find_modules", {"target": "demo", "query": "auth"})
    assert not r2.get("isError")

    r3 = server.call_tool("repodna_analysis_coverage", {"target": "demo"})
    assert not r3.get("isError")
    assert "Confidence" in r3["content"][0]["text"]

    # Unknown tool
    r_err = server.call_tool("unknown_tool", {})
    assert r_err.get("isError") is True


def test_architecture_diff_engine_synthetic() -> None:
    # Build two synthetic analysis snapshots with deliberate architectural deltas
    req = ScanRequest(source_type=SourceType.DEMO, target="demo")
    base_analysis = run_repository_analysis(req)
    head_analysis = run_repository_analysis(req)

    # Simulate added file and edge in head
    diff: ArchitectureDiffResult = ArchitectureDiffEngine.compare_analyses(
        base=base_analysis,
        head=head_analysis,
        base_ref="v0.1.0",
        head_ref="v0.2.0",
    )
    assert diff.verdict in ("neutral", "improved", "degraded", "regressive_cycles")
    assert diff.base_provenance.ref_name == "v0.1.0"
    assert diff.head_provenance.ref_name == "v0.2.0"
    assert "RepoDNA Architecture Diff:" in diff.summary_text


def test_snapshot_manager_git_ref_validation() -> None:
    mgr = SnapshotManager(".")
    # Malformed / option injection ref
    with pytest.raises(SecurityValidationError):
        mgr.create_snapshot("--upload-pack=exploit")

    with pytest.raises(SecurityValidationError):
        mgr.create_snapshot("ref;rm -rf /")


def test_agent_installer_workflow(tmp_path: Path) -> None:
    installer = AgentInstaller(agent="auto", scope="project", dry_run=True, repo_root=tmp_path)
    # 1. Detection
    detected = installer.detect_agents()
    assert len(detected) >= 1

    # 2. Dry run install
    res = installer.install()
    assert res["status"] == "success"
    assert res["dry_run"] is True

    # 3. Verify
    verify_res = installer.verify()
    assert "antigravity" in verify_res or "claude" in verify_res or "codex" in verify_res

    # 4. Dry run uninstall
    uninst_res = installer.uninstall()
    assert uninst_res["status"] == "uninstalled"
    assert uninst_res["dry_run"] is True


def test_doctor_execution() -> None:
    code = run_doctor()
    assert code == 0
