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

        # Harden git environment: disable interactive prompts, hooks, symlinks, submodules, and LFS smudge filters
        env = os.environ.copy()
        env["GIT_TERMINAL_PROMPT"] = "0"
        env["GIT_ASKPASS"] = "echo"
        env["GIT_LFS_SKIP_SMUDGE"] = "1"
        env["GIT_CONFIG_NOSYSTEM"] = "1"

        null_hooks_dir = temp_root / "_empty_hooks"
        null_hooks_dir.mkdir(parents=True, exist_ok=True)

        cmd = [
            "git",
            "-c",
            f"core.hooksPath={null_hooks_dir.as_posix()}",
            "-c",
            "core.symlinks=false",
            "-c",
            "core.quotepath=false",
            "-c",
            "protocol.file.allow=never",
            "-c",
            "submodule.recurse=false",
            "-c",
            "http.lowSpeedLimit=1024",
            "-c",
            "http.lowSpeedTime=15",
            "clone",
            "--depth",
            "50",
            "--single-branch",
            "--no-tags",
        ]
        if safe_branch:
            cmd.extend(["--branch", safe_branch])
        cmd.extend(["--", canonical_url, str(repo_dir)])

        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
        )

        try:
            _, stderr = proc.communicate(timeout=max(5.0, min(timeout_seconds, 120.0)))
        except subprocess.TimeoutExpired as exc:
            proc.kill()
            proc.communicate()
            raise SecurityValidationError(
                "CLONE_TIMEOUT",
                f"Cloning {owner}/{repo} timed out after {timeout_seconds:.0f}s.",
            ) from exc

        if is_cancelled and is_cancelled():
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
