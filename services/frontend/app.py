"""NOAVIA's public test-mode ticket form and private submission boundary."""
from __future__ import annotations

import base64
import asyncio
from collections import defaultdict, deque
import ipaddress
import os
import re
import secrets
import time
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

import httpx
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from authlib.integrations.starlette_client import OAuth
from starlette.middleware.sessions import SessionMiddleware

ROOT = Path(__file__).parent
app = FastAPI(title="NOAVIA test portal")
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("NOAVIA_SESSION_SECRET") or secrets.token_urlsafe(32),
    https_only=True,
    # Lax is required so the signed OAuth state cookie returns from Google on
    # the top-level callback. The callback still validates Authlib state.
    same_site="lax",
    max_age=3600,
)
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
KB_RATE_WINDOW_SECONDS = 600
KB_RATE_MAX_REQUESTS = 20
CHAT_RATE_MAX_REQUESTS = 12
CHAT_RATE_WINDOW_SECONDS = 600
_kb_attempts: dict[str, deque[float]] = defaultdict(deque)
_chat_attempts: dict[str, deque[float]] = defaultdict(deque)
_kb_source_locks: dict[str, asyncio.Lock] = {}
_kb_sessions: dict[str, float] = {}
KB_SESSION_SECONDS = 3600
MAX_KB_FILE_BYTES = 5 * 1024 * 1024
# Base64 expands a 5 MB document to at most this many ASCII characters.
MAX_KB_BASE64_CHARS = 7_000_000


class Ticket(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=254)
    subject: str = Field(min_length=1, max_length=240)
    message: str = Field(min_length=1, max_length=20_000)
    attachment_name: str | None = Field(default=None, max_length=255)
    attachment_type: str | None = None
    attachment_base64: str | None = None


class KnowledgeBaseUpload(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    content_base64: str = Field(min_length=1, max_length=MAX_KB_BASE64_CHARS)
    collection: str = Field(default="ticket", pattern=r"^(ticket|public|admin)$")


class KnowledgeBaseLogin(BaseModel):
    username: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=1, max_length=512)


class PublicChatQuestion(BaseModel):
    message: str = Field(min_length=1, max_length=2_000)


class KnowledgeLibraryAction(BaseModel):
    collection: str = Field(pattern=r"^(ticket|public|admin)$")
    action: str = Field(pattern=r"^(list|read|delete)$")
    source: str | None = Field(default=None, max_length=255)


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


def public_webhook_target() -> str | None:
    """Return the local-testing public webhook URL, if the operator opted in.

    Separate from internal_webhook_target(): that path is for the
    docker-internal, owner-approved production scenario and its strict
    same-origin validation must stay untouched. This path is for running
    the frontend standalone (e.g. on a developer's own machine) against
    the real public n8n webhook, gated behind its own explicit env var so
    it's never accidentally active in the docker-internal deployment.
    """
    return os.getenv("NOAVIA_N8N_PUBLIC_WEBHOOK_URL", "").strip() or None


def public_kb_update_target() -> str | None:
    """Return the separately configured, owner-approved KB update endpoint."""
    return os.getenv("NOAVIA_N8N_KB_UPDATE_WEBHOOK_URL", "").strip() or None


def document_manager_target() -> str | None:
    """Return the single protected workflow which owns source documents."""
    return os.getenv("NOAVIA_N8N_DOCUMENT_MANAGER_WEBHOOK_URL", "").strip() or None


def public_chat_target() -> str | None:
    """Return the isolated public-company chatbot webhook, if configured."""
    target = os.getenv("NOAVIA_N8N_PUBLIC_CHAT_WEBHOOK_URL", "").strip()
    parsed = urlsplit(target)
    if not target or parsed.scheme != "https" or parsed.query or parsed.fragment or parsed.path.rstrip("/") != "/webhook/noavia/public-chat/v1":
        return None
    return target


def knowledge_library_target() -> str | None:
    return os.getenv("NOAVIA_N8N_KB_LIBRARY_WEBHOOK_URL", "").strip() or None


def source_library_target() -> str | None:
    return os.getenv("NOAVIA_N8N_SOURCE_LIBRARY_WEBHOOK_URL", "").strip() or None


