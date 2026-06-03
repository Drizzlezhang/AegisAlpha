"""Frozen at M1 v1.2. Changes require owner review."""
from typing import Literal

from pydantic import BaseModel


class AgentManifest(BaseModel):
    """每个 Agent 必须导出的注册信息。"""

    name: str
    version: str = "0.1.0"
    requires: list[str] = []  # 依赖的 state 字段或上游 Agent 输出 key
    provides: list[str] = []  # 写入 state 的字段或 extensions key
    tags: list[str] = []  # 能力标签
    llm_dependency: bool = True  # 是否需要 LLM（决定能否进 Lightweight）
    parallel_group: str | None = None  # 同组可并行
    pipeline_mode: Literal["full", "lightweight", "both"] = "full"
    enabled: bool = True
