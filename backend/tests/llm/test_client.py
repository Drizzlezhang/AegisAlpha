"""Tests for LLMClient.embed() method."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aegis.llm.client import LLMClient


class TestEmbed:
    @pytest.mark.asyncio
    async def test_embed_returns_vector(self):
        with patch("aegis.llm.client.AsyncOpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client

            mock_embedding = MagicMock()
            mock_embedding.embedding = [0.1] * 1536
            mock_resp = MagicMock()
            mock_resp.data = [mock_embedding]
            mock_client.embeddings.create = AsyncMock(return_value=mock_resp)

            client = LLMClient()
            result = await client.embed("test text")
            assert len(result) == 1536
            assert result == [0.1] * 1536

    @pytest.mark.asyncio
    async def test_embed_failure_returns_empty(self):
        with patch("aegis.llm.client.AsyncOpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client
            mock_client.embeddings.create = AsyncMock(side_effect=Exception("API error"))

            client = LLMClient()
            result = await client.embed("test text")
            assert result == []

    @pytest.mark.asyncio
    async def test_embed_custom_model(self):
        with patch("aegis.llm.client.AsyncOpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client

            mock_embedding = MagicMock()
            mock_embedding.embedding = [0.5] * 1536
            mock_resp = MagicMock()
            mock_resp.data = [mock_embedding]
            mock_client.embeddings.create = AsyncMock(return_value=mock_resp)

            client = LLMClient()
            result = await client.embed("test", model="custom-model")
            assert len(result) == 1536
            mock_client.embeddings.create.assert_called_once_with(
                model="custom-model",
                input="test",
            )
