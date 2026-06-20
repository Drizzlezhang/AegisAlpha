"""VectorStore — ChromaDB semantic search via OpenAI-compatible embedding API."""

from __future__ import annotations

from typing import Any

import chromadb
from chromadb.api import ClientAPI
from loguru import logger

from aegis.llm.client import LLMClient
from aegis.utils.settings import settings


class VectorStore:
    """Wraps ChromaDB PersistentClient + LLMClient.embed() for semantic search."""

    def __init__(
        self,
        persist_dir: str = "",
        collection_prefix: str = "",
        embedding_model: str = "",
        llm_client: LLMClient | None = None,
    ) -> None:
        self._persist_dir = persist_dir or settings.CHROMA_PERSIST_DIR
        self._prefix = collection_prefix or settings.CHROMA_COLLECTION_PREFIX
        self._embedding_model = embedding_model or settings.EMBEDDING_MODEL
        self._llm_client = llm_client or LLMClient()
        self._client: ClientAPI = chromadb.PersistentClient(path=self._persist_dir)

    def _get_collection(self, name: str) -> Any:
        """Get or create a ChromaDB collection with the configured prefix."""
        return self._client.get_or_create_collection(f"{self._prefix}{name}")

    async def _embed(self, text: str) -> list[float]:
        """Embed text via LLMClient. Returns empty list on failure."""
        try:
            return await self._llm_client.embed(text, model=self._embedding_model)
        except Exception:
            logger.warning(f"Embedding failed for text: {text[:100]}...")
            return []

    async def add(
        self,
        collection: str,
        doc_id: str,
        text: str,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Add a document to a ChromaDB collection.

        Args:
            collection: Collection name (prefix auto-added).
            doc_id: Unique document ID.
            text: Document text to embed and store.
            metadata: Optional metadata dict.

        Returns:
            True if added successfully, False if embedding failed.
        """
        embedding = await self._embed(text)
        if not embedding:
            return False
        try:
            coll = self._get_collection(collection)
            coll.add(
                ids=[doc_id],
                embeddings=[embedding],
                documents=[text],
                metadatas=[metadata or {}],
            )
            return True
        except Exception:
            logger.exception(f"ChromaDB add failed for doc_id={doc_id}")
            return False

    async def query(
        self,
        query_text: str,
        collection: str = "default",
        top_k: int = 5,
        filter: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Semantic search in a ChromaDB collection.

        Args:
            query_text: Natural language query.
            collection: Collection name (prefix auto-added).
            top_k: Number of results to return.
            filter: Optional ChromaDB where filter.

        Returns:
            List of results with id, document, metadata, distance.
            Empty list if embedding fails or collection is empty.
        """
        embedding = await self._embed(query_text)
        if not embedding:
            return []
        try:
            coll = self._get_collection(collection)
            results = coll.query(
                query_embeddings=[embedding],
                n_results=top_k,
                where=filter,
            )
            if not results or not results.get("ids") or not results["ids"][0]:
                return []
            return [
                {
                    "id": results["ids"][0][i],
                    "document": results["documents"][0][i] if results.get("documents") else "",
                    "metadata": results["metadatas"][0][i] if results.get("metadatas") else {},
                    "distance": results["distances"][0][i] if results.get("distances") else 0.0,
                }
                for i in range(len(results["ids"][0]))
            ]
        except Exception:
            logger.exception(f"ChromaDB query failed for: {query_text[:100]}...")
            return []

    def delete(self, collection: str, doc_ids: list[str]) -> int:
        """Delete documents from a ChromaDB collection.

        Args:
            collection: Collection name (prefix auto-added).
            doc_ids: List of document IDs to delete.

        Returns:
            Number of documents deleted (always len(doc_ids) if successful).
        """
        if not doc_ids:
            return 0
        try:
            coll = self._get_collection(collection)
            coll.delete(ids=doc_ids)
            return len(doc_ids)
        except Exception:
            logger.exception(f"ChromaDB delete failed for {len(doc_ids)} docs")
            return 0
