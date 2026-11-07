"""Integration tests for FastAPI endpoints and standalone CLI scanner."""

from __future__ import annotations

import time
from pathlib import Path

from fastapi.testclient import TestClient

from repodna.api.app import app
from repodna.cli.main import main as cli_main

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
