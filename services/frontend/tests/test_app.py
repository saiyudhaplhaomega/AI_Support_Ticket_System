from pathlib import Path
import sys
import asyncio

from fastapi.testclient import TestClient
import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app as frontend_module
from app import app


client = TestClient(app)


def test_test_mode_accepts_dummy_ticket_without_network(monkeypatch):
    monkeypatch.setenv("NOAVIA_TEST_MODE", "true")
    class NetworkMustNotRun:
        def __init__(self, *args, **kwargs):
            raise AssertionError("test mode must not create an HTTP client")

    monkeypatch.setattr("app.httpx.AsyncClient", NetworkMustNotRun)
    response = client.post("/api/tickets", json={"name": "Ada", "email": "ada@example.com", "subject": "Help", "message": "Test ticket"})
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "test"
    assert body["ticket_id"] == "DEMO-0001"
    assert body["demo"]["classification"]["category"] == "account_access"
    assert len(body["demo"]["rag"]["sources"]) == 3
    assert body["demo"]["rag"]["sources"][0]["retrieval_score"] == 0.93
    assert body["demo"]["rag"]["fallback"]["used"] is False
    assert body["demo"]["routing"]["queue"] == "account-support"
    assert body["demo"]["manual_review"]["required"] is False
    assert body["demo"]["processing_log"][-1]["status"] == "skipped"
    assert body["demo"]["internal_draft_reply"]["visibility"] == "internal_draft_only"


def test_invalid_email_and_non_pdf_are_rejected():
    invalid = client.post("/api/tickets", json={"name": "Ada", "email": "not-email", "subject": "Help", "message": "Test"})
    attachment = client.post("/api/tickets", json={"name": "Ada", "email": "ada@example.com", "subject": "Help", "message": "Test", "attachment_name": "x.txt", "attachment_type": "text/plain", "attachment_base64": "eA=="})
    assert invalid.status_code == attachment.status_code == 422


def test_ticket_rejects_a_pdf_mime_spoof_without_pdf_magic_bytes():
    response = client.post(
        "/api/tickets",
        json={"name": "Ada", "email": "ada@example.com", "subject": "Help", "message": "Test",
              "attachment_name": "not-a-pdf.pdf", "attachment_type": "application/pdf", "attachment_base64": "bm90IGEgcGRm"},
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "Attachment does not contain a valid PDF header."


def test_controlled_live_target_must_match_approved_internal_origin(monkeypatch):
    monkeypatch.setenv("NOAVIA_TEST_MODE", "false")
    monkeypatch.setenv("NOAVIA_N8N_INTERNAL_ALLOWED_ORIGIN", "http://n8n:5678")
    monkeypatch.setenv("NOAVIA_N8N_INTERNAL_WEBHOOK_URL", "https://example.invalid/webhook")
    response = client.post("/api/tickets", json={"name": "Ada", "email": "ada@example.com", "subject": "Help", "message": "Test"})
    assert response.status_code == 503
    assert "approved internal" in response.json()["detail"]

    monkeypatch.setenv("NOAVIA_N8N_INTERNAL_WEBHOOK_URL", "http://127.0.0.1:5678/webhook/test")
    response = client.post("/api/tickets", json={"name": "Ada", "email": "ada@example.com", "subject": "Help", "message": "Test"})
    assert response.status_code == 503


def test_controlled_live_request_error_is_sanitized(monkeypatch):
    monkeypatch.setenv("NOAVIA_TEST_MODE", "false")
    monkeypatch.setenv("NOAVIA_N8N_INTERNAL_ALLOWED_ORIGIN", "http://n8n:5678")
    monkeypatch.setenv("NOAVIA_N8N_INTERNAL_WEBHOOK_URL", "http://n8n:5678/webhook/test")

    class FailingClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, *args, **kwargs):
            request = httpx.Request("POST", "http://n8n:5678/webhook/test")
            raise httpx.ConnectError("connection refused", request=request)

    monkeypatch.setattr("app.httpx.AsyncClient", lambda **kwargs: FailingClient())
    response = client.post("/api/tickets", json={"name": "Ada", "email": "ada@example.com", "subject": "Help", "message": "Test"})
    assert response.status_code == 502
    assert response.json()["detail"] == "The private ticket service could not accept the request."


