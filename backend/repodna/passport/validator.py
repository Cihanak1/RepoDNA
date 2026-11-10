"""Schema validation and verification for RepoDNA Repository Passport manifests."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from repodna.passport.models import (
    PASSPORT_SCHEMA_VERSION_V1,
    PASSPORT_SCHEMA_VERSION_V2,
    RepositoryPassport,
    RepositoryPassportV2,
)
from repodna.security.validators import SecurityValidationError

MAX_PASSPORT_SIZE_BYTES = 2_097_152  # 2 MB

PRIVACY_LEAK_PATTERNS = [
    re.compile(r"[A-Za-z]:[\\/](Users|home|temp|tmp)[\\/]", re.IGNORECASE),
    re.compile(r"/(Users|home|tmp|var/folders)/", re.IGNORECASE),
    re.compile(r"(ghp_[A-Za-z0-9_]{30,}|github_pat_[A-Za-z0-9_]{50,}|xox[baprs]-[A-Za-z0-9_]+)"),
    re.compile(r"bearer\s+[A-Za-z0-9\-\._~\+\/]+=*", re.IGNORECASE),
]


def check_passport_privacy(passport: RepositoryPassport | RepositoryPassportV2) -> list[str]:
    """Scans a RepositoryPassport or RepositoryPassportV2 for accidental leaks of absolute host paths, user home folders, or secrets."""
    violations: list[str] = []

    # 1. Metadata check
    for k, v in passport.metadata.items():
        val_str = str(v)
        for pattern in PRIVACY_LEAK_PATTERNS:
            if pattern.search(val_str):
                violations.append(f"Private host path or secret in metadata['{k}']: '{val_str}'")

    # 2. Module inventory and hub path check (must be relative)
    for m in passport.module_inventory:
        if m.id.startswith("/") or (len(m.id) >= 2 and m.id[1] == ":"):
            violations.append(f"Absolute host path in module_inventory id: '{m.id}'")

    for h in passport.architectural_hubs:
        if h.file_id.startswith("/") or (len(h.file_id) >= 2 and h.file_id[1] == ":"):
            violations.append(f"Absolute host path in architectural_hubs: '{h.file_id}'")

    # 3. Findings and evidence checks
    for finding in passport.verified_findings:
        for pattern in PRIVACY_LEAK_PATTERNS:
            if pattern.search(finding):
                violations.append(f"Private host path in verified_findings: '{finding}'")

    for ev in passport.evidence_references:
        for pattern in PRIVACY_LEAK_PATTERNS:
            if pattern.search(ev):
                violations.append(f"Private host path in evidence_references: '{ev}'")

    # 4. v2 additions (entrypoints, module roles)
    if isinstance(passport, RepositoryPassportV2):
        for ep in passport.architectural_entrypoints:
            if ep.file_path.startswith("/") or (len(ep.file_path) >= 2 and ep.file_path[1] == ":"):
                violations.append(f"Absolute host path in architectural_entrypoints: '{ep.file_path}'")
        for mr in passport.major_module_roles:
            if mr.file_path.startswith("/") or (len(mr.file_path) >= 2 and mr.file_path[1] == ":"):
                violations.append(f"Absolute host path in major_module_roles: '{mr.file_path}'")

    return violations


def validate_passport_json(json_str: str) -> RepositoryPassport | RepositoryPassportV2:
    """Validates passport JSON string against schema and privacy policies."""
    if len(json_str.encode("utf-8")) > MAX_PASSPORT_SIZE_BYTES:
        raise SecurityValidationError(
            "PASSPORT_SIZE_LIMIT_EXCEEDED",
            f"Passport manifest size exceeds limit of {MAX_PASSPORT_SIZE_BYTES} bytes.",
        )

    try:
        data: Any = json.loads(json_str)
    except Exception as exc:
        raise ValueError(f"Invalid JSON format in passport manifest: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError("Passport manifest must be a JSON object.")

    version = data.get("schema_version")
    if version == PASSPORT_SCHEMA_VERSION_V1:
        passport: RepositoryPassport | RepositoryPassportV2 = RepositoryPassport.model_validate(data)
    elif version == PASSPORT_SCHEMA_VERSION_V2:
        passport = RepositoryPassportV2.model_validate(data)
    else:
        raise ValueError(
            f"Unsupported passport schema version: '{version}'. Supported: ['{PASSPORT_SCHEMA_VERSION_V1}', '{PASSPORT_SCHEMA_VERSION_V2}']"
        )

    privacy_leaks = check_passport_privacy(passport)
    if privacy_leaks:
        raise SecurityValidationError(
            "PASSPORT_PRIVACY_LEAK",
            f"Passport manifest violates privacy guardrails ({len(privacy_leaks)} leaks detected): {'; '.join(privacy_leaks)}",
        )

    return passport


def validate_passport_file(path: Path | str) -> RepositoryPassport | RepositoryPassportV2:

    """Validates passport manifest file from disk."""
    file_path = Path(path).resolve()
    if not file_path.exists():
        raise FileNotFoundError(f"Passport manifest file not found: {file_path}")
    if not file_path.is_file():
        raise ValueError(f"Path is not a regular file: {file_path}")

    size = file_path.stat().st_size
    if size > MAX_PASSPORT_SIZE_BYTES:
        raise SecurityValidationError(
            "PASSPORT_SIZE_LIMIT_EXCEEDED",
            f"Passport manifest '{file_path.name}' exceeds limit ({size} > {MAX_PASSPORT_SIZE_BYTES} bytes).",
        )

    content = file_path.read_text(encoding="utf-8", errors="replace")
    return validate_passport_json(content)
