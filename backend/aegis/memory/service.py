"""MemoryService — implements MemoryInterface v1.1, routes to four memory stores."""

from __future__ import annotations

from typing import Any

from aegis.memory.interface import MemoryInterface, MemoryScope
from aegis.memory.long_term_store import LongTermStore
from aegis.memory.short_term_store import ShortTermStore
from aegis.memory.vector_store import VectorStore


class MemoryService(MemoryInterface):
    """Implements MemoryInterface v1.1 by routing to four specialized stores.

    Scope routing:
        working   → no-op / empty (working memory lives in PipelineState.scratchpad)
        short     → ShortTermStore (SQLite, TTL-based)
        long      → LongTermStore (SQLite, compression support)
        episodic  → no-op (ThesisStore used directly by WeightAdapter)
    """

    def __init__(
        self,
        short_term: ShortTermStore,
        long_term: LongTermStore,
        vector: VectorStore,
    ) -> None:
        self._short_term = short_term
        self._long_term = long_term
        self._vector = vector

    async def read(
        self, scope: MemoryScope, query: dict[str, Any], limit: int = 10
    ) -> list[dict[str, Any]]:
        """Read records from the specified memory scope.

        Args:
            scope: Memory layer to read from.
            query: Filter dict passed to the store's query method.
            limit: Max records to return.

        Returns:
            List of record dicts.
        """
        if scope == "working":
            return []
        if scope == "short":
            return self._short_term.query(**query, limit=limit)
        if scope == "long":
            return self._long_term.query(**query, limit=limit)
        if scope == "episodic":
            return []
        return []

    async def write(
        self, scope: MemoryScope, data: dict[str, Any], ttl_days: int | None = None
    ) -> None:
        """Write data to the specified memory scope.

        Args:
            scope: Memory layer to write to.
            data: Record data dict.
            ttl_days: TTL in days (short-term only).
        """
        if scope == "working":
            return
        if scope == "short":
            self._short_term.insert(data, ttl_days=ttl_days or 14)
            return
        if scope == "long":
            self._long_term.insert(data)
            return
        if scope == "episodic":
            return

    async def search(
        self,
        query: str,
        collection: str = "default",
        top_k: int = 5,
        filter: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Semantic search via VectorStore.

        Args:
            query: Natural language search query.
            collection: ChromaDB collection name.
            top_k: Number of results.
            filter: Optional ChromaDB where filter.

        Returns:
            List of search result dicts.
        """
        return await self._vector.query(
            query_text=query,
            collection=collection,
            top_k=top_k,
            filter=filter,
        )

    async def summarize(
        self, ticker: str | None, date_range: tuple[str, str], data_type: str = ""
    ) -> dict[str, Any]:
        """Aggregate summary of long-term memory records.

        Args:
            ticker: Optional ticker filter.
            date_range: (start_iso, end_iso) tuple.
            data_type: Optional data_type filter.

        Returns:
            Dict with count, date_range, and data_types.
        """
        return self._long_term.summarize(ticker=ticker, date_range=date_range, data_type=data_type)

    async def archive_scratchpad(self, pipeline_id: str, scratchpad: dict[str, str]) -> None:
        """Archive pipeline scratchpad to short-term memory.

        Args:
            pipeline_id: Pipeline run ID.
            scratchpad: Dict of {agent_name: reasoning_trace}.
        """
        for agent_name, trace in scratchpad.items():
            self._short_term.insert(
                {
                    "data_type": f"scratchpad/{agent_name}",
                    "content": {"trace": trace},
                    "pipeline_id": pipeline_id,
                },
                ttl_days=7,
            )
