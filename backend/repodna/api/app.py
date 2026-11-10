"""FastAPI application providing synchronous and asynchronous repository analysis and report exports."""

from __future__ import annotations

import logging
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel

from repodna import __version__
from repodna.brain.indexer import SymbolIndexer
from repodna.brain.models import (
    EvidenceLedgerResponse,
    EvidenceReference,
    EvidenceType,
    SearchResponse,
    SymbolQueryResponse,
    SymbolTraceResult,
)
from repodna.brain.retrieval import SmartRetrievalEngine
from repodna.brain.tracer import AmbiguousSymbolError, SymbolTracer
from repodna.context.builder import AgentContextBuilder
from repodna.context.models import AgentContextResponse
from repodna.contract.loader import find_contract_file, load_contract_file
from repodna.contract.models import ArchitectureContract, ContractMode
from repodna.core.analyzer import (
    ScanCancelledError,
    ScanTimeoutError,
    run_repository_analysis,
)
from repodna.diff.snapshot import SnapshotManager
from repodna.guardian.engine import PRArchitectureGuardian
from repodna.guardian.models import GuardianReport
from repodna.parsers.treesitter_parser import get_parser_engine_summary
from repodna.passport.generator import (
    generate_repository_passport,
    generate_repository_passport_v2,
)
from repodna.passport.migrator import migrate_v1_to_v2
from repodna.passport.models import (
    RepositoryPassport,
    RepositoryPassportV2,
)
from repodna.passport.validator import validate_passport_json
from repodna.reports.exporter import export_analysis_to_html, export_analysis_to_json
from repodna.schemas.models import (
    AnalysisResult,
    ScanProgress,
    ScanRequest,
    ScanStatus,
)
from repodna.security.validators import SecurityValidationError, validate_local_directory

logger = logging.getLogger("repodna.api")

app = FastAPI(
    title="RepoDNA API",
    description="Developer Repository Intelligence Platform — Static AST Dependency Graph & Explainable Architecture Health API.",
    version=__version__,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# In-memory bounded job & result store
_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="repodna_worker")
_LOCK = threading.Lock()
_JOBS: dict[str, ScanProgress] = {}
_CANCEL_FLAGS: dict[str, threading.Event] = {}
_JOB_RESULTS: dict[str, AnalysisResult] = {}
_RESULTS_BY_ID: dict[str, AnalysisResult] = {}
_INDEXERS_BY_ID: dict[str, SymbolIndexer] = {}
_MAX_STORED_RESULTS = 25


def _store_result(result: AnalysisResult, job_id: str | None = None) -> None:
    with _LOCK:
        if len(_RESULTS_BY_ID) >= _MAX_STORED_RESULTS:
            oldest_key = next(iter(_RESULTS_BY_ID))
            _RESULTS_BY_ID.pop(oldest_key, None)
            _INDEXERS_BY_ID.pop(oldest_key, None)
        _RESULTS_BY_ID[result.analysis_id] = result
        if job_id:
            _JOB_RESULTS[job_id] = result


def _complete_job_atomically(job_id: str, result: AnalysisResult) -> None:
    """
    Atomically persist the analysis result in `_JOB_RESULTS` / `_RESULTS_BY_ID` AND
    transition `_JOBS[job_id]` to `ScanStatus.COMPLETED` under a single `_LOCK` acquisition.
    This guarantees that no reader can ever observe `status == COMPLETED` before `_JOB_RESULTS[job_id]` exists.
    """
    with _LOCK:
        if len(_RESULTS_BY_ID) >= _MAX_STORED_RESULTS:
            oldest_key = next(iter(_RESULTS_BY_ID))
            _RESULTS_BY_ID.pop(oldest_key, None)
            _INDEXERS_BY_ID.pop(oldest_key, None)
        _RESULTS_BY_ID[result.analysis_id] = result
        _JOB_RESULTS[job_id] = result
        curr = _JOBS.get(job_id)
        if curr and curr.status not in (ScanStatus.CANCELLED, ScanStatus.FAILED):
            _JOBS[job_id] = curr.model_copy(
                update={
                    "status": ScanStatus.COMPLETED,
                    "phase_message": "Analysis complete.",
                    "progress_percent": 100.0,
                    "files_discovered": result.total_files,
                    "files_processed": result.total_files,
                    "updated_at": datetime.now(UTC),
                }
            )


