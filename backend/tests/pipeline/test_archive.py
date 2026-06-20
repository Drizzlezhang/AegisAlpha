"""Tests for _post_pipeline_archive in runner.py."""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from aegis.pipeline.runner import _post_pipeline_archive
from aegis.pipeline.state import PipelineState, Recommendation


@pytest.fixture
def full_state():
    return PipelineState(
        pipeline_id="test_001",
        tickers=["QQQ"],
        scratchpad={"agent_a": "trace a"},
        debate_results={"QQQ": {"direction": "bullish", "confidence": 0.8}},
        recommendations=[
            Recommendation(
                ticker="QQQ",
                action="buy",
                strategy="leaps_call",
                rationale="test",
            )
        ],
        smart_money_data={"QQQ": {"score": 75}},
        fund_flow_data={"QQQ": {"net_flow": 100}},
    )


@pytest.fixture
def empty_state():
    return PipelineState(pipeline_id="test_002", tickers=["QQQ"])


class TestPostPipelineArchive:
    @pytest.mark.asyncio
    async def test_full_state_archives_all(self, full_state):
        with patch("aegis.pipeline.runner.create_engine") as mock_engine, \
             patch("aegis.pipeline.runner.Session") as mock_session_cls, \
             patch("aegis.pipeline.runner.ShortTermStore") as mock_short, \
             patch("aegis.pipeline.runner.LongTermStore") as mock_long:
            mock_session = MagicMock()
            mock_session_cls.return_value.__enter__.return_value = mock_session
            mock_short_instance = MagicMock()
            mock_long_instance = MagicMock()
            mock_short.return_value = mock_short_instance
            mock_long.return_value = mock_long_instance

            await _post_pipeline_archive(full_state)

            # scratchpad → short-term
            assert mock_short_instance.insert.call_count >= 1
            # debate → long-term
            assert mock_long_instance.insert.call_count >= 3  # debate + recommendation + smart_money + fund_flow

    @pytest.mark.asyncio
    async def test_empty_state_no_errors(self, empty_state):
        with patch("aegis.pipeline.runner.create_engine") as mock_engine, \
             patch("aegis.pipeline.runner.Session") as mock_session_cls, \
             patch("aegis.pipeline.runner.ShortTermStore") as mock_short, \
             patch("aegis.pipeline.runner.LongTermStore") as mock_long:
            mock_session = MagicMock()
            mock_session_cls.return_value.__enter__.return_value = mock_session

            # Should not raise
            await _post_pipeline_archive(empty_state)

    @pytest.mark.asyncio
    async def test_exception_non_blocking(self, full_state):
        with patch("aegis.pipeline.runner.create_engine") as mock_engine:
            mock_engine.side_effect = Exception("DB down")
            # Should not raise
            await _post_pipeline_archive(full_state)
