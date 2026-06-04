"""Positions routes — GET /api/v1/positions, /portfolio/health, /portfolio/delta-dollars."""

from fastapi import APIRouter

from aegis.api.schemas.responses import (
    DeltaDollarsResponse,
    PortfolioHealthResponse,
    PositionResponse,
)

router = APIRouter(tags=["positions"])


@router.get("/positions", response_model=list[PositionResponse])
async def list_positions() -> list[PositionResponse]:
    return []


@router.get("/portfolio/health", response_model=PortfolioHealthResponse)
async def portfolio_health() -> PortfolioHealthResponse:
    """Return health scores and alerts for all passive holdings."""
    return PortfolioHealthResponse()


@router.get("/portfolio/delta-dollars", response_model=DeltaDollarsResponse)
async def delta_dollars() -> DeltaDollarsResponse:
    """Return Delta Dollars summary and budget usage."""
    return DeltaDollarsResponse()
