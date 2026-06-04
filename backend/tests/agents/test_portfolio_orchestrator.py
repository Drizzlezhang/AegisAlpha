"""Test PortfolioOrchestratorAgent — entry_mode 分流, health_score, edge cases."""

import json
import tempfile
from typing import Any

import pytest

from aegis.agents.portfolio_orchestrator_agent import PortfolioOrchestratorAgent
from aegis.pipeline.state import PipelineState


@pytest.fixture
def mock_portfolio_data() -> list[dict[str, Any]]:
    return [
        {
            "ticker": "QQQ",
            "quantity": 100,
            "avg_cost": 380.0,
            "current_price": 420.0,
            "entry_mode": "passive",
            "dte": None,
        },
        {
            "ticker": "QQQ",
            "quantity": 2,
            "avg_cost": 15.0,
            "current_price": 18.5,
            "entry_mode": "active_left",
            "dte": 365,
            "strike": 400,
            "expiration": "2027-06-15",
            "type": "call",
        },
    ]


@pytest.fixture
def mock_portfolio_path(mock_portfolio_data: list[dict[str, Any]]) -> str:
    """Write mock data to a temp file and return its path."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({"positions": mock_portfolio_data}, f)
        return f.name


@pytest.fixture
def mock_config_with_path(mock_portfolio_path: str) -> dict[str, Any]:
    return {"mock_portfolio_path": mock_portfolio_path}


class TestPortfolioOrchestratorAgent:
    """Verify PortfolioOrchestratorAgent behavior."""

    # --- Manifest ---

    def test_manifest_fields(self) -> None:
        """AC-6: manifest should have correct field values."""
        m = PortfolioOrchestratorAgent.manifest
        assert m.name == "portfolio_orchestrator"
        assert m.version == "0.2.0"
        assert m.requires == []
        assert "tickers_holdings_active" in m.provides
        assert "tickers_holdings_passive" in m.provides
        assert "entry_mode" in m.provides
        assert "health_scores" in m.provides
        assert "positions" in m.provides
        assert "portfolio" in m.tags
        assert "orchestrator" in m.tags
        assert m.llm_dependency is False
        assert m.parallel_group is None
        assert m.pipeline_mode == "both"

    # --- Entry mode classification ---

    @pytest.mark.asyncio
    async def test_classify_by_entry_mode(
        self,
        mock_memory: Any,
        mock_tools: Any,
        mock_config_with_path: dict[str, Any],
    ) -> None:
        """AC-4: passive → passive list, active_left → active list."""
        agent = PortfolioOrchestratorAgent(
            memory=mock_memory, tools=mock_tools, config=mock_config_with_path
        )
        state = PipelineState()

        result = await agent.run(state)

        assert "QQQ" in result.tickers_holdings_passive
        assert "QQQ" in result.tickers_holdings_active
        assert result.entry_mode.get("QQQ") in ("passive", "active_left")

    @pytest.mark.asyncio
    async def test_entry_mode_mapping(
        self,
        mock_memory: Any,
        mock_tools: Any,
        mock_config_with_path: dict[str, Any],
    ) -> None:
        """AC-4: entry_mode dict should be populated correctly."""
        agent = PortfolioOrchestratorAgent(
            memory=mock_memory, tools=mock_tools, config=mock_config_with_path
        )
        state = PipelineState()

        result = await agent.run(state)

        # At least one ticker should have entry_mode set
        assert len(result.entry_mode) > 0

    # --- Health scores ---

    @pytest.mark.asyncio
    async def test_health_scores_populated(
        self,
        mock_memory: Any,
        mock_tools: Any,
        mock_config_with_path: dict[str, Any],
    ) -> None:
        """AC-5: health_scores should be populated for each ticker."""
        agent = PortfolioOrchestratorAgent(
            memory=mock_memory, tools=mock_tools, config=mock_config_with_path
        )
        state = PipelineState()

        result = await agent.run(state)

        assert len(result.health_scores) > 0
        for score in result.health_scores.values():
            assert 0.0 <= score <= 100.0

    @pytest.mark.asyncio
    async def test_health_score_passive_stock(
        self,
        mock_memory: Any,
        mock_tools: Any,
    ) -> None:
        """AC-5: passive stock (no DTE) should have dte_score=100, pnl-based health."""
        data = {
            "positions": [
                {
                    "ticker": "QQQ",
                    "quantity": 100,
                    "avg_cost": 380.0,
                    "current_price": 420.0,
                    "entry_mode": "passive",
                    "dte": None,
                }
            ]
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            path = f.name

        agent = PortfolioOrchestratorAgent(
            memory=mock_memory, tools=mock_tools, config={"mock_portfolio_path": path}
        )
        state = PipelineState()
        result = await agent.run(state)

        # pnl_ratio = (420-380)/380 = 0.1053
        # pnl_score = 50 + 10.53 = 60.53
        # dte_score = 100 (no DTE)
        # health = 0.4*100 + 0.6*60.53 = 40 + 36.32 = 76.32
        assert 70.0 < result.health_scores["QQQ"] < 80.0

    @pytest.mark.asyncio
    async def test_health_score_active_left_option(
        self,
        mock_memory: Any,
        mock_tools: Any,
    ) -> None:
        """AC-5: active_left option with DTE should factor DTE into health."""
        data = {
            "positions": [
                {
                    "ticker": "QQQ",
                    "quantity": 2,
                    "avg_cost": 15.0,
                    "current_price": 18.5,
                    "entry_mode": "active_left",
                    "dte": 365,
                    "strike": 400,
                    "expiration": "2027-06-15",
                    "type": "call",
                }
            ]
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            path = f.name

        agent = PortfolioOrchestratorAgent(
            memory=mock_memory, tools=mock_tools, config={"mock_portfolio_path": path}
        )
        state = PipelineState()
        result = await agent.run(state)

        # dte_score = min(365/365, 1.0) * 100 = 100
        # pnl_ratio = (18.5-15)/15 = 0.2333
        # pnl_score = 50 + 23.33 = 73.33
        # health = 0.4*100 + 0.6*73.33 = 40 + 44.0 = 84.0
        assert 80.0 < result.health_scores["QQQ"] < 90.0

    @pytest.mark.asyncio
    async def test_health_score_low_dte(
        self,
        mock_memory: Any,
        mock_tools: Any,
    ) -> None:
        """Low DTE should reduce health score."""
        data = {
            "positions": [
                {
                    "ticker": "QQQ",
                    "quantity": 2,
                    "avg_cost": 15.0,
                    "current_price": 15.0,
                    "entry_mode": "active_left",
                    "dte": 30,
                    "strike": 400,
                    "expiration": "2027-06-15",
                    "type": "call",
                }
            ]
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            path = f.name

        agent = PortfolioOrchestratorAgent(
            memory=mock_memory, tools=mock_tools, config={"mock_portfolio_path": path}
        )
        state = PipelineState()
        result = await agent.run(state)

        # dte_score = min(30/365, 1.0) * 100 = 8.22
        # pnl_score = 50 (breakeven)
        # health = 0.4*8.22 + 0.6*50 = 3.29 + 30 = 33.29
        assert result.health_scores["QQQ"] < 50.0

    # --- Edge cases ---

    @pytest.mark.asyncio
    async def test_missing_file_writes_error(
        self, mock_memory: Any, mock_tools: Any, mock_config: Any
    ) -> None:
        """Edge-2: missing mock_portfolio.json should return empty state."""
        agent = PortfolioOrchestratorAgent(
            memory=mock_memory,
            tools=mock_tools,
            config={"mock_portfolio_path": "/nonexistent/path.json"},
        )
        state = PipelineState()

        result = await agent.run(state)

        assert result.tickers_holdings_active == []
        assert result.tickers_holdings_passive == []
        assert result.health_scores == {}

    @pytest.mark.asyncio
    async def test_unknown_entry_mode_defaults_to_passive(
        self, mock_memory: Any, mock_tools: Any
    ) -> None:
        """Edge-4: unknown entry_mode should default to passive with warning."""
        data = {
            "positions": [
                {
                    "ticker": "QQQ",
                    "quantity": 100,
                    "avg_cost": 380.0,
                    "current_price": 420.0,
                    "entry_mode": "unknown_mode",
                    "dte": None,
                }
            ]
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            path = f.name

        agent = PortfolioOrchestratorAgent(
            memory=mock_memory, tools=mock_tools, config={"mock_portfolio_path": path}
        )
        state = PipelineState()
        result = await agent.run(state)

        assert "QQQ" in result.tickers_holdings_passive
        assert "QQQ" not in result.tickers_holdings_active
        assert len(result.error_flags) > 0

    @pytest.mark.asyncio
    async def test_missing_price_uses_neutral_score(
        self, mock_memory: Any, mock_tools: Any
    ) -> None:
        """Edge-5: missing avg_cost/current_price should use neutral pnl_score=50."""
        data = {
            "positions": [
                {
                    "ticker": "QQQ",
                    "quantity": 100,
                    "entry_mode": "passive",
                    "dte": None,
                }
            ]
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            path = f.name

        agent = PortfolioOrchestratorAgent(
            memory=mock_memory, tools=mock_tools, config={"mock_portfolio_path": path}
        )
        state = PipelineState()
        result = await agent.run(state)

        # dte_score = 100, pnl_score = 50
        # health = 0.4*100 + 0.6*50 = 70
        assert result.health_scores["QQQ"] == 70.0
        assert len(result.error_flags) > 0

    @pytest.mark.asyncio
    async def test_positions_populated(
        self,
        mock_memory: Any,
        mock_tools: Any,
        mock_config_with_path: dict[str, Any],
    ) -> None:
        """state.positions should contain position details."""
        agent = PortfolioOrchestratorAgent(
            memory=mock_memory, tools=mock_tools, config=mock_config_with_path
        )
        state = PipelineState()
        result = await agent.run(state)

        assert "QQQ" in result.positions
        assert "quantity" in result.positions["QQQ"]

    @pytest.mark.asyncio
    async def test_cc_entry_mode_goes_to_active(self, mock_memory: Any, mock_tools: Any) -> None:
        """CC entry_mode should be classified as active."""
        data = {
            "positions": [
                {
                    "ticker": "QQQ",
                    "quantity": 1,
                    "avg_cost": 5.0,
                    "current_price": 4.0,
                    "entry_mode": "cc",
                    "dte": 30,
                    "strike": 450,
                    "expiration": "2027-06-15",
                    "type": "call",
                }
            ]
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            path = f.name

        agent = PortfolioOrchestratorAgent(
            memory=mock_memory, tools=mock_tools, config={"mock_portfolio_path": path}
        )
        state = PipelineState()
        result = await agent.run(state)

        assert "QQQ" in result.tickers_holdings_active
        assert "QQQ" not in result.tickers_holdings_passive
