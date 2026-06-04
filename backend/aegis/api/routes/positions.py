"""GET /api/v1/positions — positions list endpoint."""

from fastapi import APIRouter

from aegis.api.schemas.responses import PositionResponse

router = APIRouter(tags=["positions"])


@router.get("/positions", response_model=list[PositionResponse])
async def list_positions() -> list[PositionResponse]:
    return []
