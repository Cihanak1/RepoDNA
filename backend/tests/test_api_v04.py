"""FastAPI endpoint tests for RepoDNA v0.4.0 features (Passport, Contract, Guardian)."""

from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from repodna.api.app import app
from repodna.contract.loader import init_starter_contract

client = TestClient(app)


def test_api_contract_endpoints() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        # 1. Initially 404
        r404 = client.get("/api/contract", params={"path": str(tmp_path)})
        assert r404.status_code == 404

        # 2. Init starter contract
        init_starter_contract(tmp_path)

        # 3. Retrieve contract
        r200 = client.get("/api/contract", params={"path": str(tmp_path)})
        assert r200.status_code == 200
        data = r200.json()
        assert data["version"] == 1
        assert len(data["rules"]) >= 2


def test_api_passport_and_guardian_endpoints() -> None:
    # 1. Run demo scan to store an analysis result
    scan_req = {
        "source_type": "demo",
        "target": "demo",
        "limits": {"max_files": 100, "timeout_seconds": 30.0},
    }
    r_scan = client.post("/api/scan", json=scan_req)
    assert r_scan.status_code == 200
    analysis = r_scan.json()
    analysis_id = analysis["analysis_id"]

    # 2. Retrieve passport for analysis
    r_pass = client.get(f"/api/analyses/{analysis_id}/passport")
    assert r_pass.status_code == 200
    p_data = r_pass.json()
    assert p_data["schema_version"] == "1.0.0"
    assert "acme-commerce-platform" in p_data["repo_name"]
    assert "ast_coverage" in p_data
    assert "architectural_hubs" in p_data

    # 3. Assess guardian on local repo
    guardian_req = {
        "target": ".",
        "base_ref": "HEAD",
        "head_ref": "HEAD",
        "mode": "advisory",
    }
    r_guard = client.post("/api/guardian/assess", json=guardian_req)
    assert r_guard.status_code == 200
    g_data = r_guard.json()
    assert g_data["verdict"] == "PASS"
    assert "risk_assessment" in g_data
    assert "summary_markdown" in g_data
