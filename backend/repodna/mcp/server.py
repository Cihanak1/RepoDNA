"""Official Model Context Protocol (MCP) server for RepoDNA repository intelligence.

Supports the 2024-11-05/2026 standard via the official Python SDK v2 (mcp>=2.0.0),
providing stdio transport, strict stdout cleanliness, and read-only tools.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from datetime import UTC, datetime
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

RELEVANT_EXTENSIONS = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs",
    ".go", ".rs", ".cs", ".java",
    ".json", ".toml", ".yaml", ".yml", ".md",
    ".csproj", ".sln",
}

IGNORED_SCAN_DIRS = {
    ".git", "node_modules", ".venv", "venv", "dist", "build",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    ".next", ".nuxt", "bin", "obj",
}


def _log(msg: str) -> None:
    """Logs diagnostics strictly to stderr to prevent stdout JSON-RPC corruption."""
    sys.stderr.write(f"[repodna-mcp] {msg}\n")
    sys.stderr.flush()


class RepoDNAMCPServer:
    """Dual-engine Model Context Protocol server (Official SDK v2 + Stdio fallback)."""

    def __init__(self, allowed_roots: list[Path] | None = None) -> None:
        configured_roots: list[Path] = []
        if allowed_roots:
            configured_roots = [p.resolve() for p in allowed_roots if p]
        else:
            env_val = os.environ.get("REPODNA_ALLOWED_ROOTS", "").strip()
            if env_val:
                raw_parts = re.split(r"(?<![a-zA-Z]):|;", env_val) if sys.platform == "win32" else env_val.split(":")
                for part in raw_parts:
                    p_str = part.strip()
                    if p_str:
                        p = Path(p_str).resolve()
                        if p.exists() and p.is_dir():
                            configured_roots.append(p)

        if not configured_roots:
            configured_roots = [Path.cwd().resolve()]

        self.allowed_roots: list[Path] = configured_roots
        _log(f"Configured authorized workspace roots: {[str(r) for r in self.allowed_roots]}")

        # Analysis cache: (cache_type, repo_str, git_rev) -> (fingerprint, time_iso, dur_ms, AnalysisResult)
        self._analysis_cache: dict[tuple[str, str, str], tuple[str, str, float, AnalysisResult]] = {}
        # Per-repo file stat cache for fast incremental hashing: {repo_str: {norm_rel: (size, mtime_ns, hash)}}
        self._file_stat_cache: dict[str, dict[str, tuple[int, int, str]]] = {}
        self._last_cache_report: dict[str, Any] = {}

        self._official_server: Any = None
        if HAS_OFFICIAL_MCP and MCPServer is not None:
            self._setup_official_server()

    def _resolve_target(self, target: str) -> tuple[Path | str, SourceType]:
        cleaned = target.strip()
        if cleaned.lower() == "demo":
            return "demo", SourceType.DEMO

        if cleaned in ("", ".", "./", ".\\"):
            resolved = self.allowed_roots[0]
        else:
            target_path = Path(cleaned)
            if not target_path.is_absolute():
                resolved = (self.allowed_roots[0] / target_path).resolve()
            else:
                resolved = target_path.resolve()

        validate_local_directory(str(resolved))

        # Strict boundary enforcement
        is_allowed = False
        for root in self.allowed_roots:
            try:
                if resolved == root or resolved.is_relative_to(root):
                    is_allowed = True
                    break
            except (ValueError, TypeError):
                continue

        if not is_allowed:
            roots_str = ", ".join(f"'{r}'" for r in self.allowed_roots)
            raise SecurityValidationError(
                "ROOT_VIOLATION",
                f"Access denied: path '{resolved}' is outside authorized workspace roots ({roots_str}). "
                "Use --allowed-root or set REPODNA_ALLOWED_ROOTS to authorize additional locations.",
            )

        return resolved, SourceType.LOCAL

    def _compute_fingerprint(self, repo_path: Path) -> tuple[str, str]:
        """
        Fast composite fingerprinting of repository files and Git state.
        Uses incremental stat caching: only files with changed size or mtime_ns are re-hashed.
        Returns: (fingerprint_hex, git_revision_or_head)
        """
        repo_str = str(repo_path)
        if repo_str not in self._file_stat_cache:
            self._file_stat_cache[repo_str] = {}
        cached_files = self._file_stat_cache[repo_str]

        # 1. Git metadata
        git_dir = repo_path / ".git"
        git_metadata = "no_git"
        git_rev = "working_tree"
        if git_dir.exists():
            head_file = git_dir / "HEAD"
            index_file = git_dir / "index"
            head_content = ""
            head_mtime = 0
            index_stat = "0_0"
            if head_file.exists():
                try:
                    head_content = head_file.read_text(encoding="utf-8", errors="replace").strip()
                    head_mtime = head_file.stat().st_mtime_ns
                except OSError:
                    pass
            if index_file.exists():
                try:
                    st = index_file.stat()
                    index_stat = f"{st.st_size}_{st.st_mtime_ns}"
                except OSError:
                    pass
            git_metadata = f"{head_content}|{head_mtime}|{index_stat}"
            git_rev = head_content.split("/")[-1] if "/" in head_content else (head_content[:8] or "HEAD")

        # 2. Collect relevant source files
        file_entries: list[tuple[str, int, int]] = []
        for root, dirs, files in os.walk(repo_path):
            dirs[:] = [d for d in dirs if d not in IGNORED_SCAN_DIRS and not d.startswith(".")]
            rel_root = os.path.relpath(root, repo_path)
            for f in files:
                ext = os.path.splitext(f)[1].lower()
                if ext in RELEVANT_EXTENSIONS or f in ("pyproject.toml", "package.json", "Cargo.toml", "go.mod"):
                    rel_path = f if rel_root == "." else os.path.join(rel_root, f)
                    norm_rel = rel_path.replace("\\", "/")
                    full_path = os.path.join(root, f)
                    try:
                        st = os.stat(full_path)
                        file_entries.append((norm_rel, st.st_size, st.st_mtime_ns))
                    except OSError:
                        continue

        file_entries.sort(key=lambda x: x[0])
        current_rel_paths = {entry[0] for entry in file_entries}

        # Evict deleted files from cache
        for stale in list(cached_files.keys()):
            if stale not in current_rel_paths:
                del cached_files[stale]

        # 3. Incremental hash
        hasher = hashlib.blake2b(digest_size=16)
        hasher.update(git_metadata.encode("utf-8"))

        for norm_rel, size, mtime_ns in file_entries:
            if norm_rel in cached_files and cached_files[norm_rel][:2] == (size, mtime_ns):
                file_hash = cached_files[norm_rel][2]
            else:
                target_file = repo_path / norm_rel
                try:
                    content_bytes = target_file.read_bytes()
                    file_hash = hashlib.blake2b(content_bytes, digest_size=16).hexdigest()
                    cached_files[norm_rel] = (size, mtime_ns, file_hash)
                except OSError:
                    file_hash = f"err_{size}_{mtime_ns}"

            hasher.update(f"{norm_rel}:{file_hash}\n".encode())

        return hasher.hexdigest(), git_rev

    def get_analysis(self, target: str) -> AnalysisResult:
        resolved, stype = self._resolve_target(target)
        if stype == SourceType.DEMO:
            req = ScanRequest(
                source_type=SourceType.DEMO,
                target="demo",
                limits=ScanLimits(max_files=2500, timeout_seconds=60.0),
            )
            return run_repository_analysis(req)

        assert isinstance(resolved, Path)
        repo_str = str(resolved)
        fingerprint, git_rev = self._compute_fingerprint(resolved)
        cache_key = ("worktree", repo_str, git_rev)

        t0 = time.perf_counter()
        if cache_key in self._analysis_cache:
            cached_fp, cached_time_iso, cached_dur, cached_res = self._analysis_cache[cache_key]
            if cached_fp == fingerprint:
                duration_ms = (time.perf_counter() - t0) * 1000.0
                self._last_cache_report = {
                    "target": repo_str,
                    "cache_hit": True,
                    "analysis_time_iso": cached_time_iso,
                    "revision": git_rev,
                    "fingerprint": fingerprint[:16],
                    "duration_ms": round(duration_ms, 2),
                }
                return cached_res

        # Cache miss / stale: Run full analysis
        req = ScanRequest(
            source_type=stype,
            target=repo_str,
            limits=ScanLimits(max_files=2500, timeout_seconds=60.0),
        )
        res = run_repository_analysis(req)
        duration_ms = (time.perf_counter() - t0) * 1000.0
        analysis_time_iso = datetime.now(UTC).isoformat()
        self._analysis_cache[cache_key] = (fingerprint, analysis_time_iso, duration_ms, res)
        self._last_cache_report = {
            "target": repo_str,
            "cache_hit": False,
            "analysis_time_iso": analysis_time_iso,
            "revision": git_rev,
            "fingerprint": fingerprint[:16],
            "duration_ms": round(duration_ms, 2),
        }
        return res

    def get_last_cache_report(self) -> dict[str, Any]:
        """Returns the cache report from the most recent get_analysis query."""
        return dict(self._last_cache_report)

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
        engine = ArchitectureDiffEngine()
        diff_res = engine.compare_analyses(
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
        return diff_res.model_dump_json(indent=2)

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
        report = cov.model_dump()
        report["cache_status"] = self.get_last_cache_report()
        return json.dumps(report, indent=2)

    # -------------------------------------------------------------------------
    # Official Python MCP SDK Server Setup
    # -------------------------------------------------------------------------
    def _setup_official_server(self) -> None:
        """Configures official MCPServer with typed tools when SDK is available."""
        self._official_server = MCPServer(name=SERVER_NAME)

        @self._official_server.tool(name="repodna_repository_overview", description="Provides high-level codebase architecture snapshot, health metrics, and component vitals.")
        def _mcp_overview(target: str, format: str = "text") -> str:
            return self.tool_repository_overview(target=target, format=format)

        @self._official_server.tool(name="repodna_architecture_map", description="Outputs component taxonomy, dependency graph linkages, and modular hierarchy.")
        def _mcp_arch_map(target: str, level: str = "clusters", limit: int = 30) -> str:
            return self.tool_architecture_map(target=target, level=level, limit=limit)

        @self._official_server.tool(name="repodna_find_modules", description="Finds repository modules matching a search query by filename, symbols, or architectural hub status.")
        def _mcp_find_modules(target: str, query: str, limit: int = 10) -> str:
            return self.tool_find_modules(target=target, query=query, limit=limit)

        @self._official_server.tool(name="repodna_module_dependencies", description="Traces direct or transitive incoming/outgoing dependencies for a specific module.")
        def _mcp_dependencies(target: str, file_path: str, direction: str = "outgoing", depth: int = 1) -> str:
            return self.tool_module_dependencies(target=target, file_path=file_path, direction=direction, depth=depth)

        @self._official_server.tool(name="repodna_module_findings", description="Lists architectural rule findings (circular dependencies, coupling hotspots) filtered by module or rule.")
        def _mcp_findings(target: str, file_path: str | None = None, rule_id: str | None = None, severity: str | None = None) -> str:
            return self.tool_module_findings(target=target, file_path=file_path, rule_id=rule_id, severity=severity)

        @self._official_server.tool(name="repodna_architecture_diff", description="Compares two Git revisions or working tree against a revision for architectural changes.")
        def _mcp_diff(target: str, base_ref: str = "HEAD~1", head_ref: str = "HEAD") -> str:
            return self.tool_architecture_diff(target=target, base_ref=base_ref, head_ref=head_ref)

        @self._official_server.tool(name="repodna_change_impact", description="Evaluates architectural risk and direct/transitive blast radius of proposed file edits.")
        def _mcp_change_impact(target: str, changed_files: list[str], max_depth: int = 2) -> str:
            return self.tool_change_impact(target=target, changed_files=changed_files, max_depth=max_depth)

        @self._official_server.tool(name="repodna_analysis_coverage", description="Returns full AST vs partial static language coverage, unverified rules, and honesty guarantees.")
        def _mcp_coverage(target: str) -> str:
            return self.tool_analysis_coverage(target=target)

    def run(self, transport: str = "stdio") -> None:
        """Runs the server. Enforces official Python MCP SDK as standard."""
        if not HAS_OFFICIAL_MCP or self._official_server is None:
            raise RuntimeError(
                f"RepoDNA MCP server requires the official Python Model Context Protocol SDK (mcp>=2.0.0). "
                f"Currently installed: {MCP_SDK_VERSION}. Please install with: pip install 'mcp>=2.0.0'"
            )

        _log(f"Starting RepoDNA MCP server via official Python SDK v2 ({MCP_SDK_VERSION}), transport={transport}")
        self._official_server.run(transport=transport)

    # -------------------------------------------------------------------------
    # JSON-RPC 2.0 Direct Handling (For fast in-process tests & fallback)
    # -------------------------------------------------------------------------
    def get_tools_list(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "repodna_repository_overview",
                "description": "Provides high-level codebase architecture snapshot, health metrics, and component vitals.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "target": {"type": "string", "description": "Local path, repo URL, or 'demo'."},
                        "format": {"type": "string", "enum": ["text", "json"], "default": "text"},
                    },
                    "required": ["target"],
                },
            },
            {
                "name": "repodna_architecture_map",
                "description": "Outputs component taxonomy, dependency graph linkages, and modular hierarchy.",
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
        """Direct dispatch for in-process tests and fallback handling."""
        if not isinstance(arguments, dict):
            return {
                "isError": True,
                "content": [{"type": "text", "text": f"Invalid arguments for {name}: expected JSON object."}],
            }
        target = arguments.get("target", ".")
        try:
            if name == "repodna_repository_overview":
                content = self.tool_repository_overview(
                    target=target,
                    format=arguments.get("format", "text"),
                )
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

    def handle_request(self, request: dict[str, Any]) -> dict[str, Any] | None:
        """Processes raw JSON-RPC 2.0 requests with strict validation."""
        if not isinstance(request, dict):
            return {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32600, "message": "Invalid Request: root must be JSON object."},
            }

        msg_id = request.get("id")
        method = request.get("method")
        params = request.get("params", {})

        if request.get("jsonrpc") != "2.0":
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
            call_res = self.call_tool(tool_name, args)
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": call_res,
            }

        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {"code": -32601, "message": f"Method not found: '{method}'"},
        }

    def run_stdio(self) -> None:
        """Synchronous stdio event loop."""
        _log(f"RepoDNA MCP server listening on stdio (JSON-RPC 2.0 / {PROTOCOL_VERSION}).")
        while True:
            line = sys.stdin.readline()
            if not line:
                break
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
    parser = argparse.ArgumentParser(description="RepoDNA MCP Server")
    parser.add_argument(
        "--allowed-root",
        action="append",
        dest="allowed_roots",
        help="Authorized workspace root directory (can be specified multiple times).",
    )
    args, _ = parser.parse_known_args()
    roots = [Path(r) for r in args.allowed_roots] if args.allowed_roots else None
    server = RepoDNAMCPServer(allowed_roots=roots)
    server.run(transport="stdio")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
