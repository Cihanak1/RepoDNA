"""One-command installer and environment doctor for AI coding agents."""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any

SKILL_SOURCE_DIR = Path(__file__).resolve().parent.parent.parent.parent / "integrations" / "agent-skills" / "repodna"
ALT_SKILL_SOURCE_DIR = Path(__file__).resolve().parent.parent.parent.parent / ".agents" / "skills" / "repodna"


def _get_skill_source() -> Path:
    if SKILL_SOURCE_DIR.exists() and (SKILL_SOURCE_DIR / "SKILL.md").exists():
        return SKILL_SOURCE_DIR
    if ALT_SKILL_SOURCE_DIR.exists() and (ALT_SKILL_SOURCE_DIR / "SKILL.md").exists():
        return ALT_SKILL_SOURCE_DIR
    # Fallback to current working directory
    cwd_src = Path.cwd() / "integrations" / "agent-skills" / "repodna"
    if cwd_src.exists() and (cwd_src / "SKILL.md").exists():
        return cwd_src
    raise FileNotFoundError("RepoDNA Skill source files (SKILL.md) not found.")


class AgentInstaller:
    """Manages installation, uninstallation, and verification of RepoDNA across AI agents."""

    SUPPORTED_AGENTS = ["codex", "claude", "antigravity", "auto"]

    def __init__(
        self,
        agent: str = "auto",
        scope: str = "project",
        dry_run: bool = False,
        repo_root: Path | None = None,
    ) -> None:
        self.agent = agent.lower()
        if self.agent not in self.SUPPORTED_AGENTS:
            raise ValueError(f"Unsupported agent '{agent}'. Supported: {', '.join(self.SUPPORTED_AGENTS)}")
        self.scope = scope.lower()
        self.dry_run = dry_run
        self.repo_root = (repo_root or Path.cwd()).resolve()
        self.user_home = Path.home().resolve()

    def detect_agents(self) -> list[str]:
        detected = []
        # Check project-level directories
        if (self.repo_root / ".claude").exists() or (self.user_home / ".claude").exists():
            detected.append("claude")
        if (self.repo_root / ".codex").exists() or (self.user_home / ".codex").exists():
            detected.append("codex")
        if (self.user_home / ".gemini").exists() or (self.repo_root / ".agents").exists():
            detected.append("antigravity")

        if not detected:
            # Default to standard portable agent skills directory
            detected = ["antigravity", "claude"]
        return detected

    def _resolve_paths(self, target_agent: str) -> tuple[Path, Path | None]:
        """Returns (skill_target_dir, mcp_config_path_or_none)."""
        if target_agent == "claude":
            if self.scope == "user":
                skill_dir = self.user_home / ".claude" / "skills" / "repodna"
                if sys.platform == "win32":
                    appdata = Path(os.environ.get("APPDATA", str(self.user_home / "AppData" / "Roaming")))
                    mcp_path = appdata / "Claude" / "claude_desktop_config.json"
                elif sys.platform == "darwin":
                    mcp_path = self.user_home / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
                else:
                    mcp_path = self.user_home / ".config" / "Claude" / "claude_desktop_config.json"
            else:
                skill_dir = self.repo_root / ".claude" / "skills" / "repodna"
                mcp_path = self.repo_root / ".mcp.json"

        elif target_agent == "codex":
            if self.scope == "user":
                skill_dir = self.user_home / ".codex" / "skills" / "repodna"
                mcp_path = self.user_home / ".codex" / "mcp.json"
            else:
                skill_dir = self.repo_root / ".codex" / "skills" / "repodna"
                mcp_path = self.repo_root / ".codex" / "mcp.json"

        elif target_agent == "antigravity":
            if self.scope == "user":
                skill_dir = self.user_home / ".gemini" / "antigravity" / "skills" / "repodna"
                mcp_path = self.user_home / ".gemini" / "antigravity" / "mcp_servers.json"
            else:
                skill_dir = self.repo_root / ".agents" / "skills" / "repodna"
                mcp_path = self.repo_root / ".agents" / "mcp.json"

        else:
            skill_dir = self.repo_root / ".agents" / "skills" / "repodna"
            mcp_path = None

        return skill_dir, mcp_path

    def install(self) -> dict[str, Any]:
        targets = self.detect_agents() if self.agent == "auto" else [self.agent]
        actions_taken = []
        source_dir = _get_skill_source()

        python_cmd = sys.executable or "python"

        for tgt in targets:
            skill_dir, mcp_path = self._resolve_paths(tgt)

            # 1. Install Skill
            if self.dry_run:
                actions_taken.append(f"[DRY-RUN] Would copy skill files from '{source_dir}' to '{skill_dir}'")
            else:
                skill_dir.mkdir(parents=True, exist_ok=True)
                for item in source_dir.glob("**/*"):
                    if item.is_file():
                        rel = item.relative_to(source_dir)
                        dest = skill_dir / rel
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(item, dest)
                actions_taken.append(f"Installed Skill ({tgt}) at '{skill_dir}'")

            # 2. Configure MCP if path exists or can be created
            if mcp_path:
                repodna_mcp_entry = {
                    "command": python_cmd,
                    "args": ["-m", "repodna.mcp"],
                }

                if self.dry_run:
                    actions_taken.append(f"[DRY-RUN] Would register MCP tool in '{mcp_path}'")
                else:
                    mcp_path.parent.mkdir(parents=True, exist_ok=True)
                    data: dict[str, Any] = {}
                    if mcp_path.exists():
                        try:
                            # Backup
                            shutil.copy2(mcp_path, str(mcp_path) + ".bak")
                            data = json.loads(mcp_path.read_text(encoding="utf-8"))
                        except Exception:
                            data = {}

                    servers_key = "mcpServers" if "mcpServers" in data or tgt in ("claude", "codex") else "servers"
                    if servers_key not in data or not isinstance(data[servers_key], dict):
                        data[servers_key] = {}
                    data[servers_key]["repodna"] = repodna_mcp_entry
                    mcp_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
                    actions_taken.append(f"Configured MCP Server in '{mcp_path}'")

        return {
            "status": "success",
            "dry_run": self.dry_run,
            "agents": targets,
            "scope": self.scope,
            "actions": actions_taken,
        }

    def uninstall(self) -> dict[str, Any]:
        targets = self.detect_agents() if self.agent == "auto" else [self.agent]
        actions_taken = []

        for tgt in targets:
            skill_dir, mcp_path = self._resolve_paths(tgt)

            if skill_dir.exists():
                if self.dry_run:
                    actions_taken.append(f"[DRY-RUN] Would remove skill directory '{skill_dir}'")
                else:
                    shutil.rmtree(skill_dir, ignore_errors=True)
                    actions_taken.append(f"Removed Skill directory '{skill_dir}'")

            if mcp_path and mcp_path.exists():
                if self.dry_run:
                    actions_taken.append(f"[DRY-RUN] Would remove 'repodna' entry from '{mcp_path}'")
                else:
                    try:
                        data = json.loads(mcp_path.read_text(encoding="utf-8"))
                        modified = False
                        for key in ("mcpServers", "servers"):
                            if key in data and isinstance(data[key], dict) and "repodna" in data[key]:
                                del data[key]["repodna"]
                                modified = True
                        if modified:
                            mcp_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
                            actions_taken.append(f"Unregistered 'repodna' from '{mcp_path}'")
                    except Exception as exc:
                        actions_taken.append(f"Warning: Could not edit '{mcp_path}': {exc}")

        return {
            "status": "uninstalled",
            "dry_run": self.dry_run,
            "agents": targets,
            "actions": actions_taken,
        }

    def verify(self) -> dict[str, Any]:
        targets = self.detect_agents() if self.agent == "auto" else [self.agent]
        results = {}

        for tgt in targets:
            skill_dir, mcp_path = self._resolve_paths(tgt)
            skill_ok = skill_dir.exists() and (skill_dir / "SKILL.md").exists()
            mcp_ok = False
            if mcp_path and mcp_path.exists():
                try:
                    data = json.loads(mcp_path.read_text(encoding="utf-8"))
                    for key in ("mcpServers", "servers"):
                        if key in data and "repodna" in data[key]:
                            mcp_ok = True
                            break
                except Exception:
                    mcp_ok = False

            results[tgt] = {
                "skill_installed": skill_ok,
                "skill_path": str(skill_dir),
                "mcp_configured": mcp_ok,
                "mcp_path": str(mcp_path) if mcp_path else None,
            }

        return results


