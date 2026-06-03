"""Async token bucket rate limiter."""

import asyncio
import time


class AsyncTokenBucket:
    """Token bucket rate limiter with async acquire."""

    def __init__(self, max_tokens: int, period_sec: float) -> None:
        self.max_tokens = max_tokens
        self.period_sec = period_sec
        self._tokens = float(max_tokens)
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        rate = self.max_tokens / self.period_sec
        self._tokens = min(self.max_tokens, self._tokens + elapsed * rate)
        self._last_refill = now

    async def acquire(self) -> None:
        """Wait until a token is available, then consume one."""
        async with self._lock:
            self._refill()
            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return
            # Calculate wait time for next token
            wait = (1.0 - self._tokens) * self.period_sec / self.max_tokens
            self._tokens = 0.0
        await asyncio.sleep(wait)
        async with self._lock:
            self._refill()
            self._tokens -= 1.0
