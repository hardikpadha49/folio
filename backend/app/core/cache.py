"""
FolioPulse AI — Provider-Aware Caching Layer

Supports Redis when configured and reachable, with automatic fallback
to an in-memory TTL cache so local dev, offline environments, and tests
run reliably without external daemon requirements.
"""
import json
import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Optional

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class BaseCache(ABC):
    """Abstract caching interface."""

    @abstractmethod
    def get(self, key: str) -> Optional[Any]:
        """Retrieve value by key if not expired."""
        pass

    @abstractmethod
    def set(self, key: str, value: Any, ttl_seconds: int = 300) -> bool:
        """Store value with TTL in seconds."""
        pass

    @abstractmethod
    def delete(self, key: str) -> bool:
        """Remove a key."""
        pass

    @abstractmethod
    def clear(self) -> bool:
        """Clear all keys in cache."""
        pass


class MemoryCache(BaseCache):
    """Thread-safe, process-local in-memory cache with TTL."""

    def __init__(self):
        self._store: dict[str, tuple[Any, float]] = {}

    def get(self, key: str) -> Optional[Any]:
        entry = self._store.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if time.time() > expires_at:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: Any, ttl_seconds: int = 300) -> bool:
        expires_at = time.time() + ttl_seconds
        self._store[key] = (value, expires_at)
        return True

    def delete(self, key: str) -> bool:
        if key in self._store:
            del self._store[key]
            return True
        return False

    def clear(self) -> bool:
        self._store.clear()
        return True


class RedisCache(BaseCache):
    """Redis-backed cache with serialized JSON payloads."""

    def __init__(self, redis_url: str):
        import redis
        self._client = redis.Redis.from_url(redis_url, decode_responses=True, socket_timeout=2.0)
        # Test connection
        self._client.ping()

    def get(self, key: str) -> Optional[Any]:
        try:
            raw = self._client.get(key)
            if raw is None:
                return None
            return json.loads(raw)
        except Exception as e:
            logger.warning("Redis get error for key %s: %s", key, e)
            return None

    def set(self, key: str, value: Any, ttl_seconds: int = 300) -> bool:
        try:
            payload = json.dumps(value)
            self._client.setex(key, ttl_seconds, payload)
            return True
        except Exception as e:
            logger.warning("Redis set error for key %s: %s", key, e)
            return False

    def delete(self, key: str) -> bool:
        try:
            self._client.delete(key)
            return True
        except Exception as e:
            logger.warning("Redis delete error for key %s: %s", key, e)
            return False

    def clear(self) -> bool:
        try:
            self._client.flushdb()
            return True
        except Exception as e:
            logger.warning("Redis flushdb error: %s", e)
            return False


_cache_instance: Optional[BaseCache] = None


def get_cache() -> BaseCache:
    """
    Factory returning the active cache instance.
    Attempts Redis first; falls back gracefully to MemoryCache.
    """
    global _cache_instance
    if _cache_instance is not None:
        return _cache_instance

    if settings.redis_url:
        try:
            redis_cache = RedisCache(settings.redis_url)
            _cache_instance = redis_cache
            logger.info("Connected to Redis cache at %s", settings.redis_url)
            return _cache_instance
        except Exception as e:
            logger.info("Redis unavailable (%s); using in-memory TTL cache.", e)

    _cache_instance = MemoryCache()
    return _cache_instance


def reset_cache_instance() -> None:
    """Helper for testing to reset cache singleton."""
    global _cache_instance
    _cache_instance = None
