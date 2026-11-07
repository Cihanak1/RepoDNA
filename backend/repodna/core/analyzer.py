"""Core repository intelligence orchestrator with limits, timeout, cancellation, and progress hooks."""

from __future__ import annotations

import os
import time
import uuid
from collections import defaultdict
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from repodna.git_insights.analyzer import analyze_git_history
from repodna.graph.engine import build_dependency_graph
from repodna.parsers.base import ParsedFileData, detect_language
from repodna.parsers.resolver import ImportResolver
from repodna.parsers.treesitter_parser import get_parser_engine_summary, parse_source_file
from repodna.rules.health import evaluate_architecture_health
from repodna.schemas.models import (
    AnalysisResult,
    FileNode,
    GitCommitSummary,
    GitHotspot,
    GitInsights,
    LanguageBreakdownItem,
    LanguageSupportLevel,
    ScanLimits,
    ScanRequest,
    ScanStatus,
    SkippedItem,
    SourceType,
    SymbolItem,
    TransparencyReport,
    UnresolvedReference,
)
from repodna.security.validators import (
    SENSITIVE_FILENAMES,
    is_safe_subpath,
    scan_line_for_secrets,
    validate_local_directory,
)
from repodna.storage.workspace import clone_github_repo_safely

ProgressCallback = Callable[[ScanStatus, str, float, int, int], None]

IGNORED_DIRS = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "dist",
    "build",
    "out",
    "coverage",
    ".next",
    ".nuxt",
    "target",
    "vendor",
    ".idea",
    ".vscode",
    "playwright-report",
    "test-results",
    ".repodna_tmp",
}

BINARY_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".ico",
    ".svg",
    ".pdf",
    ".zip",
    ".tar",
    ".gz",
    ".7z",
    ".rar",
    ".exe",
    ".dll",
    ".so",
    ".dylib",
    ".wasm",
    ".pyc",
    ".pyo",
    ".pyd",
    ".class",
    ".jar",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
    ".mp3",
    ".mp4",
    ".webm",
    ".db",
    ".sqlite",
    ".sqlite3",
    ".lockb",
    ".tsbuildinfo",
}

IGNORED_LOCKFILES = {
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "poetry.lock",
    "cargo.lock",
    "uv.lock",
    "composer.lock",
    "gemfile.lock",
}


class ScanCancelledError(RuntimeError):
    """Raised when a scan is cancelled by the user."""


class ScanTimeoutError(TimeoutError):
    """Raised when a scan exceeds its configured timeout_seconds."""


def run_repository_analysis(
    request: ScanRequest,
    on_progress: ProgressCallback | None = None,
    is_cancelled: Callable[[], bool] | None = None,
) -> AnalysisResult:
    """Execute end-to-end static architectural analysis on a local directory, GitHub URL, or demo dataset."""
    start_monotonic = time.monotonic()

    def notify(status: ScanStatus, msg: str, pct: float, disc: int = 0, proc: int = 0) -> None:
        if on_progress:
            on_progress(status, msg, pct, disc, proc)

    if request.source_type == SourceType.DEMO or request.target.strip().lower() == "demo":
        notify(ScanStatus.COMPLETED, "Loaded labeled Demo Repository dataset.", 100.0, 10, 10)
        return build_labeled_demo_analysis()

    if request.source_type == SourceType.GITHUB:
        notify(ScanStatus.CLONING, f"Validating and cloning GitHub repository {request.target}...", 8.0, 0, 0)
        with clone_github_repo_safely(
            request.target,
            branch=request.branch,
            timeout_seconds=min(request.limits.timeout_seconds, 60.0),
            is_cancelled=is_cancelled,
        ) as (cloned_path, repo_display_name, canonical_url):
            return _analyze_directory_internal(
                root_path=cloned_path,
                repo_name=repo_display_name,
                source_type=SourceType.GITHUB,
                target_display=canonical_url,
                limits=request.limits,
                start_monotonic=start_monotonic,
                notify=notify,
                is_cancelled=is_cancelled,
            )

    # Local directory scan
    resolved_root = validate_local_directory(request.target)
    repo_name = resolved_root.name or str(resolved_root)
    return _analyze_directory_internal(
        root_path=resolved_root,
        repo_name=repo_name,
        source_type=SourceType.LOCAL,
        target_display=str(resolved_root),
        limits=request.limits,
        start_monotonic=start_monotonic,
        notify=notify,
        is_cancelled=is_cancelled,
    )


