"""OpenAI chat-completions client for classification/drafting.

Uses a plain (non-reasoning) model with `response_format: json_object`.
Unlike MiniMax-M3, these models return bare JSON in `message.content` with
no `<think>` reasoning trace, so no extraction step is needed here.
"""
from __future__ import annotations

import json
from typing import Any

from openai import APIError, APITimeoutError, AsyncOpenAI

from app.clients.chat_errors import ChatAPIError, ChatTimeoutError
from app.clients.openai_client import get_openai_client
from app.config import Settings


class OpenAIChatClient:
    def __init__(self, client: AsyncOpenAI):
        self._client = client

    async def complete_json(self, *, model: str, messages: list[dict[str, str]]) -> dict[str, Any]:
        try:
            response = await self._client.chat.completions.create(
                model=model, messages=messages, response_format={"type": "json_object"}
            )
        except APITimeoutError as exc:
            raise ChatTimeoutError from exc
        except APIError as exc:
            raise ChatAPIError from exc
        try:
            content = response.choices[0].message.content
            return {
                "parsed": json.loads(content),
                "id": response.id,
                "model": response.model,
                "usage": response.usage.model_dump() if response.usage else None,
            }
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise ChatAPIError from exc


def get_openai_chat_client(settings: Settings) -> OpenAIChatClient:
    return OpenAIChatClient(get_openai_client(settings))
