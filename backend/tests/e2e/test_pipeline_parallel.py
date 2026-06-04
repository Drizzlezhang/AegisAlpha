"""E2E tests for full pipeline with parallel execution.

Verifies GraphBuilder assembles correct graph structure with parallel groups,
and the pipeline runner produces expected output with all required fields.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aegis.pipeline.graph_builder import GraphBuilder, _group_by_parallel, _load_agents_yaml
from aegis.pipeline.state import PipelineState


class TestGraphBuilderParallelE2E:
    """E2E: GraphBuilder assembles correct parallel execution structure."""

    def test_full_pipeline_has_parallel_groups(self) -> None:
        """Full pipeline should group signal_analysts into parallel composite nodes."""
        config = _load_agents_yaml()
        agents = config.get("agents", {})

        # Filter for full pipeline agents
        full_agents = {
            name: agent
            for name, agent in agents.items()
            if agent.get("pipeline_mode") in ("full", "both")
            and agent.get("enabled", True)
        }

        assert len(full_agents) > 0, "No full pipeline agents found"

        # Check that signal_analysts parallel group exists
        signal_agents = [
            name
            for name, agent in full_agents.items()
            if agent.get("parallel_group") == "signal_analysts"
        ]
        assert len(signal_agents) >= 2, (
            f"Expected at least 2 signal_analysts agents, got {len(signal_agents)}"
        )

    def test_lightweight_pipeline_no_llm_agents(self) -> None:
        """Lightweight pipeline should only include llm_dependency=False agents."""
        config = _load_agents_yaml()
        agents = config.get("agents", {})

        lw_agents = {
            name: agent
            for name, agent in agents.items()
            if agent.get("pipeline_mode") in ("lightweight", "both")
            and agent.get("enabled", True)
        }

        for name, agent in lw_agents.items():
            assert agent.get("llm_dependency") is False, (
                f"Lightweight agent {name} must have llm_dependency=False"
            )

    def test_parallel_grouping_preserves_order(self) -> None:
        """_group_by_parallel should group consecutive same-group agents."""
        agents = {
            "a": {"parallel_group": "g1"},
            "b": {"parallel_group": "g1"},
            "c": {"parallel_group": None},
            "d": {"parallel_group": "g2"},
            "e": {"parallel_group": "g2"},
        }
        ordered = ["a", "b", "c", "d", "e"]
        groups = _group_by_parallel(ordered, agents)

        assert groups == [["a", "b"], ["c"], ["d", "e"]]

    def test_parallel_grouping_singletons(self) -> None:
        """_group_by_parallel should create singleton groups for non-parallel agents."""
        agents = {
            "a": {"parallel_group": None},
            "b": {"parallel_group": None},
        }
        ordered = ["a", "b"]
        groups = _group_by_parallel(ordered, agents)

        assert groups == [["a"], ["b"]]

    def test_graph_builder_creates_composite_nodes(self) -> None:
        """GraphBuilder should create composite nodes for parallel groups."""
        builder = GraphBuilder()
        graph = builder.build("full")

        # The compiled graph should have nodes
        assert graph is not None
        # Verify it's a compiled graph
        assert hasattr(graph, "ainvoke")

    def test_graph_builder_lightweight_creates_graph(self) -> None:
        """GraphBuilder should create a valid lightweight graph."""
        builder = GraphBuilder()
        graph = builder.build("lightweight")

        assert graph is not None
        assert hasattr(graph, "ainvoke")


class TestPipelineRunnerE2E:
    """E2E: Pipeline runner produces correct output structure."""

    @pytest.mark.asyncio
    async def test_run_full_returns_pipeline_state(self) -> None:
        """run_full should return a PipelineState with expected fields."""
        from aegis.pipeline.runner import run_full

        # Mock all agent modules to avoid real imports
        with patch("aegis.pipeline.graph_builder.GraphBuilder.build") as mock_build:
            mock_graph = MagicMock()
            mock_state = PipelineState(
                pipeline_id="e2e-001",
                pipeline_mode="full",
                tickers=["QQQ"],
                recommendations=[],
                health_scores={"QQQ": 100.0},
                agent_timings={"_total": 0.5},
            )
            mock_graph.ainvoke = AsyncMock(return_value=mock_state.model_dump())
            mock_build.return_value = mock_graph

            result = await run_full("QQQ", mode="manual")

            assert isinstance(result, PipelineState)
            assert result.pipeline_id == "e2e-001"
            assert result.pipeline_mode == "full"
            assert "_total" in result.agent_timings

    @pytest.mark.asyncio
    async def test_run_lightweight_returns_pipeline_state(self) -> None:
        """run_lightweight should return a PipelineState with health scores."""
        from aegis.pipeline.runner import run_lightweight

        with patch("aegis.pipeline.graph_builder.GraphBuilder.build") as mock_build:
            mock_graph = MagicMock()
            mock_state = PipelineState(
                pipeline_id="e2e-002",
                pipeline_mode="lightweight",
                tickers=["QQQ"],
                health_scores={"QQQ": 95.0},
                passive_health_alerts=[],
                agent_timings={"_total": 0.3},
            )
            mock_graph.ainvoke = AsyncMock(return_value=mock_state.model_dump())
            mock_build.return_value = mock_graph

            result = await run_lightweight(["QQQ"])

            assert isinstance(result, PipelineState)
            assert result.pipeline_mode == "lightweight"
            assert "QQQ" in result.health_scores

    @pytest.mark.asyncio
    async def test_run_lightweight_empty_tickers(self) -> None:
        """run_lightweight with empty tickers should return empty state."""
        from aegis.pipeline.runner import run_lightweight

        result = await run_lightweight([])

        assert isinstance(result, PipelineState)
        assert result.pipeline_mode == "lightweight"
        assert result.tickers == []

    @pytest.mark.asyncio
    async def test_run_full_with_ws_manager(self) -> None:
        """run_full with ws_manager should emit pipeline_complete event."""
        from aegis.pipeline.runner import run_full

        mock_ws = MagicMock()
        mock_ws.emit_pipeline_complete = AsyncMock()

        with patch("aegis.pipeline.graph_builder.GraphBuilder.build") as mock_build:
            mock_graph = MagicMock()
            mock_state = PipelineState(
                pipeline_id="e2e-003",
                pipeline_mode="full",
                tickers=["QQQ"],
                agent_timings={"_total": 0.5},
            )
            mock_graph.ainvoke = AsyncMock(return_value=mock_state.model_dump())
            mock_build.return_value = mock_graph

            result = await run_full("QQQ", ws_manager=mock_ws)

            assert result.pipeline_id == "e2e-003"
            mock_ws.emit_pipeline_complete.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_lightweight_with_ws_manager(self) -> None:
        """run_lightweight with ws_manager should emit pipeline_complete event."""
        from aegis.pipeline.runner import run_lightweight

        mock_ws = MagicMock()
        mock_ws.emit_pipeline_complete = AsyncMock()

        with patch("aegis.pipeline.graph_builder.GraphBuilder.build") as mock_build:
            mock_graph = MagicMock()
            mock_state = PipelineState(
                pipeline_id="e2e-004",
                pipeline_mode="lightweight",
                tickers=["QQQ"],
                health_scores={"QQQ": 95.0},
                agent_timings={"_total": 0.3},
            )
            mock_graph.ainvoke = AsyncMock(return_value=mock_state.model_dump())
            mock_build.return_value = mock_graph

            result = await run_lightweight(["QQQ"], ws_manager=mock_ws)

            assert result.pipeline_mode == "lightweight"
            mock_ws.emit_pipeline_complete.assert_called_once()


class TestPipelineStateE2E:
    """E2E: PipelineState schema validation."""

    def test_pipeline_state_all_fields(self) -> None:
        """PipelineState should accept all v1.3 fields."""
        state = PipelineState(
            pipeline_id="e2e-005",
            mode="manual",
            pipeline_mode="full",
            tickers=["QQQ", "SPY"],
            tickers_holdings_active=["QQQ"],
            tickers_holdings_passive=["SPY"],
            entry_mode={"QQQ": "active_left", "SPY": "passive"},
            health_scores={"QQQ": 90.0, "SPY": 95.0},
            delta_dollars_delta=5000.0,
            smart_money_data={"QQQ": {"score": 75}},
            fund_flow_data={"QQQ": {"net_flow": 1.2e9}},
            trigger_conditions=[{"ticker": "QQQ", "type": "price_below"}],
            strategy_comparisons={"QQQ": [{"plan_no": 1, "strategy": "leaps_call"}]},
            scenario_pnl={"QQQ": {"target": {"price": 520, "pnl": 5000}}},
        )

        assert state.pipeline_id == "e2e-005"
        assert state.pipeline_mode == "full"
        assert len(state.tickers) == 2
        assert state.entry_mode["QQQ"] == "active_left"
        assert state.health_scores["QQQ"] == 90.0
        assert state.delta_dollars_delta == 5000.0
        assert "QQQ" in state.smart_money_data
        assert "QQQ" in state.fund_flow_data
        assert len(state.trigger_conditions) == 1
        assert "QQQ" in state.strategy_comparisons
        assert "QQQ" in state.scenario_pnl

    def test_pipeline_state_defaults(self) -> None:
        """PipelineState should have sensible defaults."""
        state = PipelineState()

        assert state.pipeline_id == ""
        assert state.mode == "manual"
        assert state.pipeline_mode == "full"
        assert state.tickers == []
        assert state.recommendations == []
        assert state.blocked_recommendations == []
        assert state.error_flags == []
        assert state.health_scores == {}
        assert state.delta_dollars_delta == 0.0
