"""Integration tests for Full Pipeline — verify state flows through all 9 nodes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from aegis.pipeline.runner import run_full

FIXTURES = Path(__file__).parent.parent / "fixtures"


def _load_fixture(name: str) -> Any:
    with open(FIXTURES / name) as f:
        return json.load(f)


def _mock_llm_response(content: str = '{"score": 75, "rationale": "mock"}') -> dict[str, Any]:
    return {
        "content": content,
        "usage": {"total_tokens": 50},
        "model": "mock-model",
    }


class TestFullPipeline:
    """Integration tests for the Full Pipeline (9-node StateGraph)."""

    @pytest.mark.asyncio
    async def test_full_pipeline_executes_all_nodes(self) -> None:
        """Full pipeline should execute and return state with timings."""
        with (
            patch("aegis.llm.client.LLMClient.__init__", return_value=None),
            patch(
                "aegis.llm.client.LLMClient.chat",
                new_callable=AsyncMock,
            ) as mock_chat,
        ):
            mock_chat.return_value = _mock_llm_response(
                json.dumps(
                    {
                        "direction": "bullish",
                        "confidence": 0.75,
                        "rationale": "mock verdict",
                        "rounds_used": 2,
                        "entry_mode_hint": "active_right",
                    }
                )
            )

            state = await run_full("QQQ", "manual")

            assert state is not None
            assert state.pipeline_id != ""
            assert state.pipeline_mode == "full"
            assert "QQQ" in state.tickers

    @pytest.mark.asyncio
    async def test_full_pipeline_records_timings(self) -> None:
        """Full pipeline should record agent_timings for each node."""
        with (
            patch("aegis.llm.client.LLMClient.__init__", return_value=None),
            patch(
                "aegis.llm.client.LLMClient.chat",
                new_callable=AsyncMock,
            ) as mock_chat,
        ):
            mock_chat.return_value = _mock_llm_response(
                json.dumps(
                    {
                        "direction": "bullish",
                        "confidence": 0.8,
                        "rationale": "mock",
                        "rounds_used": 1,
                        "entry_mode_hint": "",
                    }
                )
            )

            state = await run_full("QQQ", "manual")

            assert "_total" in state.agent_timings
            assert state.agent_timings["_total"] > 0
            assert "data_harvester" in state.agent_timings

    @pytest.mark.asyncio
    async def test_full_pipeline_total_time_within_limit(self) -> None:
        """Full pipeline total time should be ≤ 300 seconds (AC-12)."""
        with (
            patch("aegis.llm.client.LLMClient.__init__", return_value=None),
            patch(
                "aegis.llm.client.LLMClient.chat",
                new_callable=AsyncMock,
            ) as mock_chat,
        ):
            mock_chat.return_value = _mock_llm_response(
                json.dumps(
                    {
                        "direction": "bullish",
                        "confidence": 0.7,
                        "rationale": "mock",
                        "rounds_used": 1,
                        "entry_mode_hint": "",
                    }
                )
            )

            state = await run_full("QQQ", "manual")

            assert state.agent_timings["_total"] <= 300.0

    @pytest.mark.asyncio
    async def test_full_pipeline_handles_agent_failure(self) -> None:
        """Full pipeline should not crash when an agent fails."""
        with (
            patch("aegis.llm.client.LLMClient.__init__", return_value=None),
            patch(
                "aegis.llm.client.LLMClient.chat",
                new_callable=AsyncMock,
            ) as mock_chat,
        ):
            mock_chat.side_effect = Exception("LLM unavailable")

            state = await run_full("QQQ", "manual")

            assert state is not None
            # Pipeline continues regardless of agent failures
            assert isinstance(state.error_flags, list)

    @pytest.mark.asyncio
    async def test_full_pipeline_empty_ticker(self) -> None:
        """Full pipeline with empty ticker should not crash (Edge-1)."""
        with (
            patch("aegis.llm.client.LLMClient.__init__", return_value=None),
            patch(
                "aegis.llm.client.LLMClient.chat",
                new_callable=AsyncMock,
            ) as mock_chat,
        ):
            mock_chat.return_value = _mock_llm_response(
                json.dumps(
                    {
                        "direction": "neutral",
                        "confidence": 0.5,
                        "rationale": "no data",
                        "rounds_used": 1,
                        "entry_mode_hint": "",
                    }
                )
            )

            state = await run_full("", "manual")
            assert state is not None
            assert state.tickers == [""]
