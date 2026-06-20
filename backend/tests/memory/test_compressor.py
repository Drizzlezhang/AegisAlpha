"""Tests for MemoryCompressor."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from aegis.memory.compressor import MemoryCompressor


@pytest.fixture
def mock_long_term():
    return MagicMock()


@pytest.fixture
def mock_vector():
    store = MagicMock()
    store.add = AsyncMock(return_value=True)
    return store


@pytest.fixture
def mock_llm():
    client = MagicMock()
    client.chat = AsyncMock(return_value={"content": "Test summary"})
    return client


@pytest.fixture
def config():
    return {
        "long_term": {
            "compression_windows": {
                "debate": {"full_days": 60},
                "recommendation": {"full_days": 60},
            }
        }
    }


@pytest.fixture
def compressor(mock_long_term, mock_vector, mock_llm, config):
    return MemoryCompressor(mock_long_term, mock_vector, mock_llm, config)


class TestRunCompression:
    @pytest.mark.asyncio
    async def test_no_records(self, compressor, mock_long_term):
        mock_long_term.get_uncompressed_before.return_value = []
        stats = await compressor.run_compression()
        assert stats == {"debate": 0, "recommendation": 0}

    @pytest.mark.asyncio
    async def test_compresses_records(self, compressor, mock_long_term, mock_vector, mock_llm):
        d1 = datetime.now(UTC) - timedelta(days=90)
        d2 = datetime.now(UTC) - timedelta(days=80)
        mock_long_term.get_uncompressed_before.return_value = [
            {"id": 1, "ticker": "QQQ", "data_type": "debate", "content": {"a": 1},
             "original_date": d1.isoformat(), "is_compressed": False, "embedding_id": None},
            {"id": 2, "ticker": "QQQ", "data_type": "debate", "content": {"b": 2},
             "original_date": d2.isoformat(), "is_compressed": False, "embedding_id": None},
        ]
        stats = await compressor.run_compression()
        assert stats["debate"] == 2
        mock_llm.chat.assert_called()
        mock_vector.add.assert_called()
        mock_long_term.mark_compressed.assert_called()

    @pytest.mark.asyncio
    async def test_no_config_skips(self, compressor, mock_long_term):
        compressor._config = {"long_term": {}}
        stats = await compressor.run_compression()
        assert stats == {}

    @pytest.mark.asyncio
    async def test_llm_failure_skips_ticker(self, compressor, mock_long_term, mock_llm):
        d1 = datetime.now(UTC) - timedelta(days=90)
        mock_long_term.get_uncompressed_before.return_value = [
            {"id": 1, "ticker": "QQQ", "data_type": "debate", "content": {},
             "original_date": d1.isoformat(), "is_compressed": False, "embedding_id": None},
        ]
        mock_llm.chat.side_effect = Exception("LLM error")
        stats = await compressor.run_compression()
        assert stats["debate"] == 1
        # mark_compressed should NOT be called since LLM failed
        mock_long_term.mark_compressed.assert_not_called()

    @pytest.mark.asyncio
    async def test_groups_by_ticker(self, compressor, mock_long_term):
        d1 = datetime.now(UTC) - timedelta(days=90)
        mock_long_term.get_uncompressed_before.return_value = [
            {"id": 1, "ticker": "QQQ", "data_type": "debate", "content": {},
             "original_date": d1.isoformat(), "is_compressed": False, "embedding_id": None},
            {"id": 2, "ticker": "SPY", "data_type": "debate", "content": {},
             "original_date": d1.isoformat(), "is_compressed": False, "embedding_id": None},
        ]
        stats = await compressor.run_compression()
        # 2 tickers × 2 data_types (debate + recommendation) = 4 mark_compressed calls
        assert mock_long_term.mark_compressed.call_count == 4
