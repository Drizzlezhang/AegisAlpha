"""ThesisStore — query closed ThesisCards for WeightAdapter sample collection."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from aegis.models.thesis import ThesisCard


class ThesisStore:
    """Read-only query interface for ThesisCard (episodic memory)."""

    def get_closed_cards(self, session: Session, since: datetime | None = None) -> list[ThesisCard]:
        """Return closed cards with both judgment_score and execution_score populated.

        Args:
            session: SQLAlchemy session.
            since: Optional lower bound on close_date.

        Returns:
            List of ThesisCard with non-null judgment_score, execution_score, actual_pnl_pct.
        """
        stmt = select(ThesisCard).where(
            ThesisCard.close_date.isnot(None),
            ThesisCard.judgment_score.isnot(None),
            ThesisCard.execution_score.isnot(None),
            ThesisCard.actual_pnl_pct.isnot(None),
        )
        if since is not None:
            stmt = stmt.where(ThesisCard.close_date >= since)
        stmt = stmt.order_by(ThesisCard.close_date.desc())
        return list(session.execute(stmt).scalars().all())

    def get_closed_cards_by_factor(self, session: Session, factor_name: str) -> list[ThesisCard]:
        """Return closed cards that contain the given factor in their factor_snapshot.

        factor_snapshot is a JSON dict like {"trend_phase": 75, "smart_money": 60, ...}.
        """
        all_cards = self.get_closed_cards(session)
        return [c for c in all_cards if c.factor_snapshot and factor_name in c.factor_snapshot]

    def get_first_card_date(self, session: Session) -> datetime | None:
        """Return the earliest ThesisCard created_at, or None if table is empty."""
        stmt = select(ThesisCard.created_at).order_by(ThesisCard.created_at.asc()).limit(1)
        result = session.execute(stmt).scalar_one_or_none()
        return result