def admin_chat_target() -> str | None:
    return os.getenv("NOAVIA_N8N_ADMIN_CHAT_WEBHOOK_URL", "").strip() or None


def require_kb_admin(request: Request, token: str | None, *, rate_limit: bool = True) -> None:
    """Fail closed for administration; rate-limit document mutations per caller."""
    if test_mode():
        return
    expected = os.getenv("NOAVIA_KB_ADMIN_TOKEN", "")
    session = request.cookies.get("noavia_kb_session", "")
    legacy_session_valid = bool(session and _kb_sessions.get(session, 0) > time.monotonic())
    google_session_valid = request.session.get("google_admin_email", "") in google_admin_emails()
    session_valid = legacy_session_valid or google_session_valid
    token_valid = bool(expected and token and secrets.compare_digest(token, expected))
    if not session_valid and not token_valid:
        raise HTTPException(401, "Knowledge-base administrator authentication is required.")
    if not rate_limit:
        return
    client = request.client.host if request.client else "unknown"
    now = time.monotonic()
    recent = _kb_attempts[client]
    while recent and recent[0] <= now - KB_RATE_WINDOW_SECONDS:
        recent.popleft()
    if len(recent) >= KB_RATE_MAX_REQUESTS:
        raise HTTPException(429, "Too many knowledge-base update requests. Try again later.")
    recent.append(now)


def has_kb_admin_session(request: Request) -> bool:
    """Return whether this browser owns a current administrator session."""
    session = request.cookies.get("noavia_kb_session", "")
    expires_at = _kb_sessions.get(session, 0)
    if expires_at <= time.monotonic():
        _kb_sessions.pop(session, None)
        return False
    return bool(session)


def google_admin_emails() -> set[str]:
    return {
        email.strip().lower()
        for email in os.getenv("NOAVIA_GOOGLE_ADMIN_EMAILS", "").split(",")
        if email.strip()
    }


def google_oauth_client() -> OAuth:
    client_id = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "").strip()
    client_secret = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret or not google_admin_emails() or not os.getenv("NOAVIA_SESSION_SECRET", ""):
        raise HTTPException(503, "Google administrator sign-in is not configured.")
    oauth = OAuth()
    oauth.register(
        name="google",
        client_id=client_id,
        client_secret=client_secret,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )
    return oauth


async def submit_to_public_webhook(ticket: Ticket, target: str) -> dict:
    ticket_id = f"TEST-{uuid4().hex[:10].upper()}"
    header_name = os.getenv("NOAVIA_N8N_WEBHOOK_HEADER_NAME", "").strip()
    header_value = os.getenv("NOAVIA_N8N_WEBHOOK_HEADER_VALUE", "").strip()
    headers = {header_name: header_value} if header_name and header_value else {}
    form = {
        "ticket_id": ticket_id,
        "requester_email": ticket.email,
        "requester_name": ticket.name,
        "subject": ticket.subject,
        "text": ticket.message,
    }
    files = None
    if ticket.attachment_base64:
        attachment = base64.b64decode(ticket.attachment_base64, validate=True)
        files = {"data": (ticket.attachment_name or "attachment.pdf", attachment, "application/pdf")}
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(target, headers=headers, data=form, files=files)
    except httpx.RequestError as exc:
        raise HTTPException(502, "The n8n webhook could not accept the request.") from exc
    try:
        body = response.json()
    except ValueError:
        raise HTTPException(502, "The n8n webhook returned an unexpected response.")
    if not body.get("ok"):
        error = body.get("error", {})
        raise HTTPException(422, error.get("message") or "The ticket was rejected by the webhook.")
    return {"ok": True, "ticket_id": ticket_id, "mode": "live", "message": "Ticket submitted to the live NOAVIA webhook.", "webhook_response": body}


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
        if not attachment.startswith(b"%PDF-"):
            raise HTTPException(422, "Attachment does not contain a valid PDF header.")
    if test_mode():
        return demo_result()
    public_target = public_webhook_target()
    if public_target:
        return await submit_to_public_webhook(ticket, public_target)
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


