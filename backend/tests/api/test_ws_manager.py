"""Tests for PipelineWSManager — WebSocket event broadcasting."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest


class TestPipelineWSManager:
    """Test WebSocket connection management and event broadcasting."""

    @pytest.mark.asyncio
    async def test_connect_adds_connection(self) -> None:
        """connect() should accept and add a WebSocket."""
        from aegis.api.ws_manager import PipelineWSManager

        mgr = PipelineWSManager()
        ws = AsyncMock()
        await mgr.connect(ws)
        ws.accept.assert_called_once()
        assert mgr.connection_count == 1

    @pytest.mark.asyncio
    async def test_disconnect_removes_connection(self) -> None:
        """disconnect() should remove a WebSocket."""
        from aegis.api.ws_manager import PipelineWSManager

        mgr = PipelineWSManager()
        ws = AsyncMock()
        await mgr.connect(ws)
        assert mgr.connection_count == 1
        await mgr.disconnect(ws)
        assert mgr.connection_count == 0

    @pytest.mark.asyncio
    async def test_broadcast_sends_to_all(self) -> None:
        """broadcast() should send to all connected clients."""
        from aegis.api.ws_manager import PipelineWSManager

        mgr = PipelineWSManager()
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        await mgr.connect(ws1)
        await mgr.connect(ws2)

        await mgr.broadcast({
            "event_type": "agent_start",
            "pipeline_id": "p1",
            "agent_name": "test",
        })

        ws1.send_text.assert_called_once()
        ws2.send_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_broadcast_no_connections(self) -> None:
        """broadcast() with no connections should not raise."""
        from aegis.api.ws_manager import PipelineWSManager

        mgr = PipelineWSManager()
        await mgr.broadcast({"event_type": "pipeline_complete", "pipeline_id": "p1"})

    @pytest.mark.asyncio
    async def test_broadcast_removes_dead_connections(self) -> None:
        """broadcast() should remove dead connections."""
        from aegis.api.ws_manager import PipelineWSManager

        mgr = PipelineWSManager()
        ws_good = AsyncMock()
        ws_dead = AsyncMock()
        ws_dead.send_text.side_effect = RuntimeError("connection lost")
        await mgr.connect(ws_good)
        await mgr.connect(ws_dead)

        await mgr.broadcast({
            "event_type": "agent_start",
            "pipeline_id": "p1",
            "agent_name": "test",
        })

        assert mgr.connection_count == 1

    @pytest.mark.asyncio
    async def test_emit_agent_start(self) -> None:
        """emit_agent_start() should broadcast correct event."""
        from aegis.api.ws_manager import PipelineWSManager

        mgr = PipelineWSManager()
        ws = AsyncMock()
        await mgr.connect(ws)

        await mgr.emit_agent_start("p1", "test_agent", {"mode": "full"})

        ws.send_text.assert_called_once()
        import json

        payload = json.loads(ws.send_text.call_args[0][0])
        assert payload["event_type"] == "agent_start"
        assert payload["pipeline_id"] == "p1"
        assert payload["agent_name"] == "test_agent"
        assert payload["data"] == {"mode": "full"}

    @pytest.mark.asyncio
    async def test_emit_agent_complete(self) -> None:
        """emit_agent_complete() should broadcast correct event."""
        from aegis.api.ws_manager import PipelineWSManager

        mgr = PipelineWSManager()
        ws = AsyncMock()
        await mgr.connect(ws)

        await mgr.emit_agent_complete("p1", "test_agent", {"elapsed": 1.5})

        import json

        payload = json.loads(ws.send_text.call_args[0][0])
        assert payload["event_type"] == "agent_complete"
        assert payload["agent_name"] == "test_agent"
        assert payload["data"]["elapsed"] == 1.5

    @pytest.mark.asyncio
    async def test_emit_agent_failed(self) -> None:
        """emit_agent_failed() should broadcast correct event."""
        from aegis.api.ws_manager import PipelineWSManager

        mgr = PipelineWSManager()
        ws = AsyncMock()
        await mgr.connect(ws)

        await mgr.emit_agent_failed("p1", "test_agent", "timeout")

        import json

        payload = json.loads(ws.send_text.call_args[0][0])
        assert payload["event_type"] == "agent_failed"
        assert payload["data"]["error"] == "timeout"

    @pytest.mark.asyncio
    async def test_emit_pipeline_complete(self) -> None:
        """emit_pipeline_complete() should broadcast correct event."""
        from aegis.api.ws_manager import PipelineWSManager

        mgr = PipelineWSManager()
        ws = AsyncMock()
        await mgr.connect(ws)

        await mgr.emit_pipeline_complete("p1", {"recommendations": 3})

        import json

        payload = json.loads(ws.send_text.call_args[0][0])
        assert payload["event_type"] == "pipeline_complete"
        assert payload["data"]["recommendations"] == 3

    @pytest.mark.asyncio
    async def test_emit_trigger_fired(self) -> None:
        """emit_trigger_fired() should broadcast correct event."""
        from aegis.api.ws_manager import PipelineWSManager

        mgr = PipelineWSManager()
        ws = AsyncMock()
        await mgr.connect(ws)

        trigger = {"ticker": "QQQ", "trigger_type": "price_below"}
        await mgr.emit_trigger_fired("p1", trigger)

        import json

        payload = json.loads(ws.send_text.call_args[0][0])
        assert payload["event_type"] == "trigger_fired"
        assert payload["data"]["ticker"] == "QQQ"

    @pytest.mark.asyncio
    async def test_broadcast_adds_timestamp(self) -> None:
        """broadcast() should add timestamp if not provided."""
        from aegis.api.ws_manager import PipelineWSManager

        mgr = PipelineWSManager()
        ws = AsyncMock()
        await mgr.connect(ws)

        await mgr.broadcast({"event_type": "agent_start", "pipeline_id": "p1"})

        import json

        payload = json.loads(ws.send_text.call_args[0][0])
        assert "timestamp" in payload
        assert payload["timestamp"] != ""
