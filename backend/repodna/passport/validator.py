"""Schema validation and verification for RepoDNA Repository Passport manifests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from repodna.passport.models import PASSPORT_SCHEMA_VERSION, RepositoryPassport
from repodna.security.validators import SecurityValidationError

MAX_PASSPORT_SIZE_BYTES = 2_097_152  # 2 MB


def validate_passport_json(json_str: str) -> RepositoryPassport:
    """Validates passport JSON string against schema."""
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
    if version != PASSPORT_SCHEMA_VERSION:
        raise ValueError(
            f"Unsupported passport schema version: '{version}'. Supported: ['{PASSPORT_SCHEMA_VERSION}']"
        )

    return RepositoryPassport.model_validate(data)


def validate_passport_file(path: Path | str) -> RepositoryPassport:
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
