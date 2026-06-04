"""WebSocket manager for pipeline event broadcasting.

Manages WebSocket connections and broadcasts pipeline lifecycle events:
agent_start, agent_complete, agent_failed, pipeline_complete, trigger_fired.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from fastapi import WebSocket
from loguru import logger


class PipelineWSManager:
    """Manages WebSocket connections for pipeline event broadcasting.

    Thread-safe connection management with graceful disconnect handling.
    Events are broadcast as JSON to all connected clients.
    """

    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()

    async def connect(self, ws: WebSocket) -> None:
        """Accept a new WebSocket connection."""
        await ws.accept()
        self._connections.add(ws)
        logger.info(f"WebSocket connected (total: {len(self._connections)})")

    async def disconnect(self, ws: WebSocket) -> None:
        """Remove a disconnected WebSocket."""
        self._connections.discard(ws)
        logger.info(f"WebSocket disconnected (total: {len(self._connections)})")

    async def broadcast(self, event: dict[str, Any]) -> None:
        """Broadcast an event to all connected clients.

        Args:
            event: A dict matching PipelineEvent schema with keys:
                event_type, pipeline_id, agent_name, data, timestamp.
        """
        if not self._connections:
            return

        if "timestamp" not in event:
            event["timestamp"] = datetime.now(UTC).isoformat()

        payload = json.dumps(event, default=str)
        dead: list[WebSocket] = []

        for ws in self._connections:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)

        for ws in dead:
            self._connections.discard(ws)

        if dead:
            logger.warning(
                f"Removed {len(dead)} dead WebSocket connections "
                f"(remaining: {len(self._connections)})"
            )

    async def emit_agent_start(
        self, pipeline_id: str, agent_name: str, data: dict[str, Any] | None = None
    ) -> None:
        """Emit an agent_start event."""
        await self.broadcast({
            "event_type": "agent_start",
            "pipeline_id": pipeline_id,
            "agent_name": agent_name,
            "data": data or {},
        })

    async def emit_agent_complete(
        self, pipeline_id: str, agent_name: str, data: dict[str, Any] | None = None
    ) -> None:
        """Emit an agent_complete event."""
        await self.broadcast({
            "event_type": "agent_complete",
            "pipeline_id": pipeline_id,
            "agent_name": agent_name,
            "data": data or {},
        })

    async def emit_agent_failed(
        self, pipeline_id: str, agent_name: str, error: str
    ) -> None:
        """Emit an agent_failed event."""
        await self.broadcast({
            "event_type": "agent_failed",
            "pipeline_id": pipeline_id,
            "agent_name": agent_name,
            "data": {"error": error},
        })

    async def emit_pipeline_complete(
        self, pipeline_id: str, data: dict[str, Any] | None = None
    ) -> None:
        """Emit a pipeline_complete event."""
        await self.broadcast({
            "event_type": "pipeline_complete",
            "pipeline_id": pipeline_id,
            "data": data or {},
        })

    async def emit_trigger_fired(
        self, pipeline_id: str, trigger: dict[str, Any]
    ) -> None:
        """Emit a trigger_fired event."""
        await self.broadcast({
            "event_type": "trigger_fired",
            "pipeline_id": pipeline_id,
            "data": trigger,
        })

    @property
    def connection_count(self) -> int:
        """Return the number of active connections."""
        return len(self._connections)
