"""Frozen at M1 v1.0. Changes require owner review."""

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel


class ToolResult(BaseModel):
    success: bool
    data: Any = None
    error: str | None = None
    source: str = ""
    cached: bool = False


class BaseTool(ABC):
    name: str = "base"

    @abstractmethod
    async def fetch(self, **kwargs: Any) -> ToolResult: ...
