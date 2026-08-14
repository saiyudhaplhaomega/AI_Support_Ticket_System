from pathlib import Path
import sys

from fastapi.testclient import TestClient

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
