"""GET /api/v1/agents — agent manifest list endpoint."""

from fastapi import APIRouter

from aegis.api.schemas.responses import AgentManifestResponse

router = APIRouter(tags=["agents"])


@router.get("/agents", response_model=list[AgentManifestResponse])
async def list_agents() -> list[AgentManifestResponse]:
    return []
