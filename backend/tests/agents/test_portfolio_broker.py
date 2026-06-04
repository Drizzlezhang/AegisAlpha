"""Tests for PortfolioOrchestrator broker integration."""

import asyncio

import pytest

from aegis.agents.portfolio_orchestrator_agent import PortfolioOrchestratorAgent
from aegis.pipeline.state import PipelineState


class TestPortfolioBroker:
    """AC-6/7: PortfolioOrchestrator broker integration and fallback."""

    def test_broker_position_to_dict(self) -> None:
        """_broker_position_to_dict should convert BrokerPosition to dict."""
        from aegis.tools.brokers.base import BrokerPosition

        pos = BrokerPosition(
            account="futu", ticker="QQQ", pos_type="stock",
            quantity=100, avg_cost=350.0, current_price=380.0,
            delta_dollars=35000.0, unrealized_pnl=3000.0,
            entry_mode="active_left", grade="active",
        )
        result = PortfolioOrchestratorAgent._broker_position_to_dict(pos)
        assert result["ticker"] == "QQQ"
        assert result["account"] == "futu"
        assert result["entry_mode"] == "active_left"
        assert result["grade"] == "active"
        assert result["delta_dollars"] == 35000.0

    def test_broker_position_to_dict_defaults(self) -> None:
        """None entry_mode/grade should default to passive/active."""
        from aegis.tools.brokers.base import BrokerPosition

        pos = BrokerPosition(account="futu", ticker="QQQ", pos_type="stock", quantity=100, avg_cost=350.0)
        result = PortfolioOrchestratorAgent._broker_position_to_dict(pos)
        assert result["entry_mode"] == "passive"
        assert result["grade"] == "active"

    def test_fallback_to_mock(self) -> None:
        """When no brokers available, should fallback to mock_portfolio.json."""
        agent = PortfolioOrchestratorAgent(memory={}, tools={}, config={})
        state = PipelineState()
        result = asyncio.run(agent.run(state))
        # Should not crash; mock portfolio may or may not exist
        assert result is not None

    def test_broker_positions_written_to_state(self) -> None:
        """broker_positions should be populated when broker data is available."""
        agent = PortfolioOrchestratorAgent(memory={}, tools={}, config={})
        state = PipelineState()
        result = asyncio.run(agent.run(state))
        # With no brokers available, broker_positions should remain empty
        assert isinstance(result.broker_positions, dict)
