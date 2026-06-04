"""Short-term memory SQLAlchemy model for agent context persistence.

TTL: 7-30 days configurable via MEMORY_SHORT_TTL_DAYS.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from aegis.models.base import Base


class ShortTermMemory(Base):
    __tablename__ = "short_term_memory"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(20), index=True, default="")
    data_type: Mapped[str] = mapped_column(String(50), default="")
    content: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    pipeline_id: Mapped[str] = mapped_column(String(64), default="")
