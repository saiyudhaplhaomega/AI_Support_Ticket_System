"""HTTP entrypoint. Implements:

  POST /ai/classify-ticket/v1   -- ai.classify-ticket.v1
  POST /ai/rag-lookup/v1        -- ai.rag-lookup.v1
  POST /internal/ingest/v1      -- ingestion pipeline (operational, unversioned per §4)
  GET  /healthz                 -- liveness (no auth, no upstream calls)
  GET  /readyz                  -- readiness (checks Qdrant reachability)

See README.md for the full interface contract, auth, and error-envelope docs.
"""
from __future__ import annotations

import logging
import uuid

from fastapi import Depends, FastAPI, Header, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app.config import Settings, load_settings_or_exit
from app.clients.openai_client import get_openai_client
from app.clients.qdrant_client import get_qdrant_client
from app.errors import ErrorCode, ModuleError, error_envelope, success_envelope
from app.logging_utils import configure_logging, log_event
from app.schemas import (
    ClassifyTicketInput,
    IngestRequest,
    RagLookupInput,
)
from app.security import verify_bearer_token
from app.services.classify_service import INTERFACE_ID as CLASSIFY_INTERFACE_ID
from app.services.classify_service import classify_ticket
from app.services.ingest_service import ingest_documents
from app.services.rag_service import INTERFACE_ID as RAG_INTERFACE_ID
from app.services.rag_service import rag_lookup

logger = logging.getLogger(__name__)

_PUBLIC_VALIDATION_MESSAGE = "Request validation failed."
_PUBLIC_INTERNAL_MESSAGE = "Internal service error."
_SAFE_VALIDATION_FIELDS = {"text", "context", "locale", "query", "top_k", "filter", "collection", "records", "id", "content", "metadata"}

settings: Settings = load_settings_or_exit()
configure_logging(settings.log_level)

app = FastAPI(title="ai-classification-service", version=settings.service_version)


def get_settings() -> Settings:
    return settings


def get_correlation_id(request: Request) -> str:
    # Set once by attach_correlation_id below, before any dependency/route
    # runs, so every log line and the X-Correlation-Id response header for a
    # given request agree on the same value.
    correlation_id = getattr(request.state, "correlation_id", None)
    return correlation_id or str(uuid.uuid4())


def require_auth(
    authorization: str | None = Header(default=None),
    cfg: Settings = Depends(get_settings),
    correlation_id: str = Depends(get_correlation_id),
) -> None:
    verify_bearer_token(authorization, cfg.ai_classify_api_key, interface_id="auth")


# ---------------------------------------------------------------------------
# Exception handlers — every path out of this app is a structured envelope,
# per qa.validation-and-logging.v1 §3.4 ("never partially execute / throw").
# ---------------------------------------------------------------------------


@app.exception_handler(ModuleError)
async def handle_module_error(request: Request, exc: ModuleError) -> JSONResponse:
    correlation_id = getattr(request.state, "correlation_id", None) or str(uuid.uuid4())
    log_event(
        logger, "error" if exc.code != ErrorCode.AUTH_ERROR else "warning", exc.message,
        interface_id=exc.interface_id, version=exc.version, correlation_id=correlation_id,
        error_code=exc.code.value,
    )
    return JSONResponse(
        status_code=exc.http_status,
        content=error_envelope(
            exc.code, exc.message, interface_id=exc.interface_id, version=exc.version, correlation_id=correlation_id
        ),
    )


@app.exception_handler(RequestValidationError)
@app.exception_handler(ValidationError)
async def handle_validation_error(request: Request, exc: Exception) -> JSONResponse:
    correlation_id = getattr(request.state, "correlation_id", None) or str(uuid.uuid4())
    interface_id = _interface_id_for_path(request.url.path)
    log_event(
        logger, "warning", "request validation failed",
        interface_id=interface_id, correlation_id=correlation_id,
        error_code=ErrorCode.VALIDATION_ERROR.value,
        validation_errors=_safe_validation_errors(exc),
    )
    return JSONResponse(
        status_code=200,
        content=error_envelope(
            ErrorCode.VALIDATION_ERROR, _PUBLIC_VALIDATION_MESSAGE, interface_id=interface_id, version="v1",
            correlation_id=correlation_id,
        ),
    )


@app.exception_handler(Exception)
async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    correlation_id = getattr(request.state, "correlation_id", None) or str(uuid.uuid4())
    interface_id = _interface_id_for_path(request.url.path)
    # Do not log exception text or a traceback here: either can include request data, secrets, or upstream details.
    log_event(
        logger, "error", "unhandled service error",
        interface_id=interface_id, correlation_id=correlation_id,
        error_code=ErrorCode.INTERNAL_ERROR.value,
        exception_type=type(exc).__name__,
    )
    return JSONResponse(
        status_code=200,
        content=error_envelope(
            ErrorCode.INTERNAL_ERROR,
            _PUBLIC_INTERNAL_MESSAGE,
            interface_id=interface_id, version="v1", correlation_id=correlation_id,
        ),
    )