def _get_or_create_indexer_for_analysis(analysis_id: str) -> tuple[SymbolIndexer, AnalysisResult]:
    """Retrieves or builds the SymbolIndexer for an existing AnalysisResult."""
    with _LOCK:
        res = _RESULTS_BY_ID.get(analysis_id)
    if not res:
        raise HTTPException(
            status_code=404,
            detail={"code": "ANALYSIS_NOT_FOUND", "message": f"Analysis '{analysis_id}' not found."},
        )

    with _LOCK:
        if analysis_id in _INDEXERS_BY_ID:
            return _INDEXERS_BY_ID[analysis_id], res

    target_path = Path(res.target_display)
    root = target_path if (target_path.exists() and target_path.is_dir()) else Path(".")
    git_rev = res.git_insights.default_branch or "HEAD"
    indexer = SymbolIndexer(root_path=root, revision=git_rev, analysis=res)
    indexer.index_all()

    with _LOCK:
        _INDEXERS_BY_ID[analysis_id] = indexer

    return indexer, res



class DirectoryEntryItem(BaseModel):
    name: str
    path: str
    is_git_repo: bool


class DirectoryBrowseResponse(BaseModel):
    current_path: str
    parent_path: str | None
    directories: list[DirectoryEntryItem]


@app.get("/api/health")
def get_health() -> dict[str, Any]:
    return {
        "status": "ok",
        "version": __version__,
        "parsers": get_parser_engine_summary(),
        "default_workspace": str(Path.cwd().resolve()),
    }


@app.post("/api/scan", response_model=AnalysisResult)
def scan_repository_sync(request: ScanRequest) -> AnalysisResult:
    """Run an immediate repository scan and return the full AnalysisResult."""
    try:
        result = run_repository_analysis(request)
        _store_result(result)
        return result
    except SecurityValidationError as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": exc.code, "message": exc.message},
        ) from exc
    except ScanTimeoutError as exc:
        raise HTTPException(
            status_code=408,
            detail={"code": "SCAN_TIMEOUT", "message": str(exc)},
        ) from exc
    except ScanCancelledError as exc:
        raise HTTPException(
            status_code=499,
            detail={"code": "SCAN_CANCELLED", "message": str(exc)},
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected error during repository scan")
        raise HTTPException(
            status_code=500,
            detail={"code": "INTERNAL_SCAN_ERROR", "message": f"Analysis failed: {exc}"},
        ) from exc


@app.post("/api/jobs", response_model=ScanProgress, status_code=202)
def start_scan_job(request: ScanRequest) -> ScanProgress:
    """Launch an asynchronous repository analysis job with progress & cancellation support."""
    # Pre-validate target immediately so security errors return 400 synchronously
    try:
        if request.source_type.value == "local":
            validate_local_directory(request.target)
        elif request.source_type.value == "github":
            from repodna.security.validators import validate_git_branch, validate_github_url

            validate_github_url(request.target)
            validate_git_branch(request.branch)
    except SecurityValidationError as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": exc.code, "message": exc.message},
        ) from exc

    job_id = str(uuid.uuid4())
    now = datetime.now(UTC)
    progress = ScanProgress(
        job_id=job_id,
        status=ScanStatus.QUEUED,
        phase_message="Job queued for analysis...",
        progress_percent=2.0,
        started_at=now,
        updated_at=now,
    )
    cancel_event = threading.Event()

    with _LOCK:
        _JOBS[job_id] = progress
        _CANCEL_FLAGS[job_id] = cancel_event

    def update_progress(
        status: ScanStatus,
        msg: str,
        pct: float,
        discovered: int,
        processed: int,
    ) -> None:
        # Never allow an intermediate progress callback to publish a terminal state before `_complete_job_atomically`
        non_terminal_status = (
            ScanStatus.EVALUATING_RULES
            if status in (ScanStatus.COMPLETED, ScanStatus.FAILED, ScanStatus.CANCELLED)
            else status
        )
        bounded_pct = min(99.0, max(0.0, pct))
        with _LOCK:
            curr = _JOBS.get(job_id)
            if curr and curr.status not in (
                ScanStatus.COMPLETED,
                ScanStatus.CANCELLED,
                ScanStatus.FAILED,
            ):
                _JOBS[job_id] = curr.model_copy(
                    update={
                        "status": non_terminal_status,
                        "phase_message": msg,
                        "progress_percent": bounded_pct,
                        "files_discovered": discovered,
                        "files_processed": processed,
                        "updated_at": datetime.now(UTC),
                    }
                )

    def worker() -> None:
        try:
            res = run_repository_analysis(
                request=request,
                on_progress=update_progress,
                is_cancelled=cancel_event.is_set,
            )
            _complete_job_atomically(job_id=job_id, result=res)
        except ScanCancelledError as exc:
            with _LOCK:
                curr = _JOBS.get(job_id)
                if curr:
                    _JOBS[job_id] = curr.model_copy(
                        update={
                            "status": ScanStatus.CANCELLED,
                            "phase_message": str(exc),
                            "error_code": "SCAN_CANCELLED",
                            "error_message": str(exc),
                            "updated_at": datetime.now(UTC),
                        }
                    )
        except SecurityValidationError as exc:
            with _LOCK:
                curr = _JOBS.get(job_id)
                if curr:
                    _JOBS[job_id] = curr.model_copy(
                        update={
                            "status": ScanStatus.FAILED,
                            "phase_message": exc.message,
                            "error_code": exc.code,
                            "error_message": exc.message,
                            "updated_at": datetime.now(UTC),
                        }
                    )
        except ScanTimeoutError as exc:
            with _LOCK:
                curr = _JOBS.get(job_id)
                if curr:
                    _JOBS[job_id] = curr.model_copy(
                        update={
                            "status": ScanStatus.FAILED,
                            "phase_message": str(exc),
                            "error_code": "SCAN_TIMEOUT",
                            "error_message": str(exc),
                            "updated_at": datetime.now(UTC),
                        }
                    )
        except Exception as exc:
            logger.exception("Background job %s failed", job_id)
            with _LOCK:
                curr = _JOBS.get(job_id)
                if curr:
                    _JOBS[job_id] = curr.model_copy(
                        update={
                            "status": ScanStatus.FAILED,
                            "phase_message": f"Unexpected error: {exc}",
                            "error_code": "INTERNAL_SCAN_ERROR",
                            "error_message": str(exc),
                            "updated_at": datetime.now(UTC),
                        }
                    )

    _EXECUTOR.submit(worker)
    return progress


