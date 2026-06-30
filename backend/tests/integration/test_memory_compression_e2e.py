"""E2E: Memory — write → expire → compress → vector index → search."""

from __future__ import annotations

import pytest


@pytest.mark.skip(
    reason="Requires MemoryCompressor + ChromaDB + LLM client. "
    "Run manually with full memory infrastructure."
)
@pytest.mark.asyncio
async def test_memory_compression_full_cycle() -> None:
    """E2E: write → expire → compress → vector → search."""
    pass