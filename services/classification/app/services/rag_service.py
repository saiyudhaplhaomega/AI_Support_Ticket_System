"""ai.rag-lookup.v1 implementation: embed the query, search Qdrant, return
structured matches.
"""
from __future__ import annotations

import logging

import httpx
import openai
from qdrant_client.http.exceptions import ApiException
from qdrant_client.http import models as qmodels

from app.config import Settings
from app.errors import ErrorCode, ModuleError
from app.logging_utils import log_event
from app.schemas import RagLookupInput, RagLookupOutputData, RagMatch

INTERFACE_ID = "ai.rag-lookup"

logger = logging.getLogger(__name__)

_CONTENT_KEYS = ("content", "text")


async def _embed_query(openai_client: "openai.AsyncOpenAI", settings: Settings, query: str) -> list[float]:
    try:
        kwargs: dict = {"model": settings.embedding_model, "input": query}
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
    return response.data[0].embedding


def _build_filter(raw: dict | None, correlation_id: str) -> qmodels.Filter | None:
    if not raw:
        return None
    try:
        return qmodels.Filter(**raw)
    except Exception as exc:  # malformed filter payload from caller
        # Qdrant's rendered validation error may include the supplied filter.
        log_event(
            logger, "warning", "invalid vector store filter",
            interface_id=INTERFACE_ID, correlation_id=correlation_id,
            error_code=ErrorCode.VALIDATION_ERROR.value, validation_fields=["filter"],
        )
        raise ModuleError(
            ErrorCode.VALIDATION_ERROR, "Request validation failed.",
            interface_id=INTERFACE_ID,
        ) from exc


def _extract_content(payload: dict) -> str:
    for key in _CONTENT_KEYS:
        value = payload.get(key)
        if isinstance(value, str):
            return value
    return ""


async def rag_lookup(
    openai_client: "openai.AsyncOpenAI",
    qdrant_client,
    settings: Settings,
    input_data: RagLookupInput,
    correlation_id: str,
) -> RagLookupOutputData:
    collection = input_data.collection or settings.rag_default_collection
    top_k = min(input_data.top_k or settings.rag_default_top_k, settings.rag_max_top_k)
    query_filter = _build_filter(input_data.filter, correlation_id)

    vector = await _embed_query(openai_client, settings, input_data.query)

    try:
        exists = await qdrant_client.collection_exists(collection)
        if not exists:
            # Empty result, not an error: an unpopulated/unknown collection
            # is a valid (if unhelpful) answer for a lookup, and lets a
            # brand-new product call rag-lookup before its first ingest run
            # without special-casing "collection missing".
            return RagLookupOutputData(matches=[])

        response = await qdrant_client.query_points(
            collection_name=collection,
            query=vector,
            query_filter=query_filter,
            limit=top_k,
            with_payload=True,
        )
    except httpx.TimeoutException as exc:
        raise ModuleError(
            ErrorCode.UPSTREAM_TIMEOUT, "Vector store did not respond in time.", interface_id=INTERFACE_ID
        ) from exc
    except ApiException as exc:
        diagnostics: dict[str, int] = {}
        status = getattr(exc, "status", None)
        if isinstance(status, int) and 100 <= status <= 599:
            diagnostics["upstream_status"] = status
        log_event(
            logger, "error", "vector store query failed",
            interface_id=INTERFACE_ID, correlation_id=correlation_id,
            error_code=ErrorCode.UPSTREAM_ERROR.value, **diagnostics,
        )
        raise ModuleError(
            ErrorCode.UPSTREAM_ERROR, "Vector store query failed.", interface_id=INTERFACE_ID
        ) from exc

    matches = [
        RagMatch(
            id=str(point.id),
            score=point.score,
            content=_extract_content(point.payload or {}),
            metadata={k: v for k, v in (point.payload or {}).items() if k not in _CONTENT_KEYS},
        )
        for point in response.points
    ]
    return RagLookupOutputData(matches=matches)