def _check_abort(
    start_monotonic: float,
    limits: ScanLimits,
    is_cancelled: Callable[[], bool] | None,
) -> None:
    if is_cancelled and is_cancelled():
        raise ScanCancelledError("Analysis cancelled by user request.")
    elapsed = time.monotonic() - start_monotonic
    if elapsed > limits.timeout_seconds:
        raise ScanTimeoutError(
            f"Analysis exceeded configured timeout limit of {limits.timeout_seconds:.1f}s."
        )


def _is_binary_bytes(sample: bytes) -> bool:
    if not sample:
        return False
    if b"\x00" in sample:
        return True
    return False


def _analyze_directory_internal(
    root_path: Path,
    repo_name: str,
    source_type: SourceType,
    target_display: str,
    limits: ScanLimits,
    start_monotonic: float,
    notify: Callable[[ScanStatus, str, float, int, int], None],
    is_cancelled: Callable[[], bool] | None,
) -> AnalysisResult:
    notify(ScanStatus.DISCOVERING, f"Discovering files in {repo_name}...", 15.0, 0, 0)

    discovered_files: list[tuple[Path, str, int]] = []  # (abs_path, rel_posix_id, size_bytes)
    skipped_items: list[SkippedItem] = []
    truncated = False
    truncation_reason: str | None = None
    cumulative_bytes = 0

    # Walk directory deterministically without following symlinks
    stack: list[Path] = [root_path]
    while stack:
        _check_abort(start_monotonic, limits, is_cancelled)
        current_dir = stack.pop()
        try:
            entries = sorted(os.scandir(current_dir), key=lambda e: e.name.lower())
        except OSError as exc:
            rel_err = current_dir.relative_to(root_path).as_posix() if current_dir != root_path else "."
            skipped_items.append(SkippedItem(path=rel_err, reason="permission_or_io_error", detail=str(exc)))
            continue

        subdirs_to_visit: list[Path] = []
        for entry in entries:
            _check_abort(start_monotonic, limits, is_cancelled)
            entry_path = Path(entry.path)
            try:
                rel_posix = entry_path.relative_to(root_path).as_posix()
            except ValueError:
                continue

            # Symlink & traversal guard
            try:
                if entry.is_symlink() or not is_safe_subpath(root_path, entry_path):
                    skipped_items.append(
                        SkippedItem(
                            path=rel_posix,
                            reason="symlink_blocked",
                            detail="Symbolic links and external junctions are blocked for security.",
                        )
                    )
                    continue
            except OSError:
                continue

            if entry.is_dir(follow_symlinks=False):
                if entry.name in IGNORED_DIRS or (entry.name.startswith(".") and entry.name not in {".github"}):
                    continue
                subdirs_to_visit.append(entry_path)
            elif entry.is_file(follow_symlinks=False):
                if entry.name.lower() in IGNORED_LOCKFILES:
                    skipped_items.append(
                        SkippedItem(
                            path=rel_posix,
                            reason="lockfile_skipped",
                            detail=f"Skipped generated dependency lockfile '{entry.name}'.",
                        )
                    )
                    continue
                ext = entry_path.suffix.lower()
                if ext in BINARY_EXTENSIONS:
                    skipped_items.append(
                        SkippedItem(
                            path=rel_posix,
                            reason="binary_file",
                            detail=f"Skipped binary/media extension '{ext}'.",
                        )
                    )
                    continue

                try:
                    fsize = entry.stat(follow_symlinks=False).st_size
                except OSError:
                    continue

                if fsize > limits.max_file_size_bytes:
                    skipped_items.append(
                        SkippedItem(
                            path=rel_posix,
                            reason="file_size_limit",
                            detail=f"File size ({fsize:,} B) exceeds max_file_size_bytes ({limits.max_file_size_bytes:,} B).",
                        )
                    )
                    continue

                if len(discovered_files) >= limits.max_files:
                    truncated = True
                    truncation_reason = f"Reached max_files limit ({limits.max_files:,} files)."
                    break

                if cumulative_bytes + fsize > limits.max_total_size_bytes:
                    truncated = True
                    truncation_reason = f"Reached max_total_size_bytes limit ({limits.max_total_size_bytes:,} B)."
                    break

                cumulative_bytes += fsize
                discovered_files.append((entry_path, rel_posix, fsize))

        if truncated:
            break

        # Push in reverse order so alphabetical order is popped first
        for d in reversed(subdirs_to_visit):
            stack.append(d)

    total_discovered = len(discovered_files)
    notify(
        ScanStatus.PARSING,
        f"Parsing AST and imports across {total_discovered} files...",
        30.0,
        total_discovered,
        0,
    )

    parsed_map: dict[str, ParsedFileData] = {}
    file_nodes: list[FileNode] = []
    all_file_ids: set[str] = {rel_id for _, rel_id, _ in discovered_files}

    for idx, (abs_path, rel_id, fsize) in enumerate(discovered_files):
        _check_abort(start_monotonic, limits, is_cancelled)
        if idx % 15 == 0 or idx == total_discovered - 1:
            pct = 30.0 + (idx / max(1, total_discovered)) * 35.0
            notify(
                ScanStatus.PARSING,
                f"Parsing {rel_id} ({idx + 1}/{total_discovered})...",
                round(pct, 1),
                total_discovered,
                idx + 1,
            )

        fname = abs_path.name
        ext = abs_path.suffix.lower()
        parent_dir = str(Path(rel_id).parent.as_posix())
        if parent_dir == ".":
            parent_dir = ""

        secret_warnings: list[str] = []
        if fname.lower() in SENSITIVE_FILENAMES:
            secret_warnings.append(f"Sensitive filename '{fname}' present in repository")

        try:
            with abs_path.open("rb") as fh:
                raw_bytes = fh.read(limits.max_file_size_bytes)
        except OSError as exc:
            skipped_items.append(SkippedItem(path=rel_id, reason="read_error", detail=str(exc)))
            all_file_ids.discard(rel_id)
            continue

        if _is_binary_bytes(raw_bytes[:4096]):
            skipped_items.append(
                SkippedItem(path=rel_id, reason="binary_file", detail="Detected null bytes in file header.")
            )
            all_file_ids.discard(rel_id)
            continue

        content = raw_bytes.decode("utf-8", errors="replace")

        # Scan lines for credential patterns without storing or returning raw secrets
        if fname.lower() not in SENSITIVE_FILENAMES and "test" not in rel_id.lower():
            for line_idx, line_str in enumerate(content.splitlines()[:1000], start=1):
                line_warnings = scan_line_for_secrets(line_str, line_idx)
                if line_warnings:
                    secret_warnings.extend(line_warnings)
                    if len(secret_warnings) >= 5:
                        break

        # If it is a sensitive file (like .env), do not parse its contents for AST
        if fname.lower() in SENSITIVE_FILENAMES:
            lang, sup, _ = detect_language(fname, ext)
            lines_count = len(content.splitlines())
            pdata = ParsedFileData(
                language=lang,
                support_level=sup,
                lines_total=lines_count,
                lines_code=lines_count,
                lines_comment=0,
                lines_blank=0,
                parser_used="redacted_sensitive_file",
            )
        else:
            pdata = parse_source_file(fname, ext, content)

        parsed_map[rel_id] = pdata
        file_nodes.append(
            FileNode(
                id=rel_id,
                name=fname,
                directory=parent_dir,
                extension=ext,
                language=pdata.language,
                support_level=pdata.support_level,
                size_bytes=fsize,
                lines_total=pdata.lines_total,
                lines_code=pdata.lines_code,
                lines_comment=pdata.lines_comment,
                lines_blank=pdata.lines_blank,
                symbols=pdata.symbols,
                secret_warnings=secret_warnings,
            )
        )

    # Resolve imports and construct dependency graph
    _check_abort(start_monotonic, limits, is_cancelled)
    notify(
        ScanStatus.BUILDING_GRAPH,
        "Resolving module imports and computing Tarjan SCC dependency graph...",
        70.0,
        len(file_nodes),
        len(file_nodes),
    )

    resolver = ImportResolver(all_file_ids)
    raw_edges: list[tuple[str, str, list[str], int]] = []
    unresolved_internal_count = 0
    dynamic_imports_count = 0

    for fnode in file_nodes:
        pdata = parsed_map[fnode.id]
        if not pdata.raw_imports:
            continue
        resolved_pairs, ext_pkgs, unres_list = resolver.resolve_for_file(
            source_file_id=fnode.id,
            language=fnode.language,
            raw_imports=pdata.raw_imports,
        )
        fnode.imports_external = ext_pkgs
        fnode.unresolved_imports = unres_list
        for u in unres_list:
            if u.reason == "dynamic_import":
                dynamic_imports_count += 1
            else:
                unresolved_internal_count += 1

        for target_id, raw_imp in resolved_pairs:
            raw_edges.append((fnode.id, target_id, raw_imp.imported_names, raw_imp.line))

    edges, cycles, graph_metrics = build_dependency_graph(file_nodes, raw_edges)

    # Analyze Git history
    _check_abort(start_monotonic, limits, is_cancelled)
    notify(
        ScanStatus.ANALYZING_GIT,
        "Inspecting Git commit history and file churn hotspots...",
        82.0,
        len(file_nodes),
        len(file_nodes),
    )
    git_insights = analyze_git_history(
        repo_root=root_path,
        files=file_nodes,
        timeout_seconds=min(15.0, limits.timeout_seconds * 0.3),
    )

    # Evaluate Explainable Architecture Health Rules
    _check_abort(start_monotonic, limits, is_cancelled)
    notify(
        ScanStatus.EVALUATING_RULES,
        "Evaluating rule-based Architecture Health Report...",
        92.0,
        len(file_nodes),
        len(file_nodes),
    )
    health_report = evaluate_architecture_health(file_nodes, edges, cycles, graph_metrics)

    # Aggregate language distribution and transparency report
    lang_agg: dict[str, dict[str, int | LanguageSupportLevel]] = defaultdict(
        lambda: {
            "support_level": LanguageSupportLevel.UNSUPPORTED,
            "file_count": 0,
            "lines_code": 0,
            "lines_total": 0,
            "size_bytes": 0,
        }
    )
    total_loc = sum(f.lines_code for f in file_nodes)
    total_lines_all = sum(f.lines_total for f in file_nodes)
    total_size = sum(f.size_bytes for f in file_nodes)

    supported_langs: set[str] = set()
    unsupported_langs: set[str] = set()
    unsupported_files_count = 0

    for f in file_nodes:
        item = lang_agg[f.language]
        item["support_level"] = f.support_level
        item["file_count"] = int(item["file_count"]) + 1
        item["lines_code"] = int(item["lines_code"]) + f.lines_code
        item["lines_total"] = int(item["lines_total"]) + f.lines_total
        item["size_bytes"] = int(item["size_bytes"]) + f.size_bytes

        if f.support_level == LanguageSupportLevel.UNSUPPORTED:
            unsupported_langs.add(f.language)
            unsupported_files_count += 1
        else:
            supported_langs.add(f.language)

    languages_list: list[LanguageBreakdownItem] = []
    for lang_name, stats in sorted(lang_agg.items(), key=lambda kv: int(kv[1]["lines_code"]), reverse=True):
        loc_val = int(stats["lines_code"])
        pct_val = round((loc_val / total_loc) * 100.0, 1) if total_loc > 0 else 0.0
        languages_list.append(
            LanguageBreakdownItem(
                language=lang_name,
                support_level=stats["support_level"],  # type: ignore[arg-type]
                file_count=int(stats["file_count"]),
                lines_code=loc_val,
                lines_total=int(stats["lines_total"]),
                size_bytes=int(stats["size_bytes"]),
                percentage_of_code=pct_val,
            )
        )

    transparency = TransparencyReport(
        supported_languages_detected=sorted(supported_langs),
        unsupported_languages_detected=sorted(unsupported_langs),
        unsupported_files_count=unsupported_files_count,
        unresolved_internal_imports_count=unresolved_internal_count,
        dynamic_imports_count=dynamic_imports_count,
        skipped_files=skipped_items[:100],
        truncated_by_limits=truncated,
        truncation_reason=truncation_reason,
        parser_engine_info=get_parser_engine_summary(),
    )

    duration_ms = max(1, int((time.monotonic() - start_monotonic) * 1000))
    notify(ScanStatus.COMPLETED, "Analysis completed.", 100.0, len(file_nodes), len(file_nodes))

    return AnalysisResult(
        analysis_id=str(uuid.uuid4()),
        repo_name=repo_name,
        source_type=source_type,
        target_display=target_display,
        is_demo=False,
        analyzed_at=datetime.now(UTC),
        duration_ms=duration_ms,
        total_files=len(file_nodes),
        total_lines_code=total_loc,
        total_lines_all=total_lines_all,
        total_size_bytes=total_size,
        languages=languages_list,
        files=file_nodes,
        edges=edges,
        cycles=cycles,
        graph_metrics=graph_metrics,
        health_report=health_report,
        git_insights=git_insights,
        transparency=transparency,
    )


