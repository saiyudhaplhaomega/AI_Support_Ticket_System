"""Provider-specific MiniMax chat-completions client; OpenAI is embeddings only."""
from __future__ import annotations
from functools import lru_cache
from typing import Any
import json
import re
import httpx
from app.clients.chat_errors import ChatAPIError, ChatTimeoutError
from app.config import Settings
_CHAT_COMPLETIONS_URL = "https://api.minimax.io/v1/chat/completions"
_THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)
_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*\})\s*```", re.DOTALL)
def _extract_json_object(content: str) -> str:
    """MiniMax-M3 is a reasoning model: even with response_format=json_object it
    emits a `<think>...</think>` reasoning trace and/or wraps the JSON in a
    markdown code fence instead of returning bare JSON in `content`. Strip
    both so downstream `json.loads` sees only the object."""
    stripped = _THINK_BLOCK_RE.sub("", content).strip()
    fence_match = _JSON_FENCE_RE.search(stripped)
    if fence_match:
        return fence_match.group(1)
    first, last = stripped.find("{"), stripped.rfind("}")
    if first != -1 and last != -1 and last > first:
        return stripped[first : last + 1]
    return stripped
class MiniMaxChatClient:
    def __init__(self, api_key: str, timeout: float): self._api_key, self._timeout = api_key, timeout
    async def complete_json(self, *, model: str, messages: list[dict[str, str]]) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(_CHAT_COMPLETIONS_URL, headers={"Authorization": f"Bearer {self._api_key}"}, json={"model": model, "messages": messages, "response_format": {"type": "json_object"}})
                response.raise_for_status(); payload = response.json()
        except httpx.TimeoutException as exc: raise ChatTimeoutError from exc
        except (httpx.HTTPError, ValueError) as exc: raise ChatAPIError from exc
        try:
            content = payload["choices"][0]["message"]["content"]
            return {"parsed": json.loads(_extract_json_object(content)), "id": payload.get("id"), "model": payload.get("model", model), "usage": payload.get("usage")}
        except (KeyError, IndexError, TypeError, ValueError) as exc: raise ChatAPIError from exc
@lru_cache(maxsize=1)
def _cached_client(api_key: str, timeout: float) -> MiniMaxChatClient: return MiniMaxChatClient(api_key, timeout)
def get_minimax_client(settings: Settings) -> MiniMaxChatClient: return _cached_client(settings.minimax_api_key, settings.request_timeout_seconds)
