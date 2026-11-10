"""Historical Architecture Snapshot Engine.

Extracts and analyzes immutable architectural snapshots from Git commit history
without modifying or checking out the user's active working tree.
"""

from __future__ import annotations

import os
import re
import subprocess
import tarfile
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from repodna.brain.indexer import SymbolIndexer
from repodna.core.analyzer import run_repository_analysis
from repodna.history.cache import HistoricalCache
from repodna.history.models import (
    SNAPSHOT_SCHEMA_VERSION,
    HistoricalCouplingMetrics,
    HistoricalCycle,
    HistoricalDependencyEdge,
    HistoricalEvidenceItem,
    HistoricalHealthMetrics,
    HistoricalLanguageSummary,
    HistoricalModuleSummary,
    HistoricalSnapshot,
)
from repodna.schemas.models import (
    AnalysisResult,
    ScanLimits,
    ScanRequest,
    SourceType,
)
from repodna.security.validators import (
    SecurityValidationError,
    is_safe_subpath,
)

SAFE_GIT_REF_PATTERN = re.compile(r"^[a-zA-Z0-9_\-.~^/]+$")
WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


class ShallowCloneLimitationError(SecurityValidationError):
    """Raised when an operation cannot proceed due to shallow Git clone limits."""


class HistoricalSnapshotEngine:
    """Read-only engine that constructs deterministic architectural snapshots of Git commits."""

    def __init__(
        self,
        repo_path: Path | str,
        cache_dir: Path | str | None = None,
        limits: ScanLimits | None = None,
    ) -> None:
        self.repo_path = Path(repo_path).resolve()
        if not (self.repo_path / ".git").exists():
            raise ValueError(f"Directory '{self.repo_path}' is not a valid Git repository.")

        self.limits = limits or ScanLimits()
        default_cache = self.repo_path / ".repodna" / "cache" / "historical"
        self.cache = HistoricalCache(cache_dir or default_cache)
        self.repo_identity = self._resolve_repo_identity()

    def _resolve_repo_identity(self) -> str:
        """Determines canonical repository identity from origin URL or root directory hash."""
        cmd = ["git", "-C", str(self.repo_path), "config", "--get", "remote.origin.url"]
        try:
            url = subprocess.check_output(
                cmd, stderr=subprocess.PIPE, text=True, timeout=5.0
            ).strip()
            if url:
                # Normalize git URL
                clean_url = url.rstrip("/").removesuffix(".git")
                return clean_url
        except Exception:
            pass
        # Fallback to repository root directory name
        return self.repo_path.name

    def is_shallow_repository(self) -> bool:
        """Returns True if the repository is a shallow clone (--depth)."""
        cmd = ["git", "-C", str(self.repo_path), "rev-parse", "--is-shallow-repository"]
        try:
            out = subprocess.check_output(
                cmd, stderr=subprocess.PIPE, text=True, timeout=5.0
            ).strip()
            return out.lower() == "true"
        except Exception:
            return False

    def resolve_commit(self, git_ref: str) -> tuple[str, list[str], str, str, str]:
        """
        Resolves git_ref to (commit_sha, parent_shas, author, iso_timestamp, message).
        Guarantees reference syntax security and verifies the commit exists.
        """
        ref = git_ref.strip()
        if not SAFE_GIT_REF_PATTERN.match(ref) or ref.startswith("-"):
            raise SecurityValidationError(
                "INVALID_GIT_REF", f"Invalid git reference syntax: '{ref}'"
            )

        # 1. Verify revision actually resolves to a valid commit object
        verify_cmd = [
            "git",
            "-C",
            str(self.repo_path),
            "rev-parse",
            "--verify",
            "--quiet",
            f"{ref}^{{commit}}",
        ]
        try:
            sha = subprocess.check_output(
                verify_cmd, stderr=subprocess.PIPE, text=True, timeout=5.0
            ).strip()
            if not sha or len(sha) != 40:
                raise SecurityValidationError(
                    "UNKNOWN_GIT_REF", f"Git commit revision '{ref}' not found."
                )
        except subprocess.CalledProcessError as exc:
            if self.is_shallow_repository():
                raise ShallowCloneLimitationError(
                    "SHALLOW_CLONE_LIMITATION",
                    f"Commit '{ref}' not found in shallow repository. Run 'git fetch --unshallow' to fetch full history.",
                ) from exc
            raise SecurityValidationError(
                "UNKNOWN_GIT_REF", f"Git commit revision '{ref}' not found."
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise SecurityValidationError(
                "GIT_TIMEOUT", f"Timeout verifying git revision '{ref}'."
            ) from exc

        # 2. Extract commit metadata using ASCII Unit Separator (%x1f)
        log_cmd = [
            "git",
            "-C",
            str(self.repo_path),
            "log",
            "-1",
            "--format=%H%x1f%P%x1f%an%x1f%cI%x1f%s",
            sha,
            "--",
        ]
        try:
            out = subprocess.check_output(
                log_cmd, stderr=subprocess.PIPE, text=True, timeout=10.0
            ).strip()
            parts = out.split("\x1f", 4)
            if len(parts) == 5:
                commit_sha = parts[0]
                parents = parts[1].split() if parts[1] else []
                author = parts[2]
                iso_date = parts[3]
                subject = parts[4]
                return commit_sha, parents, author, iso_date, subject
            return sha, [], "unknown", "", ""
        except Exception as exc:
            raise ValueError(f"Failed to extract metadata for commit '{sha}': {exc}") from exc

    def create_snapshot(
        self,
        git_ref: str,
        use_cache: bool = True,
        config_fingerprint: str = "default-v1",
    ) -> HistoricalSnapshot:
        """
        Creates an immutable HistoricalSnapshot at git_ref.
        Uses cached snapshot if available; otherwise securely extracts archive and analyzes.
        The user's working tree is never checked out or modified.
        """
        commit_sha, parent_shas, author, iso_date, subject = self.resolve_commit(git_ref)
        analyzer_ver = "0.6.0"

        cache_key = HistoricalCache.generate_key(
            repo_identity=self.repo_identity,
            commit_sha=commit_sha,
            analyzer_version=analyzer_ver,
            config_fingerprint=config_fingerprint,
        )

        if use_cache:
            cached = self.cache.get(cache_key)
            if cached is not None:
                return cached

        # Perform cold analysis via secure git archive extraction
        is_shallow = self.is_shallow_repository()
        limitations: list[str] = []
        if is_shallow:
            limitations.append("Repository is a shallow clone; commit history is truncated.")

        analysis, evidence_items, lfs_limitations = self._extract_and_analyze(commit_sha)
        limitations.extend(lfs_limitations)

        # Build HistoricalSnapshot
        snapshot = self._build_historical_snapshot(
            commit_sha=commit_sha,
            parent_shas=parent_shas,
            author=author,
            iso_date=iso_date,
            subject=subject,
            analyzer_version=analyzer_ver,
            analysis=analysis,
            evidence_items=evidence_items,
            limitations=limitations,
            is_shallow=is_shallow,
        )

        # Store in cache
        self.cache.put(cache_key, snapshot, config_fingerprint=config_fingerprint)
        return snapshot

    def _extract_and_analyze(
        self,
        commit_sha: str,
    ) -> tuple[AnalysisResult, list[HistoricalEvidenceItem], list[str]]:
        """Extracts tar archive of commit_sha into sandboxed tempdir and runs analysis."""
        limits = self.limits
        lfs_detected: list[str] = []

        with tempfile.TemporaryDirectory(prefix="repodna_hist_") as tmp_dir:
            tmp_path = Path(tmp_dir).resolve()
            archive_cmd = ["git", "-C", str(self.repo_path), "archive", "--format=tar", commit_sha]
            spool_file = tempfile.NamedTemporaryFile(
                prefix="repodna_htmp_", suffix=".tar", delete=False
            )
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
                    if total_stream_bytes > limits.max_total_size_bytes:
                        proc.kill()
                        proc.wait()
                        raise SecurityValidationError(
                            "MAX_SIZE_EXCEEDED",
                            f"Git archive stream size ({total_stream_bytes} bytes) exceeds limit of {limits.max_total_size_bytes} bytes.",
                        )
                    spool_file.write(chunk)

                spool_file.flush()
                spool_file.close()

                _, stderr_data = proc.communicate(timeout=15.0)
                if proc.returncode != 0:
                    err_msg = stderr_data.decode("utf-8", errors="replace")
                    raise RuntimeError(f"git archive failed (code {proc.returncode}): {err_msg}")

                # Security inspection of tar members before extraction
                total_bytes = 0
                total_files = 0
                symlink_targets: dict[Path, str] = {}
                extract_members: list[tarfile.TarInfo] = []

                with tarfile.open(spool_path, mode="r:*") as tar:
                    for member in tar.getmembers():
                        # 1. Skip submodules (gitlink entries typically have mode 0o160000 or type DIR with empty content)
                        # Tar doesn't have a direct gitlink type, but submodule folders in git archive appear as empty directories or skipped
                        if not (member.isreg() or member.isdir() or member.issym()):
                            continue

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
                                f"Historical archive member '{member.name}' attempts path traversal.",
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
                                    f"Historical symlink '{member.name}' -> '{linkname}' has absolute or UNC target.",
                                )
                            link_dest = (member_dest.parent / linkname).resolve()
                            if not is_safe_subpath(tmp_path, link_dest):
                                raise SecurityValidationError(
                                    "SYMLINK_ESCAPE_IN_ARCHIVE",
                                    f"Historical symlink '{member.name}' -> '{linkname}' escapes root.",
                                )
                            symlink_targets[member_dest] = linkname

                        total_files += 1
                        total_bytes += member.size

                        if total_files > limits.max_files:
                            raise SecurityValidationError(
                                "MAX_FILES_EXCEEDED",
                                f"Historical archive contains {total_files} files, exceeding limit {limits.max_files}.",
                            )
                        if total_bytes > limits.max_total_size_bytes:
                            raise SecurityValidationError(
                                "MAX_SIZE_EXCEEDED",
                                f"Historical archive uncompressed size exceeds limit of {limits.max_total_size_bytes} bytes.",
                            )

                        extract_members.append(member)

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
                                f"Historical symlink chain for '{sym_dest.name}' escapes root or forms excessive loop.",
                            )

                    # Safe extraction
                    tar.extractall(
                        path=tmp_path,
                        members=extract_members,
                        filter="data" if hasattr(tarfile, "data_filter") else None,
                    )

                # 6. Post-extraction check for Git LFS pointer files
                for fpath in tmp_path.rglob("*"):
                    if fpath.is_file() and fpath.stat().st_size <= 500:
                        try:
                            sample = fpath.read_bytes()
                            if sample.startswith(b"version https://git-lfs.github.com/spec/v1"):
                                rel = fpath.relative_to(tmp_path).as_posix()
                                lfs_detected.append(
                                    f"Git LFS pointer detected for '{rel}'; pointer file skipped from AST analysis."
                                )
                                # Replace with dummy comment so AST parser doesn't choke on pointer
                                fpath.write_text("# git-lfs-pointer-unsmudged\n", encoding="utf-8")
                        except Exception:
                            pass

            finally:
                if spool_path.exists():
                    try:
                        spool_path.unlink()
                    except OSError:
                        pass

            # Run RepoDNA analysis on extracted tree
            scan_req = ScanRequest(
                source_type=SourceType.LOCAL,
                target=str(tmp_path),
                limits=limits,
            )
            analysis = run_repository_analysis(scan_req)
            analysis.target_display = f"{self.repo_identity} @ {commit_sha[:8]}"

            # Run SymbolIndexer to capture symbols and evidence ledger
            indexer = SymbolIndexer(
                root_path=tmp_path,
                revision=commit_sha,
                analysis=analysis,
            )
            indexer.index_all()

            # Transform ledger evidence items into HistoricalEvidenceItem
            raw_evidence = indexer.ledger.get_all()
            evidence_items: list[HistoricalEvidenceItem] = []
            for ev in raw_evidence:
                evidence_items.append(
                    HistoricalEvidenceItem(
                        evidence_id=ev.evidence_id,
                        commit_sha=commit_sha,
                        file_path=ev.file_path,
                        line_start=ev.line_start,
                        line_end=ev.line_end,
                        evidence_type=ev.evidence_type.value,
                        symbol_name=ev.symbol_name,
                        code_snippet=ev.code_snippet or "",
                        content_hash=ev.content_hash or "",
                        support_level=ev.support_level.value,
                        snapshot_identity=f"git:{commit_sha}",
                    )
                )

            return analysis, evidence_items, lfs_detected

    def _build_historical_snapshot(
        self,
        commit_sha: str,
        parent_shas: list[str],
        author: str,
        iso_date: str,
        subject: str,
        analyzer_version: str,
        analysis: AnalysisResult,
        evidence_items: list[HistoricalEvidenceItem],
        limitations: list[str],
        is_shallow: bool,
    ) -> HistoricalSnapshot:
        """Assembles the final HistoricalSnapshot model."""
        # Modules
        modules: list[HistoricalModuleSummary] = []
        coupling: dict[str, HistoricalCouplingMetrics] = {}
        for f in analysis.files:
            modules.append(
                HistoricalModuleSummary(
                    path=f.id,
                    name=f.name,
                    language=f.language,
                    lines_code=f.lines_code,
                    fan_in=f.fan_in,
                    fan_out=f.fan_out,
                    instability=f.instability,
                    is_hub=f.is_hub,
                    in_cycle=f.in_cycle,
                    symbol_count=len(f.symbols),
                )
            )
            coupling[f.id] = HistoricalCouplingMetrics(
                fan_in=f.fan_in,
                fan_out=f.fan_out,
                instability=f.instability,
            )

        # Dependencies
        dependencies: list[HistoricalDependencyEdge] = []
        for e in analysis.edges:
            dependencies.append(
                HistoricalDependencyEdge(
                    source=e.source,
                    target=e.target,
                    import_names=e.import_names,
                    is_dynamic=False,
                )
            )

        # Cycles
        cycles: list[HistoricalCycle] = []
        for c in analysis.cycles:
            cycles.append(
                HistoricalCycle(
                    id=c.id,
                    nodes=c.nodes,
                    length=c.length,
                    severity=c.severity,
                    description=c.description,
                )
            )

        # Languages
        languages: dict[str, HistoricalLanguageSummary] = {}
        if analysis.languages:
            for l_sum in analysis.languages:
                languages[l_sum.language] = HistoricalLanguageSummary(
                    files_count=l_sum.file_count,
                    lines_code=l_sum.lines_code,
                    percentage=l_sum.percentage_of_code,
                )

        # Health
        hr = analysis.health_report
        penalties: dict[str, float] = {}
        for cat in hr.category_scores:
            if cat.score is not None and cat.score < 100.0:
                penalties[cat.category] = round(100.0 - cat.score, 1)

        health = HistoricalHealthMetrics(
            score=hr.overall_score,
            grade=hr.grade,
            status=hr.status,
            penalties=penalties,
        )

        # Add any skipped file caveats
        for sf in analysis.transparency.skipped_files:
            limitations.append(f"Skipped file '{sf.path}': {sf.reason}")

        return HistoricalSnapshot(
            schema_version=SNAPSHOT_SCHEMA_VERSION,
            commit_sha=commit_sha,
            parent_shas=parent_shas,
            repo_identity=self.repo_identity,
            commit_timestamp=iso_date,
            commit_author=author,
            commit_message=subject,
            analyzed_at=datetime.now(UTC).isoformat(),
            analyzer_version=analyzer_version,
            total_files=analysis.total_files,
            total_lines_code=analysis.total_lines_code,
            ast_loc_coverage_pct=analysis.transparency.ast_loc_coverage_pct,
            languages=languages,
            modules=modules,
            dependencies=dependencies,
            cycles=cycles,
            coupling=coupling,
            health=health,
            findings=hr.findings,
            evidence=evidence_items,
            limitations=limitations,
            is_shallow=is_shallow,
            cache_hit=False,
        )
