"""Tests for ThesisValidatorAgent — LLM validation + status transitions."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aegis.agents.thesis_validator_agent import ThesisValidatorAgent


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_thesis_service() -> AsyncMock:
    service = AsyncMock()
    service.get_active_theses = AsyncMock(return_value=[])
    service.update_valid_status = AsyncMock()
    return service


@pytest.fixture
def mock_llm_client() -> MagicMock:
    client = MagicMock()
    client.chat = AsyncMock()
    return client


@pytest.fixture
def agent(
    mock_thesis_service: AsyncMock,
    mock_llm_client: MagicMock,
) -> ThesisValidatorAgent:
    return ThesisValidatorAgent(
        thesis_service=mock_thesis_service,
        llm_client=mock_llm_client,
    )


def _active_thesis(**overrides: Any) -> dict[str, Any]:
    base = {
        "id": 1,
        "ticker": "QQQ",
        "direction": "long",
        "entry_price": 450.0,
        "entry_date": "2026-05-01T00:00:00+00:00",
        "key_assumptions": ["QQQ above 200MA", "tech momentum", "Fed dovish"],
        "thesis_valid_status": "valid",
    }
    base.update(overrides)
    return base


def _llm_response(assumptions: list[dict[str, str]], analysis: str = "healthy") -> dict[str, Any]:
    return {
        "content": json.dumps({
            "assumptions": assumptions,
            "overall_analysis": analysis,
        }),
        "usage": {"total_tokens": 100},
        "model": "gpt-4o-mini",
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestValidateAll:
    @pytest.mark.asyncio
    async def test_no_active_theses(
        self, agent: ThesisValidatorAgent, mock_thesis_service: AsyncMock
    ) -> None:
        """Should return empty dict when no active theses."""
        mock_thesis_service.get_active_theses = AsyncMock(return_value=[])

        result = await agent.validate_all()

        assert result == {}

    @pytest.mark.asyncio
    async def test_all_valid(
        self,
        agent: ThesisValidatorAgent,
        mock_thesis_service: AsyncMock,
        mock_llm_client: MagicMock,
    ) -> None:
        """Should keep status as valid when all assumptions pass."""
        mock_thesis_service.get_active_theses = AsyncMock(
            return_value=[_active_thesis()]
        )
        mock_llm_client.chat = AsyncMock(
            return_value=_llm_response([
                {"assumption": "QQQ above 200MA", "status": "valid", "reasoning": "still above"},
                {"assumption": "tech momentum", "status": "valid", "reasoning": "sector strong"},
                {"assumption": "Fed dovish", "status": "valid", "reasoning": "rates steady"},
            ])
        )

        market_data = {"QQQ": {"current_price": 460.0, "price_change_pct": 0.02}}

        result = await agent.validate_all(market_data=market_data)

        assert "QQQ" in result
        assert result["QQQ"]["new_status"] == "valid"
        assert result["QQQ"]["broken_count"] == 0

    @pytest.mark.asyncio
    async def test_partial_broken(
        self,
        agent: ThesisValidatorAgent,
        mock_thesis_service: AsyncMock,
        mock_llm_client: MagicMock,
    ) -> None:
        """Should transition to partial_broken when ≤ half assumptions broken."""
        mock_thesis_service.get_active_theses = AsyncMock(
            return_value=[_active_thesis()]
        )
        mock_llm_client.chat = AsyncMock(
            return_value=_llm_response([
                {"assumption": "QQQ above 200MA", "status": "broken", "reasoning": "broke below"},
                {"assumption": "tech momentum", "status": "valid", "reasoning": "still ok"},
                {"assumption": "Fed dovish", "status": "valid", "reasoning": "unchanged"},
            ])
        )

        market_data = {"QQQ": {"current_price": 430.0, "price_change_pct": -0.04}}

        result = await agent.validate_all(market_data=market_data)

        assert result["QQQ"]["new_status"] == "partial_broken"
        assert result["QQQ"]["broken_count"] == 1

    @pytest.mark.asyncio
    async def test_fully_broken(
        self,
        agent: ThesisValidatorAgent,
        mock_thesis_service: AsyncMock,
        mock_llm_client: MagicMock,
    ) -> None:
        """Should transition to fully_broken when > half assumptions broken."""
        mock_thesis_service.get_active_theses = AsyncMock(
            return_value=[_active_thesis()]
        )
        mock_llm_client.chat = AsyncMock(
            return_value=_llm_response([
                {"assumption": "QQQ above 200MA", "status": "broken", "reasoning": "broke below"},
                {"assumption": "tech momentum", "status": "broken", "reasoning": "sector weak"},
                {"assumption": "Fed dovish", "status": "valid", "reasoning": "unchanged"},
            ])
        )

        market_data = {"QQQ": {"current_price": 410.0, "price_change_pct": -0.09}}

        result = await agent.validate_all(market_data=market_data)

        assert result["QQQ"]["new_status"] == "fully_broken"
        assert result["QQQ"]["broken_count"] == 2

    @pytest.mark.asyncio
    async def test_skips_without_market_data(
        self,
        agent: ThesisValidatorAgent,
        mock_thesis_service: AsyncMock,
    ) -> None:
        """Should skip thesis when no market data available."""
        mock_thesis_service.get_active_theses = AsyncMock(
            return_value=[_active_thesis()]
        )

        result = await agent.validate_all(market_data={})

        assert result == {}

    @pytest.mark.asyncio
    async def test_skips_empty_assumptions(
        self,
        agent: ThesisValidatorAgent,
        mock_thesis_service: AsyncMock,
    ) -> None:
        """Should skip thesis with no key_assumptions."""
        mock_thesis_service.get_active_theses = AsyncMock(
            return_value=[_active_thesis(key_assumptions=[])]
        )

        market_data = {"QQQ": {"current_price": 460.0}}
        result = await agent.validate_all(market_data=market_data)

        assert result == {}

    @pytest.mark.asyncio
    async def test_llm_failure_skips(
        self,
        agent: ThesisValidatorAgent,
        mock_thesis_service: AsyncMock,
        mock_llm_client: MagicMock,
    ) -> None:
        """Should skip thesis when LLM call fails."""
        mock_thesis_service.get_active_theses = AsyncMock(
            return_value=[_active_thesis()]
        )
        mock_llm_client.chat = AsyncMock(side_effect=Exception("LLM timeout"))

        market_data = {"QQQ": {"current_price": 460.0}}
        result = await agent.validate_all(market_data=market_data)

        assert result == {}

    @pytest.mark.asyncio
    async def test_calls_update_valid_status(
        self,
        agent: ThesisValidatorAgent,
        mock_thesis_service: AsyncMock,
        mock_llm_client: MagicMock,
    ) -> None:
        """Should call ThesisService.update_valid_status with correct args."""
        mock_thesis_service.get_active_theses = AsyncMock(
            return_value=[_active_thesis()]
        )
        mock_llm_client.chat = AsyncMock(
            return_value=_llm_response([
                {"assumption": "QQQ above 200MA", "status": "broken", "reasoning": "broke"},
                {"assumption": "tech momentum", "status": "valid", "reasoning": "ok"},
                {"assumption": "Fed dovish", "status": "valid", "reasoning": "ok"},
            ])
        )

        market_data = {"QQQ": {"current_price": 430.0}}
        await agent.validate_all(market_data=market_data)

        mock_thesis_service.update_valid_status.assert_called_once_with(
            thesis_id=1,
            new_status="partial_broken",
            broken_assumptions=["QQQ above 200MA"],
        )
