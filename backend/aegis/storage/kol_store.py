"""KOL Store — CRUD for kol_sources and kol_calls tables."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select, update

from aegis.models.kol import KOLCall, KOLSource


class KOLStore:
    """CRUD operations for kol_sources and kol_calls tables."""

    def __init__(self, session_factory: Any) -> None:
        self._session_factory = session_factory

    # ------------------------------------------------------------------
    # KOL Sources
    # ------------------------------------------------------------------

    async def create_source(self, data: dict[str, Any]) -> int:
        """Create a KOL source. data: name, platform, handle."""
        async with self._session_factory() as session:
            source = KOLSource(**data)
            session.add(source)
            await session.commit()
            await session.refresh(source)
            return source.id

    async def get_source(self, source_id: int) -> KOLSource | None:
        """Get a KOL source by ID."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(KOLSource).where(KOLSource.id == source_id)
            )
            return result.scalar_one_or_none()  # type: ignore[no-any-return]

    async def list_sources(self, enabled_only: bool = True) -> list[KOLSource]:
        """List KOL sources, optionally filtered to enabled only."""
        async with self._session_factory() as session:
            stmt = select(KOLSource)
            if enabled_only:
                stmt = stmt.where(KOLSource.enabled.is_(True))
            stmt = stmt.order_by(KOLSource.reliability_score.desc())
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def update_source(self, source_id: int, data: dict[str, Any]) -> None:
        """Update a KOL source's fields."""
        async with self._session_factory() as session:
            await session.execute(
                update(KOLSource).where(KOLSource.id == source_id).values(**data)
            )
            await session.commit()

    # ------------------------------------------------------------------
    # KOL Calls
    # ------------------------------------------------------------------

    async def record_call(self, call_data: dict[str, Any]) -> int:
        """Record a KOL call.

        call_data: kol_source_id, ticker, direction, call_date, call_price,
                   source_url, content_snippet.
        """
        async with self._session_factory() as session:
            # Normalize call_date
            if isinstance(call_data.get("call_date"), str):
                call_data["call_date"] = datetime.fromisoformat(
                    call_data["call_date"]
                )
            if not call_data.get("call_date"):
                call_data["call_date"] = datetime.now(UTC)

            call = KOLCall(**call_data)
            session.add(call)
            await session.commit()
            await session.refresh(call)
            return call.id

    async def get_pending_attribution(self, days_ago: int = 30) -> list[KOLCall]:
        """Get pending calls older than N days for attribution."""
        cutoff = datetime.now(UTC) - timedelta(days=days_ago)
        async with self._session_factory() as session:
            stmt = (
                select(KOLCall)
                .where(KOLCall.attribution_status == "pending")
                .where(KOLCall.call_date <= cutoff)
                .order_by(KOLCall.call_date.asc())
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def update_attribution(
        self, call_id: int, status: str, pnl_30d: float
    ) -> None:
        """Update attribution status and 30d P&L for a call."""
        async with self._session_factory() as session:
            await session.execute(
                update(KOLCall)
                .where(KOLCall.id == call_id)
                .values(attribution_status=status, pnl_30d=pnl_30d)
            )
            await session.commit()

    async def update_pnl_60d(self, call_id: int, pnl_60d: float) -> None:
        """Update 60d P&L for a call (supplementary)."""
        async with self._session_factory() as session:
            await session.execute(
                update(KOLCall).where(KOLCall.id == call_id).values(pnl_60d=pnl_60d)
            )
            await session.commit()

    async def get_calls_needing_60d_update(self) -> list[KOLCall]:
        """Get calls with 30d attribution but missing 60d P&L."""
        cutoff = datetime.now(UTC) - timedelta(days=60)
        async with self._session_factory() as session:
            stmt = (
                select(KOLCall)
                .where(KOLCall.attribution_status != "pending")
                .where(KOLCall.pnl_60d.is_(None))
                .where(KOLCall.call_date <= cutoff)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_calls_by_ticker(
        self, ticker: str, limit: int = 20
    ) -> list[KOLCall]:
        """Get KOL calls for a specific ticker."""
        async with self._session_factory() as session:
            stmt = (
                select(KOLCall)
                .where(KOLCall.ticker == ticker)
                .order_by(KOLCall.call_date.desc())
                .limit(limit)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_attribution_stats(
        self, source_id: int | None = None
    ) -> dict[str, int]:
        """Get attribution statistics, optionally filtered by source."""
        async with self._session_factory() as session:
            stmt = select(
                KOLCall.attribution_status,
                func.count(KOLCall.id),
            ).group_by(KOLCall.attribution_status)

            if source_id:
                stmt = stmt.where(KOLCall.kol_source_id == source_id)

            result = await session.execute(stmt)
            rows = result.all()
            return {
                "total": sum(count for _, count in rows),
                "validated": next(
                    (c for s, c in rows if s == "validated"), 0
                ),
                "invalidated": next(
                    (c for s, c in rows if s == "invalidated"), 0
                ),
                "pending": next(
                    (c for s, c in rows if s == "pending"), 0
                ),
            }
