"""Tests for RateLimiter: in-memory token-bucket rate limiting."""
from __future__ import annotations

import asyncio

import pytest

from app.plugins.rate_limiter import RateLimiter, RateLimitExceededError

pytestmark = pytest.mark.asyncio


class TestRateLimiterInMemory:
    """Test the in-memory fallback (no Redis)."""

    async def test_acquire_below_limit(self):
        limiter = RateLimiter()  # No Redis URL = in-memory
        acquired = await limiter.acquire("test_plugin", max_concurrent=3, timeout=1)
        assert acquired is True
        count = await limiter.get_current("test_plugin")
        assert count == 1
        await limiter.release("test_plugin")

    async def test_acquire_up_to_limit(self):
        limiter = RateLimiter()
        for _ in range(3):
            await limiter.acquire("test_plugin", max_concurrent=3, timeout=1)
        count = await limiter.get_current("test_plugin")
        assert count == 3

        # 4th should timeout
        with pytest.raises(RateLimitExceededError):
            await limiter.acquire("test_plugin", max_concurrent=3, timeout=0.5)

        # Release one, then acquire should work
        await limiter.release("test_plugin")
        acquired = await limiter.acquire("test_plugin", max_concurrent=3, timeout=1)
        assert acquired is True

    async def test_release_below_zero(self):
        limiter = RateLimiter()
        # Release without acquire should not go negative
        await limiter.release("unused_plugin")
        count = await limiter.get_current("unused_plugin")
        assert count == 0

    async def test_zero_limit_always_passes(self):
        limiter = RateLimiter()
        # max_concurrent=0 means unlimited
        acquired = await limiter.acquire("unlimited", max_concurrent=0, timeout=1)
        assert acquired is True

    async def test_separate_plugins(self):
        limiter = RateLimiter()
        await limiter.acquire("plugin_a", max_concurrent=1, timeout=1)
        # plugin_b should be independent
        acquired = await limiter.acquire("plugin_b", max_concurrent=1, timeout=1)
        assert acquired is True

        # plugin_a is at limit
        with pytest.raises(RateLimitExceededError):
            await limiter.acquire("plugin_a", max_concurrent=1, timeout=0.5)

    async def test_concurrent_acquire_release(self):
        limiter = RateLimiter()
        results = []

        async def worker(plugin_name, worker_id):
            try:
                await limiter.acquire(plugin_name, max_concurrent=2, timeout=5)
                results.append(f"acquired-{worker_id}")
                await asyncio.sleep(0.1)
                await limiter.release(plugin_name)
                results.append(f"released-{worker_id}")
            except RateLimitExceededError:
                results.append(f"timeout-{worker_id}")

        # Run 4 workers with max_concurrent=2
        tasks = [
            asyncio.create_task(worker("test", i)) for i in range(4)
        ]
        await asyncio.gather(*tasks)

        # All should have acquired eventually (since we release after 0.1s)
        acquired = [r for r in results if r.startswith("acquired")]
        assert len(acquired) == 4

    async def test_close(self):
        limiter = RateLimiter()
        await limiter.close()  # Should not raise


class TestRateLimiterNoRedis:
    """Test behavior when Redis URL is provided but unreachable."""

    async def test_fallback_to_memory(self):
        limiter = RateLimiter(redis_url="redis://localhost:59999/0")
        # Should fall back to in-memory
        acquired = await limiter.acquire("test", max_concurrent=2, timeout=1)
        assert acquired is True
        await limiter.release("test")
        await limiter.close()
