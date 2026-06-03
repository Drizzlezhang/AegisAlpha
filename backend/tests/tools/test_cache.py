"""Test ToolCache — Parquet + SQLite two-tier cache."""

import tempfile
from pathlib import Path

import pandas as pd
import pytest

from aegis.tools.base import ToolResult
from aegis.tools.cache import ToolCache


class TestToolCache:
    @pytest.fixture
    def cache(self) -> ToolCache:
        with tempfile.TemporaryDirectory() as tmpdir:
            yield ToolCache(tmpdir)

    @pytest.mark.asyncio
    async def test_get_miss(self, cache: ToolCache) -> None:
        """Cache miss should return None."""
        result = await cache.get("yfinance", "QQQ_2y")
        assert result is None

    @pytest.mark.asyncio
    async def test_set_and_get_json(self, cache: ToolCache) -> None:
        """JSON data should be stored in SQLite and retrievable."""
        data = {"price": 450.0, "change": 2.5}
        tr = ToolResult(success=True, data=data, source="yfinance")
        await cache.set("yfinance", "QQQ_quote", tr)

        cached = await cache.get("yfinance", "QQQ_quote")
        assert cached is not None
        assert cached.success is True
        assert cached.cached is True
        assert cached.data == data

    @pytest.mark.asyncio
    async def test_set_and_get_parquet(self, cache: ToolCache) -> None:
        """DataFrame data should be stored as Parquet and retrievable."""
        df = pd.DataFrame({"Date": ["2024-01-01"], "Close": [450.0]})
        tr = ToolResult(success=True, data=df, source="yfinance")
        await cache.set("yfinance", "QQQ_2y", tr)

        cached = await cache.get("yfinance", "QQQ_2y")
        assert cached is not None
        assert cached.success is True
        assert cached.cached is True
        assert isinstance(cached.data, pd.DataFrame)
        assert len(cached.data) == 1

    @pytest.mark.asyncio
    async def test_does_not_cache_failures(self, cache: ToolCache) -> None:
        """Failed results should not be cached."""
        tr = ToolResult(success=False, error="timeout", source="yfinance")
        await cache.set("yfinance", "QQQ_fail", tr)

        cached = await cache.get("yfinance", "QQQ_fail")
        assert cached is None

    @pytest.mark.asyncio
    async def test_expiry(self, cache: ToolCache) -> None:
        """Expired cache entries should return None."""
        tr = ToolResult(success=True, data={"x": 1}, source="test")
        await cache.set("test", "expired", tr, ttl_sec=0)  # Immediate expiry

        cached = await cache.get("test", "expired")
        assert cached is None
