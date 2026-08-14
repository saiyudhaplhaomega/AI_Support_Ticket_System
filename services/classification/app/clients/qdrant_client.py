"""Qdrant client factory + small helpers shared by rag_service and
ingest_service.
"""
from __future__ import annotations

from functools import lru_cache

from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models as qmodels

from app.config import Settings


@lru_cache(maxsize=1)
def _cached_client(url: str, api_key: str | None, timeout: float) -> AsyncQdrantClient:
    # Do not pass an empty credential through to the SDK. This keeps the
    # unauthenticated deployment mode genuinely header-free.
    kwargs: dict[str, str | float] = {"url": url, "timeout": timeout}
    if api_key:
        kwargs["api_key"] = api_key
    return AsyncQdrantClient(**kwargs)


def get_qdrant_client(settings: Settings) -> AsyncQdrantClient:
    return _cached_client(settings.qdrant_url, settings.qdrant_api_key, settings.request_timeout_seconds)


async def ensure_collection(
    client: AsyncQdrantClient,
    collection: str,
    vector_size: int,
    distance: qmodels.Distance = qmodels.Distance.COSINE,
) -> None:
    """Idempotent: creates the collection only if it doesn't already exist.
    Used by the ingestion pipeline so a fresh product/collection needs zero
    manual Qdrant setup.
    """
    exists = await client.collection_exists(collection)
    if not exists:
        await client.create_collection(
            collection_name=collection,
            vectors_config=qmodels.VectorParams(size=vector_size, distance=distance),
        )