@app.get("/api/jobs/{job_id}", response_model=ScanProgress)
def get_scan_job_progress(job_id: str) -> ScanProgress:
    with _LOCK:
        job = _JOBS.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail={"code": "JOB_NOT_FOUND", "message": "Scan job not found."})
        return job.model_copy()


@app.post("/api/jobs/{job_id}/cancel", response_model=ScanProgress)
def cancel_scan_job(job_id: str) -> ScanProgress:
    with _LOCK:
        job = _JOBS.get(job_id)
        cancel_ev = _CANCEL_FLAGS.get(job_id)
        if not job or not cancel_ev:
            raise HTTPException(status_code=404, detail={"code": "JOB_NOT_FOUND", "message": "Scan job not found."})
        cancel_ev.set()
        if job.status not in (ScanStatus.COMPLETED, ScanStatus.FAILED):
            job = job.model_copy(
                update={
                    "status": ScanStatus.CANCELLED,
                    "phase_message": "Cancellation requested by user.",
                    "error_code": "SCAN_CANCELLED",
                    "error_message": "Scan cancelled by user.",
                    "updated_at": datetime.now(UTC),
                }
            )
            _JOBS[job_id] = job
        return job.model_copy()


@app.get("/api/jobs/{job_id}/result", response_model=AnalysisResult)
def get_scan_job_result(job_id: str) -> AnalysisResult:
    with _LOCK:
        job = _JOBS.get(job_id)
        res = _JOB_RESULTS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail={"code": "JOB_NOT_FOUND", "message": "Scan job not found."})
    if job.status != ScanStatus.COMPLETED or not res:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "RESULT_NOT_READY",
                "message": f"Job is currently in status '{job.status.value}'.",
            },
        )
    return res


