"""LongTermStore — CRUD + compression marking for long_term_memory table."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from aegis.models.long_term_memory import LongTermMemory


class LongTermStore:
    """CRUD operations on long_term_memory with compression support."""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def insert(self, data: dict[str, Any]) -> int:
        """Insert a long-term memory record.

        Args:
            data: Dict with keys: ticker, data_type, content, original_date.
                  Optional: summary, is_compressed, embedding_id.

        Returns:
            The new record's ID.
        """
        session = self._session_factory()
        try:
            row = LongTermMemory(
                ticker=data.get("ticker"),
                data_type=data.get("data_type", ""),
                content=data.get("content", {}),
                summary=data.get("summary"),
                original_date=data.get("original_date", datetime.now(UTC)),
                is_compressed=data.get("is_compressed", False),
                embedding_id=data.get("embedding_id"),
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
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        is_compressed: bool | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Query long-term memory with optional filters.

        Args:
            ticker: Optional ticker filter.
            data_type: Optional data_type filter.
            date_from: Optional start of original_date range.
            date_to: Optional end of original_date range.
            is_compressed: Optional compression status filter.
            limit: Max records to return.

        Returns:
            List of record dicts, newest original_date first.
        """
        session = self._session_factory()
        try:
            stmt = select(LongTermMemory)
            if ticker is not None:
                stmt = stmt.where(LongTermMemory.ticker == ticker)
            if data_type is not None:
                stmt = stmt.where(LongTermMemory.data_type == data_type)
            if date_from is not None:
                stmt = stmt.where(LongTermMemory.original_date >= date_from)
            if date_to is not None:
                stmt = stmt.where(LongTermMemory.original_date <= date_to)
            if is_compressed is not None:
                stmt = stmt.where(LongTermMemory.is_compressed == is_compressed)
            stmt = stmt.order_by(LongTermMemory.original_date.desc()).limit(limit)
            rows = session.execute(stmt).scalars().all()
            return [
                {
                    "id": r.id,
                    "ticker": r.ticker,
                    "data_type": r.data_type,
                    "content": r.content,
                    "summary": r.summary,
                    "original_date": r.original_date.isoformat(),
                    "compressed_at": r.compressed_at.isoformat() if r.compressed_at else None,
                    "is_compressed": r.is_compressed,
                    "embedding_id": r.embedding_id,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in rows
            ]
        finally:
            session.close()

    def mark_compressed(
        self,
        record_ids: list[int],
        summary: str,
        embedding_id: str | None = None,
    ) -> int:
        """Mark records as compressed with summary and optional embedding ID.

        Args:
            record_ids: List of record IDs to mark.
            summary: Compression summary text.
            embedding_id: Optional ChromaDB embedding ID.

        Returns:
            Number of updated records.
        """
        if not record_ids:
            return 0
        session = self._session_factory()
        try:
            values: dict[str, Any] = {
                "is_compressed": True,
                "summary": summary,
                "compressed_at": datetime.now(UTC),
            }
            if embedding_id is not None:
                values["embedding_id"] = embedding_id
            stmt = update(LongTermMemory).where(LongTermMemory.id.in_(record_ids)).values(**values)
            result = session.execute(stmt)
            session.commit()
            return int(result.rowcount)
        finally:
            session.close()

    def get_uncompressed_before(
        self, data_type: str, cutoff: datetime, limit: int = 100
    ) -> list[dict[str, Any]]:
        """Get uncompressed records of a given data_type older than cutoff.

        Args:
            data_type: The data_type to query.
            cutoff: Records with original_date before this are candidates.
            limit: Max records to return.

        Returns:
            List of record dicts, oldest first.
        """
        session = self._session_factory()
        try:
            stmt = (
                select(LongTermMemory)
                .where(
                    LongTermMemory.data_type == data_type,
                    LongTermMemory.is_compressed == False,  # noqa: E712
                    LongTermMemory.original_date < cutoff,
                )
                .order_by(LongTermMemory.original_date.asc())
                .limit(limit)
            )
            rows = session.execute(stmt).scalars().all()
            return [
                {
                    "id": r.id,
                    "ticker": r.ticker,
                    "data_type": r.data_type,
                    "content": r.content,
                    "summary": r.summary,
                    "original_date": r.original_date.isoformat(),
                    "is_compressed": r.is_compressed,
                    "embedding_id": r.embedding_id,
                }
                for r in rows
            ]
        finally:
            session.close()

    def summarize(
        self,
        ticker: str | None,
        date_range: tuple[str, str],
        data_type: str = "",
    ) -> dict[str, Any]:
        """Aggregate summary of long-term memory records.

        Args:
            ticker: Optional ticker filter.
            date_range: (start_iso, end_iso) tuple.
            data_type: Optional data_type filter.

        Returns:
            Dict with count, date_range, and data_types present.
        """
        session = self._session_factory()
        try:
            stmt = select(LongTermMemory)
            if ticker is not None:
                stmt = stmt.where(LongTermMemory.ticker == ticker)
            if data_type:
                stmt = stmt.where(LongTermMemory.data_type == data_type)
            if date_range[0]:
                stmt = stmt.where(LongTermMemory.original_date >= date_range[0])
            if date_range[1]:
                stmt = stmt.where(LongTermMemory.original_date <= date_range[1])
            rows = session.execute(stmt).scalars().all()
            data_types = sorted({r.data_type for r in rows})
            return {
                "count": len(rows),
                "date_range": list(date_range),
                "data_types": data_types,
            }
        finally:
            session.close()