class _RecordingClient:
    """Captures the request public-webhook mode sends, for assertions."""

    last_call: dict | None = None

    def __init__(self, response_json: dict, status_code: int = 200):
        self._response_json = response_json
        self._status_code = status_code

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, headers=None, data=None, files=None, json=None):
        _RecordingClient.last_call = {"url": url, "headers": headers, "data": data, "files": files, "json": json}
        request = httpx.Request("POST", url)
        return httpx.Response(self._status_code, json=self._response_json, request=request)


def test_public_webhook_mode_reports_live(monkeypatch):
    monkeypatch.setenv("NOAVIA_TEST_MODE", "false")
    monkeypatch.setenv("NOAVIA_N8N_PUBLIC_WEBHOOK_URL", "https://n8n.example.com/webhook/noavia/tickets/v1")
    assert client.get("/api/mode").json() == {"mode": "live"}


def test_public_webhook_success_forwards_multipart_with_header_auth(monkeypatch):
    monkeypatch.setenv("NOAVIA_TEST_MODE", "false")
    monkeypatch.setenv("NOAVIA_N8N_PUBLIC_WEBHOOK_URL", "https://n8n.example.com/webhook/noavia/tickets/v1")
    monkeypatch.setenv("NOAVIA_N8N_WEBHOOK_HEADER_NAME", "X-NOAVIA-Webhook-Secret")
    monkeypatch.setenv("NOAVIA_N8N_WEBHOOK_HEADER_VALUE", "test-secret")
    _RecordingClient.last_call = None
    monkeypatch.setattr(
        "app.httpx.AsyncClient",
        lambda **kwargs: _RecordingClient({"ok": True, "data": {"ticket_id": "TEST-1", "status": "routed"}, "correlation_id": "corr-1"}),
    )

    response = client.post("/api/tickets", json={"name": "Ada", "email": "ada@example.com", "subject": "Help", "message": "Test"})

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "live"
    assert body["webhook_response"]["data"]["ticket_id"] == "TEST-1"
    call = _RecordingClient.last_call
    assert call["url"] == "https://n8n.example.com/webhook/noavia/tickets/v1"
    assert call["headers"] == {"X-NOAVIA-Webhook-Secret": "test-secret"}
    assert call["data"]["requester_email"] == "ada@example.com"
    assert call["files"] is None


def test_public_webhook_forwards_pdf_as_multipart_file(monkeypatch):
    monkeypatch.setenv("NOAVIA_TEST_MODE", "false")
    monkeypatch.setenv("NOAVIA_N8N_PUBLIC_WEBHOOK_URL", "https://n8n.example.com/webhook/noavia/tickets/v1")
    _RecordingClient.last_call = None
    monkeypatch.setattr(
        "app.httpx.AsyncClient",
        lambda **kwargs: _RecordingClient({"ok": True, "data": {"ticket_id": "TEST-2", "status": "routed"}, "correlation_id": "corr-2"}),
    )

    response = client.post(
        "/api/tickets",
        json={
            "name": "Ada", "email": "ada@example.com", "subject": "Help", "message": "Test",
            "attachment_name": "invoice.pdf", "attachment_type": "application/pdf",
            "attachment_base64": "JVBERi0xLjQK",
        },
    )

    assert response.status_code == 200
    call = _RecordingClient.last_call
    assert call["files"]["data"][0] == "invoice.pdf"
    assert call["files"]["data"][2] == "application/pdf"


