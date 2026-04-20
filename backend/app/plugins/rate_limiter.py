"""RateLimiter: Redis token-bucket rate limiter for plugin execution."""
from __future__ import annotations

import asyncio
import time
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class RateLimitExceededError(Exception):
    """Raised when the rate limit is exceeded and wait is not allowed."""


class RateLimiter:
    """Token-bucket rate limiter backed by Redis.

    Each plugin gets its own bucket keyed by name.
    If Redis is unavailable, falls back to an in-memory dict (single-process only).

    Usage:
        limiter = RateLimiter(redis_url="redis://...")
        await limiter.acquire("nmap", max_concurrent=2, timeout=60)
        try:
            ... run tool ...
        finally:
            await limiter.release("nmap")
    """

    def __init__(self, redis_url: str | None = None):
        self._redis_url = redis_url
        self._redis = None
        # In-memory fallback
        self._local_counts: dict[str, int] = {}
        self._local_lock = asyncio.Lock()

    async def _get_redis(self):
        """Lazily connect to Redis."""
        if self._redis is not None:
            return self._redis
        if not self._redis_url:
            return None
        try:
            import redis.asyncio as aioredis

            self._redis = aioredis.from_url(
                self._redis_url, decode_responses=True
            )
            # Test connection
            await self._redis.ping()
            return self._redis
        except Exception as e:
            logger.warning("rate_limiter.redis_unavailable", error=str(e))
            self._redis = None
            return None

    def _key(self, plugin_name: str) -> str:
        return f"drift:ratelimit:{plugin_name}:concurrent"

    async def acquire(
        self,
        plugin_name: str,
        max_concurrent: int,
        timeout: float = 60.0,
    ) -> bool:
        """Acquire a rate limit slot for a plugin.

        Args:
            plugin_name: Plugin identifier.
            max_concurrent: Maximum concurrent executions allowed.
            timeout: How long to wait for a slot (seconds).

        Returns:
            True if acquired, raises RateLimitExceededError if timeout.
        """
        if max_concurrent <= 0:
            return True  # No limit

        r = await self._get_redis()
        start = time.monotonic()

        while True:
            if r:
                acquired = await self._redis_acquire(r, plugin_name, max_concurrent)
            else:
                acquired = await self._local_acquire(plugin_name, max_concurrent)

            if acquired:
                logger.debug(
                    "rate_limiter.acquired",
                    plugin=plugin_name,
                    max=max_concurrent,
                )
                return True

            elapsed = time.monotonic() - start
            if elapsed >= timeout:
                raise RateLimitExceededError(
                    f"Rate limit timeout for plugin '{plugin_name}' "
                    f"(max_concurrent={max_concurrent}, waited={elapsed:.1f}s)"
                )

            await asyncio.sleep(0.5)

    async def release(self, plugin_name: str) -> None:
        """Release a rate limit slot."""
        r = await self._get_redis()
        if r:
            await self._redis_release(r, plugin_name)
        else:
            await self._local_release(plugin_name)

        logger.debug("rate_limiter.released", plugin=plugin_name)

    async def get_current(self, plugin_name: str) -> int:
        """Get current concurrent count for a plugin."""
        r = await self._get_redis()
        if r:
            key = self._key(plugin_name)
            val = await r.get(key)
            return int(val) if val else 0
        else:
            return self._local_counts.get(plugin_name, 0)

    async def _redis_acquire(self, r, plugin_name: str, max_concurrent: int) -> bool:
        """Atomically increment counter if below max, using Redis WATCH/MULTI."""
        key = self._key(plugin_name)
        # Use a Lua script for atomicity
        lua = """
        local current = tonumber(redis.call('GET', KEYS[1]) or '0')
        if current < tonumber(ARGV[1]) then
            redis.call('INCR', KEYS[1])
            redis.call('EXPIRE', KEYS[1], 3600)
            return 1
        end
        return 0
        """
        result = await r.eval(lua, 1, key, str(max_concurrent))
        return result == 1

    async def _redis_release(self, r, plugin_name: str) -> None:
        key = self._key(plugin_name)
        lua = """
        local current = tonumber(redis.call('GET', KEYS[1]) or '0')
        if current > 0 then
            redis.call('DECR', KEYS[1])
        end
        return current
        """
        await r.eval(lua, 1, key)

    async def _local_acquire(self, plugin_name: str, max_concurrent: int) -> bool:
        async with self._local_lock:
            current = self._local_counts.get(plugin_name, 0)
            if current < max_concurrent:
                self._local_counts[plugin_name] = current + 1
                return True
            return False

    async def _local_release(self, plugin_name: str) -> None:
        async with self._local_lock:
            current = self._local_counts.get(plugin_name, 0)
            if current > 0:
                self._local_counts[plugin_name] = current - 1

    async def close(self) -> None:
        """Close Redis connection if open."""
        if self._redis:
            try:
                await self._redis.close()
            except Exception:
                pass
            self._redis = None
