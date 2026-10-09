"""Cache backends for raw, versioned PYMK Top-M results.

The engine talks only to :class:`RecommendationCache`.  Redis is therefore an
optional operational optimization rather than a dependency of graph retrieval
or topology ranking.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from collections.abc import Callable


class CacheUnavailableError(RuntimeError):
    """A cache transport could not complete a request safely.

    Callers may bypass this error and compute a recommendation from the active
    graph.  Cache payload validation errors deliberately use other exception
    types and must not be disguised as a backend outage.
    """


class RecommendationCache(ABC):
    """Minimal string cache boundary used by ``RecommendationEngine``."""

    @abstractmethod
    def get(self, key: str) -> str | None:
        """Return a cached serialized payload, or ``None`` on a cache miss."""

    @abstractmethod
    def set(self, key: str, value: str, ttl_seconds: float) -> None:
        """Store one serialized payload for a positive TTL."""


class NoOpRecommendationCache(RecommendationCache):
    """Explicit cache bypass for local development and deterministic tests."""

    def get(self, key: str) -> str | None:
        del key
        return None

    def set(self, key: str, value: str, ttl_seconds: float) -> None:
        del key, value, ttl_seconds


class InMemoryRecommendationCache(RecommendationCache):
    """Small process-local cache intended for unit tests and local smoke runs."""

    def __init__(self, *, clock: Callable[[], float] = time.monotonic):
        self._clock = clock
        self._entries: dict[str, tuple[str, float]] = {}

    def get(self, key: str) -> str | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if self._clock() >= expires_at:
            del self._entries[key]
            return None
        return value

    def set(self, key: str, value: str, ttl_seconds: float) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        self._entries[key] = (value, self._clock() + ttl_seconds)


class RedisRecommendationCache(RecommendationCache):
    """Redis implementation with bounded connect and operation timeouts.

    ``redis`` is imported only while constructing this adapter.  Applications
    that choose ``NoOpRecommendationCache`` therefore remain usable without
    the optional package or a running Redis server.
    """

    def __init__(
        self,
        redis_url: str,
        *,
        key_prefix: str = "",
        connect_timeout_seconds: float = 0.1,
        operation_timeout_seconds: float = 0.1,
    ):
        if not redis_url:
            raise ValueError("redis_url must be non-empty")
        if connect_timeout_seconds <= 0 or operation_timeout_seconds <= 0:
            raise ValueError("Redis timeouts must be positive")
        try:
            import redis
        except ImportError as error:
            raise RuntimeError(
                "RedisRecommendationCache requires the optional 'redis' package"
            ) from error

        self._key_prefix = key_prefix.rstrip(":")
        self._client = redis.Redis.from_url(
            redis_url,
            decode_responses=True,
            socket_connect_timeout=connect_timeout_seconds,
            socket_timeout=operation_timeout_seconds,
        )
        self._backend_errors = (
            redis.exceptions.ConnectionError,
            redis.exceptions.TimeoutError,
            redis.exceptions.BusyLoadingError,
        )

    def get(self, key: str) -> str | None:
        try:
            value = self._client.get(self._full_key(key))
        except self._backend_errors as error:
            raise CacheUnavailableError("Redis GET is unavailable") from error
        if value is not None and not isinstance(value, str):
            raise TypeError("Redis cache must return decoded string values")
        return value

    def set(self, key: str, value: str, ttl_seconds: float) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        try:
            self._client.set(self._full_key(key), value, px=round(ttl_seconds * 1000))
        except self._backend_errors as error:
            raise CacheUnavailableError("Redis SET is unavailable") from error

    def _full_key(self, key: str) -> str:
        return f"{self._key_prefix}:{key}" if self._key_prefix else key
