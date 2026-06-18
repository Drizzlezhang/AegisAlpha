"""KOL models — source management and call attribution."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from aegis.models.base import Base


class KOLSource(Base):
    __tablename__ = "kol_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    platform: Mapped[str] = mapped_column(String(20), nullable=False)
    handle: Mapped[str] = mapped_column(String(100), nullable=False)
    reliability_score: Mapped[float] = mapped_column(Float, default=0.5)
    total_calls: Mapped[int] = mapped_column(Integer, default=0)
    successful_calls: Mapped[int] = mapped_column(Integer, default=0)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class KOLCall(Base):
    __tablename__ = "kol_calls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kol_source_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    ticker: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    direction: Mapped[str] = mapped_column(String(10), nullable=False)
    call_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    call_price: Mapped[float] = mapped_column(Float, nullable=False)
    attribution_status: Mapped[str] = mapped_column(String(20), default="pending")
    pnl_30d: Mapped[float | None] = mapped_column(Float, nullable=True)
    pnl_60d: Mapped[float | None] = mapped_column(Float, nullable=True)
    source_url: Mapped[str] = mapped_column(Text, default="")
    content_snippet: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
