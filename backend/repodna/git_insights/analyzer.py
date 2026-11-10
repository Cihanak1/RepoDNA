"""Git repository history, churn hotspots, and bus-factor analyzer."""

from __future__ import annotations

import hashlib
import math
import os
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

from repodna.schemas.models import FileNode, GitCommitSummary, GitHotspot, GitInsights


def analyze_git_history(
    repo_root: Path,
    files: list[FileNode],
    timeout_seconds: float = 15.0,
) -> GitInsights:
    """
    Inspect local Git metadata safely using read-only git commands.

    Methodology & Boundaries:
    - Scans up to the most recent 250 commits on HEAD using `--no-optional-locks` and `core.quotepath=false`.
    - Churn Risk Score = `commits * log10(max(10, lines_code))`, highlighting files that are both
      frequently modified and structurally large.
    - Bus Factor Estimate = minimum number of unique commit authors accounting for >= 50% of scanned commits.
    """
    git_dir = repo_root / ".git"
    if not git_dir.exists():
        path_hash = hashlib.sha256(repo_root.as_posix().encode("utf-8")).hexdigest()[:12]
        return GitInsights(
            is_git_repo=False,
            commit_sha=None,
            is_dirty=False,
            dirty_files_count=0,
            verification_status="UNVERIFIED_NON_GIT",
            snapshot_identity=f"directory:{path_hash}",
            source_type="directory",
            note="Directory is not a Git repository (.git folder not present). Git churn metrics skipped.",
        )

    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_OPTIONAL_LOCKS"] = "0"

    def run_git(args: list[str]) -> str | None:
        try:
            proc = subprocess.run(
                [
                    "git",
                    "--no-optional-locks",
                    "-c",
                    "core.quotepath=false",
                    "-c",
                    f"safe.directory={repo_root.as_posix()}",
                    "-C",
                    str(repo_root),
                    *args,
                ],
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
                timeout=max(3.0, min(timeout_seconds, 20.0)),
                check=False,
            )
            if proc.returncode != 0:
                return None
            return proc.stdout
        except (OSError, subprocess.SubprocessError):
            return None

    branch_out = run_git(["rev-parse", "--abbrev-ref", "HEAD"])
    default_branch = branch_out.strip() if branch_out else None

    # Resolve immutable full 40-character commit SHA
    head_sha_raw = run_git(["rev-parse", "HEAD"])
    commit_sha: str | None = None
    if head_sha_raw:
        sha_cand = head_sha_raw.strip()
        if len(sha_cand) == 40 and all(c in "0123456789abcdefABCDEF" for c in sha_cand):
            commit_sha = sha_cand.lower()

    # Detect dirty working tree status safely
    status_raw = run_git(["status", "--porcelain"])
    dirty_lines = [line for line in (status_raw or "").splitlines() if line.strip()]
    is_dirty = len(dirty_lines) > 0
    dirty_count = len(dirty_lines)

    if commit_sha:
        verification_status = "VERIFIED_DIRTY" if is_dirty else "VERIFIED_CLEAN"
        snapshot_identity = f"git:{commit_sha}{'+dirty' if is_dirty else ''}"
    else:
        path_hash = hashlib.sha256(repo_root.as_posix().encode("utf-8")).hexdigest()[:12]
        verification_status = "UNVERIFIED_NON_GIT"
        snapshot_identity = f"directory:{path_hash}"

    # Use ASCII Unit Separator (%x1f) to avoid collisions with '|' in author names or commit subjects
    log_raw = run_git(
        [
            "log",
            "-n",
            "250",
            "--date=short",
            "--pretty=format:__COMMIT__%h%x1f%an%x1f%ad%x1f%s",
            "--name-only",
        ]
    )
    if not log_raw or not log_raw.strip():
        return GitInsights(
            is_git_repo=True,
            default_branch=default_branch,
            commit_sha=commit_sha,
            is_dirty=is_dirty,
            dirty_files_count=dirty_count,
            verification_status=verification_status,
            snapshot_identity=snapshot_identity,
            source_type="git",
            note="Git repository initialized, but no commit history found.",
        )

    recent_commits: list[GitCommitSummary] = []
    author_commit_counts: Counter[str] = Counter()
    file_commit_counts: Counter[str] = Counter()
    file_authors: dict[str, set[str]] = defaultdict(set)
    file_last_author: dict[str, str] = {}
    file_last_date: dict[str, str] = {}

    current_author = "unknown"
    current_date = ""
    total_commits = 0
    first_date: str | None = None
    latest_date: str | None = None

    for raw_line in log_raw.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("__COMMIT__"):
            payload = line.removeprefix("__COMMIT__")
            parts = payload.split("\x1f", 3)
            if len(parts) == 4:
                sha, author, date_str, subject = parts
                current_author = author.strip() or "unknown"
                current_date = date_str.strip()
                total_commits += 1
                author_commit_counts[current_author] += 1
                if latest_date is None:
                    latest_date = current_date
                first_date = current_date
                if len(recent_commits) < 10:
                    recent_commits.append(
                        GitCommitSummary(
                            sha=sha.strip(),
                            author=current_author,
                            date=current_date,
                            subject=subject.strip()[:120],
                        )
                    )
        else:
            norm_path = line.replace("\\", "/").lstrip("/").strip('"')
            file_commit_counts[norm_path] += 1
            file_authors[norm_path].add(current_author)
            if norm_path not in file_last_author:
                file_last_author[norm_path] = current_author
                file_last_date[norm_path] = current_date

    hotspots: list[GitHotspot] = []
    for f in files:
        c_count = file_commit_counts.get(f.id, 0)
        f.git_commits = c_count
        f.git_last_author = file_last_author.get(f.id)
        f.git_last_modified = file_last_date.get(f.id)
        if c_count > 0:
            churn_score = round(c_count * math.log10(max(10, f.lines_code)), 2)
            hotspots.append(
                GitHotspot(
                    path=f.id,
                    commits=c_count,
                    authors_count=len(file_authors.get(f.id, set())),
                    lines_code=f.lines_code,
                    churn_risk_score=churn_score,
                )
            )

    hotspots.sort(key=lambda h: (h.churn_risk_score, h.commits, h.lines_code, h.path), reverse=True)

    bus_factor = 1
    if total_commits > 0 and author_commit_counts:
        running = 0
        bus_factor = 0
        for _, count in author_commit_counts.most_common():
            running += count
            bus_factor += 1
            if running >= total_commits * 0.5:
                break

    return GitInsights(
        is_git_repo=True,
        default_branch=default_branch,
        commit_sha=commit_sha,
        is_dirty=is_dirty,
        dirty_files_count=dirty_count,
        verification_status=verification_status,
        snapshot_identity=snapshot_identity,
        source_type="git",
        total_commits_scanned=total_commits,
        unique_contributors=len(author_commit_counts),
        first_commit_date=first_date,
        latest_commit_date=latest_date,
        recent_commits=recent_commits,
        hotspots=hotspots[:12],
        bus_factor_estimate=max(1, bus_factor),
    )