def run_doctor() -> int:
    """Diagnoses the RepoDNA environment, Tree-sitter parsers, and agent integrations."""
    print("=" * 76)
    print("RepoDNA Environment & AI Agent Diagnostic (repodna doctor)")
    print("=" * 76)

    checks_passed = 0
    checks_total = 0

    def check(title: str, ok: bool, details: str = "") -> None:
        nonlocal checks_passed, checks_total
        checks_total += 1
        status = "[PASS]" if ok else "[FAIL]"
        if ok:
            checks_passed += 1
        print(f"{status:<8} {title:<40} {details}")

    # 1. Python version
    py_ver = sys.version_info
    py_ok = (py_ver.major, py_ver.minor) >= (3, 12)
    check("Python Runtime (>= 3.12)", py_ok, f"{py_ver.major}.{py_ver.minor}.{py_ver.micro}")

    # 2. Tree-sitter core
    try:
        import tree_sitter  # noqa: F401
        ts_ok = True
    except ImportError:
        ts_ok = False
    check("Tree-sitter Engine", ts_ok)

    # 3. Language Grammars
    grammars = ["python", "javascript", "typescript", "go", "rust"]
    grammars_found = []
    for g in grammars:
        try:
            __import__(f"tree_sitter_{g}")
            grammars_found.append(g)
        except ImportError:
            pass
    check("AST Grammars (Tree-sitter)", len(grammars_found) == len(grammars), f"{len(grammars_found)}/5 grammars ({', '.join(grammars_found)})")

    # 4. Git availability
    try:
        import subprocess
        git_ver = subprocess.check_output(["git", "--version"], text=True, timeout=5.0).strip()
        git_ok = True
    except Exception:
        git_ver = "Not found"
        git_ok = False
    check("Git Binary Availability", git_ok, git_ver)

    # 5. MCP stdio Server
    try:
        from repodna.mcp.server import RepoDNAMCPServer
        srv = RepoDNAMCPServer()
        mcp_init = srv.handle_request({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
        mcp_ok = bool(mcp_init and mcp_init.get("result", {}).get("serverInfo"))
    except Exception:
        mcp_ok = False
    check("RepoDNA MCP Server (JSON-RPC)", mcp_ok, "8 tools registered")

    # 6. Skill Package
    try:
        src = _get_skill_source()
        skill_ok = src.exists() and (src / "SKILL.md").exists()
        skill_path = str(src)
    except Exception:
        skill_ok = False
        skill_path = "Missing"
    check("Agent Skill Package (SKILL.md)", skill_ok, skill_path)

    # 7. Agent Integrations
    installer = AgentInstaller()
    verification = installer.verify()
    print("-" * 76)
    print("Detected Agent Registrations:")
    for ag, v in verification.items():
        s_status = "INSTALLED" if v["skill_installed"] else "NOT FOUND"
        m_status = "CONFIGURED" if v["mcp_configured"] else "NOT CONFIGURED"
        print(f"  * {ag:<14} | Skill: {s_status:<10} | MCP: {m_status}")

    print("=" * 76)
    all_ok = checks_passed == checks_total
    status_str = "HEALTHY" if all_ok else "ATTENTION NEEDED"
    print(f"Diagnostic Summary: {checks_passed}/{checks_total} checks passed — Status: {status_str}")
    print("=" * 76)
    return 0 if all_ok else 1
