from pathlib import Path
import sys

from fastapi.testclient import TestClient
import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import app


client = TestClient(app)


def test_test_mode_accepts_dummy_ticket_without_network(monkeypatch):
    monkeypatch.setenv("NOAVIA_TEST_MODE", "true")
    response = client.post("/api/tickets", json={"name": "Ada", "email": "ada@example.com", "subject": "Help", "message": "Test ticket"})
    assert response.status_code == 200
    assert response.json()["mode"] == "test"


def test_invalid_email_and_non_pdf_are_rejected():
    invalid = client.post("/api/tickets", json={"name": "Ada", "email": "not-email", "subject": "Help", "message": "Test"})
    attachment = client.post("/api/tickets", json={"name": "Ada", "email": "ada@example.com", "subject": "Help", "message": "Test", "attachment_name": "x.txt", "attachment_type": "text/plain", "attachment_base64": "eA=="})
    assert invalid.status_code == attachment.status_code == 422


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
