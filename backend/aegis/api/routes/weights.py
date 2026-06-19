"""Weights routes — GET /api/v1/memory/weights, history, manual override."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from aegis.memory.observation_period import ObservationPeriodManager
from aegis.memory.thesis_store import ThesisStore
from aegis.memory.weight_adapter import WeightAdapter
from aegis.memory.weight_store import WeightStore
from aegis.utils.settings import settings

router = APIRouter(tags=["weights"])

# ---------------------------------------------------------------------------
# Response models (inline to avoid circular imports with schemas/responses.py)
# ---------------------------------------------------------------------------


class WeightFactorItem(BaseModel):
    weight: float
    previous_weight: float | None = None
    changed_by: str = "system"
    observation_period_active: bool = True
    sample_count: int = 0
    updated_at: str | None = None


class WeightSnapshotResponse(BaseModel):
    factors: dict[str, WeightFactorItem]
    observation_period_active: bool
    observation_days_remaining: int | None = None


class WeightHistoryItem(BaseModel):
    factor_name: str
    weight: float
    previous_weight: float | None = None
    changed_by: str = "system"
    sample_count: int = 0
    updated_at: str | None = None


class WeightOverrideRequest(BaseModel):
    weight: float = Field(ge=0.2, le=3.0, description="New weight, clamped to [0.2, 3.0]")
    reason: str = ""


class WeightOverrideResponse(BaseModel):
    factor: str
    previous_weight: float
    new_weight: float
    changed_by: str = "manual"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_session() -> Session:
    engine = create_engine(settings.DATABASE_URL)
    return Session(engine)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/memory/weights", response_model=WeightSnapshotResponse)
async def get_weights() -> WeightSnapshotResponse:
    """Return current weights for all factors + observation period status."""
    session = _get_session()
    try:
        store = WeightStore()
        thesis_store = ThesisStore()
        weight_adapter = WeightAdapter(store, thesis_store)
        manager = ObservationPeriodManager(store, thesis_store, weight_adapter)

        factors_raw = store.get_all_weights(session)
        factors = {name: WeightFactorItem(**data) for name, data in factors_raw.items()}
        in_period = manager.is_in_observation_period(session)

        remaining: int | None = None
        if in_period:
            first = thesis_store.get_first_card_date(session)
            if first is not None:
                from datetime import UTC, datetime

                if first.tzinfo is None:
                    first = first.replace(tzinfo=UTC)
                age_days = (datetime.now(UTC) - first).total_seconds() / 86400.0
                remaining = max(0, settings.OBSERVATION_PERIOD_DAYS - int(age_days))

        return WeightSnapshotResponse(
            factors=factors,
            observation_period_active=in_period,
            observation_days_remaining=remaining,
        )
    finally:
        session.close()


@router.get("/memory/weights/history", response_model=list[WeightHistoryItem])
async def get_weight_history(factor: str | None = None) -> list[WeightHistoryItem]:
    """Return weight change history, optionally filtered by factor name."""
    session = _get_session()
    try:
        store = WeightStore()
        history = store.get_weight_history(session, factor_name=factor)
        return [WeightHistoryItem(**item) for item in history]
    finally:
        session.close()


@router.post(
    "/memory/weights/{factor}/override",
    response_model=WeightOverrideResponse,
)
async def override_weight(factor: str, body: WeightOverrideRequest) -> WeightOverrideResponse:
    """Manually override a factor's weight."""
    session = _get_session()
    try:
        store = WeightStore()
        previous = store.get_weight(session, factor)
        store.update_weight(
            session,
            factor_name=factor,
            new_weight=body.weight,
            sample_count=0,
            changed_by="manual",
        )
        return WeightOverrideResponse(
            factor=factor,
            previous_weight=previous,
            new_weight=body.weight,
            changed_by="manual",
        )
    finally:
        session.close()