@app.get("/api/analyses/{analysis_id}/export/json")
def export_json_endpoint(analysis_id: str) -> Response:
    with _LOCK:
        res = _RESULTS_BY_ID.get(analysis_id)
    if not res:
        raise HTTPException(status_code=404, detail={"code": "ANALYSIS_NOT_FOUND", "message": "Analysis not found."})
    payload = export_analysis_to_json(res, indent=2)
    safe_name = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in res.repo_name)
    return Response(
        content=payload,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="repodna-{safe_name}.json"'},
    )


@app.get("/api/analyses/{analysis_id}/export/html")
def export_html_endpoint(analysis_id: str) -> HTMLResponse:
    with _LOCK:
        res = _RESULTS_BY_ID.get(analysis_id)
    if not res:
        raise HTTPException(status_code=404, detail={"code": "ANALYSIS_NOT_FOUND", "message": "Analysis not found."})
    html_doc = export_analysis_to_html(res)
    safe_name = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in res.repo_name)
    return HTMLResponse(
        content=html_doc,
        headers={"Content-Disposition": f'attachment; filename="repodna-{safe_name}.html"'},
    )


@app.get("/api/fs/browse", response_model=DirectoryBrowseResponse)
def browse_local_directories(
    path: str | None = Query(default=None, description="Directory path to list subdirectories for selection."),
) -> DirectoryBrowseResponse:
    """
    Safe directory-only browser used strictly when the user opens the folder selector modal.
    Does not scan or read any files.
    """
    target_str = path.strip() if path and path.strip() else str(Path.cwd().resolve())
    try:
        resolved = validate_local_directory(target_str)
    except SecurityValidationError as exc:
        raise HTTPException(status_code=400, detail={"code": exc.code, "message": exc.message}) from exc

    parent_path: str | None = None
    if resolved.parent != resolved and resolved.parent.parent != resolved.parent:
        parent_path = str(resolved.parent)

    dirs: list[DirectoryEntryItem] = []
    try:
        for entry in sorted(resolved.iterdir(), key=lambda p: p.name.lower()):
            if entry.name.startswith(".") or entry.is_symlink():
                continue
            try:
                if entry.is_dir():
                    is_git = (entry / ".git").exists()
                    dirs.append(
                        DirectoryEntryItem(
                            name=entry.name,
                            path=str(entry.resolve()),
                            is_git_repo=is_git,
                        )
                    )
            except OSError:
                continue
    except OSError as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": "DIRECTORY_READ_ERROR", "message": f"Cannot list directory: {exc}"},
        ) from exc

    return DirectoryBrowseResponse(
        current_path=str(resolved),
        parent_path=parent_path,
        directories=dirs[:100],
    )


class GuardianAssessRequest(BaseModel):
    target: str = "."
    base_ref: str = "HEAD~1"
    head_ref: str = "HEAD"
    mode: str | None = None


@app.get("/api/analyses/{analysis_id}/passport", response_model=RepositoryPassport)
def get_analysis_passport(
    analysis_id: str,
    max_modules: int = Query(default=150, ge=10, le=2000),
) -> RepositoryPassport:
    """Returns the portable Repository Passport manifest for an existing analysis."""
    with _LOCK:
        res = _RESULTS_BY_ID.get(analysis_id)
    if not res:
        raise HTTPException(status_code=404, detail={"code": "ANALYSIS_NOT_FOUND", "message": "Analysis not found."})

    contract = None
    target_path = Path(res.target_display)
    if target_path.exists() and target_path.is_dir():
        c_file = find_contract_file(target_path)
        if c_file:
            try:
                contract = load_contract_file(c_file)
            except Exception:
                pass

    return generate_repository_passport(
        analysis=res,
        git_revision=res.git_insights.default_branch or "HEAD",
        contract=contract,
        max_modules=max_modules,
    )


@app.get("/api/contract", response_model=ArchitectureContract)
def get_architecture_contract(
    path: str = Query(default=".", description="Target repository path to locate .repodna/architecture.yml"),
) -> ArchitectureContract:
    """Returns the parsed ArchitectureContract if .repodna/architecture.yml exists."""
    try:
        resolved = validate_local_directory(path)
    except SecurityValidationError as exc:
        raise HTTPException(status_code=400, detail={"code": exc.code, "message": exc.message}) from exc

    c_file = find_contract_file(resolved)
    if not c_file:
        raise HTTPException(
            status_code=404,
            detail={"code": "CONTRACT_NOT_FOUND", "message": "No architecture contract found in repository."},
        )

    try:
        return load_contract_file(c_file)
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "CONTRACT_INVALID", "message": f"Failed to parse contract: {exc}"},
        ) from exc


