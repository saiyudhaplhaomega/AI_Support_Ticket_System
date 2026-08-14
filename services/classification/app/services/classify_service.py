"""ai.classify-ticket.v1 using MiniMax JSON chat completion (OpenAI is embeddings-only)."""
from __future__ import annotations
import logging
from pydantic import ValidationError
from app.clients.minimax_client import MiniMaxAPIError, MiniMaxTimeoutError
from app.config import Settings
from app.errors import ErrorCode, ModuleError
from app.logging_utils import log_event
from app.schemas import ClassifyTicketInput, ClassifyTicketOutputData, _ModelClassification
INTERFACE_ID = "ai.classify-ticket"
logger = logging.getLogger(__name__)
_SYSTEM_PROMPT = "Return JSON only. Classify the ticket from the taxonomy. Fields: category, urgency (low|medium|high|critical), sentiment (negative|neutral|positive), confidence (0-1), summary, tags (array of short free-form labels, e.g. 'refund', 'urgent'; [] if none apply). Do not invent facts."
def _build_user_prompt(data, categories):
    parts=[f"Taxonomy (pick exactly one): {', '.join(categories)}"]
    if data.locale: parts.append(f"Locale: {data.locale}")
    if data.context:
        extra={k:v for k,v in data.context.items() if k != "categories"}
        if extra: parts.append(f"Additional context: {extra!r}")
    return "\n".join(parts+["Ticket text:", data.text])
async def classify_ticket(minimax_client, settings: Settings, input_data: ClassifyTicketInput, correlation_id: str) -> ClassifyTicketOutputData:
    categories = [str(c) for c in input_data.context.get("categories", [])] if input_data.context and input_data.context.get("categories") else settings.classify_default_categories
    try:
        result = await minimax_client.complete_json(model=settings.chat_model, messages=[{"role":"system","content":_SYSTEM_PROMPT},{"role":"user","content":_build_user_prompt(input_data,categories)}])
        parsed = _ModelClassification.model_validate(result["parsed"])
    except MiniMaxTimeoutError as exc: raise ModuleError(ErrorCode.UPSTREAM_TIMEOUT,"Classification model did not respond in time.",interface_id=INTERFACE_ID) from exc
    except (MiniMaxAPIError, ValidationError) as exc: raise ModuleError(ErrorCode.UPSTREAM_ERROR,"Classification model returned no structured output.",interface_id=INTERFACE_ID) from exc
    if parsed.category not in categories: log_event(logger,"warning","model returned category outside requested taxonomy",interface_id=INTERFACE_ID,correlation_id=correlation_id,category=parsed.category,taxonomy=categories)
    return ClassifyTicketOutputData(category=parsed.category, confidence=max(0.0,min(1.0,parsed.confidence)), tags=parsed.tags, urgency=parsed.urgency, sentiment=parsed.sentiment, summary=parsed.summary, raw_model_output={"provider":"minimax","model":result["model"],"id":result["id"],"usage":result["usage"]})
