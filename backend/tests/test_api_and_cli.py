"""Integration tests for FastAPI endpoints and standalone CLI scanner."""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

import repodna.api.app as api_app_module
from repodna.api.app import app
from repodna.cli.main import main as cli_main
from repodna.core.analyzer import run_repository_analysis as real_run_repository_analysis
from repodna.schemas.models import AnalysisResult, ScanRequest, ScanStatus

client = TestClient(app)


def test_api_health_and_demo_scan() -> None:
    r = client.get("/api/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert "Python" in data["parsers"]

    scan_resp = client.post("/api/scan", json={"source_type": "demo", "target": "demo"})
    assert scan_resp.status_code == 200
    result = scan_resp.json()
    assert result["is_demo"] is True
    assert result["graph_metrics"]["cycle_count"] >= 1

    analysis_id = result["analysis_id"]
    json_exp = client.get(f"/api/analyses/{analysis_id}/export/json")
    assert json_exp.status_code == 200
    assert "attachment" in json_exp.headers["content-disposition"]

    html_exp = client.get(f"/api/analyses/{analysis_id}/export/html")
    assert html_exp.status_code == 200
    assert "RepoDNA Architectural Intelligence Report" in html_exp.text


def test_api_async_job_lifecycle_and_security_rejection(tmp_path: Path) -> None:
    # SSRF rejection on /api/jobs
    bad_resp = client.post(
        "/api/jobs",
        json={"source_type": "github", "target": "http://127.0.0.1/admin"},
    )
    assert bad_resp.status_code == 400
    assert bad_resp.json()["detail"]["code"] == "UNSAFE_PROTOCOL"

    # Valid local folder async job
    proj = tmp_path / "mini_proj"
    proj.mkdir()
    (proj / "main.py").write_text("import helper\n", encoding="utf-8")
    (proj / "helper.py").write_text("def run(): return 42\n", encoding="utf-8")

    job_resp = client.post("/api/jobs", json={"source_type": "local", "target": str(proj)})
    assert job_resp.status_code == 202
    job_id = job_resp.json()["job_id"]

    # Poll until completed (takes < 0.5s locally)
    for _ in range(30):
        st = client.get(f"/api/jobs/{job_id}").json()
        if st["status"] == "completed":
            break
        time.sleep(0.05)

    res_resp = client.get(f"/api/jobs/{job_id}/result")
    assert res_resp.status_code == 200
    assert res_resp.json()["total_files"] == 2


def test_cli_analyze_json_and_html(tmp_path: Path) -> None:
    out_json = tmp_path / "report.json"
    out_html = tmp_path / "report.html"

    code_json = cli_main(["analyze", "demo", "--format", "json", "--output", str(out_json)])
    assert code_json == 0
    assert out_json.exists()

    code_html = cli_main(["analyze", "demo", "--format", "html", "--output", str(out_html)])
    assert code_html == 0
    assert out_html.exists()
    assert "<!DOCTYPE html>" in out_html.read_text(encoding="utf-8")

    # Security error exit code 2
    code_sec = cli_main(["analyze", "https://evil.example.com/user/repo"])
    assert code_sec == 2


def test_async_job_completion_is_atomic_under_concurrent_polling(
    tmp_path: Path, monkeypatch: Any
) -> None:
    """
    Deterministic regression test for the v0.1.1 async job race condition:
    - Even if the orchestrator emits a premature `ScanStatus.COMPLETED` progress callback
      followed by cleanup latency (simulating `CloneWorkspace.__exit__` before `_store_result`),
      `GET /api/jobs/{job_id}` must NEVER expose `status == 'completed'` until `_JOB_RESULTS[job_id]`
      is atomically populated under `_LOCK`.
    - Concurrent polling threads immediately fetching `GET /api/jobs/{job_id}/result` upon seeing
      `status == 'completed'` must receive `200 OK` with zero `409 RESULT_NOT_READY` responses.
    """
    proj = tmp_path / "race_proj"
    proj.mkdir()
    (proj / "app.py").write_text("import service\n", encoding="utf-8")
    (proj / "service.py").write_text("def handle(): return True\n", encoding="utf-8")

    premature_callback_fired = threading.Event()

    def slow_closing_analyzer(
        request: ScanRequest,
        on_progress: Any = None,
        is_cancelled: Any = None,
    ) -> AnalysisResult:
        res = real_run_repository_analysis(
            request=request,
            on_progress=on_progress,
            is_cancelled=is_cancelled,
        )
        # Simulate the exact v0.1.0 bug: progress callback emits COMPLETED before result is returned/stored
        if on_progress:
            on_progress(ScanStatus.COMPLETED, "Premature completion callback", 100.0, 2, 2)
        premature_callback_fired.set()
        # Hold for 80ms to give 8 concurrent polling threads ample window to hit the race if unguarded
        time.sleep(0.08)
        return res

    monkeypatch.setattr(api_app_module, "run_repository_analysis", slow_closing_analyzer)

    job_resp = client.post("/api/jobs", json={"source_type": "local", "target": str(proj)})
    assert job_resp.status_code == 202
    job_id = job_resp.json()["job_id"]

    # Wait until the premature callback inside slow_closing_analyzer has fired
    assert premature_callback_fired.wait(timeout=5.0)
    # While slow_closing_analyzer is still sleeping (before _complete_job_atomically), status must NOT be completed
    mid_progress = client.get(f"/api/jobs/{job_id}").json()
    assert mid_progress["status"] != "completed"
    assert mid_progress["progress_percent"] <= 99.0

    errors_409: list[int] = []
    success_results: list[dict[str, Any]] = []

    def concurrent_poller() -> None:
        for _ in range(150):
            prog = client.get(f"/api/jobs/{job_id}").json()
            if prog["status"] == "completed":
                res_r = client.get(f"/api/jobs/{job_id}/result")
                if res_r.status_code == 409:
                    errors_409.append(res_r.status_code)
                elif res_r.status_code == 200:
                    success_results.append(res_r.json())
                return
            time.sleep(0.003)

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(concurrent_poller) for _ in range(8)]
        for f in futures:
            f.result(timeout=10.0)

    assert errors_409 == [], f"Expected zero 409 race errors, got: {errors_409}"
    assert len(success_results) == 8
    assert all(r["total_files"] == 2 for r in success_results)


def test_csharp_partial_static_transparency_not_reported_as_full_ast(tmp_path: Path) -> None:
    """
    Verify that C# repositories (like NiceWP) report C# under `partial_static_languages_detected`
    and never misclassify `partial_static` files as `full_ast` in `supported_languages_detected`.
    """
    cs_repo = tmp_path / "NiceWP_Fixture"
    cs_repo.mkdir()
    (cs_repo / "Program.cs").write_text(
        "using System;\nusing NiceWP.Core;\nnamespace NiceWP {\n    public class Program {\n        static void Main() {}\n    }\n}\n",
        encoding="utf-8",
    )
    (cs_repo / "WallpaperService.cs").write_text(
        "using System.Runtime.InteropServices;\nnamespace NiceWP.Core {\n    public class WallpaperService {}\n}\n",
        encoding="utf-8",
    )

    scan_resp = client.post("/api/scan", json={"source_type": "local", "target": str(cs_repo)})
    assert scan_resp.status_code == 200
    data = scan_resp.json()
    tr = data["transparency"]

    assert tr["supported_languages_detected"] == []
    assert tr["partial_static_languages_detected"] == ["C#"]
    assert tr["partial_static_files_count"] == 2
    assert data["languages"][0]["language"] == "C#"
    assert data["languages"][0]["support_level"] == "partial_static"

