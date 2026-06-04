"""Trigger routes — GET/POST/DELETE /api/v1/triggers."""

from fastapi import APIRouter

from aegis.api.schemas.responses import TriggerCreateRequest, TriggerResponse

router = APIRouter(tags=["triggers"])


@router.get("/triggers", response_model=list[TriggerResponse])
async def list_triggers() -> list[TriggerResponse]:
    return []


@router.post("/triggers", response_model=TriggerResponse)
async def create_trigger(request: TriggerCreateRequest) -> TriggerResponse:
    return TriggerResponse(id=0, ticker=request.ticker, condition=request.condition)


@router.delete("/triggers/{trigger_id}")
async def delete_trigger(trigger_id: int) -> dict[str, bool]:
    return {"deleted": True}
