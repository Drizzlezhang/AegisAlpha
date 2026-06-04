"""Test DebateAgent — early stop, max rounds, JSON parse failure, token timing."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from aegis.agents.debate_agent import DebateAgent
from aegis.pipeline.state import PipelineState

FIXTURES = Path(__file__).parent.parent / "fixtures"


def _load_fixture(name: str) -> Any:
    with open(FIXTURES / name) as f:
        return json.load(f)


def _make_state(ticker: str = "QQQ") -> PipelineState:
    """Create a PipelineState with factor_scores loaded from fixture."""
    fixture = _load_fixture("debate_mock_factor_scores.json")
    state = PipelineState(tickers=[ticker])
    state.analyst_outputs = fixture
    return state


def _judge_response(direction: str, confidence: float, rounds_used: int) -> dict[str, Any]:
    return {
        "content": json.dumps(
            {
                "direction": direction,
                "confidence": confidence,
                "rationale": f"Mock verdict: {direction} at {confidence}",
                "rounds_used": rounds_used,
                "entry_mode_hint": "",
            }
        ),
        "usage": {"total_tokens": 50},
        "model": "gpt-4o-mini",
    }


def _bull_response() -> dict[str, Any]:
    return {
        "content": "Bullish argument: momentum and technicals are strong.",
        "usage": {"total_tokens": 80},
        "model": "gpt-4o",
    }


def _bear_response() -> dict[str, Any]:
    return {
        "content": "Bearish argument: valuation and macro headwinds persist.",
        "usage": {"total_tokens": 80},
        "model": "gpt-4o",
    }


# ---------------------------------------------------------------------------
# Test: early stop
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_debate_early_stop_same_direction_high_confidence(
    mock_memory: Any,
    mock_tools: Any,
    mock_config: Any,
) -> None:
    """Early stop: Judge same direction + confidence > 0.85 for 2 consecutive rounds."""
    # Round 1: bullish 0.90, Round 2: bullish 0.88 → early stop after round 2
    judge_calls = [
        _judge_response("bullish", 0.90, 1),
        _judge_response("bullish", 0.88, 2),
    ]
    call_index = 0

    async def mock_chat(
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
        **kwargs: Any,
    ) -> dict[str, Any]:
        nonlocal call_index
        # Sequence per round: Bull, Bear, Judge
        pos = call_index % 3
        if pos == 0:
            resp = _bull_response()
        elif pos == 1:
            resp = _bear_response()
        else:
            judge_idx = call_index // 3
            resp = judge_calls[min(judge_idx, len(judge_calls) - 1)]
        call_index += 1
        return resp

    with patch("aegis.agents.debate_agent.LLMClient") as mock_llm_cls:
        mock_llm = AsyncMock()
        mock_llm.chat = AsyncMock(side_effect=mock_chat)
        mock_llm_cls.return_value = mock_llm

        agent = DebateAgent(memory=mock_memory, tools=mock_tools, config={"max_rounds": 3})
        state = _make_state()
        result_state = await agent.run(state)

    # Should have stopped early (only 2 rounds, not 3)
    assert "QQQ" in result_state.debate_results
    verdict = result_state.debate_results["QQQ"]
    assert verdict["direction"] == "bullish"
    assert verdict["confidence"] == 0.88
    assert verdict["rounds_used"] == 2
    # Verify only 2 rounds of calls (6 LLM calls: 2×Bull + 2×Bear + 2×Judge)
    assert call_index == 6
    # Verify timing recorded
    assert "debate_agent" in result_state.agent_timings
    assert result_state.agent_timings["debate_agent"] > 0


# ---------------------------------------------------------------------------
# Test: max rounds
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_debate_max_rounds_alternating_direction(
    mock_memory: Any,
    mock_tools: Any,
    mock_config: Any,
) -> None:
    """Debate should run all 3 rounds when Judge alternates direction each round."""
    judge_calls = [
        _judge_response("bullish", 0.70, 1),
        _judge_response("bearish", 0.65, 2),
        _judge_response("bullish", 0.75, 3),
    ]
    call_index = 0

    async def mock_chat(
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
        **kwargs: Any,
    ) -> dict[str, Any]:
        nonlocal call_index
        pos = call_index % 3
        if pos == 0:
            resp = _bull_response()
        elif pos == 1:
            resp = _bear_response()
        else:
            judge_idx = call_index // 3
            resp = judge_calls[min(judge_idx, len(judge_calls) - 1)]
        call_index += 1
        return resp

    with patch("aegis.agents.debate_agent.LLMClient") as mock_llm_cls:
        mock_llm = AsyncMock()
        mock_llm.chat = AsyncMock(side_effect=mock_chat)
        mock_llm_cls.return_value = mock_llm

        agent = DebateAgent(memory=mock_memory, tools=mock_tools, config={"max_rounds": 3})
        state = _make_state()
        result_state = await agent.run(state)

    assert "QQQ" in result_state.debate_results
    verdict = result_state.debate_results["QQQ"]
    assert verdict["direction"] == "bullish"
    assert verdict["confidence"] == 0.75
    assert verdict["rounds_used"] == 3
    # 3 rounds × 3 calls = 9
    assert call_index == 9


# ---------------------------------------------------------------------------
# Test: JSON parse failure
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_debate_json_parse_failure_writes_error_flag(
    mock_memory: Any,
    mock_tools: Any,
    mock_config: Any,
) -> None:
    """When Judge returns non-JSON twice, error_flag written and Pipeline continues."""
    call_index = 0

    async def mock_chat(
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
        **kwargs: Any,
    ) -> dict[str, Any]:
        nonlocal call_index
        pos = call_index % 3
        if pos == 0:
            resp = _bull_response()
        elif pos == 1:
            resp = _bear_response()
        else:
            # Judge returns non-JSON both attempts
            resp = {
                "content": "I think bullish is the way to go, but let me think more...",
                "usage": {"total_tokens": 30},
                "model": "gpt-4o-mini",
            }
        call_index += 1
        return resp

    with patch("aegis.agents.debate_agent.LLMClient") as mock_llm_cls:
        mock_llm = AsyncMock()
        mock_llm.chat = AsyncMock(side_effect=mock_chat)
        mock_llm_cls.return_value = mock_llm

        agent = DebateAgent(memory=mock_memory, tools=mock_tools, config={"max_rounds": 3})
        state = _make_state()
        result_state = await agent.run(state)

    # No debate result for QQQ (parse failed)
    assert "QQQ" not in result_state.debate_results
    # Error flag written
    assert len(result_state.error_flags) >= 1
    error = result_state.error_flags[0]
    assert error["agent"] == "debate_agent"
    assert error["ticker"] == "QQQ"
    assert "JSON parse failure" in error["error"]
    # Pipeline continued (state returned, no exception)
    assert "debate_agent" in result_state.agent_timings


# ---------------------------------------------------------------------------
# Test: model selection (AC-1)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_debate_model_selection_bull_bear_primary_judge_mini(
    mock_memory: Any,
    mock_tools: Any,
    mock_config: Any,
) -> None:
    """Bull/Bear should use LLM_MODEL_PRIMARY, Judge should use LLM_MODEL_MINI."""
    judge_calls = [
        _judge_response("bullish", 0.90, 1),
        _judge_response("bullish", 0.88, 2),
    ]
    call_index = 0
    model_log: list[tuple[int, str]] = []

    async def mock_chat(
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
        **kwargs: Any,
    ) -> dict[str, Any]:
        nonlocal call_index
        pos = call_index % 3
        model_log.append((pos, model))
        if pos == 0:
            resp = _bull_response()
        elif pos == 1:
            resp = _bear_response()
        else:
            judge_idx = call_index // 3
            resp = judge_calls[min(judge_idx, len(judge_calls) - 1)]
        call_index += 1
        return resp

    with patch("aegis.agents.debate_agent.LLMClient") as mock_llm_cls:
        mock_llm = AsyncMock()
        mock_llm.chat = AsyncMock(side_effect=mock_chat)
        mock_llm_cls.return_value = mock_llm

        agent = DebateAgent(memory=mock_memory, tools=mock_tools, config={"max_rounds": 3})
        state = _make_state()
        await agent.run(state)

    # pos 0 = Bull → PRIMARY, pos 1 = Bear → PRIMARY, pos 2 = Judge → MINI
    for pos, model in model_log:
        if pos in (0, 1):
            assert model == "gpt-4o", f"Expected PRIMARY for pos={pos}, got {model}"
        else:
            assert model == "gpt-4o-mini", f"Expected MINI for pos={pos}, got {model}"


# ---------------------------------------------------------------------------
# Test: token timing (AC-6)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_debate_token_timing_recorded(
    mock_memory: Any,
    mock_tools: Any,
    mock_config: Any,
) -> None:
    """Token consumption should be written to state.agent_timings['debate_agent']."""
    judge_calls = [
        _judge_response("bullish", 0.90, 1),
        _judge_response("bullish", 0.88, 2),
    ]
    call_index = 0

    async def mock_chat(
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
        **kwargs: Any,
    ) -> dict[str, Any]:
        nonlocal call_index
        pos = call_index % 3
        if pos == 0:
            resp = _bull_response()
        elif pos == 1:
            resp = _bear_response()
        else:
            judge_idx = call_index // 3
            resp = judge_calls[min(judge_idx, len(judge_calls) - 1)]
        call_index += 1
        return resp

    with patch("aegis.agents.debate_agent.LLMClient") as mock_llm_cls:
        mock_llm = AsyncMock()
        mock_llm.chat = AsyncMock(side_effect=mock_chat)
        mock_llm_cls.return_value = mock_llm

        agent = DebateAgent(memory=mock_memory, tools=mock_tools, config={"max_rounds": 3})
        state = _make_state()
        result_state = await agent.run(state)

    assert "debate_agent" in result_state.agent_timings
    assert result_state.agent_timings["debate_agent"] > 0
    # total_tokens written to extensions
    assert result_state.extensions.get("debate_agent", {}).get("total_tokens", 0) > 0
