"""Git revision snapshot manager for immutable architecture diffing with security hardening."""

from __future__ import annotations

import os
import re
import subprocess
import tarfile
import tempfile
from pathlib import Path

from repodna.core.analyzer import run_repository_analysis
from repodna.schemas.models import AnalysisResult, ScanLimits, ScanRequest, SourceType
from repodna.security.validators import SecurityValidationError, is_safe_subpath

# Strict ref pattern preventing flag injection or malformed shell arguments
SAFE_GIT_REF_PATTERN = re.compile(r"^[a-zA-Z0-9_\-.~^/]+$")
WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


class SnapshotManager:
    """Manages immutable analysis snapshots extracted from Git revisions."""

    def __init__(self, repo_path: Path | str) -> None:
        self.repo_path = Path(repo_path).resolve()
        if not (self.repo_path / ".git").exists():
            raise ValueError(f"Directory '{self.repo_path}' is not a valid Git repository.")

    def resolve_commit_metadata(self, git_ref: str) -> tuple[str, str, str]:
        """Returns (commit_sha, author, date_iso) for a git ref, ensuring commit exists."""
        if git_ref in ("working_tree", "worktree", "current"):
            git_ref = "HEAD"

        if not SAFE_GIT_REF_PATTERN.match(git_ref) or git_ref.startswith("-"):
            raise SecurityValidationError("INVALID_GIT_REF", f"Invalid git reference syntax: '{git_ref}'")

        # Verify revision actually points to a valid commit object
        verify_cmd = ["git", "-C", str(self.repo_path), "rev-parse", "--verify", "--quiet", f"{git_ref}^{{commit}}"]
        try:
            verified_sha = subprocess.check_output(verify_cmd, stderr=subprocess.PIPE, text=True, timeout=5.0).strip()
            if not verified_sha:
                raise SecurityValidationError("UNKNOWN_GIT_REF", f"Git commit revision '{git_ref}' does not exist.")
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            raise SecurityValidationError("UNKNOWN_GIT_REF", f"Git commit revision '{git_ref}' does not exist.") from exc

        cmd = ["git", "-C", str(self.repo_path), "log", "-1", "--format=%H|%an|%cI", verified_sha, "--"]
        try:
            out = subprocess.check_output(cmd, stderr=subprocess.PIPE, text=True, timeout=10.0).strip()
            parts = out.split("|", 2)
            if len(parts) == 3:
                return parts[0], parts[1], parts[2]
            return verified_sha, "unknown", ""
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            raise ValueError(f"Failed to resolve git metadata for '{git_ref}': {exc}") from exc

    def find_git_renames(self, base_ref: str, head_ref: str) -> dict[str, str]:
        """Finds verified renames tracked by Git between base and head revisions."""
        try:
            base_sha, _, _ = self.resolve_commit_metadata(base_ref)
            head_sha, _, _ = self.resolve_commit_metadata(head_ref)
            cmd = ["git", "-C", str(self.repo_path), "diff", "-M", "--name-status", base_sha, head_sha]
            out = subprocess.check_output(cmd, stderr=subprocess.PIPE, text=True, timeout=15.0)
            renames: dict[str, str] = {}
            for line in out.splitlines():
                parts = line.strip().split("\t")
                if len(parts) >= 3 and parts[0].startswith("R"):
                    # R100\told_path\tnew_path
                    renames[parts[1]] = parts[2]
            return renames
        except Exception:
            return {}

    def create_snapshot(
        self,
        git_ref: str,
        limits: ScanLimits | None = None,
    ) -> tuple[AnalysisResult, str | None, bool]:
        """
        Creates an immutable AnalysisResult snapshot of a repository at a specific git ref.
        Extracts repository tree into a sandboxed tempdir with strict memory and security bounds.
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

        # Extract git revision via git archive with bounded streaming into disk spool
        sha, _, _ = self.resolve_commit_metadata(git_ref)

        with tempfile.TemporaryDirectory(prefix="repodna_snap_") as tmp_dir:
            tmp_path = Path(tmp_dir).resolve()
            archive_cmd = ["git", "-C", str(self.repo_path), "archive", "--format=tar", sha]
            spool_file = tempfile.NamedTemporaryFile(prefix="repodna_tar_", suffix=".tar", delete=False)
            spool_path = Path(spool_file.name)
            try:
                proc = subprocess.Popen(
                    archive_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                assert proc.stdout is not None
                total_stream_bytes = 0
                chunk_size = 64 * 1024
                while True:
                    chunk = proc.stdout.read(chunk_size)
                    if not chunk:
                        break
                    total_stream_bytes += len(chunk)
                    if total_stream_bytes > scan_limits.max_total_size_bytes:
                        proc.kill()
                        proc.wait()
                        raise SecurityValidationError(
                            "MAX_SIZE_EXCEEDED",
                            f"Archive stream size ({total_stream_bytes} bytes) exceeds limit of {scan_limits.max_total_size_bytes} bytes.",
                        )
                    spool_file.write(chunk)

                spool_file.flush()
                spool_file.close()

                _, stderr_data = proc.communicate(timeout=10.0)
                if proc.returncode != 0:
                    raise RuntimeError(f"git archive failed (code {proc.returncode}): {stderr_data.decode('utf-8', errors='replace')}")

                # Strict security inspection of tar members before extraction
                total_bytes = 0
                total_files = 0
                symlink_targets: dict[Path, str] = {}

                with tarfile.open(spool_path, mode="r:*") as tar:
                    for member in tar.getmembers():
                        # 1. Member type check: disallow devices, FIFOs, hardlinks
                        if not (member.isreg() or member.isdir() or member.issym()):
                            raise SecurityValidationError(
                                "UNSAFE_TAR_MEMBER_TYPE",
                                f"Archive member '{member.name}' has prohibited type.",
                            )

                        # 2. Path normalization & traversal checks
                        norm_name = os.path.normpath(member.name).replace("\\", "/")
                        if (
                            norm_name.startswith(("/", "\\"))
                            or (len(norm_name) > 1 and norm_name[1] == ":")
                            or norm_name.startswith("../")
                            or "/../" in norm_name
                        ):
                            raise SecurityValidationError(
                                "PATH_TRAVERSAL_IN_ARCHIVE",
                                f"Archive member '{member.name}' attempts path traversal.",
                            )

                        # 3. Windows reserved names check
                        for part in Path(norm_name).parts:
                            stem = part.split(".")[0].upper()
                            if stem in WINDOWS_RESERVED_NAMES:
                                raise SecurityValidationError(
                                    "UNSAFE_ARCHIVE_FILENAME",
                                    f"Archive member '{member.name}' contains prohibited Windows reserved name '{stem}'.",
                                )

                        member_dest = (tmp_path / norm_name).resolve()
                        if not is_safe_subpath(tmp_path, member_dest):
                            raise SecurityValidationError(
                                "PATH_TRAVERSAL_IN_ARCHIVE",
                                f"Archive member '{member.name}' resolves outside destination root.",
                            )

                        # 4. Symlink security
                        if member.issym():
                            linkname = member.linkname
                            if (
                                os.path.isabs(linkname)
                                or (len(linkname) > 1 and linkname[1] == ":")
                                or linkname.startswith(("/", "\\"))
                            ):
                                raise SecurityValidationError(
                                    "SYMLINK_ESCAPE_IN_ARCHIVE",
                                    f"Archive symlink '{member.name}' -> '{linkname}' has absolute or UNC target.",
                                )
                            link_dest = (member_dest.parent / linkname).resolve()
                            if not is_safe_subpath(tmp_path, link_dest):
                                raise SecurityValidationError(
                                    "SYMLINK_ESCAPE_IN_ARCHIVE",
                                    f"Archive symlink '{member.name}' -> '{linkname}' escapes root.",
                                )
                            symlink_targets[member_dest] = linkname

                        total_files += 1
                        total_bytes += member.size

                        if total_files > scan_limits.max_files:
                            raise SecurityValidationError(
                                "MAX_FILES_EXCEEDED",
                                f"Archive contains {total_files} files, exceeding limit {scan_limits.max_files}.",
                            )
                        if total_bytes > scan_limits.max_total_size_bytes:
                            raise SecurityValidationError(
                                "MAX_SIZE_EXCEEDED",
                                f"Archive uncompressed size exceeds limit of {scan_limits.max_total_size_bytes} bytes.",
                            )

                    # 5. Nested symlink check
                    for sym_dest, orig_link in symlink_targets.items():
                        chain_dest = sym_dest.parent / orig_link
                        hops = 0
                        while chain_dest in symlink_targets and hops < 10:
                            chain_dest = chain_dest.parent / symlink_targets[chain_dest]
                            hops += 1
                        if hops >= 10 or not is_safe_subpath(tmp_path, chain_dest.resolve()):
                            raise SecurityValidationError(
                                "SYMLINK_ESCAPE_IN_ARCHIVE",
                                f"Archive symlink chain for '{sym_dest.name}' escapes root or forms excessive loop.",
                            )

                    tar.extractall(path=tmp_path, filter="data" if hasattr(tarfile, "data_filter") else None)

            except SecurityValidationError:
                raise
            except Exception as exc:
                raise RuntimeError(f"Failed to extract revision '{git_ref}' ({sha}): {exc}") from exc
            finally:
                if spool_path.exists():
                    try:
                        spool_path.unlink()
                    except OSError:
                        pass

            req = ScanRequest(
                source_type=SourceType.LOCAL,
                target=str(tmp_path),
                limits=scan_limits,
            )
            analysis = run_repository_analysis(req)
            analysis.target_display = f"{self.repo_path.name} @ {git_ref} ({sha[:8]})"
            return analysis, sha, False
