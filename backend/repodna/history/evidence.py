"""Historical Evidence Provider.

Provides safe, read-only extraction of code content directly from Git commit history
without touching the current working tree or filesystem.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

from repodna.brain.evidence import extract_evidence_snippet, normalize_text_newlines
from repodna.brain.models import StalenessReason
from repodna.history.models import HistoricalEvidenceItem
from repodna.security.validators import SecurityValidationError

COMMIT_SHA_PATTERN = re.compile(r"^[0-9a-fA-F]{40}$")
SAFE_POSIX_PATH_PATTERN = re.compile(r"^[a-zA-Z0-9_\-./]+$")


class HistoricalEvidenceProvider:
    """Safe, read-only historical blob reader directly querying Git object database."""

    def __init__(self, repo_path: Path | str) -> None:
        self.repo_path = Path(repo_path).resolve()
        if not (self.repo_path / ".git").exists():
            raise ValueError(f"Directory '{self.repo_path}' is not a valid Git repository.")

    def read_historical_file(
        self,
        commit_sha: str,
        file_path: str,
        max_bytes: int = 5 * 1024 * 1024,  # 5 MB safety limit
    ) -> str:
        """
        Safely reads the contents of a file at a specific historical commit SHA.
        Guarantees:
        - Commit SHA is validated (40-character hex)
        - File path is strictly POSIX relative with traversal prevention
        - Blob size is checked before retrieval to prevent memory exhaustion
        - Uses argument lists without shell execution
        """
        norm_sha = commit_sha.strip().lower()
        if not COMMIT_SHA_PATTERN.match(norm_sha):
            raise SecurityValidationError(
                "INVALID_COMMIT_SHA", f"Invalid commit SHA: '{commit_sha}'"
            )

        norm_path = file_path.replace("\\", "/").strip().lstrip("/")
        if (
            not norm_path
            or ".." in norm_path
            or norm_path.startswith("/")
            or (len(norm_path) > 1 and norm_path[1] == ":")
            or not SAFE_POSIX_PATH_PATTERN.match(norm_path)
        ):
            raise SecurityValidationError(
                "INVALID_FILE_PATH", f"Invalid or unsafe historical file path: '{file_path}'"
            )

        # 1. Query blob size via git cat-file -s
        size_cmd = ["git", "-C", str(self.repo_path), "cat-file", "-s", f"{norm_sha}:{norm_path}"]
        try:
            size_out = subprocess.check_output(
                size_cmd, stderr=subprocess.PIPE, text=True, timeout=5.0
            ).strip()
            blob_size = int(size_out)
            if blob_size > max_bytes:
                raise SecurityValidationError(
                    "MAX_FILE_SIZE_EXCEEDED",
                    f"Historical file '{norm_path}' ({blob_size} bytes) exceeds limit of {max_bytes} bytes.",
                )
        except subprocess.CalledProcessError as exc:
            # File might not exist in that commit
            err_msg = (
                exc.stderr
                if isinstance(exc.stderr, str)
                else (exc.stderr or b"").decode("utf-8", "replace")
            )
            raise FileNotFoundError(
                f"File '{norm_path}' not found at commit {norm_sha}: {err_msg.strip()}"
            ) from exc
        except (subprocess.TimeoutExpired, ValueError) as exc:
            raise RuntimeError(
                f"Failed to inspect historical file size for '{norm_path}': {exc}"
            ) from exc

        # 2. Read blob content via git show <sha>:<path>
        show_cmd = ["git", "-C", str(self.repo_path), "show", f"{norm_sha}:{norm_path}"]
        env = os.environ.copy()
        env["GIT_TERMINAL_PROMPT"] = "0"
        env["GIT_OPTIONAL_LOCKS"] = "0"

        try:
            proc = subprocess.run(
                show_cmd,
                capture_output=True,
                check=True,
                timeout=10.0,
                env=env,
            )
            return proc.stdout.decode("utf-8", errors="replace")
        except subprocess.CalledProcessError as exc:
            raise FileNotFoundError(
                f"Failed to read historical file '{norm_path}' at commit {norm_sha}"
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise TimeoutError(
                f"Timed out reading historical file '{norm_path}' at commit {norm_sha}"
            ) from exc

    def verify_evidence_at_commit(
        self,
        evidence: HistoricalEvidenceItem,
    ) -> tuple[bool, StalenessReason, str]:
        """
        Verifies that a historical evidence citation matches the exact code snippet
        and content hash at its recorded commit.
        """
        try:
            content = self.read_historical_file(evidence.commit_sha, evidence.file_path)
            norm_content = normalize_text_newlines(content)
            lines = norm_content.splitlines()

            if not lines:
                return False, StalenessReason.FILE_DELETED, "File is empty in historical commit."

            snippet_now, hash_now = extract_evidence_snippet(
                norm_content, evidence.line_start, evidence.line_end
            )

            if hash_now == evidence.content_hash:
                return True, StalenessReason.FRESH, "Verified exact match at recorded coordinates."

            # Check if snippet shifted within file
            if evidence.code_snippet and evidence.code_snippet in norm_content:
                return (
                    False,
                    StalenessReason.LINE_SHIFT,
                    "Exact snippet found at different line coordinates.",
                )

            return (
                False,
                StalenessReason.CONTENT_CHANGED,
                "Snippet modified or not found at recorded coordinates.",
            )

        except FileNotFoundError:
            return False, StalenessReason.FILE_DELETED, "File does not exist in recorded commit."
        except Exception as exc:
            return False, StalenessReason.CONTENT_CHANGED, f"Verification error: {exc}"
