"""ThesisStore — thesis_cards table CRUD operations (AsyncSession).

Distinct from aegis.memory.thesis_store.ThesisStore (read-only, sync Session).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select, update

from aegis.models.thesis import ThesisCard


class ThesisStore:
    """CRUD operations on thesis_cards table using SQLAlchemy AsyncSession."""

    def __init__(self, session_factory: Any) -> None:
        self._session_factory = session_factory

    async def create(self, card_data: dict[str, Any]) -> int:
        """Create a ThesisCard record.

        Required keys: ticker, direction, entry_mode, entry_date,
                       entry_price, key_assumptions, factor_snapshot.

        Returns:
            New record id.
        """
        async with self._session_factory() as session:
            card = ThesisCard(**card_data)
            session.add(card)
            await session.commit()
            await session.refresh(card)
            return card.id

    async def get_by_id(self, thesis_id: int) -> ThesisCard | None:
        """Get a ThesisCard by id."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(ThesisCard).where(ThesisCard.id == thesis_id)
            )
            return result.scalar_one_or_none()

    async def get_active(self, ticker: str | None = None) -> list[ThesisCard]:
        """Get active (unclosed) ThesisCards, optionally filtered by ticker."""
        async with self._session_factory() as session:
            stmt = select(ThesisCard).where(ThesisCard.close_date.is_(None))
            if ticker:
                stmt = stmt.where(ThesisCard.ticker == ticker)
            stmt = stmt.order_by(ThesisCard.entry_date.desc())
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_closed_with_scores(self) -> list[dict[str, Any]]:
        """Get closed ThesisCards with both scores populated.

        Returns dicts (cross-session safe), not ORM objects.
        """
        async with self._session_factory() as session:
            stmt = (
                select(ThesisCard)
                .where(ThesisCard.close_date.is_not(None))
                .where(ThesisCard.judgment_score.is_not(None))
                .where(ThesisCard.execution_score.is_not(None))
                .where(ThesisCard.actual_pnl_pct.is_not(None))
                .order_by(ThesisCard.close_date.desc())
            )
            result = await session.execute(stmt)
            cards = result.scalars().all()
            return [
                {
                    "id": c.id,
                    "ticker": c.ticker,
                    "direction": c.direction,
                    "entry_price": c.entry_price,
                    "close_price": c.close_price,
                    "close_date": c.close_date,
                    "actual_pnl_pct": c.actual_pnl_pct,
                    "judgment_score": c.judgment_score,
                    "execution_score": c.execution_score,
                    "factor_snapshot": c.factor_snapshot or {},
                }
                for c in cards
            ]

    async def get_earliest_card(self) -> ThesisCard | None:
        """Get the earliest created ThesisCard (for observation period check)."""
        async with self._session_factory() as session:
            stmt = select(ThesisCard).order_by(ThesisCard.created_at.asc()).limit(1)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_recently_closed(
        self, ticker: str, days: int = 90
    ) -> list[ThesisCard]:
        """Get recently closed ThesisCards for a ticker (for re-entry check)."""
        cutoff = datetime.now(UTC) - timedelta(days=days)
        async with self._session_factory() as session:
            stmt = (
                select(ThesisCard)
                .where(ThesisCard.ticker == ticker)
                .where(ThesisCard.close_date.is_not(None))
                .where(ThesisCard.close_date >= cutoff)
                .order_by(ThesisCard.close_date.desc())
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def update(self, thesis_id: int, data: dict[str, Any]) -> None:
        """Partial update of a ThesisCard. Automatically sets updated_at."""
        async with self._session_factory() as session:
            values = {**data, "updated_at": datetime.now(UTC)}
            await session.execute(
                update(ThesisCard)
                .where(ThesisCard.id == thesis_id)
                .values(**values)
            )
            await session.commit()

    async def close(self, thesis_id: int, close_data: dict[str, Any]) -> None:
        """Close a ThesisCard. Delegates to update().

        close_data must contain: close_date, close_price, actual_pnl_pct,
                                  judgment_score, execution_score, close_reason.
        """
        await self.update(thesis_id, close_data)

    async def list_all(
        self,
        filters: dict[str, Any] | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ThesisCard]:
        """List ThesisCards with optional filters and pagination.

        Supported filters:
            status: "valid" | "partial_broken" | "fully_broken" | "closed"
            ticker: exact match
            direction: "long" | "short_put" | "cc"
        """
        async with self._session_factory() as session:
            stmt = select(ThesisCard)

            if filters:
                if filters.get("status") == "closed":
                    stmt = stmt.where(ThesisCard.close_date.is_not(None))
                elif filters.get("status"):
                    stmt = stmt.where(
                        ThesisCard.thesis_valid_status == filters["status"]
                    ).where(ThesisCard.close_date.is_(None))

                if filters.get("ticker"):
                    stmt = stmt.where(ThesisCard.ticker == filters["ticker"])
                if filters.get("direction"):
                    stmt = stmt.where(ThesisCard.direction == filters["direction"])

            stmt = (
                stmt.order_by(ThesisCard.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())
