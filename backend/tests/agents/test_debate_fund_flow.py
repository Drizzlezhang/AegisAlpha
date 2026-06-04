"""Test Debate Agent fund_flow_context integration."""
from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from aegis.agents.debate_agent import DebateAgent
from aegis.pipeline.state import PipelineState


def _judge_response(direction: str, confidence: float, rounds_used: int) -> dict[str, Any]:
    return {
        "content": json.dumps({
            "direction": direction,
            "confidence": confidence,
            "rationale": f"Mock verdict: {direction}",
            "rounds_used": rounds_used,
            "entry_mode_hint": "",
        }),
        "usage": {"total_tokens": 50},
        "model": "gpt-4o-mini",
    }


def _make_state_with_fund_flow() -> PipelineState:
    state = PipelineState(tickers=["QQQ"])
    state.analyst_outputs = {
        "QQQ": {
            "factor_scores": [
                {"factor": "momentum", "score": 72, "confidence": 0.80, "rationale": "test"},
            ]
        }
    }
    state.extensions["fund_flow_agent"] = {
        "macro_liquidity": "expanding",
        "credit_appetite": "risk_on",
        "sector_rotation": {"into": ["XLK", "XLY"], "out_of": ["XLU"]},
        "narrative": "Liquidity expanding, risk-on, tech leading.",
    }
    return state


@pytest.mark.asyncio
async def test_debate_prompt_contains_fund_flow_context(
    mock_memory: Any, mock_tools: Any, mock_config: Any,
) -> None:
    """Debate Bull/Bear prompts should contain real fund_flow_context data."""
    judge_calls = [
        _judge_response("bullish", 0.90, 1),
        _judge_response("bullish", 0.88, 2),
    ]
    call_index = 0
    captured_prompts: list[str] = []

    async def mock_chat(
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
        **kwargs: Any,
    ) -> dict[str, Any]:
        nonlocal call_index
        pos = call_index % 3
        if pos in (0, 1):  # Bull or Bear
            captured_prompts.append(messages[0]["content"])
        if pos == 0:
            resp = {
                "content": "Bullish argument.",
                "usage": {"total_tokens": 80},
                "model": "gpt-4o",
            }
        elif pos == 1:
            resp = {
                "content": "Bearish argument.",
                "usage": {"total_tokens": 80},
                "model": "gpt-4o",
            }
        else:
            judge_idx = call_index // 3
            resp = judge_calls[min(judge_idx, len(judge_calls) - 1)]
        call_index += 1
        return resp

    with patch("aegis.agents.debate_agent.LLMClient") as mock_llm_cls:
        mock_llm = AsyncMock()
        mock_llm.chat = AsyncMock(side_effect=mock_chat)
        mock_llm_cls.return_value = mock_llm

        agent = DebateAgent(
            memory=mock_memory, tools=mock_tools, config={"max_rounds": 3}
        )
        state = _make_state_with_fund_flow()
        await agent.run(state)

    # At least one prompt should contain fund flow data
    fund_flow_found = any(
        "expanding" in p and "risk_on" in p
        for p in captured_prompts
    )
    assert fund_flow_found, (
        f"Expected fund_flow_context in prompts, got: {captured_prompts[:2]}"
    )


@pytest.mark.asyncio
async def test_debate_empty_fund_flow_context(
    mock_memory: Any, mock_tools: Any, mock_config: Any,
) -> None:
    """When fund_flow_agent extension is missing, context should be empty string."""
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
            resp = {
                "content": "Bullish argument.",
                "usage": {"total_tokens": 80},
                "model": "gpt-4o",
            }
        elif pos == 1:
            resp = {
                "content": "Bearish argument.",
                "usage": {"total_tokens": 80},
                "model": "gpt-4o",
            }
        else:
            judge_idx = call_index // 3
            resp = judge_calls[min(judge_idx, len(judge_calls) - 1)]
        call_index += 1
        return resp

    with patch("aegis.agents.debate_agent.LLMClient") as mock_llm_cls:
        mock_llm = AsyncMock()
        mock_llm.chat = AsyncMock(side_effect=mock_chat)
        mock_llm_cls.return_value = mock_llm

        agent = DebateAgent(
            memory=mock_memory, tools=mock_tools, config={"max_rounds": 3}
        )
        state = PipelineState(tickers=["QQQ"])
        state.analyst_outputs = {
            "QQQ": {
                "factor_scores": [
                    {"factor": "momentum", "score": 72, "confidence": 0.80, "rationale": "test"},
                ]
            }
        }
        # No fund_flow_agent extension
        result = await agent.run(state)

    assert "QQQ" in result.debate_results
