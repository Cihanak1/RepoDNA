"""Security validation unit tests covering SSRF, URL hygiene, branch injection, and path traversal."""

from __future__ import annotations

from pathlib import Path

import pytest

from repodna.security.validators import (
    SecurityValidationError,
    sanitize_url_for_display,
    scan_line_for_secrets,
    validate_git_branch,
    validate_github_url,
    validate_local_directory,
)


def test_validate_github_url_accepts_canonical_https() -> None:
    url, owner, repo = validate_github_url("https://github.com/Cihanak1/RepoDNA")
    assert url == "https://github.com/Cihanak1/RepoDNA.git"
    assert owner == "Cihanak1"
    assert repo == "RepoDNA"

    url2, owner2, repo2 = validate_github_url("https://github.com/fastapi/fastapi.git/")
    assert url2 == "https://github.com/fastapi/fastapi.git"
    assert owner2 == "fastapi"
    assert repo2 == "fastapi"


@pytest.mark.parametrize(
    ("unsafe_url", "expected_code"),
    [
        ("http://github.com/owner/repo", "UNSAFE_PROTOCOL"),
        ("ssh://git@github.com/owner/repo.git", "UNSAFE_PROTOCOL"),
        ("file:///etc/passwd", "UNSAFE_PROTOCOL"),
        ("https://token123:x-oauth@github.com/owner/repo", "CREDENTIALS_IN_URL"),
        ("https://127.0.0.1/owner/repo", "SSRF_IP_LITERAL"),
        ("https://169.254.169.254/latest/meta-data", "SSRF_IP_LITERAL"),
        ("https://[::1]/owner/repo", "SSRF_IP_LITERAL"),
        ("https://localhost/owner/repo", "SSRF_LOCAL_HOST"),
        ("https://internal.service.local/owner/repo", "SSRF_LOCAL_HOST"),
        ("https://gitlab.com/owner/repo", "UNTRUSTED_GIT_HOST"),
        ("https://github.com:8443/owner/repo", "NON_STANDARD_PORT"),
        ("https://github.com/owner/repo?ref=main", "URL_QUERY_FORBIDDEN"),
        ("https://github.com/owner/repo/tree/main/sub", "INVALID_GITHUB_REPO_PATH"),
    ],
)
def test_validate_github_url_rejects_unsafe_urls(unsafe_url: str, expected_code: str) -> None:
    with pytest.raises(SecurityValidationError) as exc_info:
        validate_github_url(unsafe_url)
    assert exc_info.value.code == expected_code


def test_validate_git_branch_blocks_option_injection() -> None:
    assert validate_git_branch("main") == "main"
    assert validate_git_branch("feature/tree-sitter-v2") == "feature/tree-sitter-v2"
    assert validate_git_branch(None) is None

    for bad_branch in ["--upload-pack=evil", "-oProxyCommand=evil", "main..origin", "branch with space"]:
        with pytest.raises(SecurityValidationError) as exc_info:
            validate_git_branch(bad_branch)
        assert exc_info.value.code == "INVALID_BRANCH_NAME"


def test_sanitize_url_redacts_credentials() -> None:
    raw = "https://ghp_secretToken12345:x-oauth-basic@github.com/owner/repo.git"
    sanitized = sanitize_url_for_display(raw)
    assert "ghp_secretToken12345" not in sanitized
    assert "***:***@github.com" in sanitized


def test_validate_local_directory_guards(tmp_path: Path) -> None:
    valid_dir = tmp_path / "sample_repo"
    valid_dir.mkdir()
    assert validate_local_directory(str(valid_dir)) == valid_dir.resolve()

    sample_file = valid_dir / "main.py"
    sample_file.write_text("print('hi')", encoding="utf-8")
    with pytest.raises(SecurityValidationError) as exc_info:
        validate_local_directory(str(sample_file))
    assert exc_info.value.code == "NOT_A_DIRECTORY"

    ssh_dir = tmp_path / ".ssh"
    ssh_dir.mkdir()
    with pytest.raises(SecurityValidationError) as exc_info2:
        validate_local_directory(str(ssh_dir))
    assert exc_info2.value.code == "SENSITIVE_DIR_BLOCKED"


def test_scan_line_for_secrets_redacts_values() -> None:
    fake_pat = "ghp_" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8"
    warnings = scan_line_for_secrets(f'TOKEN = "{fake_pat}"', 42)
    assert len(warnings) == 1
    assert "GitHub Personal Access Token" in warnings[0]
    assert "line 42" in warnings[0]
    assert fake_pat not in warnings[0]
