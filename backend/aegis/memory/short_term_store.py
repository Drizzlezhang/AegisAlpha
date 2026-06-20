"""ShortTermStore — CRUD + TTL cleanup for short_term_memory table."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from aegis.models.memory import ShortTermMemory


class ShortTermStore:
    """CRUD operations on short_term_memory with automatic TTL filtering."""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def insert(self, data: dict[str, Any], ttl_days: int = 14) -> int:
        """Insert a short-term memory record.

        Args:
            data: Dict with keys: ticker, data_type, content, pipeline_id.
            ttl_days: Days until expiration. Default 14.

        Returns:
            The new record's ID.
        """
        session = self._session_factory()
        try:
            row = ShortTermMemory(
                ticker=data.get("ticker", ""),
                data_type=data.get("data_type", ""),
                content=data.get("content", {}),
                pipeline_id=data.get("pipeline_id", ""),
                expires_at=datetime.now(UTC) + timedelta(days=ttl_days),
            )
            session.add(row)
            session.commit()
            return int(row.id)
        finally:
            session.close()

    def query(
        self,
        ticker: str | None = None,
        data_type: str | None = None,
        pipeline_id: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Query short-term memory, automatically filtering expired records.

        Args:
            ticker: Optional ticker filter.
            data_type: Optional data_type filter.
            pipeline_id: Optional pipeline_id filter.
            limit: Max records to return.

        Returns:
            List of record dicts, newest first.
        """
        session = self._session_factory()
        try:
            stmt = select(ShortTermMemory).where(ShortTermMemory.expires_at > datetime.now(UTC))
            if ticker is not None:
                stmt = stmt.where(ShortTermMemory.ticker == ticker)
            if data_type is not None:
                stmt = stmt.where(ShortTermMemory.data_type == data_type)
            if pipeline_id is not None:
                stmt = stmt.where(ShortTermMemory.pipeline_id == pipeline_id)
            stmt = stmt.order_by(ShortTermMemory.created_at.desc()).limit(limit)
            rows = session.execute(stmt).scalars().all()
            return [
                {
                    "id": r.id,
                    "ticker": r.ticker,
                    "data_type": r.data_type,
                    "content": r.content,
                    "pipeline_id": r.pipeline_id,
                    "expires_at": r.expires_at.isoformat(),
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in rows
            ]
        finally:
            session.close()

    def cleanup_expired(self) -> int:
        """Delete all expired short-term memory records.

        Returns:
            Number of deleted records.
        """
        session = self._session_factory()
        try:
            stmt = delete(ShortTermMemory).where(ShortTermMemory.expires_at <= datetime.now(UTC))
            result = session.execute(stmt)
            session.commit()
            return int(result.rowcount)
        finally:
            session.close()
