"""ai.classify-ticket.v1 implementation.

Uses OpenAI structured outputs (`chat.completions.parse` against a Pydantic
model) so the model is constrained to emit schema-conformant JSON rather
than free text that downstream automation would have to parse/guess at.
"""
from __future__ import annotations

import logging

import openai

from app.config import Settings
from app.errors import ErrorCode, ModuleError
from app.logging_utils import log_event
from app.schemas import ClassifyTicketInput, ClassifyTicketOutputData, _ModelClassification

INTERFACE_ID = "ai.classify-ticket"

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are a support-ticket classification engine for an AI-powered SaaS "
    "support platform. Classify the ticket into exactly one category from "
    "the provided taxonomy, estimate your confidence honestly (0-1, where 1 "
    "means unambiguous), and attach a few short free-form tags (e.g. "
    "'refund', 'urgent', 'bug'). Only use information present in the ticket "
    "text and context; never invent facts."
)


def _build_user_prompt(input_data: ClassifyTicketInput, categories: list[str]) -> str:
    lines = [
        f"Taxonomy (pick exactly one): {', '.join(categories)}",
    ]
    if input_data.locale:
        lines.append(f"Locale: {input_data.locale}")
    if input_data.context:
        extra_context = {k: v for k, v in input_data.context.items() if k != "categories"}
        if extra_context:
            lines.append(f"Additional context: {extra_context!r}")
    lines.append("Ticket text:")
    lines.append(input_data.text)
    return "\n".join(lines)


async def classify_ticket(
    openai_client: "openai.AsyncOpenAI",
    settings: Settings,
    input_data: ClassifyTicketInput,
    correlation_id: str,
) -> ClassifyTicketOutputData:
    categories = (
        [str(c) for c in input_data.context.get("categories", [])]
        if input_data.context and input_data.context.get("categories")
        else settings.classify_default_categories
    )

    try:
        completion = await openai_client.chat.completions.parse(
            model=settings.chat_model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": _build_user_prompt(input_data, categories)},
            ],
            response_format=_ModelClassification,
            timeout=settings.request_timeout_seconds,
        )
    except openai.APITimeoutError as exc:
        raise ModuleError(
            ErrorCode.UPSTREAM_TIMEOUT,
            "Classification model did not respond in time.",
            interface_id=INTERFACE_ID,
        ) from exc
    except openai.APIError as exc:
        raise ModuleError(
            ErrorCode.UPSTREAM_ERROR,
            "Classification model call failed.",
            interface_id=INTERFACE_ID,
        ) from exc

    parsed = completion.choices[0].message.parsed
    if parsed is None:
        refusal = getattr(completion.choices[0].message, "refusal", None)
        log_event(
            logger, "warning", "model refused or returned unparsable output",
            interface_id=INTERFACE_ID, correlation_id=correlation_id, refusal=refusal,
        )
        raise ModuleError(
            ErrorCode.UPSTREAM_ERROR,
            "Classification model returned no structured output.",
            interface_id=INTERFACE_ID,
        )

    category = parsed.category or "uncategorized"
    if category not in categories:
        # Schema constrains shape (a string), not membership in the
        # taxonomy — the model can still drift outside it. Don't silently
        # coerce; surface it so prompt/taxonomy drift is visible in logs.
        log_event(
            logger, "warning", "model returned category outside requested taxonomy",
            interface_id=INTERFACE_ID, correlation_id=correlation_id, category=category, taxonomy=categories,
        )
    confidence = max(0.0, min(1.0, parsed.confidence))

    return ClassifyTicketOutputData(
        category=category,
        confidence=confidence,
        tags=parsed.tags,
        raw_model_output={
            "model": completion.model,
            "id": completion.id,
            "finish_reason": completion.choices[0].finish_reason,
            "usage": completion.usage.model_dump() if completion.usage else None,
        },
    )