@app.post("/api/guardian/assess", response_model=GuardianReport)
def assess_architecture_guardian(request: GuardianAssessRequest) -> GuardianReport:
    """Evaluates architectural drift and contract policies between two Git revisions."""
    try:
        resolved = validate_local_directory(request.target)
    except SecurityValidationError as exc:
        raise HTTPException(status_code=400, detail={"code": exc.code, "message": exc.message}) from exc

    try:
        snap_mgr = SnapshotManager(resolved)
        base_analysis, base_sha, base_is_wt = snap_mgr.create_snapshot(request.base_ref)
        head_analysis, head_sha, head_is_wt = snap_mgr.create_snapshot(request.head_ref)
        git_renames = snap_mgr.find_git_renames(request.base_ref, request.head_ref)
    except SecurityValidationError as exc:
        raise HTTPException(status_code=400, detail={"code": exc.code, "message": exc.message}) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail={"code": "GIT_SNAPSHOT_ERROR", "message": str(exc)}) from exc

    contract = None
    c_file = find_contract_file(resolved)
    if c_file and c_file.exists():
        try:
            contract = load_contract_file(c_file)
        except Exception:
            pass

    mode_override = ContractMode(request.mode) if request.mode else None
    guardian = PRArchitectureGuardian(contract=contract, mode_override=mode_override)
    return guardian.assess(
        base_analysis=base_analysis,
        head_analysis=head_analysis,
        base_ref=request.base_ref,
        head_ref=request.head_ref,
        base_commit_sha=base_sha,
        head_commit_sha=head_sha,
        base_is_working_tree=base_is_wt,
        head_is_working_tree=head_is_wt,
        git_renames=git_renames,
    )


# -----------------------------------------------------------------------------
# Repository Brain & Code Intelligence Endpoints (Phase 3)
# -----------------------------------------------------------------------------


class BrainSearchRequest(BaseModel):
    query: str
    limit: int = 15
    kind: str | None = None
    path_filter: str | None = None
    language: str | None = None


class BrainContextRequest(BaseModel):
    mode: str = "compact"
    query: str | None = None
    target_files: list[str] | None = None
    max_tokens: int | None = 2000
    max_chars: int | None = None
    page: int = 0
    page_size: int = 15
    minimal_contract: bool = False


class PassportValidateRequest(BaseModel):
    manifest_json: str


class PassportMigrateRequest(BaseModel):
    manifest_json: str


@app.post("/api/analyses/{analysis_id}/brain/search", response_model=SearchResponse)
def search_repository_brain(analysis_id: str, request: BrainSearchRequest) -> SearchResponse:
    """Performs deterministic, explainable code and architectural location discovery."""
    indexer, analysis = _get_or_create_indexer_for_analysis(analysis_id)
    engine = SmartRetrievalEngine(indexer=indexer, analysis=analysis)
    resp = engine.search(query=request.query, limit=request.limit)

    # Optional path filter
    if request.path_filter:
        pf_low = request.path_filter.lower()
        resp.matches = [m for m in resp.matches if pf_low in m.file_id.lower()]
        resp.total_matches = len(resp.matches)

    # Optional language filter
    if request.language:
        lang_low = request.language.lower()
        resp.matches = [m for m in resp.matches if m.language.lower() == lang_low]
        resp.total_matches = len(resp.matches)

    # Optional symbol kind filter
    if request.kind:
        k_low = request.kind.lower()
        for m in resp.matches:
            m.matched_symbols = [s for s in m.matched_symbols if s.kind.value.lower() == k_low]

    return resp


