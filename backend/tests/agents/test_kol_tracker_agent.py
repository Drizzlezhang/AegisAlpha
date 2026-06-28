"""Tests for KOLTrackerAgent — signal collection, extraction, and storage."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aegis.agents.kol_tracker_agent import KOLTrackerAgent
from aegis.pipeline.state import PipelineState
from aegis.tools.base import ToolResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_state(tickers: list[str] | None = None) -> PipelineState:
    return PipelineState(tickers=tickers or ["QQQ"])


def _mock_tool_result(success: bool, data: Any) -> MagicMock:
    mock = MagicMock()
    mock.fetch = AsyncMock(return_value=ToolResult(success=success, data=data, source="mock"))
    return mock


def _mock_kol_source(
    source_id: int = 1,
    name: str = "test_kol",
    platform: str = "x",
    handle: str = "testuser",
    reliability: float = 0.7,
) -> MagicMock:
    src = MagicMock()
    src.id = source_id
    src.name = name
    src.platform = platform
    src.handle = handle
    src.reliability_score = reliability
    return src


def _mock_kol_store(sources: list[MagicMock] | None = None) -> MagicMock:
    store = MagicMock()
    store.list_sources = AsyncMock(return_value=sources or [])
    store.record_call = AsyncMock(return_value=1)
    return store


def _mock_llm_signals_response(signals: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "content": '{"signals": ' + str(
            signals or [
                {
                    "ticker": "QQQ",
                    "direction": "bullish",
                    "confidence": "high",
                    "timeframe": "weeks",
                    "reasoning": "Strong momentum and institutional buying",
                    "handle": "testuser",
                    "source": "x",
                    "url": "https://x.com/testuser/status/123",
                    "content": "QQQ looks bullish here",
                    "timestamp": "2026-06-28T12:00:00Z",
                }
            ]
        ).replace("'", '"') + "}",
        "usage": {"total_tokens": 100},
        "model": "gpt-4o-mini",
    }


# ---------------------------------------------------------------------------
# Manifest tests
# ---------------------------------------------------------------------------


class TestKOLTrackerManifest:
    def test_manifest_correct(self) -> None:
        """Verify manifest fields match design spec."""
        m = KOLTrackerAgent.manifest
        assert m.name == "kol_tracker"
        assert m.version == "0.1.0"
        assert m.llm_dependency is True
        assert m.parallel_group == "signal_analysts"
        assert m.pipeline_mode == "full"
        assert "kol_signals" in m.provides
        assert "signal" in m.tags
        assert "social" in m.tags


# ---------------------------------------------------------------------------
# Agent run tests
# ---------------------------------------------------------------------------


class TestKOLTrackerAgentRun:
    @pytest.mark.asyncio
    async def test_run_no_kol_store(self, mock_memory: Any, mock_config: Any) -> None:
        """Agent should skip gracefully when no KOLStore in config."""
        with patch("aegis.agents.kol_tracker_agent.LLMClient"):
            agent = KOLTrackerAgent(memory=mock_memory, tools={}, config=mock_config)
        state = _make_state()
        result = await agent.run(state)

        assert result.kol_signals == {}
        assert "kol_tracker" in result.agent_timings

    @pytest.mark.asyncio
    async def test_run_no_enabled_sources(self, mock_memory: Any) -> None:
        """Agent should skip when no enabled KOL sources exist."""
        kol_store = _mock_kol_store(sources=[])
        config = {"kol_store": kol_store}

        with patch("aegis.agents.kol_tracker_agent.LLMClient"):
            agent = KOLTrackerAgent(memory=mock_memory, tools={}, config=config)
        state = _make_state()
        result = await agent.run(state)

        assert result.kol_signals == {}
        assert "kol_tracker" in result.agent_timings

    @pytest.mark.asyncio
    async def test_run_list_sources_failure(self, mock_memory: Any) -> None:
        """Agent should record error when listing sources fails."""
        kol_store = MagicMock()
        kol_store.list_sources = AsyncMock(side_effect=RuntimeError("DB down"))
        config = {"kol_store": kol_store}

        with patch("aegis.agents.kol_tracker_agent.LLMClient"):
            agent = KOLTrackerAgent(memory=mock_memory, tools={}, config=config)
        state = _make_state()
        result = await agent.run(state)

        assert len(result.error_flags) == 1
        assert result.error_flags[0]["agent"] == "kol_tracker"

    @pytest.mark.asyncio
    async def test_run_success_with_x_signals(self, mock_memory: Any) -> None:
        """Full flow: X source → fetch → LLM extract → write state + calls."""
        sources = [_mock_kol_source(platform="x", handle="testuser")]
        kol_store = _mock_kol_store(sources=sources)

        x_tool = _mock_tool_result(
            True,
            [
                {
                    "handle": "testuser",
                    "ticker": "QQQ",
                    "content": "QQQ looks bullish here",
                    "url": "https://x.com/testuser/status/123",
                    "published_date": "2026-06-28",
                    "source": "x",
                }
            ],
        )
        tools = {"x_search": x_tool}
        config = {"kol_store": kol_store}

        with patch("aegis.agents.kol_tracker_agent.LLMClient") as mock_llm_cls:
            mock_llm = MagicMock()
            mock_llm.chat = AsyncMock(return_value=_mock_llm_signals_response())
            mock_llm_cls.return_value = mock_llm

            agent = KOLTrackerAgent(memory=mock_memory, tools=tools, config=config)
            state = _make_state()
            result = await agent.run(state)

        assert "QQQ" in result.kol_signals
        assert len(result.kol_signals["QQQ"]["signals"]) == 1
        assert result.kol_signals["QQQ"]["signals"][0]["direction"] == "bullish"
        assert "kol_tracker" in result.agent_timings
        assert "kol_tracker" in result.extensions
        assert result.extensions["kol_tracker"]["signals_extracted"] == 1

        # Verify call was recorded
        kol_store.record_call.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_success_with_stocktwits(self, mock_memory: Any) -> None:
        """Full flow with StockTwits source."""
        sources = [_mock_kol_source(platform="stocktwits", handle="trader1")]
        kol_store = _mock_kol_store(sources=sources)

        st_tool = _mock_tool_result(
            True,
            [
                {
                    "handle": "trader1",
                    "ticker": "SPY",
                    "content": "SPY bearish divergence forming",
                    "url": "https://stocktwits.com/trader1/message/456",
                    "published_date": "2026-06-28",
                    "source": "stocktwits",
                }
            ],
        )
        tools = {"stocktwits_fetch": st_tool}
        config = {"kol_store": kol_store}

        with patch("aegis.agents.kol_tracker_agent.LLMClient") as mock_llm_cls:
            mock_llm = MagicMock()
            mock_llm.chat = AsyncMock(
                return_value=_mock_llm_signals_response([
                    {
                        "ticker": "SPY",
                        "direction": "bearish",
                        "confidence": "medium",
                        "timeframe": "days",
                        "reasoning": "Bearish divergence on daily chart",
                        "handle": "trader1",
                        "source": "stocktwits",
                        "url": "https://stocktwits.com/trader1/message/456",
                        "content": "SPY bearish divergence forming",
                        "timestamp": "2026-06-28T12:00:00Z",
                    }
                ])
            )
            mock_llm_cls.return_value = mock_llm

            agent = KOLTrackerAgent(memory=mock_memory, tools=tools, config=config)
            state = _make_state()
            result = await agent.run(state)

        assert "SPY" in result.kol_signals
        assert result.kol_signals["SPY"]["signals"][0]["direction"] == "bearish"

    @pytest.mark.asyncio
    async def test_run_success_with_reddit(self, mock_memory: Any) -> None:
        """Full flow with Reddit source."""
        sources = [_mock_kol_source(platform="reddit", handle="reddit_user")]
        kol_store = _mock_kol_store(sources=sources)

        reddit_tool = _mock_tool_result(
            True,
            [
                {
                    "author": "reddit_user",
                    "ticker": "NVDA",
                    "content": "NVDA DD: strong earnings growth",
                    "url": "https://reddit.com/r/options/comments/abc",
                    "score": 100,
                    "created_at": "2026-06-28T10:00:00Z",
                    "subreddit": "options",
                    "source": "reddit",
                }
            ],
        )
        tools = {"reddit_fetch": reddit_tool}
        config = {"kol_store": kol_store}

        with patch("aegis.agents.kol_tracker_agent.LLMClient") as mock_llm_cls:
            mock_llm = MagicMock()
            mock_llm.chat = AsyncMock(
                return_value=_mock_llm_signals_response([
                    {
                        "ticker": "NVDA",
                        "direction": "bullish",
                        "confidence": "high",
                        "timeframe": "months",
                        "reasoning": "Strong earnings growth trajectory",
                        "handle": "reddit_user",
                        "source": "reddit",
                        "url": "https://reddit.com/r/options/comments/abc",
                        "content": "NVDA DD: strong earnings growth",
                        "timestamp": "2026-06-28T10:00:00Z",
                    }
                ])
            )
            mock_llm_cls.return_value = mock_llm

            agent = KOLTrackerAgent(memory=mock_memory, tools=tools, config=config)
            state = _make_state()
            result = await agent.run(state)

        assert "NVDA" in result.kol_signals
        assert result.kol_signals["NVDA"]["signals"][0]["source"] == "reddit"

    @pytest.mark.asyncio
    async def test_run_no_posts_collected(self, mock_memory: Any) -> None:
        """Agent should handle case where tools return empty data."""
        sources = [_mock_kol_source(platform="x", handle="testuser")]
        kol_store = _mock_kol_store(sources=sources)

        x_tool = _mock_tool_result(True, [])
        tools = {"x_search": x_tool}
        config = {"kol_store": kol_store}

        with patch("aegis.agents.kol_tracker_agent.LLMClient"):
            agent = KOLTrackerAgent(memory=mock_memory, tools=tools, config=config)
        state = _make_state()
        result = await agent.run(state)

        assert result.kol_signals == {}
        assert "kol_tracker" in result.agent_timings

    @pytest.mark.asyncio
    async def test_run_llm_extraction_failure(self, mock_memory: Any) -> None:
        """Agent should handle LLM extraction failure gracefully."""
        sources = [_mock_kol_source(platform="x", handle="testuser")]
        kol_store = _mock_kol_store(sources=sources)

        x_tool = _mock_tool_result(
            True,
            [
                {
                    "handle": "testuser",
                    "ticker": "QQQ",
                    "content": "QQQ analysis",
                    "url": "https://x.com/testuser/status/123",
                    "published_date": "2026-06-28",
                    "source": "x",
                }
            ],
        )
        tools = {"x_search": x_tool}
        config = {"kol_store": kol_store}

        with patch("aegis.agents.kol_tracker_agent.LLMClient") as mock_llm_cls:
            mock_llm = MagicMock()
            mock_llm.chat = AsyncMock(side_effect=RuntimeError("LLM unavailable"))
            mock_llm_cls.return_value = mock_llm

            agent = KOLTrackerAgent(memory=mock_memory, tools=tools, config=config)
            state = _make_state()
            result = await agent.run(state)

        # Should complete without signals
        assert result.kol_signals == {}
        assert "kol_tracker" in result.agent_timings

    @pytest.mark.asyncio
    async def test_run_llm_returns_empty_signals(self, mock_memory: Any) -> None:
        """Agent should handle LLM returning no signals."""
        sources = [_mock_kol_source(platform="x", handle="testuser")]
        kol_store = _mock_kol_store(sources=sources)

        x_tool = _mock_tool_result(
            True,
            [
                {
                    "handle": "testuser",
                    "ticker": "QQQ",
                    "content": "Just chatting, no signal",
                    "url": "https://x.com/testuser/status/123",
                    "published_date": "2026-06-28",
                    "source": "x",
                }
            ],
        )
        tools = {"x_search": x_tool}
        config = {"kol_store": kol_store}

        with patch("aegis.agents.kol_tracker_agent.LLMClient") as mock_llm_cls:
            mock_llm = MagicMock()
            mock_llm.chat = AsyncMock(
                return_value={
                    "content": '{"signals": []}',
                    "usage": {"total_tokens": 50},
                    "model": "gpt-4o-mini",
                }
            )
            mock_llm_cls.return_value = mock_llm

            agent = KOLTrackerAgent(memory=mock_memory, tools=tools, config=config)
            state = _make_state()
            result = await agent.run(state)

        assert result.kol_signals == {}

    @pytest.mark.asyncio
    async def test_run_tool_fetch_exception_not_fatal(self, mock_memory: Any) -> None:
        """Tool fetch exception should not abort the agent."""
        sources = [_mock_kol_source(platform="x", handle="testuser")]
        kol_store = _mock_kol_store(sources=sources)

        x_tool = MagicMock()
        x_tool.fetch = AsyncMock(side_effect=RuntimeError("Network error"))
        tools = {"x_search": x_tool}
        config = {"kol_store": kol_store}

        with patch("aegis.agents.kol_tracker_agent.LLMClient"):
            agent = KOLTrackerAgent(memory=mock_memory, tools=tools, config=config)
        state = _make_state()
        result = await agent.run(state)

        # Should complete without crashing
        assert result.kol_signals == {}
        assert "kol_tracker" in result.agent_timings

    @pytest.mark.asyncio
    async def test_run_multiple_platforms_parallel(self, mock_memory: Any) -> None:
        """All three platforms should be queried."""
        sources = [
            _mock_kol_source(source_id=1, platform="x", handle="x_user"),
            _mock_kol_source(source_id=2, platform="stocktwits", handle="st_user"),
            _mock_kol_source(source_id=3, platform="reddit", handle="rd_user"),
        ]
        kol_store = _mock_kol_store(sources=sources)

        x_tool = _mock_tool_result(
            True,
            [{"handle": "x_user", "ticker": "QQQ", "content": "x post", "url": "http://x.com/1", "published_date": "2026-06-28", "source": "x"}],
        )
        st_tool = _mock_tool_result(
            True,
            [{"handle": "st_user", "ticker": "QQQ", "content": "st post", "url": "http://st.com/1", "published_date": "2026-06-28", "source": "stocktwits"}],
        )
        rd_tool = _mock_tool_result(
            True,
            [{"author": "rd_user", "ticker": "QQQ", "content": "rd post", "url": "http://rd.com/1", "score": 50, "created_at": "2026-06-28T10:00:00Z", "subreddit": "options", "source": "reddit"}],
        )
        tools = {"x_search": x_tool, "stocktwits_fetch": st_tool, "reddit_fetch": rd_tool}
        config = {"kol_store": kol_store}

        with patch("aegis.agents.kol_tracker_agent.LLMClient") as mock_llm_cls:
            mock_llm = MagicMock()
            mock_llm.chat = AsyncMock(
                return_value=_mock_llm_signals_response([
                    {"ticker": "QQQ", "direction": "bullish", "confidence": "high", "timeframe": "weeks", "reasoning": "x signal", "handle": "x_user", "source": "x", "url": "http://x.com/1", "content": "x post", "timestamp": "2026-06-28T12:00:00Z"},
                    {"ticker": "QQQ", "direction": "bullish", "confidence": "medium", "timeframe": "days", "reasoning": "st signal", "handle": "st_user", "source": "stocktwits", "url": "http://st.com/1", "content": "st post", "timestamp": "2026-06-28T12:00:00Z"},
                    {"ticker": "QQQ", "direction": "bearish", "confidence": "low", "timeframe": "unknown", "reasoning": "rd signal", "handle": "rd_user", "source": "reddit", "url": "http://rd.com/1", "content": "rd post", "timestamp": "2026-06-28T10:00:00Z"},
                ])
            )
            mock_llm_cls.return_value = mock_llm

            agent = KOLTrackerAgent(memory=mock_memory, tools=tools, config=config)
            state = _make_state()
            result = await agent.run(state)

        assert "QQQ" in result.kol_signals
        assert len(result.kol_signals["QQQ"]["signals"]) == 3
        # All three tools should have been called
        x_tool.fetch.assert_called_once()
        st_tool.fetch.assert_called_once()
        rd_tool.fetch.assert_called_once()
        # Three calls should be recorded
        assert kol_store.record_call.call_count == 3

    @pytest.mark.asyncio
    async def test_run_memory_write(self) -> None:
        """Agent should write to long-term memory after signal extraction."""
        sources = [_mock_kol_source(platform="x", handle="testuser")]
        kol_store = _mock_kol_store(sources=sources)

        x_tool = _mock_tool_result(
            True,
            [{"handle": "testuser", "ticker": "QQQ", "content": "bullish", "url": "http://x.com/1", "published_date": "2026-06-28", "source": "x"}],
        )
        tools = {"x_search": x_tool}
        config = {"kol_store": kol_store}

        mock_mem = MagicMock()
        mock_mem.write = AsyncMock()

        with patch("aegis.agents.kol_tracker_agent.LLMClient") as mock_llm_cls:
            mock_llm = MagicMock()
            mock_llm.chat = AsyncMock(return_value=_mock_llm_signals_response())
            mock_llm_cls.return_value = mock_llm

            agent = KOLTrackerAgent(memory=mock_mem, tools=tools, config=config)
            state = _make_state()
            await agent.run(state)

        # Verify memory.write was called with "long" scope
        mock_mem.write.assert_called()
        write_args = mock_mem.write.call_args
        assert write_args[0][0] == "long"  # scope
        assert write_args[0][1]["type"] == "kol_signals"

    @pytest.mark.asyncio
    async def test_run_empty_tickers(self, mock_memory: Any) -> None:
        """Agent should handle empty tickers list."""
        sources = [_mock_kol_source(platform="x", handle="testuser")]
        kol_store = _mock_kol_store(sources=sources)

        x_tool = _mock_tool_result(
            True,
            [{"handle": "testuser", "ticker": "QQQ", "content": "post", "url": "http://x.com/1", "published_date": "2026-06-28", "source": "x"}],
        )
        tools = {"x_search": x_tool}
        config = {"kol_store": kol_store}

        with patch("aegis.agents.kol_tracker_agent.LLMClient") as mock_llm_cls:
            mock_llm = MagicMock()
            mock_llm.chat = AsyncMock(return_value=_mock_llm_signals_response())
            mock_llm_cls.return_value = mock_llm

            agent = KOLTrackerAgent(memory=mock_memory, tools=tools, config=config)
            state = PipelineState(tickers=[])
            result = await agent.run(state)

        # Should still work — tools get empty tickers list
        assert "QQQ" in result.kol_signals
