"""FactorWeight — factor weight history for WeightAdapter."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from aegis.models.base import Base


class FactorWeight(Base):
    __tablename__ = "factor_weights"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    factor_name: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    weight: Mapped[float] = mapped_column(Float, nullable=False)
    previous_weight: Mapped[float | None] = mapped_column(Float, nullable=True)
    changed_by: Mapped[str] = mapped_column(String(20), default="system")
    observation_period_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sample_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
