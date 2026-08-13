"""OpenAI-compatible client factory.

"OpenAI-compatible" per the architecture doc means: anything that speaks the
OpenAI HTTP API shape (OpenAI itself, Azure OpenAI via a compatible proxy,
local vLLM/Ollama gateways, etc). Swap providers by setting
`AI_OPENAI_BASE_URL` — no code change.
"""
from __future__ import annotations

from functools import lru_cache

from openai import AsyncOpenAI

from app.config import Settings


@lru_cache(maxsize=1)
def _cached_client(api_key: str, base_url: str | None, timeout: float) -> AsyncOpenAI:
    kwargs: dict = {"api_key": api_key, "timeout": timeout}
    if base_url:
        kwargs["base_url"] = base_url
    return AsyncOpenAI(**kwargs)


def get_openai_client(settings: Settings) -> AsyncOpenAI:
    return _cached_client(
        settings.openai_api_key,
        settings.openai_base_url,
        settings.request_timeout_seconds,
    )
