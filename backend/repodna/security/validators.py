"""Security validators for URLs, paths, symlinks, branches, and sensitive content detection."""

from __future__ import annotations

import ipaddress
import os
import re
from pathlib import Path
from urllib.parse import urlparse


class SecurityValidationError(ValueError):
    """Raised when a target URL, path, or parameter violates security policy."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


# Strict GitHub repository path pattern: /owner/repo(.git)?
_GITHUB_REPO_PATH_RE = re.compile(
    r"^/(?P<owner>[A-Za-z0-9](?:[A-Za-z0-9-]{0,38}))/(?P<repo>[A-Za-z0-9._-]{1,100}?)(?:\.git)?/?$"
)

# Safe Git branch/ref name pattern (disallows leading '-', '..', spaces, shell metacharacters)
_SAFE_BRANCH_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,120}$")

# Sensitive file names that should be flagged and not parsed for code contents
SENSITIVE_FILENAMES = {
    ".env",
    ".env.local",
    ".env.production",
    ".env.development",
    "id_rsa",
    "id_ed25519",
    "id_ecdsa",
    ".npmrc",
    ".pypirc",
    "credentials.json",
}

# Secret patterns (never log or return the matched secret value; only report the pattern type and line)
_SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("Private Key Header", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")),
    ("GitHub Personal Access Token", re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{36,255}\b")),
    ("AWS Access Key ID", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("Slack Token", re.compile(r"\bxox[baprs]-[0-9A-Za-z-]{10,48}\b")),
]

# Blocked system directories to prevent accidental/malicious system scans
_BLOCKED_SYSTEM_PREFIXES_POSIX = (
    "/etc",
    "/proc",
    "/sys",
    "/dev",
    "/boot",
    "/root/.ssh",
)

_BLOCKED_SYSTEM_DIRS_NAMES = {
    ".ssh",
    ".aws",
    ".gnupg",
}


def sanitize_url_for_display(raw_url: str) -> str:
    """Redact any embedded userinfo/credentials from a URL string before logging or displaying."""
    try:
        parsed = urlparse(raw_url.strip())
        if parsed.username or parsed.password:
            host = parsed.hostname or "unknown-host"
            return f"{parsed.scheme}://***:***@{host}{parsed.path}"
    except Exception:
        pass
    return re.sub(r"://[^/@]+@", "://***:***@", raw_url)


def validate_github_url(raw_url: str) -> tuple[str, str, str]:
    """
    Validate that raw_url is a canonical, safe public HTTPS GitHub repository URL.

    Returns:
        (canonical_clone_url, owner, repo_name)
    Raises:
        SecurityValidationError on any SSRF, protocol, credential, or path violation.
    """
    cleaned = raw_url.strip()
    if not cleaned:
        raise SecurityValidationError("EMPTY_URL", "GitHub repository URL cannot be empty.")

    if any(ch in cleaned for ch in ("\r", "\n", "\x00", " ", "\t")):
        raise SecurityValidationError("INVALID_URL_CHARS", "URL contains disallowed control or whitespace characters.")

    parsed = urlparse(cleaned)

    if parsed.scheme.lower() != "https":
        raise SecurityValidationError(
            "UNSAFE_PROTOCOL",
            "Only HTTPS URLs are allowed. Protocols like http://, ssh://, git://, and file:// are rejected.",
        )

    if parsed.username is not None or parsed.password is not None or "@" in parsed.netloc:
        raise SecurityValidationError(
            "CREDENTIALS_IN_URL",
            "Embedded credentials or tokens in repository URLs are forbidden for security.",
        )

    if parsed.port is not None and parsed.port != 443:
        raise SecurityValidationError("NON_STANDARD_PORT", "Custom ports are not permitted in GitHub URLs.")

    hostname = (parsed.hostname or "").lower()
    if not hostname:
        raise SecurityValidationError("MISSING_HOST", "URL is missing a valid hostname.")

    # SSRF check: reject IP literals (v4 or v6) and localhost
    is_ip = False
    try:
        ipaddress.ip_address(hostname.strip("[]"))
        is_ip = True
    except ValueError:
        is_ip = False

    if is_ip:
        raise SecurityValidationError("SSRF_IP_LITERAL", "Direct IP addresses are blocked to prevent SSRF.")

    if hostname in {"localhost", "localhost.localdomain"} or hostname.endswith(".local") or hostname.endswith(".internal"):
        raise SecurityValidationError("SSRF_LOCAL_HOST", "Localhost and internal domain names are blocked.")

    if hostname != "github.com":
        raise SecurityValidationError(
            "UNTRUSTED_GIT_HOST",
            f"Unsupported host '{hostname}'. Only trusted https://github.com/<owner>/<repo> URLs are permitted.",
        )

    if parsed.query or parsed.fragment or parsed.params:
        raise SecurityValidationError(
            "URL_QUERY_FORBIDDEN",
            "Query parameters and fragments are not permitted in GitHub repository URLs.",
        )

    match = _GITHUB_REPO_PATH_RE.match(parsed.path)
    if not match:
        raise SecurityValidationError(
            "INVALID_GITHUB_REPO_PATH",
            "URL path must match https://github.com/<owner>/<repo> without extra subpaths.",
        )

    owner = match.group("owner")
    repo = match.group("repo")
    if repo in {".", ".."} or ".." in repo:
        raise SecurityValidationError("PATH_TRAVERSAL_IN_URL", "Invalid repository name.")

    canonical_url = f"https://github.com/{owner}/{repo}.git"
    return canonical_url, owner, repo


def validate_git_branch(branch: str | None) -> str | None:
    """Validate optional git branch/tag name against argument injection."""
    if branch is None:
        return None
    cleaned = branch.strip()
    if not cleaned:
        return None
    if cleaned.startswith("-") or ".." in cleaned or not _SAFE_BRANCH_RE.match(cleaned):
        raise SecurityValidationError(
            "INVALID_BRANCH_NAME",
            "Branch name contains disallowed characters or potentially unsafe Git options.",
        )
    return cleaned


def validate_local_directory(raw_path: str) -> Path:
    """
    Validate a user-specified local directory path before scanning.
    Rejects symlinks at root, non-existent paths, files, and sensitive system directories.
    """
    cleaned = raw_path.strip()
    if not cleaned:
        raise SecurityValidationError("EMPTY_PATH", "Local directory path cannot be empty.")

    if "\x00" in cleaned:
        raise SecurityValidationError("NULL_BYTE_PATH", "Path contains illegal null byte.")

    candidate = Path(cleaned)
    try:
        if candidate.is_symlink():
            raise SecurityValidationError("SYMLINK_ROOT_BLOCKED", "Root repository path cannot be a symbolic link.")
        resolved = candidate.resolve(strict=True)
    except FileNotFoundError as exc:
        raise SecurityValidationError("PATH_NOT_FOUND", f"Directory does not exist: {cleaned}") from exc
    except SecurityValidationError:
        raise
    except OSError as exc:
        raise SecurityValidationError("INVALID_PATH", f"Cannot access path '{cleaned}': {exc}") from exc

    if not resolved.is_dir():
        raise SecurityValidationError("NOT_A_DIRECTORY", f"Target path is not a directory: {resolved}")

    # Check against filesystem root or sensitive system directories
    if resolved.parent == resolved:
        raise SecurityValidationError("FILESYSTEM_ROOT_BLOCKED", "Scanning an entire filesystem drive root is blocked.")

    posix_str = resolved.as_posix().lower()
    for prefix in _BLOCKED_SYSTEM_PREFIXES_POSIX:
        if posix_str == prefix or posix_str.startswith(prefix + "/"):
            raise SecurityValidationError("SYSTEM_DIR_BLOCKED", f"Scanning system directory '{resolved}' is forbidden.")

    # Windows system directories check
    win_sys = os.environ.get("SystemRoot", r"C:\Windows").replace("\\", "/").lower()
    if posix_str == win_sys or posix_str.startswith(win_sys + "/"):
        raise SecurityValidationError("SYSTEM_DIR_BLOCKED", "Scanning Windows system directory is forbidden.")

    if any(part.lower() in _BLOCKED_SYSTEM_DIRS_NAMES for part in resolved.parts):
        raise SecurityValidationError(
            "SENSITIVE_DIR_BLOCKED",
            "Scanning credential directories (.ssh, .aws, .gnupg) is forbidden.",
        )

    return resolved


def is_safe_subpath(root_resolved: Path, target_path: Path) -> bool:
    """
    Ensure target_path is not a symlink and resolves strictly inside root_resolved.
    Protects against symlink escapes, NTFS junctions, and '..' traversal.
    """
    try:
        if os.path.islink(target_path):
            return False
        resolved_target = target_path.resolve(strict=False)
        return resolved_target.is_relative_to(root_resolved)
    except (OSError, ValueError):
        return False


def scan_line_for_secrets(line: str, line_number: int) -> list[str]:
    """
    Inspect a single line of text for high-confidence credential patterns.
    Never returns the secret itself—only the pattern name and line number.
    """
    warnings: list[str] = []
    if len(line) > 2000:
        return warnings
    for label, pattern in _SECRET_PATTERNS:
        if pattern.search(line):
            warnings.append(f"{label} detected at line {line_number} (value redacted)")
    return warnings