@app.get("/api/analyses/{analysis_id}/brain/symbols", response_model=SymbolQueryResponse)
def list_or_query_symbols(
    analysis_id: str,
    name: str | None = Query(default=None),
    kind: str | None = Query(default=None),
    language: str | None = Query(default=None),
    file_path: str | None = Query(default=None),
    container: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
) -> SymbolQueryResponse:
    """Searches or filters symbol definitions across the repository."""
    indexer, _ = _get_or_create_indexer_for_analysis(analysis_id)
    if name:
        syms = indexer.find_by_name(name=name, kind=kind, file_path=file_path, container=container, exact=False)
        return SymbolQueryResponse(
            total_symbols=len(syms),
            symbols=syms[:limit],
            summary_text=f"Found {len(syms)} symbol(s) matching '{name}'.",
            filter_criteria={"name": name, "kind": kind, "file_path": file_path, "container": container, "limit": limit},
        )
    return indexer.list_symbols(kind=kind, language=language, file_path=file_path, container=container, limit=limit)


@app.get("/api/analyses/{analysis_id}/brain/symbols/{symbol_id}/trace", response_model=SymbolTraceResult)
def trace_repository_symbol(analysis_id: str, symbol_id: str) -> SymbolTraceResult:
    """Traces callers, callees, imports, container hierarchy, and downstream blast radius for a symbol."""
    indexer, analysis = _get_or_create_indexer_for_analysis(analysis_id)
    tracer = SymbolTracer(indexer=indexer, analysis=analysis)
    try:
        return tracer.trace_symbol(symbol_id=symbol_id, allow_ambiguous=True)
    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "SYMBOL_NOT_FOUND", "message": str(exc)},
        ) from exc
    except AmbiguousSymbolError as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": "AMBIGUOUS_SYMBOL", "message": str(exc)},
        ) from exc


@app.get("/api/analyses/{analysis_id}/brain/evidence", response_model=EvidenceLedgerResponse)
def get_evidence_ledger(
    analysis_id: str,
    evidence_id: str | None = Query(default=None),
    file_path: str | None = Query(default=None),
    symbol_name: str | None = Query(default=None),
    evidence_type: str | None = Query(default=None),
    check_staleness: bool = Query(default=True),
    limit: int = Query(default=50, ge=1, le=500),
) -> EvidenceLedgerResponse:
    """Queries evidence citations with optional staleness detection against current files on disk."""
    indexer, _ = _get_or_create_indexer_for_analysis(analysis_id)
    ledger = indexer.ledger

    if evidence_id:
        ev = ledger.get_by_id(evidence_id)
        if not ev:
            return EvidenceLedgerResponse(
                total_evidence=0,
                stale_count=0,
                evidence_items=[],
                summary_text=f"Evidence citation '{evidence_id}' not found.",
            )
        if check_staleness:
            full_path = indexer.root_path / ev.file_path
            if full_path.is_file():
                try:
                    content = full_path.read_text(encoding="utf-8", errors="replace")
                    ledger.check_staleness(ev.file_path, current_content=content, current_revision=indexer.revision)
                except Exception:
                    pass
        return EvidenceLedgerResponse(
            total_evidence=1,
            stale_count=1 if ev.is_stale else 0,
            evidence_items=[ev],
            summary_text=f"Evidence citation '{evidence_id}' retrieved.",
        )

    if file_path:
        evs = ledger.find_by_file(file_path)
        if check_staleness:
            full_path = indexer.root_path / file_path
            if full_path.is_file():
                try:
                    content = full_path.read_text(encoding="utf-8", errors="replace")
                    evs = ledger.check_staleness(file_path, current_content=content, current_revision=indexer.revision)
                except Exception:
                    pass
            elif not full_path.exists():
                evs = ledger.check_staleness(file_path, current_content="", current_revision=indexer.revision)
        stale_c = sum(1 for e in evs if e.is_stale)
        return EvidenceLedgerResponse(
            total_evidence=len(evs),
            stale_count=stale_c,
            evidence_items=evs[:limit],
            summary_text=f"Found {len(evs)} evidence citation(s) for file '{file_path}'.",
        )

    if symbol_name:
        evs = ledger.find_by_symbol(symbol_name)
        stale_c = sum(1 for e in evs if e.is_stale)
        return EvidenceLedgerResponse(
            total_evidence=len(evs),
            stale_count=stale_c,
            evidence_items=evs[:limit],
            summary_text=f"Found {len(evs)} evidence citation(s) for symbol '{symbol_name}'.",
        )

    if evidence_type:
        try:
            ev_type_enum = EvidenceType(evidence_type.lower())
            evs = ledger.find_by_type(ev_type_enum)
            stale_c = sum(1 for e in evs if e.is_stale)
            return EvidenceLedgerResponse(
                total_evidence=len(evs),
                stale_count=stale_c,
                evidence_items=evs[:limit],
                summary_text=f"Found {len(evs)} evidence citation(s) of type '{evidence_type}'.",
            )
        except Exception:
            pass

    return ledger.to_response(limit=limit)


