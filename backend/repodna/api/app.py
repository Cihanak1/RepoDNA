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
from repodna.core.analyzer import (
    ScanCancelledError,
    ScanTimeoutError,
    run_repository_analysis,
)
from repodna.parsers.treesitter_parser import get_parser_engine_summary
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
_MAX_STORED_RESULTS = 25


def _store_result(result: AnalysisResult, job_id: str | None = None) -> None:
    with _LOCK:
        if len(_RESULTS_BY_ID) >= _MAX_STORED_RESULTS:
            oldest_key = next(iter(_RESULTS_BY_ID))
            _RESULTS_BY_ID.pop(oldest_key, None)
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
