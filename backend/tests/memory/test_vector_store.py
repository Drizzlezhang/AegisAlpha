"""Tests for VectorStore ChromaDB operations."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aegis.memory.vector_store import VectorStore


@pytest.fixture
def mock_llm_client():
    client = MagicMock()
    client.embed = AsyncMock(return_value=[0.1] * 1536)
    return client


@pytest.fixture
def vector_store(mock_llm_client):
    with patch("aegis.memory.vector_store.chromadb") as mock_chroma:
        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_chroma.PersistentClient.return_value = mock_client
        store = VectorStore(
            persist_dir="/tmp/test_chroma",
            collection_prefix="test_",
            embedding_model="test-model",
            llm_client=mock_llm_client,
        )
        store._mock_client = mock_client
        store._mock_collection = mock_collection
        yield store


class TestAdd:
    @pytest.mark.asyncio
    async def test_add_success(self, vector_store):
        result = await vector_store.add("debate", "doc_1", "test text", {"ticker": "QQQ"})
        assert result is True
        vector_store._mock_collection.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_embedding_fails(self, vector_store, mock_llm_client):
        mock_llm_client.embed.return_value = []
        result = await vector_store.add("debate", "doc_1", "test text")
        assert result is False

    @pytest.mark.asyncio
    async def test_add_chromadb_fails(self, vector_store):
        vector_store._mock_collection.add.side_effect = Exception("ChromaDB error")
        result = await vector_store.add("debate", "doc_1", "test text")
        assert result is False


class TestQuery:
    @pytest.mark.asyncio
    async def test_query_returns_results(self, vector_store):
        vector_store._mock_collection.query.return_value = {
            "ids": [["doc_1", "doc_2"]],
            "documents": [["text 1", "text 2"]],
            "metadatas": [[{"ticker": "QQQ"}, {"ticker": "SPY"}]],
            "distances": [[0.1, 0.2]],
        }
        results = await vector_store.query("test query", collection="debate", top_k=2)
        assert len(results) == 2
        assert results[0]["id"] == "doc_1"
        assert results[0]["document"] == "text 1"
        assert results[0]["distance"] == 0.1

    @pytest.mark.asyncio
    async def test_query_embedding_fails(self, vector_store, mock_llm_client):
        mock_llm_client.embed.return_value = []
        results = await vector_store.query("test query")
        assert results == []

    @pytest.mark.asyncio
    async def test_query_empty_collection(self, vector_store):
        vector_store._mock_collection.query.return_value = {"ids": [[]]}
        results = await vector_store.query("test query")
        assert results == []

    @pytest.mark.asyncio
    async def test_query_chromadb_fails(self, vector_store):
        vector_store._mock_collection.query.side_effect = Exception("ChromaDB error")
        results = await vector_store.query("test query")
        assert results == []


class TestDelete:
    def test_delete_empty_ids(self, vector_store):
        assert vector_store.delete("debate", []) == 0

    def test_delete_success(self, vector_store):
        result = vector_store.delete("debate", ["doc_1", "doc_2"])
        assert result == 2
        vector_store._mock_collection.delete.assert_called_once_with(ids=["doc_1", "doc_2"])

    def test_delete_fails(self, vector_store):
        vector_store._mock_collection.delete.side_effect = Exception("ChromaDB error")
        result = vector_store.delete("debate", ["doc_1"])
        assert result == 0
