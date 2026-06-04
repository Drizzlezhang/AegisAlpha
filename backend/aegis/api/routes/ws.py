"""WebSocket route — /api/v1/ws/pipeline for real-time pipeline events."""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from aegis.api.ws_manager import PipelineWSManager

router = APIRouter(tags=["websocket"])

# Singleton WS manager shared with pipeline runner
ws_manager = PipelineWSManager()


@router.websocket("/ws/pipeline")
async def pipeline_ws(ws: WebSocket) -> None:
    """WebSocket endpoint for pipeline event streaming.

    Clients connect to receive real-time pipeline events:
    agent_start, agent_complete, agent_failed, pipeline_complete, trigger_fired.
    """
    await ws_manager.connect(ws)
    try:
        while True:
            # Keep connection alive; client may send ping/pong
            await ws.receive_text()
    except WebSocketDisconnect:
        await ws_manager.disconnect(ws)
    except Exception:
        await ws_manager.disconnect(ws)
