"""Pipeline routes — trigger, run, latest."""

import uuid

from fastapi import APIRouter

from aegis.api.routes.ws import ws_manager
from aegis.api.schemas.responses import (
    PipelineLatestResponse,
    PipelineRunRequest,
    PipelineRunResponse,
    PipelineTriggerRequest,
    PipelineTriggerResponse,
)

router = APIRouter(tags=["pipeline"])


@router.get("/pipeline/latest", response_model=PipelineLatestResponse)
async def pipeline_latest() -> PipelineLatestResponse:
    return PipelineLatestResponse()


@router.post("/pipeline/run", response_model=PipelineRunResponse)
async def pipeline_run(request: PipelineRunRequest) -> PipelineRunResponse:
    return PipelineRunResponse(pipeline_id=str(uuid.uuid4())[:8])


@router.post("/pipeline/trigger", response_model=PipelineTriggerResponse)
async def pipeline_trigger(request: PipelineTriggerRequest) -> PipelineTriggerResponse:
    """Manually trigger a pipeline run (full or lightweight).

    Launches the pipeline in the background and returns immediately.
    WebSocket events are broadcast via the shared ws_manager.
    """
    from aegis.pipeline.runner import run_full, run_lightweight

    pipeline_id = str(uuid.uuid4())[:8]

    if request.mode == "lightweight":
        import asyncio

        asyncio.create_task(
            run_lightweight(request.tickers, ws_manager=ws_manager)
        )
    else:
        import asyncio

        ticker = request.tickers[0] if request.tickers else "QQQ"
        asyncio.create_task(run_full(ticker, ws_manager=ws_manager))

    return PipelineTriggerResponse(
        pipeline_id=pipeline_id,
        status="started",
        mode=request.mode,
    )
