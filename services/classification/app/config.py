"""Env-var contract for this service.

Implements the "fail fast on missing secrets" rule from
infra.secrets-and-network.v1 (retired module architecture spec): a
module must refuse to start with a clear structured error if a required env
var is missing, never fall back to a hardcoded default for a secret.

Non-secret tuning knobs (model names, timeouts, default collection, ...) *do*
get sensible in-code defaults so future products don't need to touch
internals to run this module (RAG & AI Integration Engineer priority #3).
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field


class ConfigError(RuntimeError):
    """Raised when a required env var is missing or invalid at startup."""


def _require(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ConfigError(
            f"Missing required env var {name}. Set it in the deploy environment's "
            f".env / secret-store — see infra/.env.example. Refusing to start "
            f"with a hardcoded fallback for a secret."
        )
    return value


def _optional(name: str, default: str) -> str:
    value = os.environ.get(name, "").strip()
    return value if value else default


def _optional_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(f"Env var {name}={raw!r} is not a valid integer.") from exc


def _optional_float(name: str, default: float) -> float:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ConfigError(f"Env var {name}={raw!r} is not a valid float.") from exc


def _optional_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    if not raw:
        return default
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    raise ConfigError(f"Env var {name}={raw!r} is not a valid boolean.")


@dataclass(frozen=True)
class Settings:
    # ---- secrets (required, no hardcoded fallback) ----
    openai_api_key: str
    minimax_api_key: str
    ai_classify_api_key: str  # inbound bearer token consumers present to *this* service
    qdrant_url: str

    # ---- Qdrant access mode / credential ----
    # An unauthenticated Qdrant deployment has no credential to supply. Keep
    # the mode explicit and secure-by-default so a missing key cannot silently
    # weaken an authenticated deployment.
    qdrant_auth_enabled: bool
    qdrant_api_key: str | None

    # ---- non-secret tuning knobs (sensible defaults) ----
    embedding_provider: str
    embedding_model: str
    embedding_dimensions: int | None
    chat_provider: str
    chat_model: str
    request_timeout_seconds: float
    rag_default_collection: str
    rag_default_top_k: int
    rag_max_top_k: int
    classify_default_categories: list[str] = field(default_factory=list)
    log_level: str = "info"
    service_version: str = "v1"


def load_settings() -> Settings:
    qdrant_auth_enabled = _optional_bool("AI_QDRANT_AUTH_ENABLED", True)
    qdrant_api_key = os.environ.get("AI_QDRANT_API_KEY", "").strip() or None
    if qdrant_auth_enabled and not qdrant_api_key:
        raise ConfigError(
            "Missing required env var AI_QDRANT_API_KEY while "
            "AI_QDRANT_AUTH_ENABLED is true. Set a collection-scoped Qdrant "
            "credential, or set AI_QDRANT_AUTH_ENABLED=false only for a Qdrant "
            "deployment with authentication disabled."
        )
    embedding_provider = _optional("AI_EMBEDDING_PROVIDER", "openai").lower()
    chat_provider = _optional("AI_CHAT_PROVIDER", "openai").lower()
    if embedding_provider != "openai":
        raise ConfigError("AI_EMBEDDING_PROVIDER must be 'openai'.")
    if chat_provider not in ("openai", "minimax"):
        raise ConfigError("AI_CHAT_PROVIDER must be 'openai' or 'minimax'.")
    default_chat_model = "gpt-4o-mini" if chat_provider == "openai" else "MiniMax-M3"
    return Settings(
        openai_api_key=_require("OPENAI_API_KEY"),
        # MiniMax stays optional now that OpenAI is the default chat provider;
        # only fail fast on it when a deployment actually selects minimax.
        minimax_api_key=(_require("MINIMAX_API_KEY") if chat_provider == "minimax" else os.environ.get("MINIMAX_API_KEY", "").strip()),
        ai_classify_api_key=_require("AI_CLASSIFY_API_KEY"),
        qdrant_url=_require("QDRANT_URL"),
        qdrant_auth_enabled=qdrant_auth_enabled,
        qdrant_api_key=qdrant_api_key,
        embedding_provider=embedding_provider,
        embedding_model=_optional("AI_EMBEDDING_MODEL", "text-embedding-3-small"),
        embedding_dimensions=(
            _optional_int("AI_EMBEDDING_DIMENSIONS", 0) or None
        ),
        chat_provider=chat_provider,
        chat_model=_optional("AI_CHAT_MODEL", default_chat_model),
        request_timeout_seconds=_optional_float("AI_UPSTREAM_TIMEOUT_SECONDS", 20.0),
        rag_default_collection=_optional("AI_RAG_COLLECTION", "kb_documents"),
        rag_default_top_k=_optional_int("AI_RAG_TOP_K_DEFAULT", 5),
        rag_max_top_k=_optional_int("AI_RAG_TOP_K_MAX", 50),
        classify_default_categories=[
            c.strip()
            for c in _optional(
                "AI_CLASSIFY_CATEGORIES_DEFAULT",
                "billing,technical,account,feature_request,complaint,other",
            ).split(",")
            if c.strip()
        ],
        log_level=_optional("INFRA_LOG_LEVEL", "info"),
    )


def load_settings_or_exit() -> Settings:
    """Used at process startup (see main.py). Fails loudly, not silently."""
    try:
        return load_settings()
    except ConfigError as exc:
        # Structured, single-line so it's greppable in container logs; no
        # secret *values* are ever included, only var names.
        sys.stderr.write(f'{{"level":"fatal","message":"{exc}"}}\n')
        raise SystemExit(1) from exc
