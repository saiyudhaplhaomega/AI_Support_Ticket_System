"""Test-only NOAVIA ticket UI; operational addresses stay server-side."""
from __future__ import annotations

import os
import re
from email.parser import BytesParser
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, ValidationError, field_validator

ROOT = Path(__file__).parent
app = FastAPI(title="NOAVIA test ticket portal")


class Ticket(BaseModel):
    name: str
    email: str
    subject: str
    message: str

    @field_validator("email")
    @classmethod
    def valid_email(cls, value: str) -> str:
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("invalid email")
        return value


def _test_mode() -> bool:
    return os.getenv("NOAVIA_TEST_MODE", "true").lower() == "true"


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(ROOT / "static" / "index.html")


@app.post("/api/tickets")
async def submit_ticket(request: Request) -> dict:
    if not _test_mode():
        raise HTTPException(503, "Ticket portal is available only in test mode.")
    content_type = request.headers.get("content-type", "")
    if content_type.startswith("application/json"):
        body = await request.json(); uploaded = None
    elif "multipart/form-data" in content_type:
        boundary = content_type.split("boundary=", 1)[-1].strip('"').encode()
        raw = await request.body(); body = {}; uploaded = None
        for part in raw.split(b"--" + boundary):
            if b"Content-Disposition:" not in part: continue
            message = BytesParser().parsebytes(part.lstrip(b"\r\n") + b"\r\n")
            name = message.get_param("name", header="content-disposition")
            filename = message.get_param("filename", header="content-disposition")
            value = message.get_payload(decode=True) or b""
            value = value.rstrip(b"\r\n")
            if filename: uploaded = (filename, message.get_content_type(), value)
            elif name: body[name] = value.decode("utf-8", "replace")
    else:
        raise HTTPException(415, "Use JSON or multipart form data.")
    try:
        name, email, subject, message = (str(body.get(key, "")) for key in ("name", "email", "subject", "message"))
        ticket = Ticket(name=name.strip(), email=email.strip(), subject=subject.strip(), message=message.strip())
        if not all((ticket.name, ticket.subject, ticket.message)):
            raise ValueError("Required fields must not be empty.")
    except (ValidationError, ValueError) as exc:
        raise HTTPException(422, "Enter a name, valid email, subject, and message.") from exc
    payload = {"requester_name": ticket.name, "requester_email": str(ticket.email), "subject": ticket.subject, "body": ticket.message}
    files = None
    if uploaded:
        filename, mime, content = uploaded
        if mime != "application/pdf" or not filename.lower().endswith(".pdf"):
            raise HTTPException(422, "Optional attachment must be a PDF.")
        if len(content) > 10 * 1024 * 1024: raise HTTPException(422, "PDF must be 10 MB or smaller.")
        files = {"data": (filename, content, mime)}
    url = os.getenv("NOAVIA_N8N_INTERNAL_URL", "http://n8n:5678/webhook/noavia/tickets/v1")
    headers = {"X-NOAVIA-Internal-Token": os.getenv("NOAVIA_INTERNAL_WEBHOOK_TOKEN", "")}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(url, json=None if files else payload, data=payload if files else None, files=files, headers=headers)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(502, "Test submission could not reach the private workflow.") from exc
    return {"ok": True, "message": "Test ticket accepted. No customer email is sent.", "result": response.json()}
