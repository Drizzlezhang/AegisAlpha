"""GET /api/v1/health — health check endpoint."""

from fastapi import APIRouter

from aegis.api.schemas.responses import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    return HealthResponse(status="ok", version="0.1.0")