def test_public_webhook_rejection_is_surfaced_as_422(monkeypatch):
    monkeypatch.setenv("NOAVIA_TEST_MODE", "false")
    monkeypatch.setenv("NOAVIA_N8N_PUBLIC_WEBHOOK_URL", "https://n8n.example.com/webhook/noavia/tickets/v1")
    monkeypatch.setattr(
        "app.httpx.AsyncClient",
        lambda **kwargs: _RecordingClient(
            {"ok": False, "error": {"code": "VALIDATION_ERROR", "message": "Ticket validation failed"}, "correlation_id": "corr-3"}
        ),
    )

    response = client.post("/api/tickets", json={"name": "Ada", "email": "ada@example.com", "subject": "Help", "message": "Test"})

    assert response.status_code == 422
    assert response.json()["detail"] == "Ticket validation failed"


def test_kb_update_is_local_only_in_test_mode(monkeypatch):
    monkeypatch.setenv("NOAVIA_TEST_MODE", "true")
    response = client.post("/api/knowledge-base", json={"name": "policy.md", "content_base64": "IyBQb2xpY3k="})
    assert response.status_code == 200
    assert response.json()["mode"] == "test"
    assert response.json()["collection"] == "ticket"
    assert client.get("/api/knowledge-base/mode").json() == {"mode": "test"}


def test_kb_update_rejects_non_text_file():
    response = client.post("/api/knowledge-base", json={"name": "invoice.pdf", "content_base64": "JVBERg=="})
    assert response.status_code == 422


def test_kb_update_forwards_a_text_file_to_its_own_webhook(monkeypatch):
    monkeypatch.setenv("NOAVIA_TEST_MODE", "false")
    monkeypatch.setenv("NOAVIA_N8N_KB_UPDATE_WEBHOOK_URL", "https://n8n.example.com/webhook/noavia/kb/update/v1")
    monkeypatch.setenv("NOAVIA_KB_ADMIN_TOKEN", "admin-test-token")
    monkeypatch.setenv("NOAVIA_N8N_WEBHOOK_HEADER_NAME", "X-NOAVIA-Webhook-Secret")
    monkeypatch.setenv("NOAVIA_N8N_WEBHOOK_HEADER_VALUE", "test-secret")
    _RecordingClient.last_call = None
    monkeypatch.setattr("app.httpx.AsyncClient", lambda **kwargs: _RecordingClient({"ok": True, "data": {"status": "indexed"}}))

    response = client.post("/api/knowledge-base", headers={"X-NOAVIA-KB-Admin-Token": "admin-test-token"}, json={"name": "policy.md", "content_base64": "IyBQb2xpY3k="})

    assert response.status_code == 200
    assert response.json()["mode"] == "live"
    call = _RecordingClient.last_call
    assert call["url"] == "https://n8n.example.com/webhook/noavia/kb/update/v1"
    assert call["headers"] == {"X-NOAVIA-Webhook-Secret": "test-secret"}
    assert call["files"]["data"][0] == "policy.md"


def test_document_manager_handles_an_isolated_public_source(monkeypatch):
    monkeypatch.setenv("NOAVIA_TEST_MODE", "false")
    monkeypatch.setenv("NOAVIA_N8N_DOCUMENT_MANAGER_WEBHOOK_URL", "https://n8n.example.com/webhook/noavia/documents/v1")
    monkeypatch.setenv("NOAVIA_KB_ADMIN_TOKEN", "admin-test-token")
    monkeypatch.setenv("NOAVIA_N8N_WEBHOOK_HEADER_NAME", "X-NOAVIA-Webhook-Secret")
    monkeypatch.setenv("NOAVIA_N8N_WEBHOOK_HEADER_VALUE", "test-secret")
    _RecordingClient.last_call = None
    monkeypatch.setattr("app.httpx.AsyncClient", lambda **kwargs: _RecordingClient({"ok": True, "message": "Document indexed.", "data": {"collection": "public"}}))

    response = client.post("/api/knowledge-base", headers={"X-NOAVIA-KB-Admin-Token": "admin-test-token"}, json={"name": "company.md", "collection": "public", "content_base64": "IyBDb21wYW55"})

    assert response.status_code == 200
    assert _RecordingClient.last_call["url"].endswith("/documents/v1")
    assert _RecordingClient.last_call["json"] == {"action": "upsert", "collection": "public", "source": "company.md", "content_base64": "IyBDb21wYW55"}


