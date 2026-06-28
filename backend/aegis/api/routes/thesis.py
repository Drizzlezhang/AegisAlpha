"""Thesis REST API routes — CRUD + close + validation history."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from aegis.api.deps import get_thesis_service
from aegis.services.thesis_service import ThesisService

router = APIRouter(tags=["thesis"])


# ---------------------------------------------------------------------------
# Request/Response Models
# ---------------------------------------------------------------------------


class ThesisCreateRequest(BaseModel):
    ticker: str
    direction: str = Field(..., pattern="^(long|short_put|cc)$")
    entry_mode: str = Field(default="active_right", pattern="^(active_left|active_right|passive)$")
    entry_price: float
    target_price: float | None = None
    stop_price: float | None = None
    key_assumptions: list[str] = Field(default_factory=list)


class ThesisCloseRequest(BaseModel):
    close_price: float
    judgment_score: int = Field(..., ge=1, le=5)
    execution_score: int = Field(..., ge=1, le=5)
    close_reason: str = Field(default="manual", pattern="^(stop_hit|target_reached|thesis_broken|manual)$")


class ThesisUpdateRequest(BaseModel):
    target_price: float | None = None
    stop_price: float | None = None
    key_assumptions: list[str] | None = None
    entry_mode: str | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/thesis")
async def list_theses(
    status: str | None = Query(None, pattern="^(valid|partial_broken|fully_broken|closed)$"),
    ticker: str | None = None,
    direction: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    service: ThesisService = Depends(get_thesis_service),
) -> dict[str, Any]:
    """List ThesisCards with optional filters and pagination."""
    filters: dict[str, Any] = {}
    if status:
        filters["status"] = status
    if ticker:
        filters["ticker"] = ticker
    if direction:
        filters["direction"] = direction

    cards = await service._store.list_all(filters, limit, offset)
    return {
        "items": [service._card_to_dict(c) for c in cards],
        "limit": limit,
        "offset": offset,
    }


@router.get("/thesis/{thesis_id}")
async def get_thesis(
    thesis_id: int,
    service: ThesisService = Depends(get_thesis_service),
) -> dict[str, Any]:
    """Get a single ThesisCard by ID."""
    card = await service._store.get_by_id(thesis_id)
    if card is None:
        raise HTTPException(status_code=404, detail="Thesis not found")
    return service._card_to_dict(card)


@router.post("/thesis", status_code=201)
async def create_thesis(
    request: ThesisCreateRequest,
    service: ThesisService = Depends(get_thesis_service),
) -> dict[str, Any]:
    """Manually create a ThesisCard.

    Note: Normally created automatically by Pipeline. This endpoint is for
    special cases.
    """
    recommendation = request.model_dump()
    try:
        thesis_id = await service.create_from_recommendation(
            recommendation=recommendation,
            weight_snapshot={},
            user_confirmed=True,
        )
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    return {"id": thesis_id, "message": "Thesis created"}


@router.post("/thesis/{thesis_id}/close")
async def close_thesis(
    thesis_id: int,
    request: ThesisCloseRequest,
    service: ThesisService = Depends(get_thesis_service),
) -> dict[str, Any]:
    """Close a ThesisCard with dual-dimension scoring.

    Triggers: Episodic Memory write + WeightAdapter update.
    """
    try:
        result = await service.close_thesis(
            thesis_id=thesis_id,
            close_price=request.close_price,
            judgment_score=request.judgment_score,
            execution_score=request.execution_score,
            close_reason=request.close_reason,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return result


@router.patch("/thesis/{thesis_id}")
async def update_thesis(
    thesis_id: int,
    request: ThesisUpdateRequest,
    service: ThesisService = Depends(get_thesis_service),
) -> dict[str, str]:
    """Partial update of a ThesisCard."""
    card = await service._store.get_by_id(thesis_id)
    if card is None:
        raise HTTPException(status_code=404, detail="Thesis not found")
    if card.close_date is not None:
        raise HTTPException(status_code=400, detail="Cannot update closed thesis")

    update_data = {k: v for k, v in request.model_dump().items() if v is not None}
    if update_data:
        await service._store.update(thesis_id, update_data)

    return {"message": "Updated"}


@router.get("/thesis/{thesis_id}/history")
async def get_validation_history(
    thesis_id: int,
    service: ThesisService = Depends(get_thesis_service),
) -> dict[str, Any]:
    """Get validation history for a ThesisCard from Long-term Memory."""
    card = await service._store.get_by_id(thesis_id)
    if card is None:
        raise HTTPException(status_code=404, detail="Thesis not found")

    records = await service._memory.read(
        "long",
        {"data_type": "thesis_validation", "ticker": card.ticker},
        limit=50,
    )
    return {"thesis_id": thesis_id, "history": records}
