"""Agents routes — GET /api/v1/agents."""

from fastapi import APIRouter

from aegis.api.schemas.responses import AgentManifestResponse
from aegis.pipeline.graph_builder import _load_agents_yaml

router = APIRouter(tags=["agents"])


@router.get("/agents", response_model=list[AgentManifestResponse])
async def list_agents() -> list[AgentManifestResponse]:
    config = _load_agents_yaml()
    agents = config.get("agents", {})
    return [
        AgentManifestResponse(
            name=agent.get("name", name),
            version=agent.get("version", "0.1.0"),
            tags=agent.get("tags", []),
            pipeline_mode=agent.get("pipeline_mode", "full"),
            enabled=agent.get("enabled", True),
            llm_dependency=agent.get("llm_dependency", True),
            parallel_group=agent.get("parallel_group"),
        )
        for name, agent in agents.items()
    ]