async def update_knowledge_base(upload: KnowledgeBaseUpload) -> dict:
    name = upload.name.strip()
    if name != Path(name).name:
        raise HTTPException(422, "Knowledge-base file names cannot contain a path.")
    if not name.lower().endswith((".md", ".markdown", ".txt")):
        raise HTTPException(422, "Knowledge-base files must be .md, .markdown, or .txt.")
    try:
        content = base64.b64decode(upload.content_base64, validate=True)
    except ValueError as exc:
        raise HTTPException(422, "Knowledge-base file could not be decoded.") from exc
    if not content or len(content) > MAX_KB_FILE_BYTES:
        raise HTTPException(422, "Knowledge-base files must be between 1 byte and 5 MB.")
    if test_mode():
        return {"ok": True, "mode": "test", "message": "Knowledge-base upload validated locally; no external service was contacted.", "source": name, "collection": upload.collection}
    target = document_manager_target()
    if target:
        return await call_document_manager(
            target,
            {"action": "upsert", "collection": upload.collection, "source": name, "content_base64": upload.content_base64},
            timeout=75,
        )
    # Backward-compatible ticket-only path. It is intentionally unavailable
    # for public/admin documents because those must not leak into ticket RAG.
    if upload.collection != "ticket":
        raise HTTPException(503, "Document management is not configured for this knowledge area yet.")
    target = public_kb_update_target()
    if not target:
        raise HTTPException(503, "Knowledge-base updates are disabled until the n8n update webhook is configured.")
    header_name = os.getenv("NOAVIA_N8N_WEBHOOK_HEADER_NAME", "").strip()
    header_value = os.getenv("NOAVIA_N8N_WEBHOOK_HEADER_VALUE", "").strip()
    headers = {header_name: header_value} if header_name and header_value else {}
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(target, headers=headers, files={"data": (name, content, "text/plain")})
    except httpx.RequestError as exc:
        raise HTTPException(502, "The n8n knowledge-base webhook could not accept the upload.") from exc
    try:
        body = response.json()
    except ValueError as exc:
        raise HTTPException(502, "The n8n knowledge-base webhook returned an unexpected response.") from exc
    if not response.is_success or not body.get("ok"):
        message = body.get("error", {}).get("message", "Knowledge-base update was rejected.")
        raise HTTPException(422, message)
    return {"ok": True, "mode": "live", "message": "Knowledge-base update sent to n8n for indexing.", "webhook_response": body}


async def call_document_manager(target: str, payload: dict, timeout: int = 45) -> dict:
    """Call the private n8n document manager without exposing its secret."""
    header_name = os.getenv("NOAVIA_N8N_WEBHOOK_HEADER_NAME", "").strip()
    header_value = os.getenv("NOAVIA_N8N_WEBHOOK_HEADER_VALUE", "").strip()
    headers = {header_name: header_value} if header_name and header_value else {}
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(target, headers=headers, json=payload)
        body = response.json()
    except (httpx.RequestError, ValueError) as exc:
        raise HTTPException(502, "The document manager could not process that request.") from exc
    if not response.is_success or not isinstance(body, dict) or not body.get("ok"):
        message = body.get("error", {}).get("message") if isinstance(body, dict) else None
        raise HTTPException(502, message or "The document manager could not process that request.")
    return {"ok": True, "mode": "live", "message": body.get("message", "Document indexed and saved."), "data": body.get("data", {})}


@app.get("/")
def index() -> FileResponse:
    return FileResponse(ROOT / "static" / "index.html")


@app.get("/admin/login")
def administrator_login_page() -> FileResponse:
    return FileResponse(ROOT / "static" / "admin-login.html")


@app.get("/admin/knowledge-base")
def knowledge_base_page() -> FileResponse:
    return FileResponse(ROOT / "static" / "knowledge-base.html")


@app.get("/chat")
def public_chat_page() -> FileResponse:
    return FileResponse(ROOT / "static" / "chat.html")


@app.get("/admin/assistant")
def admin_assistant_page() -> FileResponse:
    return FileResponse(ROOT / "static" / "admin-assistant.html")


@app.get("/api/mode")
def mode() -> dict:
    if test_mode():
        return {"mode": "test"}
    if public_webhook_target():
        return {"mode": "live"}
    return {"mode": "controlled-live"}


@app.get("/api/knowledge-base/mode")
def knowledge_base_mode() -> dict:
    return {"mode": "test" if test_mode() else ("live" if (document_manager_target() or public_kb_update_target()) else "disabled")}


