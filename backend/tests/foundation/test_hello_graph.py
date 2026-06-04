"""Test hello-world graph — verify state flows through graph."""

import pytest

from aegis.pipeline.graph import build_hello_graph
from aegis.pipeline.state import PipelineState


class TestHelloGraph:
    """Verify minimal LangGraph hello-world."""

    def test_graph_builds(self) -> None:
        """Graph should build without errors."""
        graph = build_hello_graph()
        assert graph is not None

    @pytest.mark.asyncio
    async def test_graph_executes(self) -> None:
        """Graph should execute and return state with echo in scratchpad."""
        state = PipelineState(
            pipeline_id="test-001",
            mode="manual",
            tickers=["QQQ", "SPY"],
        )
        graph = build_hello_graph()
        app = graph.compile()
        result = await app.ainvoke(state)

        assert result is not None
        assert "echo" in result["scratchpad"]
        assert "QQQ" in result["scratchpad"]["echo"]
        assert "SPY" in result["scratchpad"]["echo"]

    @pytest.mark.asyncio
    async def test_graph_preserves_state(self) -> None:
        """Graph should preserve existing state fields."""
        state = PipelineState(
            pipeline_id="test-002",
            mode="pre-market",
            tickers=["AAPL"],
            pipeline_mode="full",
        )
        graph = build_hello_graph()
        app = graph.compile()
        result = await app.ainvoke(state)

        assert result["pipeline_id"] == "test-002"
        assert result["mode"] == "pre-market"
        assert result["pipeline_mode"] == "full"
