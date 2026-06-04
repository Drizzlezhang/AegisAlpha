"""Pipeline routes — GET /api/v1/pipeline/latest, POST /api/v1/pipeline/run."""

from fastapi import APIRouter

from aegis.api.schemas.responses import (
    PipelineLatestResponse,
    PipelineRunRequest,
    PipelineRunResponse,
)

router = APIRouter(tags=["pipeline"])


@router.get("/pipeline/latest", response_model=PipelineLatestResponse)
async def pipeline_latest() -> PipelineLatestResponse:
    return PipelineLatestResponse()


@router.post("/pipeline/run", response_model=PipelineRunResponse)
async def pipeline_run(request: PipelineRunRequest) -> PipelineRunResponse:
    return PipelineRunResponse(pipeline_id="placeholder")
