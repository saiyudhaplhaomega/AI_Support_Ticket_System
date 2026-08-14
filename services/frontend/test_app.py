import importlib.util
from pathlib import Path
from fastapi.testclient import TestClient

_APP_PATH = Path(__file__).with_name("app.py")
_SPEC = importlib.util.spec_from_file_location("noavia_frontend_app", _APP_PATH)
assert _SPEC and _SPEC.loader
portal = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(portal)

client = TestClient(portal.app)

def test_form_and_validation_are_public_but_operational_values_are_not():
    page = client.get("/")
    assert page.status_code == 200
    assert "Test mode only" in page.text
    assert "NOAVIA_N8N_INTERNAL_URL" not in page.text
    bad = client.post("/api/tickets", json={"name":"", "email":"nope", "subject":"", "message":""})
    assert bad.status_code == 422

def test_pdf_must_be_pdf_before_private_forwarding():
    response = client.post("/api/tickets", data={"name":"A", "email":"a@example.com", "subject":"S", "message":"M"}, files={"attachment":("note.txt",b"x","text/plain")})
    assert response.status_code == 422

def test_test_mode_gate(monkeypatch):
    monkeypatch.setenv("NOAVIA_TEST_MODE", "false")
    response = client.post("/api/tickets", json={"name":"A", "email":"a@example.com", "subject":"S", "message":"M"})
    assert response.status_code == 503
