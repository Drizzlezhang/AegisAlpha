"""Trigger routes — GET/POST/DELETE /api/v1/triggers."""

from fastapi import APIRouter

from aegis.api.schemas.responses import TriggerCreateRequest, TriggerResponse
from aegis.storage.trigger_store import TriggerStore

router = APIRouter(tags=["triggers"])

_store = TriggerStore()


@router.get("/triggers", response_model=list[TriggerResponse])
async def list_triggers() -> list[TriggerResponse]:
    triggers = await _store.list_all_pending()
    return [TriggerResponse(**t) for t in triggers]


@router.post("/triggers", response_model=TriggerResponse)
async def create_trigger(request: TriggerCreateRequest) -> TriggerResponse:
    trigger_id = await _store.create_trigger({
        "ticker": request.ticker,
        "trigger_type": request.trigger_type,
        "trigger_params": request.trigger_params,
        "suggested_action": request.suggested_action,
        "valid_until": request.valid_until,
    })
    result = await _store.get_trigger(trigger_id)
    if result:
        return TriggerResponse(**result)
    return TriggerResponse(id=trigger_id, ticker=request.ticker)


@router.delete("/triggers/{trigger_id}")
async def delete_trigger(trigger_id: int) -> dict[str, bool]:
    await _store.cancel_trigger(trigger_id)
    return {"deleted": True}
