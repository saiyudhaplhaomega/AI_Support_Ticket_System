"""NOAVIA's public test-mode ticket form and private submission boundary."""
from __future__ import annotations

import base64
import ipaddress
import os
import re
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

ROOT = Path(__file__).parent
app = FastAPI(title="NOAVIA test portal")
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class Ticket(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=254)
    subject: str = Field(min_length=1, max_length=240)
    message: str = Field(min_length=1, max_length=20_000)
    attachment_name: str | None = Field(default=None, max_length=255)
    attachment_type: str | None = None
    attachment_base64: str | None = None


def test_mode() -> bool:
    return os.getenv("NOAVIA_TEST_MODE", "true").lower() == "true"


def demo_result() -> dict:
    """Return a stable, dependency-free example of the ticket pipeline output."""
    return {
        "ok": True,
        "ticket_id": "DEMO-0001",
        "mode": "test",
        "message": "Demo ticket processed locally; no external service was contacted.",
        "demo": {
            "contract_version": "ticket-processing-demo.v1",
            "classification": {"category": "account_access", "priority": "medium", "confidence": 0.94, "sentiment": "neutral", "summary": "Requester cannot reset their password after a sign-in attempt."},
            "rag": {
                "sources": [
                    {"rank": 1, "title": "Password reset", "source_id": "kb/noavia/password-reset", "retrieval_score": 0.93},
                    {"rank": 2, "title": "API token rotation", "source_id": "kb/noavia/api-token-rotation", "retrieval_score": 0.71},
                    {"rank": 3, "title": "Priority and SLA", "source_id": "kb/noavia/priority-and-sla", "retrieval_score": 0.52},
                ],
                "fallback": {"used": False, "reason": "Top source score meets the demo threshold of 0.80."},
            },
            "routing": {"queue": "account-support", "owner": "support-tier-1", "reason": "Account-access tickets route to the account-support queue."},
            "manual_review": {"required": False, "reason": "Confidence and retrieval score meet the demo thresholds."},
            "processing_log": [
                {"step": "ingest", "status": "completed", "detail": "Validated local dummy ticket."},
                {"step": "classify", "status": "completed", "detail": "Used deterministic mock classification."},
                {"step": "rag_lookup", "status": "completed", "detail": "Used deterministic mock top-three sources."},
                {"step": "route", "status": "completed", "detail": "Selected account-support queue."},
                {"step": "notify", "status": "skipped", "detail": "Test mode blocks email, Sheets, and n8n execution."},
            ],
            "internal_draft_reply": {"visibility": "internal_draft_only", "text": "Draft: Ask the requester to use the password-reset link and confirm whether the reset email arrives. Do not send automatically."},
        },
    }


def internal_webhook_target() -> str:
    """Return the explicitly approved internal n8n origin or fail closed."""
    target = os.getenv("NOAVIA_N8N_INTERNAL_WEBHOOK_URL", "").strip()
    approved_origin = os.getenv(
        "NOAVIA_N8N_INTERNAL_ALLOWED_ORIGIN", "http://n8n:5678"
    ).strip().rstrip("/")
    if not target:
        raise HTTPException(503, "Submission is disabled until an internal workflow endpoint is configured.")
    parsed_target = urlsplit(target)
    parsed_origin = urlsplit(approved_origin)
    if (
        not parsed_target.scheme
        or not parsed_target.hostname
        or parsed_target.username
        or parsed_target.password
        or parsed_target.query
        or parsed_target.fragment
        or parsed_target.scheme != parsed_origin.scheme
        or parsed_target.netloc.lower() != parsed_origin.netloc.lower()
        or parsed_origin.path
        or parsed_origin.query
        or parsed_origin.fragment
    ):
        raise HTTPException(503, "Submission is disabled until an approved internal workflow endpoint is configured.")
    try:
        ipaddress.ip_address(parsed_target.hostname)
    except ValueError:
        return target
    raise HTTPException(503, "Submission is disabled until an approved internal workflow endpoint is configured.")


async def submit(ticket: Ticket) -> dict:
    if not EMAIL.match(ticket.email):
        raise HTTPException(422, "Enter a valid email address.")
    if ticket.attachment_base64 and ticket.attachment_type not in {"application/pdf", "application/x-pdf"}:
        raise HTTPException(422, "Attachment must be a PDF.")
    if ticket.attachment_base64:
        try:
            attachment = base64.b64decode(ticket.attachment_base64, validate=True)
        except ValueError as exc:
            raise HTTPException(422, "Attachment could not be decoded.") from exc
        if len(attachment) > 10 * 1024 * 1024:
            raise HTTPException(422, "Attachment must be 10 MB or smaller.")
    if test_mode():
        return demo_result()
    ticket_id = f"TEST-{uuid4().hex[:10].upper()}"
    target = internal_webhook_target()
    payload = {"ticket_id": ticket_id, "subject": ticket.subject, "body": ticket.message,
               "requester_email": ticket.email, "requester_name": ticket.name}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(target, json=payload)
    except httpx.RequestError as exc:
        raise HTTPException(502, "The private ticket service could not accept the request.") from exc
    if response.is_error:
        raise HTTPException(502, "The private ticket service could not accept the request.")
    return {"ok": True, "ticket_id": ticket_id, "mode": "controlled-live", "message": "Ticket accepted."}


@app.get("/")
def index() -> FileResponse:
    return FileResponse(ROOT / "static" / "index.html")


@app.post("/api/tickets")
async def create_ticket(ticket: Ticket) -> dict:
    try:
        ticket = ticket.model_copy(update={"name": ticket.name.strip(), "email": ticket.email.strip(),
                                           "subject": ticket.subject.strip(), "message": ticket.message.strip()})
    except Exception as exc:
        raise HTTPException(422, "Name, email, subject, and message are required.") from exc
    return await submit(ticket)