def test_document_manager_enables_live_administrator_mode(monkeypatch):
    monkeypatch.setenv("NOAVIA_TEST_MODE", "false")
    monkeypatch.setenv("NOAVIA_N8N_DOCUMENT_MANAGER_WEBHOOK_URL", "https://n8n.example.com/webhook/noavia/documents/v1")
    monkeypatch.delenv("NOAVIA_N8N_KB_UPDATE_WEBHOOK_URL", raising=False)
    assert client.get("/api/knowledge-base/mode").json() == {"mode": "live"}


def test_public_or_admin_upload_fails_closed_without_document_manager(monkeypatch):
    monkeypatch.setenv("NOAVIA_TEST_MODE", "false")
    monkeypatch.delenv("NOAVIA_N8N_DOCUMENT_MANAGER_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("NOAVIA_N8N_KB_UPDATE_WEBHOOK_URL", raising=False)
    monkeypatch.setenv("NOAVIA_KB_ADMIN_TOKEN", "admin-test-token")
    response = client.post("/api/knowledge-base", headers={"X-NOAVIA-KB-Admin-Token": "admin-test-token"}, json={"name": "private.md", "collection": "admin", "content_base64": "IyBQcml2YXRl"})
    assert response.status_code == 503


def test_live_kb_update_requires_a_separate_admin_token(monkeypatch):
    monkeypatch.setenv("NOAVIA_TEST_MODE", "false")
    monkeypatch.setenv("NOAVIA_N8N_KB_UPDATE_WEBHOOK_URL", "https://n8n.example.com/webhook/noavia/kb/update/v1")
    monkeypatch.setenv("NOAVIA_KB_ADMIN_TOKEN", "admin-test-token")
    response = client.post("/api/knowledge-base", json={"name": "policy.md", "content_base64": "IyBQb2xpY3k="})
    assert response.status_code == 401
    assert "administrator authentication" in response.json()["detail"]


def test_live_kb_update_fails_closed_when_admin_secret_is_not_configured(monkeypatch):
    monkeypatch.setenv("NOAVIA_TEST_MODE", "false")
    monkeypatch.setenv("NOAVIA_N8N_KB_UPDATE_WEBHOOK_URL", "https://n8n.example.com/webhook/noavia/kb/update/v1")
    monkeypatch.delenv("NOAVIA_KB_ADMIN_TOKEN", raising=False)
    response = client.post("/api/knowledge-base", headers={"X-NOAVIA-KB-Admin-Token": "anything"}, json={"name": "policy.md", "content_base64": "IyBQb2xpY3k="})
    assert response.status_code == 401


def test_live_kb_login_sets_an_http_only_session(monkeypatch):
    frontend_module._kb_sessions.clear()
    monkeypatch.setenv("NOAVIA_TEST_MODE", "false")
    monkeypatch.setenv("NOAVIA_KB_ADMIN_USERNAME", "admin")
    monkeypatch.setenv("NOAVIA_KB_ADMIN_PASSWORD", "password-for-test")
    denied = client.post("/api/knowledge-base/login", json={"username": "admin", "password": "wrong"})
    assert denied.status_code == 401
    response = client.post("/api/knowledge-base/login", json={"username": "admin", "password": "password-for-test"})
    assert response.status_code == 200
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "Secure" in response.headers["set-cookie"]


def test_admin_pages_are_separate_and_session_state_is_observable(monkeypatch):
    frontend_module._kb_sessions.clear()
    monkeypatch.setenv("NOAVIA_TEST_MODE", "false")
    monkeypatch.setenv("NOAVIA_KB_ADMIN_USERNAME", "admin")
    monkeypatch.setenv("NOAVIA_KB_ADMIN_PASSWORD", "password-for-test")
    https_client = TestClient(app, base_url="https://testserver")
    assert https_client.get("/").status_code == 200
    assert https_client.get("/admin/login").status_code == 200
    assert https_client.get("/admin/knowledge-base").status_code == 200
    assert https_client.get("/api/knowledge-base/session").json()["authenticated"] is False
    assert https_client.post("/api/knowledge-base/login", json={"username": "admin", "password": "password-for-test"}).status_code == 200
    assert https_client.get("/api/knowledge-base/session").json()["authenticated"] is True
    assert https_client.post("/api/knowledge-base/logout").status_code == 200
    assert https_client.get("/api/knowledge-base/session").json()["authenticated"] is False


def test_google_administrator_login_fails_closed_without_runtime_configuration(monkeypatch):
    monkeypatch.setenv("NOAVIA_TEST_MODE", "false")
    monkeypatch.delenv("GOOGLE_OAUTH_CLIENT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_OAUTH_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("NOAVIA_GOOGLE_ADMIN_EMAILS", raising=False)
    monkeypatch.delenv("NOAVIA_SESSION_SECRET", raising=False)
    response = client.get("/api/auth/google/login")
    assert response.status_code == 503
    assert response.json()["detail"] == "Google administrator sign-in is not configured."


def test_oauth_session_cookie_is_https_lax_and_one_hour():
    middleware = next(layer for layer in app.user_middleware if layer.cls.__name__ == "SessionMiddleware")
    assert middleware.kwargs["https_only"] is True
    assert middleware.kwargs["same_site"] == "lax"
    assert middleware.kwargs["max_age"] == frontend_module.KB_SESSION_SECONDS


def test_kb_upload_rejects_path_like_names():
    response = client.post("/api/knowledge-base", json={"name": "../policy.md", "content_base64": "IyBQb2xpY3k="})
    assert response.status_code == 422
    assert response.json()["detail"] == "Knowledge-base file names cannot contain a path."


def test_live_kb_update_rate_limit_is_enforced(monkeypatch):
    frontend_module._kb_attempts.clear()
    monkeypatch.setenv("NOAVIA_TEST_MODE", "false")
    monkeypatch.setenv("NOAVIA_N8N_KB_UPDATE_WEBHOOK_URL", "https://n8n.example.com/webhook/noavia/kb/update/v1")
    monkeypatch.setenv("NOAVIA_KB_ADMIN_TOKEN", "admin-test-token")
    monkeypatch.setattr(frontend_module, "KB_RATE_MAX_REQUESTS", 1)
    monkeypatch.setattr("app.httpx.AsyncClient", lambda **kwargs: _RecordingClient({"ok": True, "data": {"status": "indexed"}}))
    headers = {"X-NOAVIA-KB-Admin-Token": "admin-test-token"}
    payload = {"name": "policy.md", "content_base64": "IyBQb2xpY3k="}
    assert client.post("/api/knowledge-base", headers=headers, json=payload).status_code == 200
    assert client.post("/api/knowledge-base", headers=headers, json=payload).status_code == 429


def test_kb_updates_for_the_same_source_are_serialized(monkeypatch):
    frontend_module._kb_source_locks.clear()
    monkeypatch.setenv("NOAVIA_TEST_MODE", "true")
    running = 0
    max_running = 0

    async def delayed_update(_upload):
        nonlocal running, max_running
        running += 1
        max_running = max(max_running, running)
        await asyncio.sleep(0.01)
        running -= 1
        return {"ok": True}

    monkeypatch.setattr(frontend_module, "update_knowledge_base", delayed_update)

    async def exercise():
        from starlette.requests import Request
        request = Request({"type": "http", "client": ("127.0.0.1", 0), "headers": []})
        upload = frontend_module.KnowledgeBaseUpload(name="Policy.md", content_base64="eA==")
        await asyncio.gather(
            frontend_module.create_knowledge_base_update(upload, request, None),
            frontend_module.create_knowledge_base_update(upload, request, None),
        )

    asyncio.run(exercise())
    assert max_running == 1


def test_public_chat_is_separate_and_forwards_only_the_question(monkeypatch):
    monkeypatch.setenv("NOAVIA_TEST_MODE", "false")
    monkeypatch.setenv("NOAVIA_N8N_PUBLIC_CHAT_WEBHOOK_URL", "https://n8n.example.com/webhook/noavia/public-chat/v1")
    monkeypatch.setenv("NOAVIA_N8N_PUBLIC_CHAT_HEADER_NAME", "X-NOAVIA-Public-Chat-Secret")
    monkeypatch.setenv("NOAVIA_N8N_PUBLIC_CHAT_HEADER_VALUE", "public-test-secret")
    _RecordingClient.last_call = None
    monkeypatch.setattr("app.httpx.AsyncClient", lambda **kwargs: _RecordingClient({"ok": True, "answer": "Approved answer.", "sources": ["public.md"]}))
    response = client.post("/api/chat", json={"message": "What does NOAVIA do?"})
    assert response.status_code == 200
    assert response.json()["sources"] == ["public.md"]
    assert _RecordingClient.last_call["url"].endswith("/public-chat/v1")
    assert _RecordingClient.last_call["headers"] == {"X-NOAVIA-Public-Chat-Secret": "public-test-secret"}
    assert _RecordingClient.last_call["json"] == {"message": "What does NOAVIA do?"}


def test_document_library_is_admin_gated_and_uses_fixed_aliases(monkeypatch):
    monkeypatch.setenv("NOAVIA_TEST_MODE", "false")
    monkeypatch.setenv("NOAVIA_KB_ADMIN_TOKEN", "admin-test-token")
    monkeypatch.setenv("NOAVIA_N8N_KB_LIBRARY_WEBHOOK_URL", "https://n8n.example.com/webhook/noavia/kb/library/v1")
    monkeypatch.setattr("app.httpx.AsyncClient", lambda **kwargs: _RecordingClient({"ok": True, "data": {"documents": []}}))
    denied = client.post("/api/knowledge-base/library", json={"collection": "public", "action": "list"})
    assert denied.status_code == 401
    allowed = client.post("/api/knowledge-base/library", headers={"X-NOAVIA-KB-Admin-Token": "admin-test-token"}, json={"collection": "public", "action": "list"})
    assert allowed.status_code == 200
    assert _RecordingClient.last_call["json"] == {"collection": "public", "action": "list", "source": ""}
    rejected = client.post("/api/knowledge-base/library", headers={"X-NOAVIA-KB-Admin-Token": "admin-test-token"}, json={"collection": "noavia_kb_v1", "action": "list"})
    assert rejected.status_code == 422


def test_public_chat_rejects_whitespace_and_invalid_target(monkeypatch):
    monkeypatch.setenv("NOAVIA_TEST_MODE", "false")
    monkeypatch.setenv("NOAVIA_N8N_PUBLIC_CHAT_WEBHOOK_URL", "https://n8n.example.com/webhook/wrong")
    assert client.post("/api/chat", json={"message": "Question"}).status_code == 503
    monkeypatch.setenv("NOAVIA_N8N_PUBLIC_CHAT_WEBHOOK_URL", "https://n8n.example.com/webhook/noavia/public-chat/v1")
    assert client.post("/api/chat", json={"message": "   "}).status_code == 422


def test_private_admin_assistant_requires_administrator(monkeypatch):
    monkeypatch.setenv("NOAVIA_TEST_MODE", "false")
    monkeypatch.setenv("NOAVIA_KB_ADMIN_TOKEN", "admin-test-token")
    assert client.post("/api/admin/assistant", json={"message": "How does indexing work?"}).status_code == 401
    monkeypatch.setenv("NOAVIA_N8N_ADMIN_CHAT_WEBHOOK_URL", "https://n8n.example.com/webhook/noavia/admin-chat/v1")
    monkeypatch.setattr("app.httpx.AsyncClient", lambda **kwargs: _RecordingClient({"ok": True, "answer": "It is versioned.", "sources": ["admin-rules.md"]}))
    allowed = client.post("/api/admin/assistant", headers={"X-NOAVIA-KB-Admin-Token": "admin-test-token"}, json={"message": "How does indexing work?"})
    assert allowed.status_code == 200
    assert allowed.json()["sources"] == ["admin-rules.md"]
