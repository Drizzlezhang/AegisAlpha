"""LongTermMemory — long-term memory with compression support."""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from aegis.models.base import Base


class LongTermMemory(Base):
    __tablename__ = "long_term_memory"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker: Mapped[str | None] = mapped_column(String(20), index=True, nullable=True)
    data_type: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    content: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    original_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    compressed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_compressed: Mapped[bool] = mapped_column(Boolean, default=False)
    embedding_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
