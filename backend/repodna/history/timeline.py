"""Historical Architecture Timeline Engine.

Traces architectural progression and health evolution across a sequence of Git commits.
"""

from __future__ import annotations

import subprocess
import threading

from repodna.history.engine import HistoricalSnapshotEngine
from repodna.history.models import (
    SNAPSHOT_SCHEMA_VERSION,
    TimelineEntry,
    TimelineResult,
)


class TimelineEngine:
    """Computes historical architectural progression across commit sequences."""

    def __init__(self, engine: HistoricalSnapshotEngine) -> None:
        self.engine = engine

    def get_commit_list(self, limit: int = 30) -> list[str]:
        """Queries Git for the most recent commit SHAs on current HEAD."""
        cmd = [
            "git",
            "-C",
            str(self.engine.repo_path),
            "log",
            f"-n{max(1, min(limit, 200))}",
            "--format=%H",
        ]
        try:
            out = subprocess.check_output(cmd, stderr=subprocess.PIPE, text=True, timeout=10.0)
            return [line.strip() for line in out.splitlines() if line.strip()]
        except Exception:
            return []

    def build_timeline(
        self,
        commits: list[str] | None = None,
        limit: int = 30,
        cancel_event: threading.Event | None = None,
    ) -> TimelineResult:
        """
        Builds chronological architectural timeline for the specified commits or recent history.
        Uses cached snapshots for lightning-fast incremental retrieval.
        """
        commit_shas = commits or self.get_commit_list(limit=limit)
        # Reverse to chronological order (oldest to newest)
        chronological_shas = list(reversed(commit_shas))

        entries: list[TimelineEntry] = []
        for sha in chronological_shas:
            if cancel_event is not None and cancel_event.is_set():
                raise InterruptedError("Timeline generation cancelled by user request.")
            try:
                snap = self.engine.create_snapshot(sha, use_cache=True)
                entries.append(
                    TimelineEntry(
                        commit_sha=snap.commit_sha,
                        commit_timestamp=snap.commit_timestamp,
                        commit_author=snap.commit_author,
                        commit_message=snap.commit_message,
                        status="success",
                        total_files=snap.total_files,
                        total_lines_code=snap.total_lines_code,
                        health_score=snap.health.score,
                        health_grade=snap.health.grade,
                        cycles_count=len(snap.cycles),
                        modules_count=len(snap.modules),
                        ast_coverage_pct=snap.ast_loc_coverage_pct,
                        cache_hit=snap.cache_hit,
                    )
                )
            except Exception as exc:
                # Failure is never silently dropped: record explicit failed entry with commit metadata
                author = "unknown"
                iso_ts = ""
                subject = f"Failed to analyze commit: {exc}"
                try:
                    cmd = [
                        "git",
                        "-C",
                        str(self.engine.repo_path),
                        "log",
                        "-1",
                        "--format=%an%x00%aI%x00%s",
                        sha,
                    ]
                    raw_meta = subprocess.check_output(
                        cmd, stderr=subprocess.PIPE, text=True, timeout=5.0
                    ).strip()
                    parts = raw_meta.split("\x00")
                    if len(parts) >= 3:
                        author, iso_ts, subject = parts[0], parts[1], parts[2]
                except Exception:
                    pass

                entries.append(
                    TimelineEntry(
                        commit_sha=sha,
                        commit_timestamp=iso_ts,
                        commit_author=author,
                        commit_message=subject,
                        status="failed",
                        error_message=str(exc),
                        total_files=0,
                        total_lines_code=0,
                        health_score=None,
                        health_grade="N/A",
                        cycles_count=0,
                        modules_count=0,
                        ast_coverage_pct=0.0,
                        cache_hit=False,
                    )
                )

        successful_commits = sum(1 for e in entries if e.status == "success")
        failed_commits = sum(1 for e in entries if e.status == "failed")
        missing_commits = [e.commit_sha for e in entries if e.status == "failed"]

        summary_text = self._format_timeline_summary(entries)

        return TimelineResult(
            schema_version=SNAPSHOT_SCHEMA_VERSION,
            repo_identity=self.engine.repo_identity,
            total_commits=len(entries),
            successful_commits=successful_commits,
            failed_commits=failed_commits,
            missing_commits=missing_commits,
            entries=entries,
            summary_text=summary_text,
        )

    def _format_timeline_summary(self, entries: list[TimelineEntry]) -> str:
        lines = [
            "=" * 84,
            f"RepoDNA Architecture Timeline — {self.engine.repo_identity} ({len(entries)} commits)",
            "=" * 84,
            f"{'COMMIT':<10} | {'DATE':<12} | {'AUTHOR':<16} | {'STATUS':<7} | {'FILES':<6} | {'HEALTH':<7} | {'CYCLES':<6}",
            "-" * 84,
        ]
        for e in entries:
            dt_short = e.commit_timestamp[:10] if e.commit_timestamp else "N/A"
            author_short = e.commit_author[:16]
            status_disp = e.status.upper()
            if e.status == "failed":
                lines.append(
                    f"{e.commit_sha[:10]:<10} | {dt_short:<12} | {author_short:<16} | {status_disp:<7} | {'FAIL':<6} | {'N/A':<7} | {'N/A':<6} -> {e.error_message}"
                )
            else:
                health_disp = (
                    f"{e.health_score:.1f} ({e.health_grade})"
                    if e.health_score is not None
                    else "N/A"
                )
                lines.append(
                    f"{e.commit_sha[:10]:<10} | {dt_short:<12} | {author_short:<16} | {status_disp:<7} | {e.total_files:<6} | {health_disp:<7} | {e.cycles_count:<6}"
                )
        lines.append("=" * 84)
        return "\n".join(lines)
