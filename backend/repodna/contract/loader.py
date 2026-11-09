"""Safe YAML parser, validator, and starter generator for Architecture Contracts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from repodna.contract.models import ArchitectureContract
from repodna.security.validators import SecurityValidationError

MAX_CONTRACT_SIZE_BYTES = 524_288  # 512 KB
DEFAULT_CONTRACT_FILENAME = "architecture.yml"
DEFAULT_CONTRACT_PATH = Path(".repodna") / DEFAULT_CONTRACT_FILENAME

STARTER_CONTRACT_YAML = """# RepoDNA Architecture Contract Specification
# Schema version: 1
version: 1

policy:
  mode: advisory          # Options: advisory | enforce
  unknown_behavior: warn  # Options: warn | ignore | fail

rules:
  - id: LAYER-001
    title: Domain Layer Isolation
    description: Core domain models must not import presentation, API, or infrastructure modules.
    from:
      - "domain/**"
      - "**/domain/**"
    disallow_imports:
      - "api/**"
      - "frontend/**"
      - "infrastructure/**"
    severity: error
    remediation: Invert the dependency using domain interfaces or repository abstractions.

  - id: BOUNDARY-001
    title: Frontend to Backend Boundary
    description: Client-side UI modules must not directly import server-side backend implementations.
    from:
      - "frontend/**"
    disallow_imports:
      - "backend/**"
    severity: warning
    remediation: Call backend endpoints via REST API or shared client contracts instead of direct import.
"""


def load_contract_from_yaml(content: str) -> ArchitectureContract:
    """Parses and validates an ArchitectureContract from a YAML string safely."""
    if len(content.encode("utf-8")) > MAX_CONTRACT_SIZE_BYTES:
        raise SecurityValidationError(
            "CONTRACT_SIZE_LIMIT_EXCEEDED",
            f"Architecture contract exceeds maximum allowed size of {MAX_CONTRACT_SIZE_BYTES} bytes.",
        )

    try:
        data: Any = yaml.safe_load(content)
    except Exception as exc:
        raise ValueError(f"Failed to parse contract YAML: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError("Contract YAML must define a mapping/dictionary at the top level.")

    return ArchitectureContract.model_validate(data)


def load_contract_file(path: Path | str) -> ArchitectureContract:
    """Loads an ArchitectureContract from a file with security checks."""
    file_path = Path(path).resolve()
    if not file_path.exists():
        raise FileNotFoundError(f"Architecture contract file not found: {file_path}")
    if not file_path.is_file():
        raise ValueError(f"Path is not a regular file: {file_path}")

    size = file_path.stat().st_size
    if size > MAX_CONTRACT_SIZE_BYTES:
        raise SecurityValidationError(
            "CONTRACT_SIZE_LIMIT_EXCEEDED",
            f"Architecture contract '{file_path.name}' exceeds limit ({size} > {MAX_CONTRACT_SIZE_BYTES} bytes).",
        )

    content = file_path.read_text(encoding="utf-8", errors="replace")
    return load_contract_from_yaml(content)


def find_contract_file(repo_path: Path | str) -> Path | None:
    """Discovers standard architecture contract file in repository root or .repodna/ directory."""
    root = Path(repo_path).resolve()
    candidates = [
        root / ".repodna" / "architecture.yml",
        root / ".repodna" / "architecture.yaml",
        root / "architecture.yml",
        root / "architecture.yaml",
    ]
    for c in candidates:
        if c.exists() and c.is_file():
            return c
    return None


def init_starter_contract(repo_path: Path | str, overwrite: bool = False) -> Path:
    """Generates starter .repodna/architecture.yml in target repository."""
    root = Path(repo_path).resolve()
    target_dir = root / ".repodna"
    target_dir.mkdir(parents=True, exist_ok=True)
    target_file = target_dir / DEFAULT_CONTRACT_FILENAME

    if target_file.exists() and not overwrite:
        raise FileExistsError(f"Architecture contract already exists at '{target_file}'. Pass overwrite=True to replace.")

    target_file.write_text(STARTER_CONTRACT_YAML, encoding="utf-8")
    return target_file


def load_baseline_file(path: Path | str) -> set[tuple[str, str, str]]:
    """Loads a set of (rule_id, source_file, target_file) baseline entries from JSON file."""
    file_path = Path(path).resolve()
    if not file_path.exists():
        return set()

    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            items: set[tuple[str, str, str]] = set()
            for entry in data:
                if isinstance(entry, dict):
                    rid = entry.get("rule_id", "")
                    src = entry.get("source_file", "")
                    tgt = entry.get("target_file", "")
                    if rid and src and tgt:
                        items.add((rid, src, tgt))
            return items
        if isinstance(data, dict) and "baseline_violations" in data:
            return {
                (v["rule_id"], v["source_file"], v["target_file"])
                for v in data["baseline_violations"]
                if "rule_id" in v and "source_file" in v and "target_file" in v
            }
        return set()
    except Exception:
        return set()
