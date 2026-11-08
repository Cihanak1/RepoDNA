"""Model Context Protocol (MCP) stdio server for RepoDNA repository intelligence."""

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

PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "repodna-mcp"
SERVER_VERSION = "0.3.0"


def _log(msg: str) -> None:
    """Logs diagnostics strictly to stderr to prevent stdout JSON-RPC corruption."""
    sys.stderr.write(f"[repodna-mcp] {msg}\n")
    sys.stderr.flush()


class RepoDNAMCPServer:
    """Implements JSON-RPC 2.0 stdio Model Context Protocol (MCP) server."""

    def __init__(self, allowed_roots: list[Path] | None = None) -> None:
        self.allowed_roots = allowed_roots or []
        self._analysis_cache: dict[str, tuple[float, AnalysisResult]] = {}

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

    def get_tools_list(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "repodna_repository_overview",
                "description": "Returns executive architecture scorecard, health grade, AST coverage, and key hubs for a repository.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "target": {
                            "type": "string",
                            "description": "Local filesystem path or 'demo'.",
                        },
                        "format": {
                            "type": "string",
                            "enum": ["text", "json"],
                            "default": "text",
                            "description": "Output formatting preference.",
                        },
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
                        "level": {
                            "type": "string",
                            "enum": ["overview", "clusters", "full"],
                            "default": "clusters",
                        },
                        "limit": {
                            "type": "integer",
                            "default": 30,
                            "description": "Maximum clusters to return.",
                        },
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
                        "query": {
                            "type": "string",
                            "description": "Search keyword, symbol name, or path substring.",
                        },
                        "limit": {
                            "type": "integer",
                            "default": 10,
                            "description": "Maximum matching modules to return.",
                        },
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
                        "file_path": {
                            "type": "string",
                            "description": "Relative file path within repository.",
                        },
                        "direction": {
                            "type": "string",
                            "enum": ["outgoing", "incoming", "both"],
                            "default": "outgoing",
                        },
                        "depth": {
                            "type": "integer",
                            "default": 1,
                            "description": "Trace traversal depth (1=direct, 2+=transitive).",
                        },
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
                        "file_path": {
                            "type": "string",
                            "description": "Optional file path to inspect.",
                        },
                        "rule_id": {
                            "type": "string",
                            "description": "Optional rule filter (e.g. ARCH-001).",
                        },
                        "severity": {
                            "type": "string",
                            "enum": ["critical", "warning", "info"],
                            "description": "Optional severity filter.",
                        },
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
                        "target": {
                            "type": "string",
                            "description": "Local Git repository directory.",
                        },
                        "base_ref": {
                            "type": "string",
                            "default": "HEAD~1",
                            "description": "Base Git revision (commit SHA, branch, or tag).",
                        },
                        "head_ref": {
                            "type": "string",
                            "default": "HEAD",
                            "description": "Head Git revision or 'working_tree'.",
                        },
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
                        "changed_files": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of file paths proposed for modification.",
                        },
                        "max_depth": {
                            "type": "integer",
                            "default": 2,
                            "description": "Blast radius traversal depth.",
                        },
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
        target = arguments.get("target", ".")
        fmt = arguments.get("format", "text")

        try:
            if name == "repodna_repository_overview":
                analysis = self.get_analysis(target)
                svc = RepositoryIntelligenceService(analysis)
                ov = svc.get_repository_overview()
                content = ov.model_dump_json(indent=2) if fmt == "json" else ov.summary_text

            elif name == "repodna_architecture_map":
                analysis = self.get_analysis(target)
                svc = RepositoryIntelligenceService(analysis)
                level = arguments.get("level", "clusters")
                limit = int(arguments.get("limit", 30))
                am = svc.get_architecture_map(level=level, limit=limit)
                content = am.model_dump_json(indent=2) if fmt == "json" else am.summary_text

            elif name == "repodna_find_modules":
                analysis = self.get_analysis(target)
                svc = RepositoryIntelligenceService(analysis)
                query = arguments.get("query", "")
                limit = int(arguments.get("limit", 10))
                res = svc.find_relevant_modules(query=query, limit=limit)
                content = res.model_dump_json(indent=2) if fmt == "json" else res.summary_text

            elif name == "repodna_module_dependencies":
                analysis = self.get_analysis(target)
                svc = RepositoryIntelligenceService(analysis)
                file_path = arguments.get("file_path", "")
                direction = arguments.get("direction", "outgoing")
                depth = int(arguments.get("depth", 1))
                deps = svc.get_dependencies(file_path=file_path, direction=direction, depth=depth)
                content = deps.model_dump_json(indent=2) if fmt == "json" else deps.summary_text

            elif name == "repodna_module_findings":
                analysis = self.get_analysis(target)
                svc = RepositoryIntelligenceService(analysis)
                file_path = arguments.get("file_path")
                rule_id = arguments.get("rule_id")
                sev = arguments.get("severity")
                if file_path:
                    dtls = svc.get_module_details(file_path)
                    content = dtls.model_dump_json(indent=2) if fmt == "json" else dtls.summary_text
                else:
                    findings = svc.get_architecture_findings(rule_id=rule_id, severity=sev)
                    content = findings.model_dump_json(indent=2) if fmt == "json" else findings.summary_text

            elif name == "repodna_architecture_diff":
                resolved, _ = self._resolve_target(target)
                base_ref = arguments.get("base_ref", "HEAD~1")
                head_ref = arguments.get("head_ref", "HEAD")
                snap_mgr = SnapshotManager(resolved)

                base_analysis, base_sha, base_is_wt = snap_mgr.create_snapshot(base_ref)
                head_analysis, head_sha, head_is_wt = snap_mgr.create_snapshot(head_ref)

                diff = ArchitectureDiffEngine.compare_analyses(
                    base=base_analysis,
                    head=head_analysis,
                    base_ref=base_ref,
                    head_ref=head_ref,
                    base_commit_sha=base_sha,
                    head_commit_sha=head_sha,
                    base_is_working_tree=base_is_wt,
                    head_is_working_tree=head_is_wt,
                )
                content = diff.model_dump_json(indent=2) if fmt == "json" else diff.summary_text

            elif name == "repodna_change_impact":
                analysis = self.get_analysis(target)
                svc = RepositoryIntelligenceService(analysis)
                changed = arguments.get("changed_files", [])
                max_depth = int(arguments.get("max_depth", 2))
                impact = svc.get_change_impact(changed_files=changed, max_depth=max_depth)
                content = impact.model_dump_json(indent=2) if fmt == "json" else impact.summary_text

            elif name == "repodna_analysis_coverage":
                analysis = self.get_analysis(target)
                svc = RepositoryIntelligenceService(analysis)
                cov = svc.get_analysis_coverage()
                content = cov.model_dump_json(indent=2) if fmt == "json" else cov.summary_text

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
        msg_id = req.get("id")
        method = req.get("method")
        params = req.get("params", {})

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

    def run_stdio(self) -> None:
        """Runs the JSON-RPC stdio event loop."""
        _log(f"Starting {SERVER_NAME} v{SERVER_VERSION} on stdio (PID: {os.getpid()})")
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
    server.run_stdio()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
