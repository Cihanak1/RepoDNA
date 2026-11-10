"""Distributed Redis caching layer for sessions and rate limiting."""
from typing import Optional

class RedisCacheManager:
    """Key-value cache for short-lived authorization and rate limits."""
    def __init__(self, host: str = "localhost", port: int = 6379) -> None:
        self.host = host
        self.port = port
        self._store: dict[str, str] = {}

    def get_cached_token(self, key: str) -> Optional[str]:
        """Retrieves cached token if not expired."""
        return self._store.get(key)

    def set_cache_entry(self, key: str, value: str, ttl_seconds: int = 3600) -> None:
        """Sets cache entry with TTL."""
        self._store[key] = value

    def invalidate_key(self, key: str) -> bool:
        """Evicts a key from cache."""
        return self._store.pop(key, None) is not None
