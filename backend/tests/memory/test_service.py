"""Tests for MemoryService scope routing."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from aegis.memory.service import MemoryService


@pytest.fixture
def mock_short_term():
    return MagicMock()


@pytest.fixture
def mock_long_term():
    return MagicMock()


@pytest.fixture
def mock_vector():
    return MagicMock()


@pytest.fixture
def service(mock_short_term, mock_long_term, mock_vector):
    return MemoryService(mock_short_term, mock_long_term, mock_vector)


class TestRead:
    @pytest.mark.asyncio
    async def test_working_returns_empty(self, service):
        result = await service.read("working", {})
        assert result == []

    @pytest.mark.asyncio
    async def test_short_routes_to_short_term(self, service, mock_short_term):
        mock_short_term.query.return_value = [{"id": 1}]
        result = await service.read("short", {"ticker": "QQQ"}, limit=5)
        mock_short_term.query.assert_called_once_with(ticker="QQQ", limit=5)
        assert result == [{"id": 1}]

    @pytest.mark.asyncio
    async def test_long_routes_to_long_term(self, service, mock_long_term):
        mock_long_term.query.return_value = [{"id": 2}]
        result = await service.read("long", {"data_type": "debate"}, limit=10)
        mock_long_term.query.assert_called_once_with(data_type="debate", limit=10)
        assert result == [{"id": 2}]

    @pytest.mark.asyncio
    async def test_episodic_returns_empty(self, service):
        result = await service.read("episodic", {})
        assert result == []


class TestWrite:
    @pytest.mark.asyncio
    async def test_working_noop(self, service, mock_short_term):
        await service.write("working", {"key": "val"})
        mock_short_term.insert.assert_not_called()

    @pytest.mark.asyncio
    async def test_short_routes_to_short_term(self, service, mock_short_term):
        await service.write("short", {"ticker": "QQQ"}, ttl_days=7)
        mock_short_term.insert.assert_called_once_with({"ticker": "QQQ"}, ttl_days=7)

    @pytest.mark.asyncio
    async def test_short_default_ttl(self, service, mock_short_term):
        await service.write("short", {"ticker": "QQQ"})
        mock_short_term.insert.assert_called_once_with({"ticker": "QQQ"}, ttl_days=14)

    @pytest.mark.asyncio
    async def test_long_routes_to_long_term(self, service, mock_long_term):
        await service.write("long", {"ticker": "QQQ", "data_type": "debate"})
        mock_long_term.insert.assert_called_once_with({"ticker": "QQQ", "data_type": "debate"})

    @pytest.mark.asyncio
    async def test_episodic_noop(self, service, mock_short_term, mock_long_term):
        await service.write("episodic", {"key": "val"})
        mock_short_term.insert.assert_not_called()
        mock_long_term.insert.assert_not_called()


class TestSearch:
    @pytest.mark.asyncio
    async def test_routes_to_vector_store(self, service, mock_vector):
        mock_vector.query = AsyncMock(return_value=[{"id": "doc_1"}])
        result = await service.search("test query", collection="debate", top_k=3)
        mock_vector.query.assert_called_once_with(
            query_text="test query", collection="debate", top_k=3, filter=None
        )
        assert result == [{"id": "doc_1"}]


class TestSummarize:
    @pytest.mark.asyncio
    async def test_routes_to_long_term(self, service, mock_long_term):
        mock_long_term.summarize.return_value = {"count": 5}
        result = await service.summarize("QQQ", ("2026-01-01", "2026-06-01"), "debate")
        mock_long_term.summarize.assert_called_once_with(
            ticker="QQQ", date_range=("2026-01-01", "2026-06-01"), data_type="debate"
        )
        assert result == {"count": 5}


class TestArchiveScratchpad:
    @pytest.mark.asyncio
    async def test_archives_each_entry(self, service, mock_short_term):
        scratchpad = {"agent_a": "trace a", "agent_b": "trace b"}
        await service.archive_scratchpad("pipe_1", scratchpad)
        assert mock_short_term.insert.call_count == 2
        # Verify first call
        mock_short_term.insert.assert_any_call(
            {
                "data_type": "scratchpad/agent_a",
                "content": {"trace": "trace a"},
                "pipeline_id": "pipe_1",
            },
            ttl_days=7,
        )

    @pytest.mark.asyncio
    async def test_empty_scratchpad(self, service, mock_short_term):
        await service.archive_scratchpad("pipe_1", {})
        mock_short_term.insert.assert_not_called()
