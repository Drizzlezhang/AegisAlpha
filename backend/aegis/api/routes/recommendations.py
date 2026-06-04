"""GET /api/v1/recommendations — recommendations list endpoint."""

from fastapi import APIRouter

from aegis.api.schemas.responses import RecommendationResponse

router = APIRouter(tags=["recommendations"])


@router.get("/recommendations", response_model=list[RecommendationResponse])
async def list_recommendations() -> list[RecommendationResponse]:
    return []
