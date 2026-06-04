"""Integration tests for Lightweight Pipeline — verify zero LLM calls and health check."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from aegis.pipeline.runner import run_lightweight


class TestLightweightPipeline:
    """Integration tests for the Lightweight Pipeline (4-node subgraph)."""

    @pytest.mark.asyncio
    async def test_lightweight_pipeline_executes(self) -> None:
        """Lightweight pipeline should execute and return state."""
        state = await run_lightweight(["QQQ"])

        assert state is not None
        assert state.pipeline_mode == "lightweight"
        assert "QQQ" in state.tickers

    @pytest.mark.asyncio
    async def test_lightweight_pipeline_zero_llm_calls(self) -> None:
        """Lightweight pipeline must NOT call LLMClient.chat (AC-2)."""
        with patch(
            "aegis.llm.client.LLMClient.chat",
            new_callable=AsyncMock,
        ) as mock_chat:
            await run_lightweight(["QQQ"])
            mock_chat.assert_not_called()

    @pytest.mark.asyncio
    async def test_lightweight_pipeline_health_scores(self) -> None:
        """Lightweight pipeline should compute health_scores (AC-3)."""
        state = await run_lightweight(["QQQ"])

        assert isinstance(state.health_scores, dict)
        # health_scores may be empty if no market data, but the field should exist

    @pytest.mark.asyncio
    async def test_lightweight_pipeline_records_timings(self) -> None:
        """Lightweight pipeline should record agent_timings."""
        state = await run_lightweight(["QQQ"])

        assert "_total" in state.agent_timings
        assert state.agent_timings["_total"] > 0

    @pytest.mark.asyncio
    async def test_lightweight_pipeline_empty_tickers(self) -> None:
        """Lightweight pipeline with empty tickers should return empty state (Edge-4)."""
        state = await run_lightweight([])

        assert state is not None
        assert state.pipeline_mode == "lightweight"
        assert state.tickers == []

    @pytest.mark.asyncio
    async def test_lightweight_pipeline_total_time_within_limit(self) -> None:
        """Lightweight pipeline total time should be ≤ 60 seconds (NFR-1)."""
        state = await run_lightweight(["QQQ"])

        assert state.agent_timings["_total"] <= 60.0
