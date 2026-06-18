"""ThesisCard — Episodic Memory: complete thesis lifecycle record."""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from aegis.models.base import Base


class ThesisCard(Base):
    __tablename__ = "thesis_cards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    direction: Mapped[str] = mapped_column(String(20), nullable=False)
    entry_mode: Mapped[str] = mapped_column(String(20), nullable=False)
    entry_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    entry_price: Mapped[float] = mapped_column(Float, nullable=False)
    target_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    stop_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    key_assumptions: Mapped[dict[str, Any]] = mapped_column(JSON, default=list)
    thesis_valid_status: Mapped[str] = mapped_column(String(20), default="valid")
    re_entry_flagged: Mapped[bool] = mapped_column(Boolean, default=False)
    factor_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    close_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    close_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    actual_pnl_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    judgment_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    execution_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    close_reason: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
