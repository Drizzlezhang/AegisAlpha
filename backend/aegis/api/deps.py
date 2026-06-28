"""Dependency injection for FastAPI routes."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from aegis.memory.long_term_store import LongTermStore
from aegis.memory.service import MemoryService
from aegis.memory.short_term_store import ShortTermStore
from aegis.memory.thesis_store import ThesisStore as MemoryThesisStore
from aegis.memory.vector_store import VectorStore
from aegis.memory.weight_adapter import WeightAdapter
from aegis.memory.weight_store import WeightStore
from aegis.services.kol_attribution import KOLAttributionService
from aegis.services.thesis_service import ThesisService
from aegis.storage.kol_store import KOLStore
from aegis.storage.thesis_store import ThesisStore
from aegis.tools.market.yfinance_adapter import YFinanceAdapter
from aegis.utils.settings import Settings, settings


def get_settings() -> Settings:
    return settings


def get_thesis_service() -> ThesisService:
    """Build ThesisService with all required dependencies.

    Uses sync Session for WeightAdapter/LongTermStore and
    async session factory for ThesisStore CRUD.
    """
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

    engine = create_engine(settings.DATABASE_URL, echo=False)

    def sync_session_factory() -> Session:
        return Session(engine)

    async_engine = create_async_engine(
        settings.DATABASE_URL.replace("sqlite:///", "sqlite+aiosqlite:///"),
        echo=False,
    )

    def async_session_factory() -> AsyncSession:
        return AsyncSession(async_engine)

    thesis_store = ThesisStore(async_session_factory)
    short_term = ShortTermStore(sync_session_factory)
    long_term = LongTermStore(sync_session_factory)
    vector = VectorStore()
    memory = MemoryService(short_term, long_term, vector)

    weight_store = WeightStore()
    memory_thesis_store = MemoryThesisStore()
    weight_adapter = WeightAdapter(weight_store, memory_thesis_store)

    return ThesisService(
        thesis_store=thesis_store,
        memory=memory,
        weight_adapter=weight_adapter,
        long_term_store=long_term,
        session_factory=sync_session_factory,
    )


def get_kol_store() -> KOLStore:
    """Build KOLStore with async session factory."""
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

    async_engine = create_async_engine(
        settings.DATABASE_URL.replace("sqlite:///", "sqlite+aiosqlite:///"),
        echo=False,
    )

    def async_session_factory() -> AsyncSession:
        return AsyncSession(async_engine)

    return KOLStore(async_session_factory)


def get_attribution_service() -> KOLAttributionService:
    """Build KOLAttributionService with KOLStore and YFinanceAdapter."""
    kol_store = get_kol_store()
    price_fetcher = YFinanceAdapter()
    return KOLAttributionService(kol_store=kol_store, price_fetcher=price_fetcher)
