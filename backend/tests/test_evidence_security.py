"""Regression tests for Evidence API Path Boundary Security and Validator Guardrails."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from repodna.api.app import app
from repodna.core.analyzer import run_repository_analysis
from repodna.schemas.models import ScanLimits, ScanRequest, SourceType
from repodna.security.validators import (
    SecurityValidationError,
    safe_read_evidence_file,
    validate_and_resolve_evidence_path,
)


@pytest.fixture
def repo_sandbox(tmp_path: Path) -> Path:
    """Creates a temporary repository sandbox with valid and sensitive files."""
    repo_dir = tmp_path / "test_repo"
    repo_dir.mkdir()

    # Valid files
    src_dir = repo_dir / "src"
    src_dir.mkdir()
    valid_py = src_dir / "app.py"
    valid_py.write_text("def run():\n    print('ok')\n", encoding="utf-8")

    # Sensitive files
    env_file = repo_dir / ".env"
    env_file.write_text("SECRET_KEY=super_secret\n", encoding="utf-8")

    ssh_dir = repo_dir / ".ssh"
    ssh_dir.mkdir()
    rsa_key = ssh_dir / "id_rsa"
    rsa_key.write_text("-----BEGIN RSA PRIVATE KEY-----\nMIIE...\n", encoding="utf-8")

    # Binary file
    bin_file = repo_dir / "binary.dat"
    bin_file.write_bytes(b"\x00\x01\x02\x03\xff\xfe")

    # Large file (> 1 MB)
    large_file = repo_dir / "large.txt"
    large_file.write_text("A" * (1_048_576 + 50), encoding="utf-8")

    return repo_dir


def test_validate_and_resolve_evidence_path_valid(repo_sandbox: Path) -> None:
    target, posix_rel = validate_and_resolve_evidence_path(repo_sandbox, "src/app.py")
    assert target == (repo_sandbox / "src" / "app.py").resolve()
    assert posix_rel == "src/app.py"


def test_validate_and_resolve_evidence_path_blocks_traversal(repo_sandbox: Path) -> None:
    with pytest.raises(SecurityValidationError) as exc:
        validate_and_resolve_evidence_path(repo_sandbox, "../test_repo/src/app.py")
    assert exc.value.code == "PATH_TRAVERSAL"

    with pytest.raises(SecurityValidationError) as exc:
        validate_and_resolve_evidence_path(repo_sandbox, "../../etc/passwd")
    assert exc.value.code == "PATH_TRAVERSAL"


def test_validate_and_resolve_evidence_path_blocks_absolute(repo_sandbox: Path) -> None:
    with pytest.raises(SecurityValidationError) as exc:
        validate_and_resolve_evidence_path(repo_sandbox, "/etc/passwd")
    assert exc.value.code == "ABSOLUTE_PATH_BLOCKED"


def test_validate_and_resolve_evidence_path_blocks_windows_drive_and_unc(repo_sandbox: Path) -> None:
    with pytest.raises(SecurityValidationError) as exc:
        validate_and_resolve_evidence_path(repo_sandbox, "C:\\Windows\\System32\\drivers\\etc\\hosts")
    assert exc.value.code in ("DRIVE_LETTER_BLOCKED", "ABSOLUTE_PATH_BLOCKED")

    with pytest.raises(SecurityValidationError) as exc:
        validate_and_resolve_evidence_path(repo_sandbox, "\\\\server\\share\\evil.txt")
    assert exc.value.code in ("UNC_PATH_BLOCKED", "ABSOLUTE_PATH_BLOCKED")


def test_validate_and_resolve_evidence_path_blocks_sensitive_files(repo_sandbox: Path) -> None:
    with pytest.raises(SecurityValidationError) as exc:
        validate_and_resolve_evidence_path(repo_sandbox, ".env")
    assert exc.value.code == "SENSITIVE_FILE_BLOCKED"

    with pytest.raises(SecurityValidationError) as exc:
        validate_and_resolve_evidence_path(repo_sandbox, ".ssh/id_rsa")
    assert exc.value.code == "SENSITIVE_FILE_BLOCKED"


def test_validate_and_resolve_evidence_path_blocks_directories(repo_sandbox: Path) -> None:
    with pytest.raises(SecurityValidationError) as exc:
        validate_and_resolve_evidence_path(repo_sandbox, "src")
    assert exc.value.code == "NOT_A_FILE"


def test_safe_read_evidence_file_blocks_binary(repo_sandbox: Path) -> None:
    with pytest.raises(SecurityValidationError) as exc:
        safe_read_evidence_file(repo_sandbox, "binary.dat")
    assert exc.value.code == "BINARY_FILE_BLOCKED"


def test_safe_read_evidence_file_blocks_oversized(repo_sandbox: Path) -> None:
    with pytest.raises(SecurityValidationError) as exc:
        safe_read_evidence_file(repo_sandbox, "large.txt", max_file_bytes=1000)
    assert exc.value.code == "FILE_TOO_LARGE"


def test_safe_read_evidence_file_handles_missing_file_for_staleness(repo_sandbox: Path) -> None:
    content, posix_rel, exists = safe_read_evidence_file(repo_sandbox, "src/missing.py")
    assert content == ""
    assert posix_rel == "src/missing.py"
    assert exists is False


def test_evidence_api_endpoint_path_boundary_security(repo_sandbox: Path) -> None:
    """Verifies that GET /api/analyses/{id}/brain/evidence rejects traversal with HTTP 400."""
    req = ScanRequest(
        target=str(repo_sandbox),
        source_type=SourceType.LOCAL,
        limits=ScanLimits(timeout_seconds=30.0),
    )
    analysis = run_repository_analysis(req)

    client = TestClient(app)
    # Store analysis into server state
    from repodna.api.app import _store_result

    _store_result(analysis)

    # 1. Traversal attempt via file_path query
    resp = client.get(f"/api/analyses/{analysis.analysis_id}/brain/evidence?file_path=../../etc/passwd")
    assert resp.status_code == 400
    err = resp.json()
    assert err["code"] == "PATH_TRAVERSAL"

    # 2. Absolute path attempt
    resp2 = client.get(f"/api/analyses/{analysis.analysis_id}/brain/evidence?file_path=/etc/passwd")
    assert resp2.status_code == 400
    err2 = resp2.json()
    assert err2["code"] == "ABSOLUTE_PATH_BLOCKED"

    # 3. Sensitive file attempt
    resp3 = client.get(f"/api/analyses/{analysis.analysis_id}/brain/evidence?file_path=.env")
    assert resp3.status_code == 400
    err3 = resp3.json()
    assert err3["code"] == "SENSITIVE_FILE_BLOCKED"

    # 4. Valid file path query returns HTTP 200
    resp4 = client.get(f"/api/analyses/{analysis.analysis_id}/brain/evidence?file_path=src/app.py")
    assert resp4.status_code == 200
    data = resp4.json()
    assert "evidence_items" in data
