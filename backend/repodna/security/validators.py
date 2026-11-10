"""Security validators for URLs, paths, symlinks, branches, and sensitive content detection."""

from __future__ import annotations

import ctypes
import ipaddress
import os
import re
import stat as stat_module
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

# Fast pre-filter regex so clean files are scanned in a single pass without line splitting
_FAST_SECRET_HINT_RE = re.compile(
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----|gh[pousr]_[A-Za-z0-9_]{36}|(?:AKIA|ASIA)[0-9A-Z]{16}|xox[baprs]-[0-9A-Za-z-]{10}"
)

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


DEFAULT_MAX_EVIDENCE_BYTES = 1_048_576  # 1 MB


def validate_and_resolve_evidence_path(
    root_path: Path,
    relative_path: str,
    max_file_bytes: int = DEFAULT_MAX_EVIDENCE_BYTES,
) -> tuple[Path, str]:
    """
    Validates a repository-relative evidence file path against traversal, escaping,
    Windows drive/UNC paths, symlinks, directories, and sensitive files.

    Returns:
        (resolved_target_path, canonical_posix_relative_path)
    Raises:
        SecurityValidationError on any boundary or safety violation.
    """
    if not isinstance(relative_path, str):
        raise SecurityValidationError("INVALID_PATH_TYPE", "File path must be a string.")

    if "\x00" in relative_path:
        raise SecurityValidationError("NULL_BYTE_PATH", "Path contains illegal null byte.")

    cleaned = relative_path.strip()
    if not cleaned:
        raise SecurityValidationError("EMPTY_PATH", "Evidence file path cannot be empty.")

    # 1. Drive letter and UNC path checks
    if cleaned.startswith(("//", "\\\\")):
        raise SecurityValidationError("UNC_PATH_BLOCKED", "UNC paths are forbidden in relative file paths.")

    drive, _ = os.path.splitdrive(cleaned)
    if drive or re.match(r"^[a-zA-Z]:", cleaned):
        raise SecurityValidationError("DRIVE_LETTER_BLOCKED", "Windows drive letters are forbidden in relative file paths.")

    # 2. Absolute path checks
    if cleaned.startswith(("/", "\\")) or Path(cleaned).is_absolute():
        raise SecurityValidationError("ABSOLUTE_PATH_BLOCKED", "Absolute paths are forbidden; path must be repository-relative.")

    # 3. Path traversal ('..' or '.') checks
    raw_parts = cleaned.replace("\\", "/").split("/")
    parts: list[str] = []
    for p in raw_parts:
        if not p or p == ".":
            continue
        if p == ".." or ".." in p:
            raise SecurityValidationError("PATH_TRAVERSAL", "Directory traversal ('..') is strictly forbidden.")
        parts.append(p)

    if not parts:
        raise SecurityValidationError("EMPTY_PATH", "Evidence file path cannot be empty.")

    posix_rel = "/".join(parts)

    # 4. Root directory containment
    try:
        root_resolved = root_path.resolve(strict=True)
    except OSError as exc:
        raise SecurityValidationError("INVALID_ROOT_PATH", f"Cannot resolve repository root: {exc}") from exc

    if not root_resolved.is_dir():
        raise SecurityValidationError("ROOT_NOT_A_DIR", f"Root path is not a directory: {root_path}")

    candidate = root_resolved / posix_rel
    candidate_resolved = candidate.resolve(strict=False)

    try:
        if not candidate_resolved.is_relative_to(root_resolved) or candidate_resolved == root_resolved:
            raise SecurityValidationError("PATH_ESCAPE", "Target path escapes repository root boundary.")
    except (ValueError, OSError) as exc:
        raise SecurityValidationError("PATH_ESCAPE", "Target path escapes repository root boundary.") from exc

    # 5. Symlink escape check
    try:
        if candidate.exists():
            strict_candidate = candidate.resolve(strict=True)
            if not strict_candidate.is_relative_to(root_resolved):
                raise SecurityValidationError("SYMLINK_ESCAPE", "Symbolic link escapes repository root boundary.")
    except SecurityValidationError:
        raise
    except OSError as exc:
        raise SecurityValidationError("SYMLINK_ERROR", f"Error resolving target path: {exc}") from exc

    # 6. Sensitive file & directory guard
    rel_parts = [p.lower() for p in candidate_resolved.relative_to(root_resolved).parts]
    if any(p in {".git", ".ssh", ".aws", ".gnupg"} for p in rel_parts):
        raise SecurityValidationError("SENSITIVE_FILE_BLOCKED", "Access to sensitive system or credential paths is forbidden.")

    file_name_lower = candidate.name.lower()
    if file_name_lower in SENSITIVE_FILENAMES or file_name_lower.startswith(".env"):
        raise SecurityValidationError("SENSITIVE_FILE_BLOCKED", "Access to sensitive configuration or secret file is forbidden.")

    # 7. Directory check
    if candidate.exists() and candidate.is_dir():
        raise SecurityValidationError("NOT_A_FILE", "Target path is a directory, not a file.")

    return candidate, posix_rel


