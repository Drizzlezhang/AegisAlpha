"""Test BaseAgent contract — abstract methods, manifest, extensions."""

from typing import Any

import pytest

from aegis.agents.base import BaseAgent
from aegis.pipeline.state import PipelineState
from aegis.registry.agent_registry import AgentManifest


class _ConcreteAgent(BaseAgent):
    """Minimal concrete agent for testing BaseAgent contract."""

    name = "test_agent"
    manifest = AgentManifest(
        name="test_agent",
        version="0.1.0",
        requires=["tickers"],
        provides=["test_output"],
        tags=["test"],
        llm_dependency=False,
        pipeline_mode="both",
    )

    async def run(self, state: PipelineState) -> PipelineState:
        self.write_extension(state, "result", "ok")
        return state


class TestBaseAgent:
    """Verify BaseAgent abstract contract."""

    def test_abstract_methods(self) -> None:
        """BaseAgent should have 'run' as abstract method."""
        assert "run" in BaseAgent.__abstractmethods__

    def test_manifest_classvar(self) -> None:
        """Concrete agent must have manifest ClassVar."""
        assert hasattr(_ConcreteAgent, "manifest")
        assert isinstance(_ConcreteAgent.manifest, AgentManifest)
        assert _ConcreteAgent.manifest.name == "test_agent"

    @pytest.mark.asyncio
    async def test_write_extension(
        self, mock_memory: Any, mock_tools: Any, mock_config: Any
    ) -> None:
        """write_extension should write to state.extensions[agent_name][key]."""
        agent = _ConcreteAgent(memory=mock_memory, tools=mock_tools, config=mock_config)
        state = PipelineState()
        agent.write_extension(state, "result", "ok")
        assert state.extensions["test_agent"]["result"] == "ok"

    @pytest.mark.asyncio
    async def test_read_extension(
        self, mock_memory: Any, mock_tools: Any, mock_config: Any
    ) -> None:
        """read_extension should read from another agent's extensions."""
        agent = _ConcreteAgent(memory=mock_memory, tools=mock_tools, config=mock_config)
        state = PipelineState()
        state.extensions["other_agent"] = {"data": 42}
        result = agent.read_extension(state, "other_agent", "data")
        assert result == 42

    @pytest.mark.asyncio
    async def test_read_extension_missing(
        self, mock_memory: Any, mock_tools: Any, mock_config: Any
    ) -> None:
        """read_extension should return None for missing keys."""
        agent = _ConcreteAgent(memory=mock_memory, tools=mock_tools, config=mock_config)
        state = PipelineState()
        result = agent.read_extension(state, "nonexistent", "key")
        assert result is None

    @pytest.mark.asyncio
    async def test_run_writes_extension(
        self, mock_memory: Any, mock_tools: Any, mock_config: Any
    ) -> None:
        """run() should write extension via write_extension."""
        agent = _ConcreteAgent(memory=mock_memory, tools=mock_tools, config=mock_config)
        state = PipelineState()
        result = await agent.run(state)
        assert result.extensions["test_agent"]["result"] == "ok"
