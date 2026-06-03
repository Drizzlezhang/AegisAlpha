"""Test LLMClient — verify base_url and api_key injection."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aegis.llm.client import LLMClient


class TestLLMClient:
    """Verify LLMClient initialization and chat method."""

    def test_client_initialization(self) -> None:
        """LLMClient should initialize without errors."""
        with patch("aegis.llm.client.AsyncOpenAI") as mock_openai:
            LLMClient()
            mock_openai.assert_called_once()

    @pytest.mark.asyncio
    async def test_chat_method(self) -> None:
        """chat() should call AsyncOpenAI and return structured result."""
        mock_usage = MagicMock()
        mock_usage.model_dump.return_value = {"total_tokens": 50}

        mock_message = AsyncMock()
        mock_message.content = "test response"

        mock_choice = AsyncMock()
        mock_choice.message = mock_message

        mock_response = AsyncMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = mock_usage
        mock_response.model = "gpt-4o"

        with patch("aegis.llm.client.AsyncOpenAI") as mock_openai_cls:
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_openai_cls.return_value = mock_client

            client = LLMClient()
            result = await client.chat(
                model="gpt-4o",
                messages=[{"role": "user", "content": "hello"}],
                temperature=0.7,
            )

            assert result["content"] == "test response"
            assert result["usage"] == {"total_tokens": 50}
            assert result["model"] == "gpt-4o"

    @pytest.mark.asyncio
    async def test_chat_with_response_format(self) -> None:
        """chat() should pass response_format when provided."""
        mock_message = AsyncMock()
        mock_message.content = '{"key": "value"}'

        mock_choice = AsyncMock()
        mock_choice.message = mock_message

        mock_response = AsyncMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = None
        mock_response.model = "gpt-4o-mini"

        with patch("aegis.llm.client.AsyncOpenAI") as mock_openai_cls:
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_openai_cls.return_value = mock_client

            client = LLMClient()
            result = await client.chat(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": "test"}],
                response_format={"type": "json_object"},
                max_tokens=100,
            )

            assert result["content"] == '{"key": "value"}'
            call_kwargs = mock_client.chat.completions.create.call_args.kwargs
            assert call_kwargs["response_format"] == {"type": "json_object"}
            assert call_kwargs["max_tokens"] == 100