def _interface_id_for_path(path: str) -> str:
    if "classify-ticket" in path:
        return CLASSIFY_INTERFACE_ID
    if "rag-lookup" in path:
        return RAG_INTERFACE_ID
    if "ingest" in path:
        return "ai.rag-lookup"
    return "unknown"


def _safe_validation_errors(exc: Exception) -> list[dict[str, str]]:
    """Return Pydantic diagnostics without input values or rendered errors."""
    errors = getattr(exc, "errors", None)
    if not callable(errors):
        return []
    try:
        raw_errors = errors()
    except Exception:
        return []
    diagnostics: list[dict[str, str]] = []
    for error in raw_errors:
        if not isinstance(error, dict):
            continue
        code = error.get("type")
        diagnostics.append({"field": _safe_field_path(error.get("loc")), "code": code if isinstance(code, str) else "unknown"})
    return diagnostics


def _safe_field_path(location: object) -> str:
    if not isinstance(location, (list, tuple)):
        return "unknown"
    parts = list(location)
    if parts and parts[0] == "body":
        parts = parts[1:]
    if not parts or not isinstance(parts[0], str) or parts[0] not in _SAFE_VALIDATION_FIELDS:
        return "unknown"
    result = parts[0]
    for part in parts[1:]:
        if isinstance(part, int):
            result += "[]"
        elif isinstance(part, str) and part in _SAFE_VALIDATION_FIELDS:
            result += f".{part}"
        else:
            return "unknown"
    return result


@app.middleware("http")
async def attach_correlation_id(request: Request, call_next):
    correlation_id = request.headers.get("x-correlation-id") or str(uuid.uuid4())
    request.state.correlation_id = correlation_id
    response = await call_next(request)
    response.headers["X-Correlation-Id"] = correlation_id
    return response


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok"}


@app.get("/readyz")
async def readyz(cfg: Settings = Depends(get_settings)) -> JSONResponse:
    try:
        client = get_qdrant_client(cfg)
        await client.get_collections()
    except Exception:  # readiness probe: report, don't crash the process
        return JSONResponse(status_code=503, content={"status": "not_ready", "reason": "dependency_unavailable"})
    return JSONResponse(status_code=200, content={"status": "ready"})


@app.post("/ai/classify-ticket/v1", dependencies=[Depends(require_auth)])
async def post_classify_ticket(
    payload: ClassifyTicketInput,
    request: Request,
    cfg: Settings = Depends(get_settings),
    correlation_id: str = Depends(get_correlation_id),
) -> JSONResponse:
    client = get_openai_client(cfg)
    data = await classify_ticket(client, cfg, payload, correlation_id)
    log_event(
        logger, "info", "classified ticket",
        interface_id=CLASSIFY_INTERFACE_ID, correlation_id=correlation_id, category=data.category,
    )
    return JSONResponse(status_code=200, content=success_envelope(data.model_dump()))


@app.post("/ai/rag-lookup/v1", dependencies=[Depends(require_auth)])
async def post_rag_lookup(
    payload: RagLookupInput,
    request: Request,
    cfg: Settings = Depends(get_settings),
    correlation_id: str = Depends(get_correlation_id),
) -> JSONResponse:
    openai_client = get_openai_client(cfg)
    qdrant_client = get_qdrant_client(cfg)
    data = await rag_lookup(openai_client, qdrant_client, cfg, payload, correlation_id)
    log_event(
        logger, "info", "rag lookup",
        interface_id=RAG_INTERFACE_ID, correlation_id=correlation_id, match_count=len(data.matches),
    )
    return JSONResponse(status_code=200, content=success_envelope(data.model_dump()))


@app.post("/internal/ingest/v1", dependencies=[Depends(require_auth)])
async def post_ingest(
    payload: IngestRequest,
    request: Request,
    cfg: Settings = Depends(get_settings),
    correlation_id: str = Depends(get_correlation_id),
) -> JSONResponse:
    openai_client = get_openai_client(cfg)
    qdrant_client = get_qdrant_client(cfg)
    data = await ingest_documents(
        openai_client, qdrant_client, cfg, payload.records, payload.collection, correlation_id
    )
    log_event(
        logger, "info", "ingest complete",
        interface_id="ai.rag-lookup", correlation_id=correlation_id,
        collection=data.collection, ingested=data.ingested,
    )
    return JSONResponse(status_code=200, content=success_envelope(data.model_dump()))
