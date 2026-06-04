"""Flows routes — GET /api/v1/flows/etf, /flows/sector, /flows/smart-money/{ticker}."""

from fastapi import APIRouter

from aegis.api.schemas.responses import (
    FlowETFResponse,
    FlowSectorResponse,
    FlowSmartMoneyResponse,
)

router = APIRouter(tags=["flows"])


@router.get("/flows/etf", response_model=list[FlowETFResponse])
async def etf_flows() -> list[FlowETFResponse]:
    """Return ETF fund flow data."""
    return [
        FlowETFResponse(ticker="QQQ", net_flow=1.2e9, flow_pct=0.8, period="5d"),
        FlowETFResponse(ticker="SPY", net_flow=2.5e9, flow_pct=1.2, period="5d"),
    ]


@router.get("/flows/sector", response_model=list[FlowSectorResponse])
async def sector_flows() -> list[FlowSectorResponse]:
    """Return sector rotation data."""
    return [
        FlowSectorResponse(sector="Technology", rotation_score=0.75, flow_direction="inflow"),
        FlowSectorResponse(sector="Energy", rotation_score=-0.30, flow_direction="outflow"),
        FlowSectorResponse(sector="Healthcare", rotation_score=0.10, flow_direction="neutral"),
    ]


@router.get("/flows/smart-money/{ticker}", response_model=FlowSmartMoneyResponse)
async def smart_money_flow(ticker: str) -> FlowSmartMoneyResponse:
    """Return Smart Money details for a ticker."""
    return FlowSmartMoneyResponse(ticker=ticker.upper())
