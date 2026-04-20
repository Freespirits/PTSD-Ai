"""Ingest PTSD articles into Qdrant for RAG.

Supports: PDF, DOCX, MD, TXT, HTML, and URL lists.
Hebrew-aware chunking that respects sentence boundaries.

Usage:
    python -m ingestion.ingest                       # process data/articles/
    python -m ingestion.ingest --path /custom/path
    python -m ingestion.ingest --reset               # wipe collection first
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import logging
import sys
from pathlib import Path

from qdrant_client import AsyncQdrantClient
from qdrant_client.http.models import (
    Distance,
    VectorParams,
    PointStruct,
)

from agent.config import settings, EmbeddingProvider
from ingestion.chunking import chunk_hebrew_text
from ingestion.loaders import load_document

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ingestion")

ARTICLES_DIR = Path("data/articles")
SUPPORTED_EXTS = {".pdf", ".docx", ".md", ".txt", ".html", ".htm"}


# =============================================================================
# Embedding helpers (mirror agent/rag.py logic but for "passage" inputs)
# =============================================================================

async def get_embedder():
    if settings.embedding_provider == EmbeddingProvider.COHERE:
        import cohere
        client = cohere.AsyncClientV2(api_key=settings.cohere_api_key)

        async def embed(texts: list[str]):
            resp = await client.embed(
                texts=texts,
                model=settings.embedding_model,
                input_type="search_document",
                embedding_types=["float"],
            )
            return resp.embeddings.float_

        return embed, _detect_dim_cohere(settings.embedding_model)

    if settings.embedding_provider == EmbeddingProvider.OPENAI:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=settings.openai_api_key)

        async def embed(texts: list[str]):
            resp = await client.embeddings.create(
                model=settings.embedding_model,
                input=texts,
            )
            return [d.embedding for d in resp.data]

        return embed, _detect_dim_openai(settings.embedding_model)

    raise ValueError(f"Unsupported embedding provider: {settings.embedding_provider}")


def _detect_dim_cohere(model: str) -> int:
    return 1024  # cohere multilingual v3

def _detect_dim_openai(model: str) -> int:
    return 3072 if "large" in model else 1536


# =============================================================================
# Qdrant setup
# =============================================================================

async def ensure_collection(client: AsyncQdrantClient, dim: int, reset: bool) -> None:
    exists = await client.collection_exists(settings.qdrant_collection)
    if exists and reset:
        logger.warning("Resetting collection %s", settings.qdrant_collection)
        await client.delete_collection(settings.qdrant_collection)
        exists = False

    if not exists:
        logger.info("Creating collection %s (dim=%d)", settings.qdrant_collection, dim)
        await client.create_collection(
            collection_name=settings.qdrant_collection,
            vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
        )


# =============================================================================
# Main ingestion logic
# =============================================================================

async def ingest_path(path: Path, reset: bool = False, batch_size: int = 64) -> None:
    embed, dim = await get_embedder()

    client = AsyncQdrantClient(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key or None,
    )
    await ensure_collection(client, dim, reset=reset)

    files = _find_files(path)
    if not files:
        logger.warning("No files found in %s", path)
        return

    logger.info("Found %d files. Starting ingestion...", len(files))

    total_chunks = 0
    for i, file_path in enumerate(files, start=1):
        logger.info("[%d/%d] %s", i, len(files), file_path.name)
        try:
            text = load_document(file_path)
            if not text or len(text.strip()) < 100:
                logger.warning("  Skipping (empty/too short)")
                continue

            chunks = chunk_hebrew_text(text, target_size=600, overlap=80)
            logger.info("  -> %d chunks", len(chunks))

            # Embed in batches
            for batch_start in range(0, len(chunks), batch_size):
                batch = chunks[batch_start : batch_start + batch_size]
                vectors = await embed(batch)

                points = [
                    PointStruct(
                        id=_chunk_id(file_path, batch_start + j, chunk),
                        vector=vec,
                        payload={
                            "text": chunk,
                            "source": str(file_path.relative_to(path) if file_path.is_relative_to(path) else file_path.name),
                            "metadata": {
                                "filename": file_path.name,
                                "chunk_index": batch_start + j,
                            },
                        },
                    )
                    for j, (chunk, vec) in enumerate(zip(batch, vectors))
                ]
                await client.upsert(
                    collection_name=settings.qdrant_collection,
                    points=points,
                )
                total_chunks += len(points)

        except Exception as e:
            logger.exception("  Failed to process %s: %s", file_path.name, e)

    logger.info("Done. Ingested %d chunks total.", total_chunks)


def _find_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    return [p for p in path.rglob("*") if p.suffix.lower() in SUPPORTED_EXTS]


def _chunk_id(file_path: Path, idx: int, content: str) -> str:
    """Deterministic ID = sha1(file + idx + content[:100])."""
    raw = f"{file_path.name}|{idx}|{content[:100]}".encode("utf-8")
    return hashlib.sha1(raw).hexdigest()


# =============================================================================
# CLI
# =============================================================================

def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest PTSD articles into Qdrant")
    parser.add_argument(
        "--path",
        type=Path,
        default=ARTICLES_DIR,
        help=f"Directory or file to ingest (default: {ARTICLES_DIR})",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Wipe the collection before ingesting",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=64,
    )
    args = parser.parse_args()

    if not args.path.exists():
        logger.error("Path does not exist: %s", args.path)
        sys.exit(1)

    asyncio.run(ingest_path(args.path, reset=args.reset, batch_size=args.batch_size))


if __name__ == "__main__":
    main()
