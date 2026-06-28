"""Global test fixtures for Aegis 2.0."""

from typing import Any
from unittest.mock import AsyncMock

import pytest


class MockLLMClient:
    """Mock LLM client for testing — no real API calls."""

    def __init__(self) -> None:
        self.chat = AsyncMock(
            return_value={
                "content": '{"score": 75, "rationale": "mock response"}',
                "usage": {"total_tokens": 100},
                "model": "mock-model",
            }
        )


class MockMemory:
    """Mock MemoryInterface for testing — v1.1 compatible."""

    async def read(
        self, scope: str, query: dict[str, Any], limit: int = 10
    ) -> list[dict[str, Any]]:
        return []

    async def write(
        self, scope: str, data: dict[str, Any], ttl_days: int | None = None
    ) -> None:
        pass

    async def search(
        self,
        query: str,
        collection: str = "default",
        top_k: int = 5,
        filter: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        return []

    async def summarize(
        self,
        ticker: str | None,
        date_range: tuple[str, str],
        data_type: str = "",
    ) -> dict[str, Any]:
        return {}

    async def archive_scratchpad(self, pipeline_id: str, scratchpad: dict[str, str]) -> None:
        pass


@pytest.fixture
def mock_llm_client() -> MockLLMClient:
    return MockLLMClient()


@pytest.fixture
def mock_memory() -> MockMemory:
    return MockMemory()


@pytest.fixture
def mock_tools() -> dict[str, Any]:
    return {}


@pytest.fixture
def mock_config() -> dict[str, Any]:
    return {}