@app.get("/api/analyses/{analysis_id}/brain/evidence/{evidence_id}", response_model=EvidenceReference)
def get_single_evidence(
    analysis_id: str,
    evidence_id: str,
    check_staleness: bool = Query(default=True),
) -> EvidenceReference:
    """Retrieves a single verified architectural evidence reference with staleness check."""
    indexer, _ = _get_or_create_indexer_for_analysis(analysis_id)
    ev = indexer.ledger.get_by_id(evidence_id)
    if not ev:
        raise HTTPException(
            status_code=404,
            detail={"code": "EVIDENCE_NOT_FOUND", "message": f"Evidence citation '{evidence_id}' not found."},
        )
    if check_staleness:
        full_path = indexer.root_path / ev.file_path
        if full_path.is_file():
            try:
                content = full_path.read_text(encoding="utf-8", errors="replace")
                indexer.ledger.check_staleness(ev.file_path, current_content=content, current_revision=indexer.revision)
            except Exception:
                pass
        elif not full_path.exists():
            indexer.ledger.check_staleness(ev.file_path, current_content="", current_revision=indexer.revision)
    return ev


@app.post("/api/analyses/{analysis_id}/brain/context", response_model=AgentContextResponse)
def build_agent_context(analysis_id: str, request: BrainContextRequest) -> AgentContextResponse:
    """Builds controlled, token-budgeted architectural context for AI agents with true vs estimated token disclosure."""
    indexer, analysis = _get_or_create_indexer_for_analysis(analysis_id)
    return AgentContextBuilder.build_context(
        analysis=analysis,
        mode=request.mode,
        query=request.query,
        target_files=request.target_files,
        max_tokens=request.max_tokens,
        max_chars=request.max_chars,
        page=request.page,
        page_size=request.page_size,
        indexer=indexer,
        minimal_contract=request.minimal_contract,
    )


@app.get("/api/analyses/{analysis_id}/passport/v2", response_model=RepositoryPassportV2)
def get_analysis_passport_v2(
    analysis_id: str,
    max_modules: int = Query(default=150, ge=10, le=2000),
) -> RepositoryPassportV2:
    """Returns the portable Repository Passport v2 manifest with symbol summaries and major module roles."""
    indexer, res = _get_or_create_indexer_for_analysis(analysis_id)
    contract = None
    target_path = Path(res.target_display)
    if target_path.exists() and target_path.is_dir():
        c_file = find_contract_file(target_path)
        if c_file:
            try:
                contract = load_contract_file(c_file)
            except Exception:
                pass

    return generate_repository_passport_v2(
        analysis=res,
        git_revision=res.git_insights.default_branch or "HEAD",
        contract=contract,
        max_modules=max_modules,
        indexer=indexer,
    )


@app.post("/api/passport/validate")
def validate_passport_manifest(request: PassportValidateRequest) -> dict[str, Any]:
    """Validates passport JSON manifest against v1 or v2 schema and privacy guardrails."""
    try:
        passport = validate_passport_json(request.manifest_json)
        return {
            "valid": True,
            "schema_version": passport.schema_version,
            "repo_name": passport.repo_name,
            "git_revision": passport.git_revision,
            "primary_languages": [lg.language for lg in passport.primary_languages],
            "violations": [],
        }
    except SecurityValidationError as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": exc.code, "message": exc.message},
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "PASSPORT_INVALID", "message": str(exc)},
        ) from exc


@app.post("/api/passport/migrate", response_model=RepositoryPassportV2)
def migrate_passport_manifest(request: PassportMigrateRequest) -> RepositoryPassportV2:
    """Migrates a v1.0 Repository Passport into a schema-compliant v2.0 manifest."""
    try:
        import json
        data = json.loads(request.manifest_json)
        return migrate_v1_to_v2(data)
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "PASSPORT_MIGRATION_ERROR", "message": f"Failed to migrate passport manifest: {exc}"},
        ) from exc