def build_labeled_demo_analysis() -> AnalysisResult:
    """
    Construct an explicitly labeled Demo dataset (`is_demo=True`, `source_type=SourceType.DEMO`)
    showcasing a multi-language architecture with a realistic circular dependency and git churn.
    """
    demo_files: list[FileNode] = [
        FileNode(
            id="src/api/router.py",
            name="router.py",
            directory="src/api",
            extension=".py",
            language="Python",
            support_level=LanguageSupportLevel.FULL_AST,
            size_bytes=4820,
            lines_total=145,
            lines_code=118,
            lines_comment=12,
            lines_blank=15,
            imports_external=["fastapi", "pydantic"],
            symbols=[
                SymbolItem(name="create_api_router", kind="function", line=18),
                SymbolItem(name="OrderEndpoint", kind="class", line=52),
            ],
            git_commits=19,
            git_last_author="Cihan Akalın",
            git_last_modified="2026-11-05",
        ),
        FileNode(
            id="src/services/order_service.py",
            name="order_service.py",
            directory="src/services",
            extension=".py",
            language="Python",
            support_level=LanguageSupportLevel.FULL_AST,
            size_bytes=18400,
            lines_total=540,
            lines_code=475,
            lines_comment=25,
            lines_blank=40,
            imports_external=["sqlalchemy", " structlog"],
            symbols=[
                SymbolItem(name="OrderService", kind="class", line=24),
                SymbolItem(name="reconcile_invoice", kind="function", line=310),
            ],
            git_commits=34,
            git_last_author="Cihan Akalın",
            git_last_modified="2026-11-06",
        ),
        FileNode(
            id="src/services/payment_gateway.py",
            name="payment_gateway.py",
            directory="src/services",
            extension=".py",
            language="Python",
            support_level=LanguageSupportLevel.FULL_AST,
            size_bytes=9200,
            lines_total=260,
            lines_code=215,
            lines_comment=20,
            lines_blank=25,
            imports_external=["httpx"],
            unresolved_imports=[
                UnresolvedReference(
                    source_file="src/services/payment_gateway.py",
                    raw_import="import_module(provider_plugin_name)",
                    line=142,
                    reason="dynamic_import",
                )
            ],
            symbols=[
                SymbolItem(name="PaymentGateway", kind="class", line=19),
                SymbolItem(name="authorize_charge", kind="function", line=88),
            ],
            git_commits=27,
            git_last_author="Cihan Akalın",
            git_last_modified="2026-11-04",
        ),
        FileNode(
            id="src/domain/models.py",
            name="models.py",
            directory="src/domain",
            extension=".py",
            language="Python",
            support_level=LanguageSupportLevel.FULL_AST,
            size_bytes=6100,
            lines_total=190,
            lines_code=160,
            lines_comment=10,
            lines_blank=20,
            imports_external=["pydantic"],
            symbols=[
                SymbolItem(name="Order", kind="class", line=14),
                SymbolItem(name="PaymentReceipt", kind="class", line=78),
            ],
            git_commits=14,
            git_last_author="Cihan Akalın",
            git_last_modified="2026-11-01",
        ),
        FileNode(
            id="src/ui/CheckoutPanel.tsx",
            name="CheckoutPanel.tsx",
            directory="src/ui",
            extension=".tsx",
            language="TypeScript (TSX)",
            support_level=LanguageSupportLevel.FULL_AST,
            size_bytes=7300,
            lines_total=210,
            lines_code=180,
            lines_comment=10,
            lines_blank=20,
            imports_external=["react"],
            symbols=[SymbolItem(name="CheckoutPanel", kind="function", line=22)],
            git_commits=12,
            git_last_author="Cihan Akalın",
            git_last_modified="2026-11-05",
        ),
        FileNode(
            id="src/ui/apiClient.ts",
            name="apiClient.ts",
            directory="src/ui",
            extension=".ts",
            language="TypeScript",
            support_level=LanguageSupportLevel.FULL_AST,
            size_bytes=3400,
            lines_total=98,
            lines_code=82,
            lines_comment=6,
            lines_blank=10,
            imports_external=[],
            symbols=[SymbolItem(name="submitOrder", kind="function", line=15)],
            git_commits=8,
            git_last_author="Cihan Akalın",
            git_last_modified="2026-11-02",
        ),
        FileNode(
            id="scripts/legacy_migration.rb",
            name="legacy_migration.rb",
            directory="scripts",
            extension=".rb",
            language="Ruby",
            support_level=LanguageSupportLevel.UNSUPPORTED,
            size_bytes=1950,
            lines_total=64,
            lines_code=50,
            lines_comment=6,
            lines_blank=8,
            git_commits=2,
            git_last_author="Cihan Akalın",
            git_last_modified="2026-10-19",
        ),
    ]

    # Intentional circular dependency between order_service.py <-> payment_gateway.py
    raw_edges = [
        ("src/api/router.py", "src/services/order_service.py", ["OrderService"], 10),
        ("src/api/router.py", "src/domain/models.py", ["Order"], 11),
        ("src/services/order_service.py", "src/services/payment_gateway.py", ["PaymentGateway"], 14),
        ("src/services/payment_gateway.py", "src/services/order_service.py", ["reconcile_invoice"], 18),
        ("src/services/order_service.py", "src/domain/models.py", ["Order", "PaymentReceipt"], 12),
        ("src/services/payment_gateway.py", "src/domain/models.py", ["PaymentReceipt"], 9),
        ("src/ui/CheckoutPanel.tsx", "src/ui/apiClient.ts", ["submitOrder"], 6),
    ]

    edges, cycles, graph_metrics = build_dependency_graph(demo_files, raw_edges)
    health_report = evaluate_architecture_health(demo_files, edges, cycles, graph_metrics)

    total_loc = sum(f.lines_code for f in demo_files)
    total_lines_all = sum(f.lines_total for f in demo_files)
    total_size = sum(f.size_bytes for f in demo_files)

    languages = [
        LanguageBreakdownItem(
            language="Python",
            support_level=LanguageSupportLevel.FULL_AST,
            file_count=4,
            lines_code=968,
            lines_total=1135,
            size_bytes=38520,
            percentage_of_code=round(968 / total_loc * 100, 1),
        ),
        LanguageBreakdownItem(
            language="TypeScript (TSX)",
            support_level=LanguageSupportLevel.FULL_AST,
            file_count=1,
            lines_code=180,
            lines_total=210,
            size_bytes=7300,
            percentage_of_code=round(180 / total_loc * 100, 1),
        ),
        LanguageBreakdownItem(
            language="TypeScript",
            support_level=LanguageSupportLevel.FULL_AST,
            file_count=1,
            lines_code=82,
            lines_total=98,
            size_bytes=3400,
            percentage_of_code=round(82 / total_loc * 100, 1),
        ),
        LanguageBreakdownItem(
            language="Ruby",
            support_level=LanguageSupportLevel.UNSUPPORTED,
            file_count=1,
            lines_code=50,
            lines_total=64,
            size_bytes=1950,
            percentage_of_code=round(50 / total_loc * 100, 1),
        ),
    ]

    git_insights = GitInsights(
        is_git_repo=True,
        default_branch="main",
        total_commits_scanned=42,
        unique_contributors=3,
        first_commit_date="2026-09-12",
        latest_commit_date="2026-11-06",
        recent_commits=[
            GitCommitSummary(
                sha="a84f29c",
                author="Cihan Akalın",
                date="2026-11-06",
                subject="feat(orders): add idempotent invoice reconciliation hook",
            ),
            GitCommitSummary(
                sha="71e0b12",
                author="Cihan Akalın",
                date="2026-11-05",
                subject="fix(gateway): handle retry timeout on payment authorization",
            ),
        ],
        hotspots=[
            GitHotspot(
                path="src/services/order_service.py",
                commits=34,
                authors_count=2,
                lines_code=475,
                churn_risk_score=91.0,
            ),
            GitHotspot(
                path="src/services/payment_gateway.py",
                commits=27,
                authors_count=2,
                lines_code=215,
                churn_risk_score=63.0,
            ),
        ],
        bus_factor_estimate=1,
        note="Explicitly labeled Demo Mode dataset. Select a local folder or GitHub URL above to run live analysis.",
    )

    transparency = TransparencyReport(
        supported_languages_detected=["Python", "TypeScript", "TypeScript (TSX)"],
        unsupported_languages_detected=["Ruby"],
        unsupported_files_count=1,
        unresolved_internal_imports_count=0,
        dynamic_imports_count=1,
        skipped_files=[],
        truncated_by_limits=False,
        parser_engine_info=get_parser_engine_summary(),
    )

    return AnalysisResult(
        analysis_id="demo-showcase-001",
        repo_name="acme-commerce-platform (DEMO MODE)",
        source_type=SourceType.DEMO,
        target_display="demo://acme-commerce-platform",
        is_demo=True,
        analyzed_at=datetime.now(UTC),
        duration_ms=18,
        total_files=len(demo_files),
        total_lines_code=total_loc,
        total_lines_all=total_lines_all,
        total_size_bytes=total_size,
        languages=languages,
        files=demo_files,
        edges=edges,
        cycles=cycles,
        graph_metrics=graph_metrics,
        health_report=health_report,
        git_insights=git_insights,
        transparency=transparency,
    )
