"""RAG retrieval over the PTSD article corpus.

Hybrid approach: dense vector search (Qdrant) + simple keyword boost.
Hebrew-aware: uses multilingual embeddings (Cohere by default).
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from qdrant_client import AsyncQdrantClient
from qdrant_client.http.models import Filter, FieldCondition, MatchValue

from agent.config import settings, EmbeddingProvider

logger = logging.getLogger(__name__)


@dataclass
class RetrievedChunk:
    text: str
    score: float
    source: str
    metadata: dict


class HebrewRAG:
    """RAG layer with Hebrew multilingual embeddings."""

    def __init__(self) -> None:
        self.qdrant = AsyncQdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key or None,
        )
        self.collection = settings.qdrant_collection
        self._embedder = self._build_embedder()

    def _build_embedder(self):
        if settings.embedding_provider == EmbeddingProvider.COHERE:
            import cohere
            client = cohere.AsyncClientV2(api_key=settings.cohere_api_key)

            async def embed(texts: list[str], input_type: str = "search_query"):
                resp = await client.embed(
                    texts=texts,
                    model=settings.embedding_model,
                    input_type=input_type,
                    embedding_types=["float"],
                )
                return resp.embeddings.float_

            return embed

        if settings.embedding_provider == EmbeddingProvider.OPENAI:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=settings.openai_api_key)

            async def embed(texts: list[str], input_type: str = "search_query"):
                resp = await client.embeddings.create(
                    model=settings.embedding_model,
                    input=texts,
                )
                return [d.embedding for d in resp.data]

            return embed

        raise ValueError(f"Unsupported embedding provider: {settings.embedding_provider}")

    async def retrieve(
        self,
        query: str,
        top_k: int | None = None,
        score_threshold: float | None = None,
        filters: dict | None = None,
    ) -> list[RetrievedChunk]:
        """Retrieve relevant chunks for a user query."""
        if not query.strip():
            return []

        top_k = top_k or settings.rag_top_k
        score_threshold = score_threshold or settings.rag_score_threshold

        try:
            embeddings = await self._embedder([query], input_type="search_query")
            query_vec = embeddings[0]
        except Exception as e:
            logger.error("Embedding failed: %s", e)
            return []

        qdrant_filter = self._build_filter(filters) if filters else None

        try:
            results = await self.qdrant.search(
                collection_name=self.collection,
                query_vector=query_vec,
                limit=top_k,
                score_threshold=score_threshold,
                query_filter=qdrant_filter,
                with_payload=True,
            )
        except Exception as e:
            logger.error("Qdrant search failed: %s", e)
            return []

        return [
            RetrievedChunk(
                text=r.payload.get("text", ""),
                score=r.score,
                source=r.payload.get("source", "unknown"),
                metadata=r.payload.get("metadata", {}),
            )
            for r in results
        ]

    @staticmethod
    def _build_filter(filters: dict) -> Filter:
        return Filter(
            must=[
                FieldCondition(key=k, match=MatchValue(value=v))
                for k, v in filters.items()
            ]
        )

    @staticmethod
    def format_context(chunks: list[RetrievedChunk], max_tokens: int = 2000) -> str:
        """Format retrieved chunks into a context string for the LLM.

        Uses ~4 chars/token as rough estimate.
        """
        if not chunks:
            return ""

        max_chars = max_tokens * 4
        parts: list[str] = []
        total = 0

        for i, chunk in enumerate(chunks, start=1):
            entry = f"[{i}] {chunk.text.strip()}"
            if total + len(entry) > max_chars:
                break
            parts.append(entry)
            total += len(entry)

        return "\n\n".join(parts)


# Singleton for app lifetime
_rag_instance: HebrewRAG | None = None


def get_rag() -> HebrewRAG:
    global _rag_instance
    if _rag_instance is None:
        _rag_instance = HebrewRAG()
    return _rag_instance


# Convenience for quick testing
async def _smoke_test() -> None:
    rag = get_rag()
    chunks = await rag.retrieve("אני סובל מסיוטים מהמילואים")
    for c in chunks:
        print(f"[{c.score:.3f}] {c.source}\n  {c.text[:200]}\n")


if __name__ == "__main__":
    asyncio.run(_smoke_test())