@app.get("/api/knowledge-base/session")
def knowledge_base_session(request: Request) -> dict:
    """Small, non-sensitive session probe used to guard the admin page UI."""
    return {
        "authenticated": test_mode() or bool(request.session.get("google_admin_email")) or has_kb_admin_session(request),
        "mode": "test" if test_mode() else ("live" if (document_manager_target() or public_kb_update_target()) else "disabled"),
    }


@app.get("/api/auth/google/login")
async def google_login(request: Request):
    """Start OAuth with Google; the final authorization remains server-side."""
    if test_mode():
        return JSONResponse({"ok": True, "mode": "test"})
    client = google_oauth_client().create_client("google")
    redirect_uri = os.getenv("NOAVIA_GOOGLE_REDIRECT_URI", "").strip() or str(request.url_for("google_callback"))
    return await client.authorize_redirect(request, redirect_uri)


@app.get("/api/auth/google/callback", name="google_callback")
async def google_callback(request: Request):
    client = google_oauth_client().create_client("google")
    token = await client.authorize_access_token(request)
    userinfo = token.get("userinfo") or await client.userinfo(token=token)
    email = str(userinfo.get("email", "")).strip().lower()
    if not userinfo.get("email_verified") or email not in google_admin_emails():
        request.session.clear()
        raise HTTPException(403, "This Google account is not authorized for NOAVIA administration.")
    request.session["google_admin_email"] = email
    return JSONResponse({"ok": True, "redirect": "/admin/knowledge-base"}, status_code=302, headers={"Location": "/admin/knowledge-base"})


@app.post("/api/knowledge-base/login")
def knowledge_base_login(credentials: KnowledgeBaseLogin) -> JSONResponse:
    if test_mode():
        return JSONResponse({"ok": True, "mode": "test"})
    username = os.getenv("NOAVIA_KB_ADMIN_USERNAME", "")
    password = os.getenv("NOAVIA_KB_ADMIN_PASSWORD", "")
    if not username or not password or not (
        secrets.compare_digest(credentials.username, username)
        and secrets.compare_digest(credentials.password, password)
    ):
        raise HTTPException(401, "Invalid administrator credentials.")
    session = secrets.token_urlsafe(32)
    _kb_sessions[session] = time.monotonic() + KB_SESSION_SECONDS
    response = JSONResponse({"ok": True, "message": "Administrator sign-in successful."})
    response.set_cookie("noavia_kb_session", session, max_age=KB_SESSION_SECONDS, httponly=True, samesite="strict", secure=True)
    return response


@app.post("/api/knowledge-base/logout")
def knowledge_base_logout(request: Request) -> JSONResponse:
    _kb_sessions.pop(request.cookies.get("noavia_kb_session", ""), None)
    request.session.clear()
    response = JSONResponse({"ok": True})
    response.delete_cookie("noavia_kb_session")
    return response


@app.post("/api/tickets")
async def create_ticket(ticket: Ticket) -> dict:
    try:
        ticket = ticket.model_copy(update={"name": ticket.name.strip(), "email": ticket.email.strip(),
                                           "subject": ticket.subject.strip(), "message": ticket.message.strip()})
    except Exception as exc:
        raise HTTPException(422, "Name, email, subject, and message are required.") from exc
    return await submit(ticket)


