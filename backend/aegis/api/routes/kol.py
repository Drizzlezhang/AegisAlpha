"""KOL REST API routes — sources, calls, and attribution report."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from aegis.api.deps import get_attribution_service, get_kol_store
from aegis.services.kol_attribution import KOLAttributionService
from aegis.storage.kol_store import KOLStore

router = APIRouter(tags=["kol"])


# ---------------------------------------------------------------------------
# Request/Response Models
# ---------------------------------------------------------------------------


class KOLSourceCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    platform: str = Field(..., pattern="^(x|stocktwits|reddit)$")
    handle: str = Field(..., min_length=1, max_length=100)


class KOLSourceUpdateRequest(BaseModel):
    enabled: bool | None = None
    name: str | None = Field(None, min_length=1, max_length=100)


# ---------------------------------------------------------------------------
# Source endpoints
# ---------------------------------------------------------------------------


@router.get("/kol/sources")
async def list_sources(
    enabled_only: bool = Query(True),
    store: KOLStore = Depends(get_kol_store),
) -> dict[str, Any]:
    """List KOL sources with reliability scores."""
    sources = await store.list_sources(enabled_only=enabled_only)
    return {
        "items": [
            {
                "id": s.id,
                "name": s.name,
                "platform": s.platform,
                "handle": s.handle,
                "reliability_score": s.reliability_score,
                "total_calls": s.total_calls,
                "successful_calls": s.successful_calls,
                "enabled": s.enabled,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in sources
        ]
    }


@router.get("/kol/sources/{source_id}")
async def get_source(
    source_id: int,
    store: KOLStore = Depends(get_kol_store),
) -> dict[str, Any]:
    """Get a single KOL source by ID."""
    source = await store.get_source(source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="KOL source not found")
    return {
        "id": source.id,
        "name": source.name,
        "platform": source.platform,
        "handle": source.handle,
        "reliability_score": source.reliability_score,
        "total_calls": source.total_calls,
        "successful_calls": source.successful_calls,
        "enabled": source.enabled,
        "created_at": source.created_at.isoformat() if source.created_at else None,
    }


@router.post("/kol/sources", status_code=201)
async def create_source(
    request: KOLSourceCreateRequest,
    store: KOLStore = Depends(get_kol_store),
) -> dict[str, Any]:
    """Create a new KOL source."""
    source_id = await store.create_source({
        "name": request.name,
        "platform": request.platform,
        "handle": request.handle,
    })
    return {"id": source_id, "message": "KOL source created"}


@router.patch("/kol/sources/{source_id}")
async def update_source(
    source_id: int,
    request: KOLSourceUpdateRequest,
    store: KOLStore = Depends(get_kol_store),
) -> dict[str, str]:
    """Update a KOL source (enable/disable, rename)."""
    source = await store.get_source(source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="KOL source not found")

    update_data = {k: v for k, v in request.model_dump().items() if v is not None}
    if update_data:
        await store.update_source(source_id, update_data)

    return {"message": "Updated"}


# ---------------------------------------------------------------------------
# Call endpoints
# ---------------------------------------------------------------------------


@router.get("/kol/calls")
async def list_calls(
    ticker: str | None = Query(None),
    status: str | None = Query(None, pattern="^(pending|validated|invalidated)$"),
    source_id: int | None = Query(None),
    limit: int = Query(20, ge=1, le=200),
    store: KOLStore = Depends(get_kol_store),
) -> dict[str, Any]:
    """List KOL calls with optional filters."""
    if ticker:
        calls = await store.get_calls_by_ticker(ticker, limit=limit)
    else:
        # For non-ticker queries, return recent calls from pending attribution
        calls = await store.get_pending_attribution(days_ago=0)
        calls = calls[:limit]

    # Apply additional filters
    if status:
        calls = [c for c in calls if c.attribution_status == status]
    if source_id:
        calls = [c for c in calls if c.kol_source_id == source_id]

    return {
        "items": [
            {
                "id": c.id,
                "kol_source_id": c.kol_source_id,
                "ticker": c.ticker,
                "direction": c.direction,
                "call_date": c.call_date.isoformat() if c.call_date else None,
                "call_price": c.call_price,
                "attribution_status": c.attribution_status,
                "pnl_30d": c.pnl_30d,
                "pnl_60d": c.pnl_60d,
                "source_url": c.source_url,
                "content_snippet": c.content_snippet,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in calls
        ]
    }


# ---------------------------------------------------------------------------
# Attribution report endpoint
# ---------------------------------------------------------------------------


@router.get("/kol/attribution/report")
async def get_attribution_report(
    source_id: int | None = Query(None),
    service: KOLAttributionService = Depends(get_attribution_service),
) -> dict[str, Any]:
    """Get KOL attribution statistics report."""
    return await service.get_attribution_report(source_id=source_id)
