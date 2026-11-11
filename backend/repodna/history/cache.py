"""Historical Architecture Snapshot Cache.

Provides atomic, verified, schema-migrated on-disk persistence for historical snapshots.
Guarantees pure JSON serialization (zero pickle / zero eval) and corruption protection via SHA-256.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from repodna.history.models import (
    CACHE_SCHEMA_VERSION,
    CacheEnvelope,
    HistoricalSnapshot,
)


def get_parser_fingerprint() -> str:
    """Returns fingerprint of tree-sitter parser and grammar runtime."""
    try:
        import tree_sitter

        ts_ver = getattr(tree_sitter, "__version__", "0.26.0")
    except Exception:
        ts_ver = "unknown"
    return f"ts:{ts_ver}:g:v1"


class HistoricalCache:
    """Bounded, corruption-protected, atomic disk cache for HistoricalSnapshots."""

    def __init__(
        self,
        cache_dir: Path | str,
        max_entries: int = 500,
        max_size_bytes: int = 100 * 1024 * 1024,  # 100 MB default
    ) -> None:
        self.cache_dir = Path(cache_dir).resolve()
        self.max_entries = max_entries
        self.max_size_bytes = max_size_bytes
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def generate_key(
        repo_identity: str,
        commit_sha: str,
        analyzer_version: str = "0.6.0",
        parser_version: str | None = None,
        config_fingerprint: str = "default-v1",
    ) -> str:
        """Computes a deterministic 64-character SHA-256 cache key."""
        p_ver = parser_version or get_parser_fingerprint()
        raw = f"{repo_identity.strip()}:{commit_sha.strip().lower()}:{analyzer_version.strip()}:{p_ver.strip()}:{config_fingerprint.strip()}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _get_entry_path(self, cache_key: str) -> Path:
        return self.cache_dir / f"{cache_key}.json"

    def get(self, cache_key: str) -> HistoricalSnapshot | None:
        """
        Retrieves a cached snapshot if present, valid, and uncorrupted.
        Returns None on cache miss, corruption, or schema mismatch.
        """
        entry_path = self._get_entry_path(cache_key)
        if not entry_path.exists() or not entry_path.is_file():
            return None

        try:
            raw_text = entry_path.read_text(encoding="utf-8")
            data = json.loads(raw_text)

            # 1. Validate envelope structure
            envelope = CacheEnvelope.model_validate(data)

            # 2. Check schema migration / compatibility
            if envelope.schema_version != CACHE_SCHEMA_VERSION:
                self._safe_unlink(entry_path)
                return None

            # 3. Cryptographic integrity check
            payload_str = json.dumps(envelope.payload, sort_keys=True, separators=(",", ":"))
            computed_checksum = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()
            if computed_checksum != envelope.checksum:
                # Corrupted cache file! Safely purge.
                self._safe_unlink(entry_path)
                return None

            # 4. Deserialize payload into HistoricalSnapshot
            snapshot = HistoricalSnapshot.model_validate(envelope.payload)
            snapshot.cache_hit = True

            # Update atime/mtime for LRU eviction tracking
            try:
                os.utime(entry_path, None)
            except OSError:
                pass

            return snapshot

        except Exception:
            # Corrupted JSON, I/O error, or validation failure: purge corrupted entry
            self._safe_unlink(entry_path)
            return None

    def put(
        self,
        cache_key: str,
        snapshot: HistoricalSnapshot,
        config_fingerprint: str = "default-v1",
    ) -> bool:
        """
        Persists a snapshot atomically with SHA-256 integrity checksum.
        Applies LRU eviction if size or entry bounds are exceeded.
        """
        try:
            payload_dict = snapshot.model_dump(mode="json")
            payload_str = json.dumps(payload_dict, sort_keys=True, separators=(",", ":"))
            checksum = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()

            envelope = CacheEnvelope(
                schema_version=CACHE_SCHEMA_VERSION,
                cache_key=cache_key,
                created_at=datetime.now(UTC).isoformat(),
                commit_sha=snapshot.commit_sha,
                analyzer_version=snapshot.analyzer_version,
                checksum=checksum,
                payload=payload_dict,
            )
            envelope_json = envelope.model_dump_json(indent=2)

            target_path = self._get_entry_path(cache_key)

            # Atomic write via temporary file in the same directory (same filesystem)
            tmp_fd, tmp_path_str = tempfile.mkstemp(
                dir=str(self.cache_dir),
                prefix=f".tmp_{cache_key[:8]}_",
                suffix=".json",
            )
            tmp_path = Path(tmp_path_str)
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                f.write(envelope_json)

            # Atomic replace with retry for Windows concurrent file locks
            max_retries = 5
            for attempt in range(max_retries):
                try:
                    os.replace(tmp_path, target_path)
                    break
                except PermissionError:
                    if attempt < max_retries - 1:
                        time.sleep(0.02 * (attempt + 1))
                    else:
                        self._safe_unlink(tmp_path)
                        raise

            # Check and enforce cache bounds
            self._enforce_bounds()
            return True

        except Exception:
            return False

    def list_keys(self) -> list[str]:
        """Lists all valid cache keys currently on disk."""
        keys: list[str] = []
        for p in self.cache_dir.glob("*.json"):
            if not p.name.startswith(".tmp_"):
                keys.append(p.stem)
        return keys

    def get_stats(self) -> dict[str, Any]:
        """Returns cache entry count and total size on disk."""
        total_size = 0
        total_entries = 0
        for p in self.cache_dir.glob("*.json"):
            if not p.name.startswith(".tmp_"):
                try:
                    total_size += p.stat().st_size
                    total_entries += 1
                except OSError:
                    pass
        return {
            "total_entries": total_entries,
            "total_size_bytes": total_size,
            "max_entries": self.max_entries,
            "max_size_bytes": self.max_size_bytes,
        }

    def clear(self) -> None:
        """Purges all entries from cache."""
        for p in self.cache_dir.glob("*.json"):
            self._safe_unlink(p)

    def _enforce_bounds(self) -> None:
        """Enforces max_entries and max_size_bytes using LRU eviction, and purges stale temp files."""
        entries: list[tuple[Path, os.stat_result]] = []
        total_size = 0
        now = time.time()

        for p in self.cache_dir.glob("*.json"):
            if p.name.startswith(".tmp_"):
                # Clean up abandoned temporary files older than 5 minutes
                try:
                    if now - p.stat().st_mtime > 300:
                        self._safe_unlink(p)
                except OSError:
                    pass
                continue
            try:
                st = p.stat()
                entries.append((p, st))
                total_size += st.st_size
            except OSError:
                pass

        if len(entries) <= self.max_entries and total_size <= self.max_size_bytes:
            return

        # Sort entries by access time (or mtime if atime not updated) ascending: oldest first
        entries.sort(key=lambda item: max(item[1].st_atime, item[1].st_mtime))

        while (len(entries) > self.max_entries or total_size > self.max_size_bytes) and entries:
            oldest_path, oldest_st = entries.pop(0)
            total_size -= oldest_st.st_size
            self._safe_unlink(oldest_path)

    @staticmethod
    def _safe_unlink(p: Path) -> None:
        try:
            if p.exists():
                p.unlink()
        except OSError:
            pass
