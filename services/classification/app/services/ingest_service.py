"""Qdrant ingestion + embeddings pipeline.

Not one of the two published `ai.*` interfaces (classify-ticket / rag-lookup)
— this is the internal pipeline that populates the collection rag-lookup
reads from. Reachable two ways:
  1. `POST /internal/ingest/v1` (small/ad-hoc batches, e.g. triggered from an
     n8n "new KB article" workflow).
  2. `python -m app.ingest_cli` (bulk/offline loads from a JSONL file).
Both call this same function so behavior never diverges between the two.
"""
from __future__ import annotations

import logging
import uuid

import httpx
import openai
from qdrant_client.http.exceptions import ApiException
from qdrant_client.http import models as qmodels

from app.clients.qdrant_client import ensure_collection
from app.config import Settings
from app.errors import ErrorCode, ModuleError
from app.logging_utils import log_event
from app.schemas import IngestOutputData, IngestRecord

INTERFACE_ID = "ai.rag-lookup"  # ingestion feeds rag-lookup's data; no separate interface id minted for it
BATCH_SIZE = 100

logger = logging.getLogger(__name__)


# Qdrant point ids must be an unsigned int or a UUID (server-side
# constraint) — arbitrary caller-supplied strings aren't valid point ids.
# uuid5 deterministically maps any caller id/content into a stable UUID, so
# re-ingesting the same `id` (or the same `content`, if no id was given)
# updates the point in place instead of duplicating it (upsert semantics).
_ID_NAMESPACE = uuid.UUID("6b3f6a1e-6c3a-4a1a-9b0e-9c0f9c9c9c9c")


def _stable_id(source: str) -> str:
    return str(uuid.uuid5(_ID_NAMESPACE, source))


async def _embed_batch(openai_client: "openai.AsyncOpenAI", settings: Settings, texts: list[str]) -> list[list[float]]:
    try:
        kwargs: dict = {"model": settings.embedding_model, "input": texts}
        if settings.embedding_dimensions:
            kwargs["dimensions"] = settings.embedding_dimensions
        response = await openai_client.embeddings.create(timeout=settings.request_timeout_seconds, **kwargs)
    except openai.APITimeoutError as exc:
        raise ModuleError(
            ErrorCode.UPSTREAM_TIMEOUT, "Embedding model did not respond in time.", interface_id=INTERFACE_ID
        ) from exc
    except openai.APIError as exc:
        raise ModuleError(
            ErrorCode.UPSTREAM_ERROR, "Embedding model call failed.", interface_id=INTERFACE_ID
        ) from exc
    return [item.embedding for item in response.data]


async def ingest_documents(
    openai_client: "openai.AsyncOpenAI",
    qdrant_client,
    settings: Settings,
    records: list[IngestRecord],
    collection: str | None,
    correlation_id: str,
) -> IngestOutputData:
    target_collection = collection or settings.rag_default_collection
    total = 0

    for start in range(0, len(records), BATCH_SIZE):
        batch = records[start : start + BATCH_SIZE]
        vectors = await _embed_batch(openai_client, settings, [r.content for r in batch])

        try:
            await ensure_collection(qdrant_client, target_collection, vector_size=len(vectors[0]))
            await qdrant_client.upsert(
                collection_name=target_collection,
                points=[
                    qmodels.PointStruct(
                        id=_stable_id(record.id or record.content),
                        vector=vector,
                        payload={"content": record.content, **record.metadata},
                    )
                    for record, vector in zip(batch, vectors)
                ],
            )
        except httpx.TimeoutException as exc:
            raise ModuleError(
                ErrorCode.UPSTREAM_TIMEOUT, "Vector store did not respond in time.", interface_id=INTERFACE_ID
            ) from exc
        except ApiException as exc:
            raise ModuleError(
                # Provider-rendered exceptions can include request details. Do not
                # reflect or log them through the shared error envelope.
                ErrorCode.UPSTREAM_ERROR, "Vector store upsert failed.", interface_id=INTERFACE_ID
            ) from exc

        total += len(batch)
        log_event(
            logger, "info", "ingested batch",
            interface_id=INTERFACE_ID, correlation_id=correlation_id,
            collection=target_collection, batch_size=len(batch), total_so_far=total,
        )

    return IngestOutputData(collection=target_collection, ingested=total)
