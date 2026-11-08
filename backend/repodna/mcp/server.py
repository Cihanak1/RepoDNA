"""Official Model Context Protocol (MCP) server for RepoDNA repository intelligence.

Supports the 2024-11-05/2026 standard via the official Python SDK v2 (mcp>=2.0.0),
providing stdio transport, strict stdout cleanliness, and read-only tools.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from repodna.core.analyzer import run_repository_analysis
from repodna.diff.engine import ArchitectureDiffEngine
from repodna.diff.snapshot import SnapshotManager
from repodna.intelligence.service import RepositoryIntelligenceService
from repodna.schemas.models import AnalysisResult, ScanLimits, ScanRequest, SourceType
from repodna.security.validators import SecurityValidationError, validate_local_directory

try:
    from mcp.server.mcpserver import MCPServer
    HAS_OFFICIAL_MCP = True
except ImportError:
    HAS_OFFICIAL_MCP = False
    MCPServer = None  # type: ignore

try:
    import importlib.metadata
    MCP_SDK_VERSION = importlib.metadata.version("mcp")
except Exception:
    MCP_SDK_VERSION = "unknown"

PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "repodna-mcp"
SERVER_VERSION = "0.3.0"


def _log(msg: str) -> None:
    """Logs diagnostics strictly to stderr to prevent stdout JSON-RPC corruption."""
    sys.stderr.write(f"[repodna-mcp] {msg}\n")
    sys.stderr.flush()


class RepoDNAMCPServer:
    """Dual-engine Model Context Protocol server (Official SDK v2 + Stdio fallback)."""

    def __init__(self, allowed_roots: list[Path] | None = None) -> None:
        self.allowed_roots = allowed_roots or []
        self._analysis_cache: dict[str, tuple[float, AnalysisResult]] = {}
        self._official_server: Any = None
        if HAS_OFFICIAL_MCP and MCPServer is not None:
            self._setup_official_server()

    def _resolve_target(self, target: str) -> tuple[Path | str, SourceType]:
        cleaned = target.strip()
        if cleaned.lower() == "demo":
            return "demo", SourceType.DEMO
        resolved = validate_local_directory(cleaned)
        if self.allowed_roots:
            is_allowed = any(
                resolved == root or root in resolved.parents for root in self.allowed_roots
            )
            if not is_allowed:
                raise SecurityValidationError(
                    "ROOT_VIOLATION", f"Access to path '{resolved}' outside authorized roots."
                )
        return resolved, SourceType.LOCAL

    def get_analysis(self, target: str) -> AnalysisResult:
        resolved, stype = self._resolve_target(target)
        cache_key = str(resolved)

        if stype == SourceType.LOCAL and isinstance(resolved, Path):
            mtime = resolved.stat().st_mtime
            if cache_key in self._analysis_cache:
                cached_mtime, cached_res = self._analysis_cache[cache_key]
                if mtime <= cached_mtime:
                    return cached_res

        req = ScanRequest(
            source_type=stype,
            target=str(resolved),
            limits=ScanLimits(max_files=2500, timeout_seconds=60.0),
        )
        res = run_repository_analysis(req)
        curr_mtime = resolved.stat().st_mtime if isinstance(resolved, Path) else 0.0
        self._analysis_cache[cache_key] = (curr_mtime, res)
        return res

    def tool_repository_overview(self, target: str, format: str = "text") -> str:
        analysis = self.get_analysis(target)
        svc = RepositoryIntelligenceService(analysis)
        ov = svc.get_repository_overview()
        return ov.model_dump_json(indent=2) if format == "json" else ov.summary_text

    def tool_architecture_map(self, target: str, level: str = "clusters", limit: int = 30) -> str:
        analysis = self.get_analysis(target)
        svc = RepositoryIntelligenceService(analysis)
        am = svc.get_architecture_map(level=level, limit=limit)
        return am.model_dump_json(indent=2)

    def tool_find_modules(self, target: str, query: str, limit: int = 10) -> str:
        analysis = self.get_analysis(target)
        svc = RepositoryIntelligenceService(analysis)
        res = svc.find_relevant_modules(query=query, limit=limit)
        return res.model_dump_json(indent=2)

    def tool_module_dependencies(
        self, target: str, file_path: str, direction: str = "outgoing", depth: int = 1
    ) -> str:
        analysis = self.get_analysis(target)
        svc = RepositoryIntelligenceService(analysis)
        deps = svc.get_dependencies(file_path=file_path, direction=direction, depth=depth)
        return deps.model_dump_json(indent=2)

    def tool_module_findings(
        self,
        target: str,
        file_path: str | None = None,
        rule_id: str | None = None,
        severity: str | None = None,
    ) -> str:
        analysis = self.get_analysis(target)
        svc = RepositoryIntelligenceService(analysis)
        if file_path:
            dtls = svc.get_module_details(file_path)
            return dtls.model_dump_json(indent=2)
        findings = svc.get_architecture_findings(rule_id=rule_id, severity=severity)
        return findings.model_dump_json(indent=2)

    def tool_architecture_diff(
        self, target: str, base_ref: str = "HEAD~1", head_ref: str = "HEAD"
    ) -> str:
        resolved, _ = self._resolve_target(target)
        snap_mgr = SnapshotManager(resolved)
        base_analysis, base_sha, base_is_wt = snap_mgr.create_snapshot(base_ref)
        head_analysis, head_sha, head_is_wt = snap_mgr.create_snapshot(head_ref)
        git_renames = snap_mgr.find_git_renames(base_ref, head_ref)

        diff = ArchitectureDiffEngine.compare_analyses(
            base=base_analysis,
            head=head_analysis,
            base_ref=base_ref,
            head_ref=head_ref,
            base_commit_sha=base_sha,
            head_commit_sha=head_sha,
            base_is_working_tree=base_is_wt,
            head_is_working_tree=head_is_wt,
            git_renames=git_renames,
        )
        return diff.model_dump_json(indent=2)

    def tool_change_impact(
        self, target: str, changed_files: list[str], max_depth: int = 2
    ) -> str:
        analysis = self.get_analysis(target)
        svc = RepositoryIntelligenceService(analysis)
        impact = svc.get_change_impact(changed_files=changed_files, max_depth=max_depth)
        return impact.model_dump_json(indent=2)

    def tool_analysis_coverage(self, target: str) -> str:
        analysis = self.get_analysis(target)
        svc = RepositoryIntelligenceService(analysis)
        cov = svc.get_analysis_coverage()
        return cov.model_dump_json(indent=2)

    def _setup_official_server(self) -> None:
        """Configures official MCPServer v2 with typed tool registrations."""
        server = MCPServer(SERVER_NAME)

        @server.tool(
            name="repodna_repository_overview",
            description="Returns executive architecture scorecard, health grade, AST coverage, and key hubs.",
        )
        def overview(target: str, format: str = "text") -> str:
            return self.tool_repository_overview(target=target, format=format)

        @server.tool(
            name="repodna_architecture_map",
            description="Returns package clusters, module counts, and inter-cluster dependency links.",
        )
        def arch_map(target: str, level: str = "clusters", limit: int = 30) -> str:
            return self.tool_architecture_map(target=target, level=level, limit=limit)

        @server.tool(
            name="repodna_find_modules",
            description="Finds repository modules matching a search query by filename, symbols, or hub status.",
        )
        def find_mods(target: str, query: str, limit: int = 10) -> str:
            return self.tool_find_modules(target=target, query=query, limit=limit)

        @server.tool(
            name="repodna_module_dependencies",
            description="Traces direct or transitive incoming/outgoing dependencies for a specific module.",
        )
        def mod_deps(
            target: str, file_path: str, direction: str = "outgoing", depth: int = 1
        ) -> str:
            return self.tool_module_dependencies(
                target=target, file_path=file_path, direction=direction, depth=depth
            )

        @server.tool(
            name="repodna_module_findings",
            description="Lists architectural rule findings (circular dependencies, coupling hotspots) filtered by module or rule.",
        )
        def mod_findings(
            target: str,
            file_path: str | None = None,
            rule_id: str | None = None,
            severity: str | None = None,
        ) -> str:
            return self.tool_module_findings(
                target=target, file_path=file_path, rule_id=rule_id, severity=severity
            )

        @server.tool(
            name="repodna_architecture_diff",
            description="Compares two Git revisions or working tree against a revision for architectural changes.",
        )
        def arch_diff(target: str, base_ref: str = "HEAD~1", head_ref: str = "HEAD") -> str:
            return self.tool_architecture_diff(target=target, base_ref=base_ref, head_ref=head_ref)

        @server.tool(
            name="repodna_change_impact",
            description="Evaluates architectural risk and direct/transitive blast radius of proposed file edits.",
        )
        def change_imp(target: str, changed_files: list[str], max_depth: int = 2) -> str:
            return self.tool_change_impact(
                target=target, changed_files=changed_files, max_depth=max_depth
            )

        @server.tool(
            name="repodna_analysis_coverage",
            description="Returns full AST vs partial static language coverage, unverified rules, and honesty guarantees.",
        )
        def coverage(target: str) -> str:
            return self.tool_analysis_coverage(target=target)

        self._official_server = server

    def get_tools_list(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "repodna_repository_overview",
                "description": "Returns executive architecture scorecard, health grade, AST coverage, and key hubs for a repository.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "target": {"type": "string", "description": "Local filesystem path or 'demo'."},
                        "format": {"type": "string", "enum": ["text", "json"], "default": "text"},
                    },
                    "required": ["target"],
                },
            },
            {
                "name": "repodna_architecture_map",
                "description": "Returns package clusters, module counts, and inter-cluster dependency links.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "target": {"type": "string", "description": "Local path or 'demo'."},
                        "level": {"type": "string", "enum": ["overview", "clusters", "full"], "default": "clusters"},
                        "limit": {"type": "integer", "default": 30},
                    },
                    "required": ["target"],
                },
            },
            {
                "name": "repodna_find_modules",
                "description": "Finds repository modules matching a search query by filename, symbols, or architectural hub status.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "target": {"type": "string", "description": "Local path or 'demo'."},
                        "query": {"type": "string", "description": "Search keyword, symbol name, or path substring."},
                        "limit": {"type": "integer", "default": 10},
                    },
                    "required": ["target", "query"],
                },
            },
            {
                "name": "repodna_module_dependencies",
                "description": "Traces direct or transitive incoming/outgoing dependencies for a specific module.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "target": {"type": "string", "description": "Local path or 'demo'."},
                        "file_path": {"type": "string", "description": "Relative file path within repository."},
                        "direction": {"type": "string", "enum": ["outgoing", "incoming", "both"], "default": "outgoing"},
                        "depth": {"type": "integer", "default": 1},
                    },
                    "required": ["target", "file_path"],
                },
            },
            {
                "name": "repodna_module_findings",
                "description": "Lists architectural rule findings (circular dependencies, coupling hotspots) filtered by module or rule.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "target": {"type": "string", "description": "Local path or 'demo'."},
                        "file_path": {"type": "string", "description": "Optional file path to inspect."},
                        "rule_id": {"type": "string", "description": "Optional rule filter (e.g. ARCH-001)."},
                        "severity": {"type": "string", "enum": ["critical", "warning", "info"]},
                    },
                    "required": ["target"],
                },
            },
            {
                "name": "repodna_architecture_diff",
                "description": "Compares two Git revisions or working tree against a revision for architectural changes.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "target": {"type": "string", "description": "Local Git repository directory."},
                        "base_ref": {"type": "string", "default": "HEAD~1"},
                        "head_ref": {"type": "string", "default": "HEAD"},
                    },
                    "required": ["target"],
                },
            },
            {
                "name": "repodna_change_impact",
                "description": "Evaluates architectural risk and direct/transitive blast radius of proposed file edits.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "target": {"type": "string", "description": "Local path or 'demo'."},
                        "changed_files": {"type": "array", "items": {"type": "string"}},
                        "max_depth": {"type": "integer", "default": 2},
                    },
                    "required": ["target", "changed_files"],
                },
            },
            {
                "name": "repodna_analysis_coverage",
                "description": "Returns full AST vs partial static language coverage, unverified rules, and honesty guarantees.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "target": {"type": "string", "description": "Local path or 'demo'."},
                    },
                    "required": ["target"],
                },
            },
        ]

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(arguments, dict):
            return {
                "isError": True,
                "content": [{"type": "text", "text": "Invalid tool arguments: expected key-value dictionary."}],
            }
        target = arguments.get("target", ".")
        fmt = arguments.get("format", "text")

        try:
            if name == "repodna_repository_overview":
                content = self.tool_repository_overview(target=target, format=fmt)
            elif name == "repodna_architecture_map":
                content = self.tool_architecture_map(
                    target=target,
                    level=arguments.get("level", "clusters"),
                    limit=int(arguments.get("limit", 30)),
                )
            elif name == "repodna_find_modules":
                content = self.tool_find_modules(
                    target=target,
                    query=arguments.get("query", ""),
                    limit=int(arguments.get("limit", 10)),
                )
            elif name in ("repodna_module_dependencies", "repodna_dependencies"):
                dep_path = arguments.get("file_path") or arguments.get("module_path", "")
                content = self.tool_module_dependencies(
                    target=target,
                    file_path=dep_path,
                    direction=arguments.get("direction", "outgoing"),
                    depth=int(arguments.get("depth", 1)),
                )
            elif name in ("repodna_module_findings", "repodna_architecture_findings"):
                content = self.tool_module_findings(
                    target=target,
                    file_path=arguments.get("file_path"),
                    rule_id=arguments.get("rule_id"),
                    severity=arguments.get("severity"),
                )
            elif name == "repodna_architecture_diff":
                content = self.tool_architecture_diff(
                    target=target,
                    base_ref=arguments.get("base_ref", "HEAD~1"),
                    head_ref=arguments.get("head_ref", "HEAD"),
                )
            elif name == "repodna_change_impact":
                content = self.tool_change_impact(
                    target=target,
                    changed_files=arguments.get("changed_files", []),
                    max_depth=int(arguments.get("max_depth", 2)),
                )
            elif name in ("repodna_analysis_coverage", "repodna_explain_health"):
                content = self.tool_analysis_coverage(target=target)
            else:
                return {
                    "isError": True,
                    "content": [{"type": "text", "text": f"Unknown tool: '{name}'"}],
                }

            return {
                "content": [{"type": "text", "text": content}],
            }

        except Exception as exc:
            _log(f"Error in tool '{name}': {exc}")
            return {
                "isError": True,
                "content": [{"type": "text", "text": f"Error executing {name}: {exc}"}],
            }

    def handle_request(self, req: dict[str, Any]) -> dict[str, Any] | None:
        if not isinstance(req, dict):
            return {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32600, "message": "Invalid Request: payload must be a JSON object."},
            }

        msg_id = req.get("id")
        jsonrpc = req.get("jsonrpc")
        method = req.get("method")
        params = req.get("params", {})
        if not isinstance(params, dict):
            params = {}

        if jsonrpc != "2.0":
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32600, "message": "Invalid Request: 'jsonrpc' version must be '2.0'."},
            }

        if not method or not isinstance(method, str):
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32600, "message": "Invalid Request: 'method' string is required."},
            }

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {"tools": {}},
                    "serverInfo": {
                        "name": SERVER_NAME,
                        "version": SERVER_VERSION,
                    },
                },
            }

        if method == "notifications/initialized":
            _log("Client initialized successfully.")
            return None

        if method == "ping":
            return {"jsonrpc": "2.0", "id": msg_id, "result": {}}

        if method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {"tools": self.get_tools_list()},
            }

        if method == "tools/call":
            tool_name = params.get("name", "")
            args = params.get("arguments", {})
            call_result = self.call_tool(tool_name, args)
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": call_result,
            }

        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {"code": -32601, "message": f"Method not found: '{method}'"},
        }

    def run(self, transport: str = "stdio") -> None:
        """Runs the MCP server using official Python SDK v2."""
        if not HAS_OFFICIAL_MCP or self._official_server is None:
            err_msg = (
                "RepoDNA MCP Server requires the official Python Model Context Protocol SDK "
                '(mcp>=2.0.0). Please install it via \'pip install "mcp>=2.0.0"\' or run \'repodna setup --repair\'.'
            )
            _log(f"FATAL: {err_msg}")
            raise RuntimeError(err_msg)

        _log(
            f"Starting official MCP SDK v2 server ({SERVER_NAME} v{SERVER_VERSION}, "
            f"SDK: {MCP_SDK_VERSION}) on {transport} (PID: {os.getpid()})"
        )
        self._official_server.run(transport=transport)

    def run_stdio(self) -> None:
        """Runs the server on stdio transport (convenience alias)."""
        self.run(transport="stdio")

    def run_legacy_stdio(self) -> None:
        """Direct JSON-RPC 2.0 stdio event loop."""
        _log(f"Starting direct JSON-RPC stdio loop ({SERVER_NAME} v{SERVER_VERSION}, PID: {os.getpid()})")
        for line in sys.stdin:
            line_str = line.strip()
            if not line_str:
                continue
            try:
                req = json.loads(line_str)
                resp = self.handle_request(req)
                if resp is not None:
                    sys.stdout.write(json.dumps(resp) + "\n")
                    sys.stdout.flush()
            except json.JSONDecodeError as err:
                _log(f"JSON decode error: {err}")
                err_resp = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32700, "message": "Parse error"},
                }
                sys.stdout.write(json.dumps(err_resp) + "\n")
                sys.stdout.flush()
            except Exception as exc:
                _log(f"Fatal error in event loop: {exc}")


def main() -> int:
    server = RepoDNAMCPServer()
    server.run(transport="stdio")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
