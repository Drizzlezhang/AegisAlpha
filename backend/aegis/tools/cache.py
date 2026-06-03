"""Two-tier cache: Parquet for tabular data, SQLite for metadata/JSON."""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

import pandas as pd
from loguru import logger

from aegis.tools.base import ToolResult


class ToolCache:
    """Two-tier local cache for tool results.

    - Parquet: OHLCV and other tabular data
    - SQLite: metadata, JSON responses, company overviews
    """

    def __init__(self, cache_dir: str) -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._db_path = self.cache_dir / "tool_cache.db"
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS tool_cache (
                    tool_name TEXT NOT NULL,
                    cache_key TEXT NOT NULL,
                    data_json TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    ttl_sec REAL NOT NULL,
                    PRIMARY KEY (tool_name, cache_key)
                )"""
            )
            conn.commit()

    def _parquet_path(self, tool_name: str, cache_key: str) -> Path:
        return self.cache_dir / f"{tool_name}_{cache_key}.parquet"

    async def get(self, tool_name: str, cache_key: str) -> ToolResult | None:
        """Try to retrieve a cached result. Returns None on miss or expiry."""
        # Check SQLite first
        with sqlite3.connect(str(self._db_path)) as conn:
            row = conn.execute(
                "SELECT data_json, created_at, ttl_sec "
                "FROM tool_cache WHERE tool_name=? AND cache_key=?",
                (tool_name, cache_key),
            ).fetchone()
            if row:
                data_json, created_at, ttl_sec = row
                if time.time() - created_at < ttl_sec:
                    logger.debug(f"Cache HIT (sqlite): {tool_name}/{cache_key}")
                    return ToolResult(
                        success=True,
                        data=json.loads(data_json),
                        source=tool_name,
                        cached=True,
                    )
                else:
                    logger.debug(f"Cache EXPIRED (sqlite): {tool_name}/{cache_key}")

        # Check Parquet
        pq_path = self._parquet_path(tool_name, cache_key)
        if pq_path.exists():
            mtime = pq_path.stat().st_mtime
            # Default TTL for parquet: 1 day
            if time.time() - mtime < 86400:
                logger.debug(f"Cache HIT (parquet): {tool_name}/{cache_key}")
                df = pd.read_parquet(pq_path)
                return ToolResult(
                    success=True,
                    data=df,
                    source=tool_name,
                    cached=True,
                )
            else:
                logger.debug(f"Cache EXPIRED (parquet): {tool_name}/{cache_key}")

        return None

    async def set(
        self,
        tool_name: str,
        cache_key: str,
        result: ToolResult,
        ttl_sec: int = 86400,
    ) -> None:
        """Store a result in cache."""
        if not result.success:
            return  # Don't cache failures

        data = result.data

        # Store tabular data as Parquet
        if isinstance(data, pd.DataFrame):
            pq_path = self._parquet_path(tool_name, cache_key)
            data.to_parquet(pq_path, index=False)
            logger.debug(f"Cache SET (parquet): {tool_name}/{cache_key}")
            return

        # Store everything else as JSON in SQLite
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO tool_cache "
                "(tool_name, cache_key, data_json, created_at, ttl_sec) "
                "VALUES (?, ?, ?, ?, ?)",
                (tool_name, cache_key, json.dumps(data), time.time(), ttl_sec),
            )
            conn.commit()
        logger.debug(f"Cache SET (sqlite): {tool_name}/{cache_key}")
