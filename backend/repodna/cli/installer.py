"""One-command installer, repair tool, and environment doctor for AI coding agents."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any

SKILL_SOURCE_DIR = Path(__file__).resolve().parent.parent.parent.parent / "integrations" / "agent-skills" / "repodna"
ALT_SKILL_SOURCE_DIR = Path(__file__).resolve().parent.parent.parent.parent / ".agents" / "skills" / "repodna"


def _get_skill_source() -> Path:
    if SKILL_SOURCE_DIR.exists() and (SKILL_SOURCE_DIR / "SKILL.md").exists():
        return SKILL_SOURCE_DIR
    if ALT_SKILL_SOURCE_DIR.exists() and (ALT_SKILL_SOURCE_DIR / "SKILL.md").exists():
        return ALT_SKILL_SOURCE_DIR
    cwd_src = Path.cwd() / "integrations" / "agent-skills" / "repodna"
    if cwd_src.exists() and (cwd_src / "SKILL.md").exists():
        return cwd_src
    raise FileNotFoundError("RepoDNA Skill source files (SKILL.md) not found.")


def _test_mcp_connection(command: str, args: list[str], cwd: Path | str | None) -> tuple[bool, str]:
    """Tests executing the MCP server via stdio and performing an initialization handshake."""
    clean_cmd = command.strip().strip('"').strip("'")
    target_cwd = str(cwd) if cwd else None
    try:
        proc = subprocess.Popen(
            [clean_cmd, *args],
            cwd=target_cwd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        init_req = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "repodna-doctor", "version": "0.3.0"},
            },
        }) + "\n"
        stdout, stderr = proc.communicate(input=init_req, timeout=4.0)
        if proc.returncode != 0 and proc.returncode is not None:
            return False, f"Process exited with code {proc.returncode}: {stderr.strip()}"

        for line in stdout.splitlines():
            line_str = line.strip()
            if not line_str:
                continue
            try:
                res = json.loads(line_str)
                if "result" in res and res.get("id") == 1:
                    return True, "Handshake successful (8 tools registered)"
            except Exception:
                continue
        return False, f"Invalid stdout response: {stdout[:100]}"
    except subprocess.TimeoutExpired:
        try:
            proc.kill()
        except Exception:
            pass
        return False, "Connection timed out after 4.0s"
    except Exception as exc:
        return False, str(exc)


class AgentInstaller:
    """Manages installation, repair, uninstallation, and verification of RepoDNA across AI agents."""

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

    def is_agent_installed_on_host(self, agent_name: str) -> bool:
        """Verifies whether an agent's runtime, config, or CLI actually exists on this host computer."""
        if agent_name == "antigravity":
            return (
                (self.user_home / ".gemini").exists()
                or any("ANTIGRAVITY" in k or "GEMINI" in k for k in os.environ)
            )
        elif agent_name == "codex":
            local_appdata = Path(os.environ.get("LOCALAPPDATA", "")) if os.environ.get("LOCALAPPDATA") else None
            codex_appdata = (local_appdata / "OpenAI" / "Codex") if local_appdata else None
            return (
                (self.user_home / ".codex").exists()
                or shutil.which("codex") is not None
                or (codex_appdata is not None and codex_appdata.exists())
            )
        elif agent_name == "claude":
            claude_desktop_win = Path(os.environ.get("APPDATA", "")) / "Claude" if os.environ.get("APPDATA") else None
            claude_desktop_mac = self.user_home / "Library" / "Application Support" / "Claude"
            return (
                (self.user_home / ".claude").exists()
                or shutil.which("claude") is not None
                or (claude_desktop_win is not None and claude_desktop_win.exists())
                or claude_desktop_mac.exists()
            )
        return False

    def detect_agents(self) -> list[str]:
        """Detects which agents are physically present on this host system."""
        detected = []
        for ag in ["antigravity", "codex", "claude"]:
            if self.is_agent_installed_on_host(ag):
                detected.append(ag)
        if not detected:
            # Fallback to universal Antigravity / Agent Skills standard directory
            detected = ["antigravity"]
        return detected

    def _resolve_paths(self, target_agent: str) -> tuple[Path, Path | None]:
        """Returns (skill_target_dir, mcp_config_path_or_none) with safe path handling."""
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
            # Codex official format: config.toml
            if self.scope == "user":
                skill_dir = self.user_home / ".codex" / "skills" / "repodna"
                mcp_path = self.user_home / ".codex" / "config.toml"
            else:
                skill_dir = self.repo_root / ".codex" / "skills" / "repodna"
                mcp_path = self.repo_root / ".codex" / "config.toml"

        elif target_agent == "antigravity":
            # Antigravity official format: mcp_config.json
            if self.scope == "user":
                skill_dir = self.user_home / ".gemini" / "antigravity" / "skills" / "repodna"
                mcp_path = self.user_home / ".gemini" / "config" / "mcp_config.json"
            else:
                skill_dir = self.repo_root / ".agents" / "skills" / "repodna"
                mcp_path = self.repo_root / ".agents" / "mcp_config.json"

        else:
            skill_dir = self.repo_root / ".agents" / "skills" / "repodna"
            mcp_path = None

        return skill_dir, mcp_path

    def _cleanup_legacy_configs(self) -> None:
        """Removes obsolete legacy .agents/mcp.json and .codex/mcp.json if present."""
        for legacy in [
            self.repo_root / ".agents" / "mcp.json",
            self.repo_root / ".codex" / "mcp.json",
        ]:
            if legacy.exists():
                try:
                    legacy.unlink()
                except Exception:
                    pass

    def install(self) -> dict[str, Any]:
        targets = self.detect_agents() if self.agent == "auto" else [self.agent]
        actions_taken = []
        warnings = []
        source_dir = _get_skill_source()
        self._cleanup_legacy_configs()

        python_exec = sys.executable or "python"

        for tgt in targets:
            if not self.is_agent_installed_on_host(tgt):
                warnings.append(f"Agent '{tgt}' does not appear to be installed on this host.")

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

            # 2. Configure MCP Server
            if mcp_path:
                if self.dry_run:
                    actions_taken.append(f"[DRY-RUN] Would configure MCP server in '{mcp_path}'")
                elif tgt == "codex":
                    self._install_codex_toml(mcp_path, python_exec)
                    actions_taken.append(f"Configured MCP Server in '{mcp_path}' ([mcp_servers.repodna])")
                else:
                    self._install_json_mcp(mcp_path, python_exec)
                    actions_taken.append(f"Configured MCP Server in '{mcp_path}'")

        return {
            "status": "success",
            "dry_run": self.dry_run,
            "agents": targets,
            "warnings": warnings,
            "scope": self.scope,
            "actions": actions_taken,
        }

    def _install_codex_toml(self, path: Path, python_exec: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        existing_text = path.read_text(encoding="utf-8") if path.exists() else ""
        if path.exists():
            shutil.copy2(path, str(path) + ".bak")

        # In TOML, single-quoted strings are literal strings (no backslash escape parsing),
        # perfectly suited for Windows file paths.
        clean_python = python_exec.strip('"').strip("'")
        new_block = (
            "[mcp_servers.repodna]\n"
            f"command = '{clean_python}'\n"
            'args = ["-m", "repodna.mcp"]\n'
            f"cwd = '{self.repo_root}'"
        )

        if "[mcp_servers.repodna]" in existing_text:
            updated_text = re.sub(
                r"\[mcp_servers\.repodna\](?:\r?\n(?:[^\[\r\n].*)?)*",
                lambda _: new_block,
                existing_text,
            )
        else:
            if existing_text.strip():
                updated_text = existing_text.rstrip() + "\n\n" + new_block + "\n"
            else:
                updated_text = new_block + "\n"

        tomllib.loads(updated_text)
        path.write_text(updated_text, encoding="utf-8")

    def _install_json_mcp(self, path: Path, python_exec: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        data: dict[str, Any] = {}
        if path.exists():
            shutil.copy2(path, str(path) + ".bak")
            try:
                raw = path.read_text(encoding="utf-8").strip()
                if raw:
                    data = json.loads(raw)
            except Exception:
                data = {}

        servers_key = "mcpServers" if "mcpServers" in data or path.name == "mcp_config.json" else "servers"
        if servers_key not in data or not isinstance(data[servers_key], dict):
            data[servers_key] = {}

        data[servers_key]["repodna"] = {
            "command": python_exec,
            "args": ["-m", "repodna.mcp"],
            "cwd": str(self.repo_root),
        }
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def repair(self) -> dict[str, Any]:
        """Detects missing components and repairs them idempotently."""
        verification = self.verify()
        repaired = []
        for ag, status in verification.items():
            if status["host_installed"]:
                if not status["skill_installed"] or not status["mcp_configured"] or not status["mcp_connected"]:
                    inst = AgentInstaller(agent=ag, scope=self.scope, dry_run=self.dry_run, repo_root=self.repo_root)
                    res = inst.install()
                    repaired.extend(res["actions"])
        return {
            "status": "repaired",
            "dry_run": self.dry_run,
            "repaired_actions": repaired,
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
                elif tgt == "codex":
                    if self._uninstall_codex_toml(mcp_path):
                        actions_taken.append(f"Removed [mcp_servers.repodna] from '{mcp_path}'")
                else:
                    if self._uninstall_json_mcp(mcp_path):
                        actions_taken.append(f"Unregistered 'repodna' from '{mcp_path}'")

        return {
            "status": "uninstalled",
            "dry_run": self.dry_run,
            "agents": targets,
            "actions": actions_taken,
        }

    def _uninstall_codex_toml(self, path: Path) -> bool:
        existing_text = path.read_text(encoding="utf-8")
        if "[mcp_servers.repodna]" not in existing_text:
            return False
        shutil.copy2(path, str(path) + ".bak")
        updated_text = re.sub(
            r"\r?\n?\[mcp_servers\.repodna\](?:\r?\n(?:[^\[\r\n].*)?)*",
            "",
            existing_text,
        )
        tomllib.loads(updated_text)
        path.write_text(updated_text, encoding="utf-8")
        return True

    def _uninstall_json_mcp(self, path: Path) -> bool:
        shutil.copy2(path, str(path) + ".bak")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            modified = False
            for key in ("mcpServers", "servers"):
                if key in data and isinstance(data[key], dict) and "repodna" in data[key]:
                    del data[key]["repodna"]
                    modified = True
            if modified:
                path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            return modified
        except Exception:
            return False

    def verify(self) -> dict[str, Any]:
        targets = ["antigravity", "codex", "claude"] if self.agent == "auto" else [self.agent]
        results = {}

        for tgt in targets:
            host_installed = self.is_agent_installed_on_host(tgt)
            skill_dir, mcp_path = self._resolve_paths(tgt)
            skill_ok = skill_dir.exists() and (skill_dir / "SKILL.md").exists()
            mcp_ok = False
            mcp_connected = False
            connection_detail = ""
            command_str = sys.executable or "python"
            args_list = ["-m", "repodna.mcp"]
            cwd_path: Path | str = self.repo_root

            if mcp_path and mcp_path.exists():
                try:
                    if tgt == "codex":
                        toml_data = tomllib.loads(mcp_path.read_text(encoding="utf-8"))
                        servers = toml_data.get("mcp_servers", {})
                        if "repodna" in servers:
                            mcp_ok = True
                            entry = servers["repodna"]
                            command_str = entry.get("command", command_str)
                            args_list = entry.get("args", args_list)
                            cwd_path = entry.get("cwd", cwd_path)
                    else:
                        json_data = json.loads(mcp_path.read_text(encoding="utf-8"))
                        for key in ("mcpServers", "servers"):
                            if key in json_data and "repodna" in json_data[key]:
                                mcp_ok = True
                                entry = json_data[key]["repodna"]
                                command_str = entry.get("command", command_str)
                                args_list = entry.get("args", args_list)
                                cwd_path = entry.get("cwd", cwd_path)
                                break
                except Exception:
                    mcp_ok = False

            if mcp_ok:
                conn_ok, conn_msg = _test_mcp_connection(command_str, args_list, cwd_path)
                mcp_connected = conn_ok
                connection_detail = conn_msg
            else:
                connection_detail = "MCP config file missing or 'repodna' not declared"

            if not host_installed:
                integration_status = "NOT INSTALLED ON HOST"
            elif skill_ok and mcp_ok and mcp_connected:
                integration_status = "READY"
            elif skill_ok and mcp_ok and not mcp_connected:
                integration_status = f"ERROR (MCP Connection Failed: {connection_detail})"
            elif skill_ok and not mcp_ok:
                integration_status = "INCOMPLETE (Skill Installed, MCP Missing)"
            elif not skill_ok and mcp_ok:
                integration_status = "INCOMPLETE (MCP Configured, Skill Missing)"
            else:
                integration_status = "NOT CONFIGURED"

            results[tgt] = {
                "host_installed": host_installed,
                "skill_installed": skill_ok,
                "skill_path": str(skill_dir),
                "mcp_configured": mcp_ok,
                "mcp_connected": mcp_connected,
                "mcp_connection_detail": connection_detail,
                "mcp_path": str(mcp_path) if mcp_path else None,
                "integration_status": integration_status,
            }

        return results


def run_doctor() -> int:
    """Diagnoses the RepoDNA environment, Tree-sitter parsers, and agent integrations separately."""
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

    print("--- Core Engine Diagnostic ---")
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
    check(
        "AST Grammars (Tree-sitter)",
        len(grammars_found) == len(grammars),
        f"{len(grammars_found)}/5 grammars ({', '.join(grammars_found)})",
    )

    # 4. Git availability
    try:
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
    check("RepoDNA MCP Server (SDK v2 & Stdio)", mcp_ok, "8 tools registered")

    # 6. Skill Package Source
    try:
        src = _get_skill_source()
        skill_ok = src.exists() and (src / "SKILL.md").exists()
        skill_path = str(src)
    except Exception:
        skill_ok = False
        skill_path = "Missing"
    check("Agent Skill Package (SKILL.md)", skill_ok, skill_path)

    core_healthy = checks_passed == checks_total
    print(f"Core Engine Status: {'HEALTHY' if core_healthy else 'ATTENTION NEEDED'}")

    # 7. Agent Integrations Section
    installer = AgentInstaller()
    verification = installer.verify()
    print("-" * 76)
    print("AI Agent Integration Status:")
    any_ready = False
    any_incomplete = False

    for ag, v in verification.items():
        host_str = "DETECTED" if v["host_installed"] else "NOT DETECTED"
        s_status = "INSTALLED" if v["skill_installed"] else "NOT FOUND"
        m_status = "CONFIGURED" if v["mcp_configured"] else "NOT CONFIGURED"
        live_status = "CONNECTED" if v["mcp_connected"] else "OFFLINE"
        integ_status = v["integration_status"]

        if integ_status == "READY":
            any_ready = True
        elif "INCOMPLETE" in integ_status:
            any_incomplete = True

        print(
            f"  * {ag.upper():<13} | Host: {host_str:<12} | Skill: {s_status:<9} | "
            f"Config: {m_status:<14} | Live: {live_status:<9} | Status: {integ_status}"
        )

    print("=" * 76)
    if any_ready:
        integ_overall = "READY"
    elif any_incomplete:
        integ_overall = "INCOMPLETE (Run 'repodna setup --repair' to complete)"
    else:
        integ_overall = "NOT CONFIGURED (Run 'repodna setup' to configure)"

    print(f"Summary: Core Engine: {'HEALTHY' if core_healthy else 'ATTENTION NEEDED'} | Agent Integration: {integ_overall}")
    print("=" * 76)
    return 0 if core_healthy else 1
