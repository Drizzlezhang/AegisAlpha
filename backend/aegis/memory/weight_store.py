"""WeightStore — CRUD for factor_weights table."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from aegis.models.factor_weight import FactorWeight


class WeightStore:
    """Encapsulates all factor_weights table operations.

    Each factor has exactly one row in factor_weights (the current weight).
    Updates record previous_weight before overwriting.
    """

    def get_weight(self, session: Session, factor_name: str) -> float:
        """Return current weight for a factor, or 1.0 if not found."""
        stmt = select(FactorWeight).where(FactorWeight.factor_name == factor_name)
        result = session.execute(stmt).scalar_one_or_none()
        return result.weight if result else 1.0

    def get_all_weights(self, session: Session) -> dict[str, dict[str, Any]]:
        """Return all factor weights with metadata.

        Returns:
            Dict like {"trend_phase": {"weight": 1.0, "previous_weight": None, ...}, ...}
        """
        stmt = select(FactorWeight).order_by(FactorWeight.factor_name)
        rows = session.execute(stmt).scalars().all()
        return {
            r.factor_name: {
                "weight": r.weight,
                "previous_weight": r.previous_weight,
                "changed_by": r.changed_by,
                "observation_period_active": r.observation_period_active,
                "sample_count": r.sample_count,
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            }
            for r in rows
        }

    def update_weight(
        self,
        session: Session,
        factor_name: str,
        new_weight: float,
        sample_count: int = 0,
        changed_by: str = "system",
    ) -> None:
        """Update a factor's weight, recording previous_weight.

        If the factor row doesn't exist, create it with previous_weight=None.
        """
        stmt = select(FactorWeight).where(FactorWeight.factor_name == factor_name)
        row = session.execute(stmt).scalar_one_or_none()

        if row is None:
            row = FactorWeight(
                factor_name=factor_name,
                weight=new_weight,
                previous_weight=None,
                changed_by=changed_by,
                observation_period_active=True,
                sample_count=sample_count,
            )
            session.add(row)
        else:
            row.previous_weight = row.weight
            row.weight = new_weight
            row.changed_by = changed_by
            row.sample_count = sample_count
            row.updated_at = datetime.now(UTC)

        session.commit()

    def get_weight_history(self, session: Session, factor_name: str | None = None) -> list[dict[str, Any]]:
        """Return weight change history.

        Note: factor_weights stores only the current row, so history is limited
        to the current state + previous_weight. For full audit trail, a separate
        history table would be needed. This returns the current state as a single
        history entry per factor.

        Args:
            session: SQLAlchemy session.
            factor_name: Optional filter by factor name.

        Returns:
            List of dicts with factor_name, weight, previous_weight, changed_by,
            sample_count, updated_at.
        """
        stmt = select(FactorWeight).order_by(FactorWeight.factor_name)
        if factor_name:
            stmt = stmt.where(FactorWeight.factor_name == factor_name)
        rows = session.execute(stmt).scalars().all()
        return [
            {
                "factor_name": r.factor_name,
                "weight": r.weight,
                "previous_weight": r.previous_weight,
                "changed_by": r.changed_by,
                "sample_count": r.sample_count,
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            }
            for r in rows
        ]

    def initialize_from_config(self, session: Session, config_path: str = "") -> None:
        """Load initial weights from config/weights.yaml if table is empty.

        Args:
            session: SQLAlchemy session.
            config_path: Path to weights.yaml. Defaults to backend/config/weights.yaml.
        """
        # Check if table already has data
        existing = session.execute(select(FactorWeight)).first()
        if existing is not None:
            return

        if not config_path:
            config_path = str(
                Path(__file__).resolve().parent.parent.parent / "config" / "weights.yaml"
            )

        with open(config_path) as f:
            config = yaml.safe_load(f)

        factors = config.get("factors", {})
        for name, cfg in factors.items():
            row = FactorWeight(
                factor_name=name,
                weight=float(cfg.get("weight", 1.0)),
                previous_weight=None,
                changed_by="system",
                observation_period_active=True,
                sample_count=0,
            )
            session.add(row)

        session.commit()

    def is_observation_period_active(self, session: Session) -> bool:
        """Check if any factor still has observation_period_active=True."""
        stmt = select(FactorWeight).where(FactorWeight.observation_period_active.is_(True)).limit(1)
        return session.execute(stmt).first() is not None