def _verify_fd_containment_and_type(
    fd: int,
    root_resolved: Path,
    posix_rel: str,
    max_file_bytes: int,
) -> None:
    """Verifies that the opened file descriptor is a regular file within repository bounds and within size limits."""
    st = os.fstat(fd)
    if not stat_module.S_ISREG(st.st_mode):
        raise SecurityValidationError("SPECIAL_FILE_BLOCKED", f"Target path '{posix_rel}' is not a regular file.")
    if st.st_size > max_file_bytes:
        raise SecurityValidationError(
            "FILE_TOO_LARGE",
            f"File size ({st.st_size} bytes) exceeds maximum limit ({max_file_bytes} bytes).",
        )

    # Platform-specific descriptor containment verification (TOCTOU guard)
    if os.name == "nt":
        try:
            import msvcrt

            get_osfhandle = getattr(msvcrt, "get_osfhandle", None)
            windll = getattr(ctypes, "windll", None)
            if get_osfhandle is not None and windll is not None:
                handle = get_osfhandle(fd)
                buf = ctypes.create_unicode_buffer(1024)
                res = windll.kernel32.GetFinalPathNameByHandleW(handle, buf, 1024, 0)
                if res > 0:
                    raw_p = buf.value
                    if raw_p.startswith("\\\\?\\"):
                        raw_p = raw_p[4:]
                    opened_path = Path(raw_p).resolve()
                    if not opened_path.is_relative_to(root_resolved) or opened_path == root_resolved:
                        raise SecurityValidationError(
                            "TOCTOU_SYMLINK_ESCAPE",
                            "Opened file descriptor resolved outside repository root.",
                        )
        except SecurityValidationError:
            raise
        except Exception:
            pass


def safe_read_evidence_file(
    root_path: Path,
    relative_path: str,
    max_file_bytes: int = DEFAULT_MAX_EVIDENCE_BYTES,
) -> tuple[str, str, bool]:
    """
    Safely reads text content of a repository-relative evidence file within strict bounds.
    Employs descriptor-level validation and platform-specific containment to guard against TOCTOU races.

    Returns:
        (text_content, canonical_posix_path, file_exists_flag)
    Raises:
        SecurityValidationError on path escaping, oversized files, or binary files.
    """
    target_path, posix_rel = validate_and_resolve_evidence_path(
        root_path=root_path,
        relative_path=relative_path,
        max_file_bytes=max_file_bytes,
    )

    root_resolved = root_path.resolve()
    flags = os.O_RDONLY
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW

    try:
        fd = os.open(target_path, flags)
    except FileNotFoundError:
        return "", posix_rel, False
    except PermissionError as exc:
        raise SecurityValidationError("FILE_PERMISSION_DENIED", "Permission denied reading evidence file.") from exc
    except OSError as exc:
        # On POSIX with O_NOFOLLOW, opening symlink raises ELOOP or EINVAL
        if getattr(exc, "errno", None) in (22, 40):
            raise SecurityValidationError("SYMLINK_ESCAPE", f"Symbolic link cannot be followed for evidence read: {type(exc).__name__}") from exc
        raise SecurityValidationError("FILE_READ_ERROR", f"Cannot open evidence file '{posix_rel}': {type(exc).__name__}") from exc

    try:
        _verify_fd_containment_and_type(fd, root_resolved, posix_rel, max_file_bytes)

        # Bounded read using file descriptor
        chunks: list[bytes] = []
        total_read = 0
        first_chunk = os.read(fd, min(1024, max_file_bytes + 1))
        if b"\x00" in first_chunk:
            raise SecurityValidationError("BINARY_FILE_BLOCKED", "Binary files cannot be read for evidence inspection.")
        chunks.append(first_chunk)
        total_read += len(first_chunk)

        while total_read <= max_file_bytes:
            to_read = min(8192, max_file_bytes - total_read + 1)
            chunk = os.read(fd, to_read)
            if not chunk:
                break
            chunks.append(chunk)
            total_read += len(chunk)

        if total_read > max_file_bytes:
            raise SecurityValidationError(
                "FILE_TOO_LARGE",
                f"File size exceeds maximum limit ({max_file_bytes} bytes).",
            )

        raw_data = b"".join(chunks)
        text_content = raw_data.decode("utf-8", errors="replace")
        return text_content, posix_rel, True
    finally:
        os.close(fd)


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


def scan_content_for_secrets(content: str, max_warnings: int = 5) -> list[str]:
    """
    Fast content-level secret scanner using a pre-filter regex before line inspection.
    """
    if not content or not _FAST_SECRET_HINT_RE.search(content):
        return []
    warnings: list[str] = []
    for line_idx, line_str in enumerate(content.splitlines()[:2000], start=1):
        line_warnings = scan_line_for_secrets(line_str, line_idx)
        if line_warnings:
            warnings.extend(line_warnings)
            if len(warnings) >= max_warnings:
                break
    return warnings[:max_warnings]
