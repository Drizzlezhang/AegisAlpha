"""Frozen at M3 v1.1. Changes require owner review."""

from abc import ABC, abstractmethod
from typing import Any, Literal

MemoryScope = Literal["working", "short", "long", "episodic"]


class MemoryInterface(ABC):
    @abstractmethod
    async def read(
        self, scope: MemoryScope, query: dict[str, Any], limit: int = 10
    ) -> list[dict[str, Any]]: ...

    @abstractmethod
    async def write(
        self, scope: MemoryScope, data: dict[str, Any], ttl_days: int | None = None
    ) -> None: ...

    @abstractmethod
    async def search(
        self,
        query: str,
        collection: str = "default",
        top_k: int = 5,
        filter: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]: ...

    @abstractmethod
    async def summarize(
        self, ticker: str | None, date_range: tuple[str, str], data_type: str = ""
    ) -> dict[str, Any]: ...

    @abstractmethod
    async def archive_scratchpad(self, pipeline_id: str, scratchpad: dict[str, str]) -> None: ...
