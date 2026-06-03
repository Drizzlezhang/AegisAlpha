"""Frozen at M1 v1.2. Changes require owner review."""
from abc import ABC, abstractmethod
from typing import Any, ClassVar

from aegis.memory.interface import MemoryInterface
from aegis.pipeline.state import PipelineState
from aegis.registry.agent_registry import AgentManifest


class BaseAgent(ABC):
    name: str = "base"
    manifest: ClassVar[AgentManifest]  # 子类必须覆盖

    def __init__(self, memory: MemoryInterface, tools: dict[str, Any], config: dict[str, Any]):
        self.memory = memory
        self.tools = tools
        self.config = config

    @abstractmethod
    async def run(self, state: PipelineState) -> PipelineState:
        ...

    def write_extension(self, state: PipelineState, key: str, value: Any) -> None:
        """将自定义产出写入 state.extensions[agent_name][key]。"""
        if self.name not in state.extensions:
            state.extensions[self.name] = {}
        state.extensions[self.name][key] = value

    def read_extension(self, state: PipelineState, agent_name: str, key: str) -> Any:
        """读取其他 Agent 的 extension 产出。"""
        return state.extensions.get(agent_name, {}).get(key)
