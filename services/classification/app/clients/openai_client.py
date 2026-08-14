"""OpenAI embedding client factory (chat is owned by MiniMax)."""
from __future__ import annotations

from functools import lru_cache

from openai import AsyncOpenAI

from app.config import Settings


@lru_cache(maxsize=1)
def _cached_client(api_key: str, timeout: float) -> AsyncOpenAI:
    return AsyncOpenAI(api_key=api_key, timeout=timeout)


def get_openai_client(settings: Settings) -> AsyncOpenAI:
    return _cached_client(
        settings.openai_api_key,
        settings.request_timeout_seconds,
    )
