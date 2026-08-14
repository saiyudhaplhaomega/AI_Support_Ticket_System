"""NOAVIA's public test-mode ticket form and private submission boundary."""
from __future__ import annotations

import base64
import os
import re
from pathlib import Path
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
    ticket_id = f"TEST-{uuid4().hex[:10].upper()}"
    if test_mode():
        return {"ok": True, "ticket_id": ticket_id, "mode": "test", "message": "Test ticket accepted; nothing was sent."}
    target = os.getenv("NOAVIA_N8N_INTERNAL_WEBHOOK_URL", "").strip()
    if not target:
        raise HTTPException(503, "Submission is disabled until an internal workflow endpoint is configured.")
    payload = {"ticket_id": ticket_id, "subject": ticket.subject, "body": ticket.message,
               "requester_email": ticket.email, "requester_name": ticket.name}
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(target, json=payload)
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
