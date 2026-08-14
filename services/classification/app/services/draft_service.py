"""Grounded support-reply drafting via MiniMax; citations always remain source metadata."""
from app.clients.minimax_client import MiniMaxAPIError, MiniMaxTimeoutError
from app.config import Settings
from app.errors import ErrorCode, ModuleError
from app.schemas import GroundedDraftInput, GroundedDraftOutputData
INTERFACE_ID="ai.grounded-draft"
FALLBACK="No specific policy found — this response is based on general knowledge."
async def grounded_draft(client, settings: Settings, data: GroundedDraftInput) -> GroundedDraftOutputData:
    matches=data.matches[:3]
    citations=[{"id":str(m.id),"score":m.score,"citation":str(m.metadata.get("source",m.metadata.get("citation",m.id))),"metadata":m.metadata} for m in matches]
    if not matches: return GroundedDraftOutputData(text=FALLBACK,citations=[])
    context="\n\n".join(m.content for m in matches)
    try:
        result=await client.complete_json(model=settings.chat_model,messages=[{"role":"system","content":"Draft a concise support reply grounded only in the supplied knowledge. Return JSON with a text string. Do not claim facts outside it."},{"role":"user","content":f"Ticket:\n{data.ticket_text}\n\nKnowledge:\n{context}"}])
        text=str(result["parsed"]["text"]).strip()
        if not text: raise ValueError
    except MiniMaxTimeoutError as exc: raise ModuleError(ErrorCode.UPSTREAM_TIMEOUT,"Draft model did not respond in time.",interface_id=INTERFACE_ID) from exc
    except (MiniMaxAPIError, KeyError, TypeError, ValueError) as exc: raise ModuleError(ErrorCode.UPSTREAM_ERROR,"Draft model returned no structured output.",interface_id=INTERFACE_ID) from exc
    return GroundedDraftOutputData(text=text,citations=citations)