@app.post("/api/chat")
async def public_chat(question: PublicChatQuestion, request: Request) -> dict:
    """Forward public questions to the dedicated public-only RAG workflow."""
    message = question.message.strip()
    if not message:
        raise HTTPException(422, "Enter a question.")
    if test_mode():
        return {"ok": True, "mode": "test", "answer": "Demo mode: connect the public chat workflow to answer from approved company sources.", "sources": []}
    target = public_chat_target()
    if not target:
        raise HTTPException(503, "The public chatbot is not configured yet.")
    client_id = request.client.host if request.client else "unknown"
    now = time.monotonic()
    recent = _chat_attempts[client_id]
    while recent and recent[0] <= now - CHAT_RATE_WINDOW_SECONDS:
        recent.popleft()
    if len(recent) >= CHAT_RATE_MAX_REQUESTS:
        raise HTTPException(429, "Too many chatbot requests. Try again later.")
    recent.append(now)
    header_name = os.getenv("NOAVIA_N8N_PUBLIC_CHAT_HEADER_NAME", "").strip()
    header_value = os.getenv("NOAVIA_N8N_PUBLIC_CHAT_HEADER_VALUE", "").strip()
    headers = {header_name: header_value} if header_name and header_value else {}
    try:
        async with httpx.AsyncClient(timeout=45) as client:
            response = await client.post(target, headers=headers, json={"message": message})
        body = response.json()
    except (httpx.RequestError, ValueError) as exc:
        raise HTTPException(502, "The public chatbot could not process the question.") from exc
    answer = body.get("answer")
    sources = body.get("sources")
    if not response.is_success or not body.get("ok") or not isinstance(answer, str) or not answer.strip() or not isinstance(sources, list):
        raise HTTPException(502, "The public chatbot could not process the question.")
    return {"ok": True, "mode": "live", "answer": answer.strip(), "sources": sources[:3]}


@app.post("/api/admin/assistant")
async def admin_assistant(question: PublicChatQuestion, request: Request, x_noavia_kb_admin_token: str | None = Header(default=None)) -> dict:
    require_kb_admin(request, x_noavia_kb_admin_token, rate_limit=False)
    message = question.message.strip()
    if not message:
        raise HTTPException(422, "Enter a question.")
    if test_mode():
        return {"ok": True, "mode": "test", "answer": "Demo mode: the private assistant will answer from the admin knowledge base.", "sources": []}
    target = admin_chat_target()
    if not target:
        raise HTTPException(503, "The private admin assistant is not configured yet.")
    headers = {os.getenv("NOAVIA_N8N_ADMIN_CHAT_HEADER_NAME", "").strip(): os.getenv("NOAVIA_N8N_ADMIN_CHAT_HEADER_VALUE", "").strip()}
    headers = {key: value for key, value in headers.items() if key and value}
    try:
        async with httpx.AsyncClient(timeout=45) as client:
            response = await client.post(target, headers=headers, json={"message": message})
        body = response.json()
    except (httpx.RequestError, ValueError) as exc:
        raise HTTPException(502, "The private admin assistant could not process that question.") from exc
    if not response.is_success or not body.get("ok") or not isinstance(body.get("answer"), str) or not isinstance(body.get("sources"), list):
        raise HTTPException(502, "The private admin assistant could not process that question.")
    return {"ok": True, "mode": "live", "answer": body["answer"].strip(), "sources": body["sources"][:3]}


@app.post("/api/knowledge-base")
async def create_knowledge_base_update(
    upload: KnowledgeBaseUpload,
    request: Request,
    x_noavia_kb_admin_token: str | None = Header(default=None),
) -> dict:
    require_kb_admin(request, x_noavia_kb_admin_token)
    # The public webhook credential lives only in this server. Serializing by
    # normalized source prevents two replacement workflows for one document
    # from racing during version cleanup.
    source_key = upload.name.strip().lower()
    lock = _kb_source_locks.setdefault(source_key, asyncio.Lock())
    async with lock:
        return await update_knowledge_base(upload)


@app.post("/api/knowledge-base/library")
async def knowledge_library(
    action: KnowledgeLibraryAction,
    request: Request,
    x_noavia_kb_admin_token: str | None = Header(default=None),
) -> dict:
    """Admin-only document lifecycle proxy; n8n owns persistent source storage."""
    require_kb_admin(request, x_noavia_kb_admin_token, rate_limit=action.action == "delete")
    source = (action.source or "").strip()
    if action.action != "list" and (not source or source != Path(source).name):
        raise HTTPException(422, "A safe document filename is required.")
    if test_mode():
        return {"ok": True, "mode": "test", "data": {"collection": action.collection, "action": action.action, "documents": []}}
    target = document_manager_target() if action.action == "delete" else (source_library_target() or knowledge_library_target())
    if not target:
        raise HTTPException(503, "Knowledge-base document management is not configured yet.")
    result = await call_document_manager(
        target, {"collection": action.collection, "action": action.action, "source": source}
    )
    return {"ok": True, "mode": result["mode"], "data": result["data"]}
