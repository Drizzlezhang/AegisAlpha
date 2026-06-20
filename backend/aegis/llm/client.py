"""Frozen at M1 v1.0. Changes require owner review."""

from typing import Any

from loguru import logger
from openai import AsyncOpenAI

from aegis.utils.settings import settings


class LLMClient:
    def __init__(self) -> None:
        self._client = AsyncOpenAI(
            base_url=settings.LLM_BASE_URL,
            api_key=settings.LLM_API_KEY,
        )

    async def chat(
        self,
        model: str,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        response_format: dict[str, Any] | None = None,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        if response_format:
            kwargs["response_format"] = response_format
        if max_tokens:
            kwargs["max_tokens"] = max_tokens
        resp = await self._client.chat.completions.create(**kwargs)
        return {
            "content": resp.choices[0].message.content,
            "usage": resp.usage.model_dump() if resp.usage else {},
            "model": resp.model,
        }

    async def embed(self, text: str, model: str | None = None) -> list[float]:
        """Call OpenAI-compatible /embeddings endpoint.

        Args:
            text: Text to embed.
            model: Embedding model name. Defaults to settings.EMBEDDING_MODEL.

        Returns:
            1536-dim embedding vector, or empty list on failure.
        """
        try:
            resp = await self._client.embeddings.create(
                model=model or settings.EMBEDDING_MODEL,
                input=text,
            )
            return list(resp.data[0].embedding)
        except Exception:
            logger.exception("Embedding API call failed")
            return []
