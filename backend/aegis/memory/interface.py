"""Frozen at M1 v1.0. Changes require owner review."""

from abc import ABC, abstractmethod
from typing import Any, Literal

MemoryScope = Literal["working", "short", "long", "episodic"]


class MemoryInterface(ABC):
    @abstractmethod
    async def read(self, scope: MemoryScope, query: dict[str, Any]) -> list[dict[str, Any]]: ...

    @abstractmethod
    async def write(self, scope: MemoryScope, data: dict[str, Any]) -> None: ...

    @abstractmethod
    async def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]: ...

    @abstractmethod
    async def summarize(self, ticker: str, date_range: tuple[str, str]) -> dict[str, Any]: ...

    @abstractmethod
    async def archive_scratchpad(self, pipeline_id: str, scratchpad: dict[str, str]) -> None: ...
