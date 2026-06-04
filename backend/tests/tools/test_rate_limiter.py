"""Test AsyncTokenBucket rate limiter."""

import asyncio
import time

from aegis.tools.rate_limiter import AsyncTokenBucket


class TestAsyncTokenBucket:
    def test_acquire_within_limit(self) -> None:
        """Tokens should be available immediately when under limit."""
        bucket = AsyncTokenBucket(max_tokens=5, period_sec=60)

        async def _run() -> None:
            for _ in range(5):
                await bucket.acquire()

        asyncio.run(_run())

    def test_acquire_exceeds_limit_waits(self) -> None:
        """Exceeding the limit should cause waiting."""
        bucket = AsyncTokenBucket(max_tokens=2, period_sec=60)

        async def _run() -> None:
            start = time.monotonic()
            await bucket.acquire()  # 1
            await bucket.acquire()  # 2
            await bucket.acquire()  # 3 — should wait
            elapsed = time.monotonic() - start
            # Should have waited at least some time for the 3rd token
            assert elapsed > 0.01

        asyncio.run(_run())

    def test_refill_over_time(self) -> None:
        """Tokens should refill over time."""
        bucket = AsyncTokenBucket(max_tokens=2, period_sec=0.1)  # Fast refill

        async def _run() -> None:
            await bucket.acquire()
            await bucket.acquire()
            # Bucket should be empty now
            await asyncio.sleep(0.15)  # Wait for refill
            # Should be able to acquire again without waiting
            start = time.monotonic()
            await bucket.acquire()
            elapsed = time.monotonic() - start
            assert elapsed < 0.05  # Should be near-instant

        asyncio.run(_run())

    def test_concurrent_acquire(self) -> None:
        """Multiple concurrent acquires should be serialized by the lock."""
        bucket = AsyncTokenBucket(max_tokens=3, period_sec=60)
        results: list[float] = []

        async def worker(i: int) -> None:
            start = time.monotonic()
            await bucket.acquire()
            results.append(time.monotonic() - start)

        async def _run() -> None:
            await asyncio.gather(*(worker(i) for i in range(3)))

        asyncio.run(_run())
        assert len(results) == 3
