"""Git revision snapshot manager for immutable architecture diffing."""

from __future__ import annotations

import io
import re
import subprocess
import tarfile
import tempfile
from pathlib import Path

from repodna.core.analyzer import run_repository_analysis
from repodna.schemas.models import AnalysisResult, ScanLimits, ScanRequest, SourceType
from repodna.security.validators import SecurityValidationError

# Strict ref pattern preventing flag injection or malformed shell arguments
SAFE_GIT_REF_PATTERN = re.compile(r"^[a-zA-Z0-9_\-.~^/]+$")


class SnapshotManager:
    """Manages immutable analysis snapshots extracted from Git revisions."""

    def __init__(self, repo_path: Path | str) -> None:
        self.repo_path = Path(repo_path).resolve()
        if not (self.repo_path / ".git").exists():
            raise ValueError(f"Directory '{self.repo_path}' is not a valid Git repository.")

    def resolve_commit_metadata(self, git_ref: str) -> tuple[str, str, str]:
        """Returns (commit_sha, author, date_iso) for a git ref."""
        if git_ref in ("working_tree", "worktree", "current"):
            # Get current HEAD info
            git_ref = "HEAD"

        if not SAFE_GIT_REF_PATTERN.match(git_ref) or git_ref.startswith("-"):
            raise SecurityValidationError("INVALID_GIT_REF", f"Invalid git reference syntax: '{git_ref}'")

        cmd = ["git", "-C", str(self.repo_path), "log", "-1", "--format=%H|%an|%cI", git_ref, "--"]
        try:
            out = subprocess.check_output(cmd, stderr=subprocess.PIPE, text=True, timeout=10.0).strip()
            parts = out.split("|", 2)
            if len(parts) == 3:
                return parts[0], parts[1], parts[2]
            return out, "unknown", ""
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            raise ValueError(f"Failed to resolve git revision '{git_ref}': {exc}") from exc

    def create_snapshot(
        self,
        git_ref: str,
        limits: ScanLimits | None = None,
    ) -> tuple[AnalysisResult, str | None, bool]:
        """
        Creates an immutable AnalysisResult snapshot of a repository at a specific git ref.
        Returns: (analysis_result, commit_sha_or_none, is_working_tree)
        """
        scan_limits = limits or ScanLimits()

        if git_ref in ("working_tree", "worktree", "current"):
            # Analyze active working tree
            sha, _, _ = self.resolve_commit_metadata("HEAD")
            req = ScanRequest(
                source_type=SourceType.LOCAL,
                target=str(self.repo_path),
                limits=scan_limits,
            )
            analysis = run_repository_analysis(req)
            return analysis, sha, True

        # Extract git revision via git archive into a sandboxed tempdir
        sha, _, _ = self.resolve_commit_metadata(git_ref)

        with tempfile.TemporaryDirectory(prefix="repodna_snap_") as tmp_dir:
            tmp_path = Path(tmp_dir)
            archive_cmd = ["git", "-C", str(self.repo_path), "archive", "--format=tar", sha]
            try:
                proc = subprocess.Popen(
                    archive_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                stdout_data, stderr_data = proc.communicate(timeout=30.0)
                if proc.returncode != 0:
                    raise RuntimeError(f"git archive failed: {stderr_data.decode('utf-8', errors='replace')}")

                with tarfile.open(fileobj=io.BytesIO(stdout_data), mode="r:*") as tar:
                    tar.extractall(path=tmp_path, filter="data" if hasattr(tarfile, "data_filter") else None)

            except Exception as exc:
                raise RuntimeError(f"Failed to extract revision '{git_ref}' ({sha}): {exc}") from exc

            req = ScanRequest(
                source_type=SourceType.LOCAL,
                target=str(tmp_path),
                limits=scan_limits,
            )
            analysis = run_repository_analysis(req)
            # Override target_display to reflect the git ref
            analysis.target_display = f"{self.repo_path.name} @ {git_ref} ({sha[:8]})"
            return analysis, sha, False
