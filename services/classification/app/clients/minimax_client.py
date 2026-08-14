"""Provider-specific MiniMax chat-completions client; OpenAI is embeddings only."""
from __future__ import annotations
from functools import lru_cache
from typing import Any
import json
import httpx
from app.config import Settings
_CHAT_COMPLETIONS_URL = "https://api.minimax.io/v1/chat/completions"
class MiniMaxTimeoutError(RuntimeError): pass
class MiniMaxAPIError(RuntimeError): pass
class MiniMaxChatClient:
    def __init__(self, api_key: str, timeout: float): self._api_key, self._timeout = api_key, timeout
    async def complete_json(self, *, model: str, messages: list[dict[str, str]]) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(_CHAT_COMPLETIONS_URL, headers={"Authorization": f"Bearer {self._api_key}"}, json={"model": model, "messages": messages, "response_format": {"type": "json_object"}})
                response.raise_for_status(); payload = response.json()
        except httpx.TimeoutException as exc: raise MiniMaxTimeoutError from exc
        except (httpx.HTTPError, ValueError) as exc: raise MiniMaxAPIError from exc
        try:
            return {"parsed": json.loads(payload["choices"][0]["message"]["content"]), "id": payload.get("id"), "model": payload.get("model", model), "usage": payload.get("usage")}
        except (KeyError, IndexError, TypeError, ValueError) as exc: raise MiniMaxAPIError from exc
@lru_cache(maxsize=1)
def _cached_client(api_key: str, timeout: float) -> MiniMaxChatClient: return MiniMaxChatClient(api_key, timeout)
def get_minimax_client(settings: Settings) -> MiniMaxChatClient: return _cached_client(settings.minimax_api_key, settings.request_timeout_seconds)
