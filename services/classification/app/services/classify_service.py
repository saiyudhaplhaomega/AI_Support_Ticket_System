"""ai.classify-ticket.v1 using JSON chat completion (provider-agnostic; see AI_CHAT_PROVIDER)."""
from __future__ import annotations
import logging
from pydantic import ValidationError
from app.clients.chat_errors import ChatAPIError, ChatTimeoutError
from app.config import Settings
from app.errors import ErrorCode, ModuleError
from app.logging_utils import log_event
from app.schemas import ClassifyTicketInput, ClassifyTicketOutputData, _ModelClassification
INTERFACE_ID = "ai.classify-ticket"
logger = logging.getLogger(__name__)
_SYSTEM_PROMPT = "Return JSON only. Classify the ticket from the taxonomy. Fields: category, urgency (low|medium|high|critical), sentiment (negative|neutral|positive), confidence (0-1), summary, tags (array of short free-form labels, e.g. 'refund', 'urgent'; [] if none apply). Do not invent facts."
_INVOICE_VERIFY_INSTRUCTION = " The ticket text includes an attached PDF's extracted content. Also return attachment_is_invoice (boolean) and attachment_invoice_confidence (0-1): true only if the attached content genuinely reads like an invoice (has line items, an amount due/total, an invoice number, or similar billing document structure) rather than some other kind of document."
def _build_system_prompt(verify_invoice: bool) -> str:
    return _SYSTEM_PROMPT + (_INVOICE_VERIFY_INSTRUCTION if verify_invoice else "")
def _build_user_prompt(data, categories):
    parts=[f"Taxonomy (pick exactly one): {', '.join(categories)}"]
    if data.locale: parts.append(f"Locale: {data.locale}")
    if data.context:
        extra={k:v for k,v in data.context.items() if k not in ("categories", "verify_attachment_is_invoice")}
        if extra: parts.append(f"Additional context: {extra!r}")
    return "\n".join(parts+["Ticket text:", data.text])
async def classify_ticket(chat_client, settings: Settings, input_data: ClassifyTicketInput, correlation_id: str) -> ClassifyTicketOutputData:
    categories = [str(c) for c in input_data.context.get("categories", [])] if input_data.context and input_data.context.get("categories") else settings.classify_default_categories
    verify_invoice = bool(input_data.context and input_data.context.get("verify_attachment_is_invoice"))
    try:
        result = await chat_client.complete_json(model=settings.chat_model, messages=[{"role":"system","content":_build_system_prompt(verify_invoice)},{"role":"user","content":_build_user_prompt(input_data,categories)}])
        parsed = _ModelClassification.model_validate(result["parsed"])
    except ChatTimeoutError as exc: raise ModuleError(ErrorCode.UPSTREAM_TIMEOUT,"Classification model did not respond in time.",interface_id=INTERFACE_ID) from exc
    except (ChatAPIError, ValidationError) as exc: raise ModuleError(ErrorCode.UPSTREAM_ERROR,"Classification model returned no structured output.",interface_id=INTERFACE_ID) from exc
    if parsed.category not in categories: log_event(logger,"warning","model returned category outside requested taxonomy",interface_id=INTERFACE_ID,correlation_id=correlation_id,category=parsed.category,taxonomy=categories)
    return ClassifyTicketOutputData(category=parsed.category, confidence=max(0.0,min(1.0,parsed.confidence)), tags=parsed.tags, urgency=parsed.urgency, sentiment=parsed.sentiment, summary=parsed.summary, attachment_is_invoice=parsed.attachment_is_invoice if verify_invoice else None, attachment_invoice_confidence=parsed.attachment_invoice_confidence if verify_invoice else None, raw_model_output={"provider":settings.chat_provider,"model":result["model"],"id":result["id"],"usage":result["usage"]})
