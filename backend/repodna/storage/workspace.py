"""Safe repository workspace acquisition and isolated temporary Git cloning."""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

from repodna.security.validators import (
    SecurityValidationError,
    sanitize_url_for_display,
    validate_git_branch,
    validate_github_url,
)


def _force_remove_readonly(func: Callable[..., object], path: str, _exc_info: object) -> None:
    """Clear read-only bit on Windows (.git packfiles) and retry deletion during temp cleanup."""
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except OSError:
        pass


def _terminate_process_tree(proc: subprocess.Popen[str]) -> None:
    """Terminate subprocess and any child helper processes (e.g., git-remote-https)."""
    if proc.poll() is not None:
        return
    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5.0,
                check=False,
            )
        else:
            import signal

            killpg_fn = getattr(os, "killpg", None)
            getpgid_fn = getattr(os, "getpgid", None)
            sigkill = getattr(signal, "SIGKILL", signal.SIGTERM)
            if callable(killpg_fn) and callable(getpgid_fn):
                killpg_fn(getpgid_fn(proc.pid), sigkill)
    except Exception:
        pass
    try:
        proc.kill()
    except OSError:
        pass


def build_hardened_git_env(empty_config_file: Path, home_dir: Path) -> dict[str, str]:
    """
    Construct a sanitized environment for git subprocesses that strips inherited credentials/tokens
    and isolates global/system git configuration files.
    """
    safe_keys = {
        "PATH",
        "SYSTEMROOT",
        "WINDIR",
        "COMSPEC",
        "PATHEXT",
        "TEMP",
        "TMP",
        "TMPDIR",
        "SSL_CERT_FILE",
        "SSL_CERT_DIR",
        "LANG",
        "LC_ALL",
    }
    env: dict[str, str] = {}
    for k, v in os.environ.items():
        if k.upper() in safe_keys:
            env[k] = v

    env["HOME"] = str(home_dir)
    env["XDG_CONFIG_HOME"] = str(home_dir)
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_CONFIG_GLOBAL"] = str(empty_config_file)
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_ASKPASS"] = "echo"
    env["SSH_ASKPASS"] = "echo"
    env["GIT_LFS_SKIP_SMUDGE"] = "1"
    return env


@contextmanager
def clone_github_repo_safely(
    raw_url: str,
    branch: str | None = None,
    timeout_seconds: float = 45.0,
    is_cancelled: Callable[[], bool] | None = None,
) -> Iterator[tuple[Path, str, str]]:
    """
    Clone a public GitHub repository into an isolated temporary directory without executing hooks
    or following symlinks, and automatically clean up the directory on exit.

    Yields:
        (cloned_repo_path, repo_display_name, canonical_url)
    """
    canonical_url, owner, repo = validate_github_url(raw_url)
    safe_branch = validate_git_branch(branch)

    temp_root = Path(tempfile.mkdtemp(prefix="repodna_clone_"))
    repo_dir = temp_root / repo

    try:
        if is_cancelled and is_cancelled():
            raise RuntimeError("Scan cancelled before cloning started.")

        null_hooks_dir = temp_root / "_empty_hooks"
        null_hooks_dir.mkdir(parents=True, exist_ok=True)
        empty_config_file = temp_root / "_empty_gitconfig"
        empty_config_file.write_text("", encoding="utf-8")

        env = build_hardened_git_env(empty_config_file=empty_config_file, home_dir=temp_root)

        cmd = [
            "git",
            "-c",
            f"core.hooksPath={null_hooks_dir.as_posix()}",
            "-c",
            "core.symlinks=false",
            "-c",
            "core.quotepath=false",
            "-c",
            "protocol.allow=never",
            "-c",
            "protocol.https.allow=always",
            "-c",
            "protocol.file.allow=never",
            "-c",
            "submodule.recurse=false",
            "-c",
            "http.followRedirects=false",
            "-c",
            "http.lowSpeedLimit=1024",
            "-c",
            "http.lowSpeedTime=15",
            "-c",
            "pack.windowMemory=32m",
            "clone",
            "--depth",
            "50",
            "--single-branch",
            "--no-tags",
        ]
        if safe_branch:
            cmd.extend(["--branch", safe_branch])
        cmd.extend(["--", canonical_url, str(repo_dir)])

        creation_flags = int(getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)) if os.name == "nt" else 0
        start_new_sess = os.name != "nt"

        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            creationflags=creation_flags,
            start_new_session=start_new_sess,
        )

        try:
            _, stderr = proc.communicate(timeout=max(5.0, min(timeout_seconds, 120.0)))
        except subprocess.TimeoutExpired as exc:
            _terminate_process_tree(proc)
            proc.communicate()
            raise SecurityValidationError(
                "CLONE_TIMEOUT",
                f"Cloning {owner}/{repo} timed out after {timeout_seconds:.0f}s.",
            ) from exc

        if is_cancelled and is_cancelled():
            _terminate_process_tree(proc)
            raise RuntimeError("Scan cancelled during GitHub clone.")

        if proc.returncode != 0:
            safe_err = sanitize_url_for_display(stderr.strip() or "Unknown git clone error")
            raise SecurityValidationError(
                "CLONE_FAILED",
                f"Failed to clone GitHub repository '{owner}/{repo}': {safe_err[:300]}",
            )

        yield repo_dir.resolve(), f"{owner}/{repo}", f"https://github.com/{owner}/{repo}"
    finally:
        shutil.rmtree(temp_root, onerror=_force_remove_readonly)
