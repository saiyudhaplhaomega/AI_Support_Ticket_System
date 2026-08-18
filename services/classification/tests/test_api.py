import openai
from app.clients.chat_errors import ChatTimeoutError
import pytest
from fastapi.testclient import TestClient
from qdrant_client.http.exceptions import ApiException

from app import main as main_module
from app.schemas import _ModelClassification
from tests.fakes import FakeMiniMax, FakeOpenAI, FakeQdrant, fake_point

AUTH = {"Authorization": "Bearer test-bearer-key"}


@pytest.fixture()
def client():
    return TestClient(main_module.app)


def test_healthz_no_auth_required(client):
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_classify_requires_auth(client):
    resp = client.post("/ai/classify-ticket/v1", json={"text": "hello"})
    assert resp.status_code == 401
    body = resp.json()
    assert body["ok"] is False
    assert body["error"]["code"] == "AUTH_ERROR"


def test_classify_rejects_blank_text(client, monkeypatch):
    monkeypatch.setattr(main_module, "get_openai_client", lambda cfg: FakeOpenAI())
    resp = client.post("/ai/classify-ticket/v1", json={"text": "   "}, headers=AUTH)
    assert resp.status_code == 200  # validation errors are envelope, not HTTP throw
    body = resp.json()
    assert body["ok"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["interface_id"] == "ai.classify-ticket"


def test_validation_error_never_exposes_ticket_pii_in_body_or_logs(client, caplog):
    pii = "SSN-123-45-6789"
    with caplog.at_level("WARNING"):
        resp = client.post("/ai/classify-ticket/v1", json={"text": {"ticket": pii}}, headers=AUTH)

    assert resp.status_code == 200
    assert resp.json()["error"]["message"] == "Request validation failed."
    assert pii not in resp.text
    assert pii not in caplog.text
    record = next(record for record in caplog.records if record.getMessage() == "request validation failed")
    assert record.extra_fields["validation_errors"] == [{"field": "text", "code": "string_type"}]


def test_classify_success(client, monkeypatch):
    parsed = _ModelClassification(category="billing", urgency="medium", sentiment="negative", confidence=0.87, summary="Duplicate charge reported.", tags=["duplicate_charge", "refund"])
    monkeypatch.setattr(main_module, "get_chat_client", lambda cfg: FakeMiniMax(parsed=parsed.model_dump()))

    resp = client.post(
        "/ai/classify-ticket/v1",
        json={"text": "I was charged twice for my subscription"},
        headers=AUTH,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["data"]["category"] == "billing"
    assert body["data"]["confidence"] == 0.87
    assert body["data"]["tags"] == ["duplicate_charge", "refund"]
    assert body["data"]["urgency"] == "medium"
    assert body["data"]["sentiment"] == "negative"
    assert body["data"]["summary"] == "Duplicate charge reported."
    assert body["data"]["raw_model_output"]["model"] == "MiniMax-M3"
    assert "X-Correlation-Id" in resp.headers


def test_classify_invoice_verification_when_requested(client, monkeypatch):
    parsed = _ModelClassification(
        category="billing", urgency="medium", sentiment="neutral", confidence=0.9,
        summary="Invoice attached.", attachment_is_invoice=True, attachment_invoice_confidence=0.95,
    )
    fake = FakeMiniMax(parsed=parsed.model_dump())
    monkeypatch.setattr(main_module, "get_chat_client", lambda cfg: fake)

    resp = client.post(
        "/ai/classify-ticket/v1",
        json={"text": "Please see attached.\n\nPDF attachment:\nInvoice #1002 Total Due: $49.99", "context": {"verify_attachment_is_invoice": True}},
        headers=AUTH,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["attachment_is_invoice"] is True
    assert body["data"]["attachment_invoice_confidence"] == 0.95
    assert "attachment_is_invoice" in fake.calls[0]["messages"][0]["content"]


def test_classify_invoice_fields_absent_when_not_requested(client, monkeypatch):
    parsed = _ModelClassification(category="billing", urgency="medium", sentiment="neutral", confidence=0.9, summary="No attachment.")
    monkeypatch.setattr(main_module, "get_chat_client", lambda cfg: FakeMiniMax(parsed=parsed.model_dump()))

    resp = client.post("/ai/classify-ticket/v1", json={"text": "Just a question, no attachment."}, headers=AUTH)
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["attachment_is_invoice"] is None
    assert body["data"]["attachment_invoice_confidence"] is None


def test_classify_correlation_id_echoed(client, monkeypatch):
    parsed = _ModelClassification(category="technical", urgency="medium", sentiment="negative", confidence=0.5, summary="Login crash reported.")
    monkeypatch.setattr(main_module, "get_chat_client", lambda cfg: FakeMiniMax(parsed=parsed.model_dump()))
    resp = client.post(
        "/ai/classify-ticket/v1",
        json={"text": "app crashes on login"},
        headers={**AUTH, "X-Correlation-Id": "corr-fixed-1"},
    )
    assert resp.headers["X-Correlation-Id"] == "corr-fixed-1"


def test_classify_upstream_timeout_maps_to_envelope(client, monkeypatch):
    timeout_exc = ChatTimeoutError()
    monkeypatch.setattr(main_module, "get_chat_client", lambda cfg: FakeMiniMax(raise_exc=timeout_exc))
    resp = client.post("/ai/classify-ticket/v1", json={"text": "hello there"}, headers=AUTH)
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is False
    assert body["error"]["code"] == "UPSTREAM_TIMEOUT"


def test_rag_lookup_success(client, monkeypatch):
    monkeypatch.setattr(main_module, "get_openai_client", lambda cfg: FakeOpenAI(vector=[0.1, 0.2]))
    points = [fake_point("p1", 0.92, {"content": "Reset your password via Settings.", "source": "kb"})]
    monkeypatch.setattr(main_module, "get_qdrant_client", lambda cfg: FakeQdrant(points=points))

    resp = client.post("/ai/rag-lookup/v1", json={"query": "how do I reset my password"}, headers=AUTH)
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert len(body["data"]["matches"]) == 1
    match = body["data"]["matches"][0]
    assert match["id"] == "p1"
    assert match["score"] == 0.92
    assert match["content"] == "Reset your password via Settings."
    assert match["metadata"] == {"source": "kb"}


def test_rag_lookup_unknown_collection_returns_empty_matches(client, monkeypatch):
    monkeypatch.setattr(main_module, "get_openai_client", lambda cfg: FakeOpenAI())
    monkeypatch.setattr(main_module, "get_qdrant_client", lambda cfg: FakeQdrant(collection_exists=False))

    resp = client.post("/ai/rag-lookup/v1", json={"query": "anything"}, headers=AUTH)
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["data"]["matches"] == []


def test_rag_upstream_error_never_exposes_provider_details_in_body_or_logs(client, monkeypatch, caplog):
    secret = "provider-secret-should-not-leak"
    # ApiException's constructor doesn't accept status/reason kwargs (they're
    # set as plain attributes by the qdrant-client transport layer); assign
    # them after construction so the app code's `getattr(exc, "status", ...)`
    # still works without the secret ever landing in str(exc).
    upstream_exc = ApiException("upstream error")
    upstream_exc.status = 502
    upstream_exc.reason = secret
    monkeypatch.setattr(main_module, "get_openai_client", lambda cfg: FakeOpenAI())
    monkeypatch.setattr(
        main_module,
        "get_qdrant_client",
        lambda cfg: FakeQdrant(query_exc=upstream_exc),
    )

    with caplog.at_level("ERROR"):
        resp = client.post("/ai/rag-lookup/v1", json={"query": "reset password"}, headers=AUTH)

    assert resp.status_code == 200
    body = resp.json()
    assert body["error"]["code"] == "UPSTREAM_ERROR"
    assert body["error"]["message"] == "Vector store query failed."
    assert secret not in resp.text
    assert secret not in caplog.text
    record = next(record for record in caplog.records if record.getMessage() == "vector store query failed")
    assert record.extra_fields["upstream_status"] == 502


def test_rag_lookup_bad_filter_is_validation_error(client, monkeypatch):
    monkeypatch.setattr(main_module, "get_openai_client", lambda cfg: FakeOpenAI())
    monkeypatch.setattr(main_module, "get_qdrant_client", lambda cfg: FakeQdrant())

    resp = client.post(
        "/ai/rag-lookup/v1",
        json={"query": "anything", "filter": {"not_a_real_filter_key": 1}},
        headers=AUTH,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_ingest_success(client, monkeypatch):
    monkeypatch.setattr(main_module, "get_openai_client", lambda cfg: FakeOpenAI(vector=[0.1, 0.2, 0.3]))
    fake_qdrant = FakeQdrant(collection_exists=False)
    monkeypatch.setattr(main_module, "get_qdrant_client", lambda cfg: fake_qdrant)

    resp = client.post(
        "/internal/ingest/v1",
        json={"collection": "kb_documents", "records": [{"content": "doc one"}, {"content": "doc two"}]},
        headers=AUTH,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["data"] == {"collection": "kb_documents", "ingested": 2}
    assert len(fake_qdrant.upserted) == 1
    assert len(fake_qdrant.upserted[0]["points"]) == 2


def test_ingest_upstream_error_never_exposes_provider_details(client, monkeypatch, caplog):
    secret = "provider-secret-should-not-leak"
    upstream_exc = ApiException(secret)
    monkeypatch.setattr(main_module, "get_openai_client", lambda cfg: FakeOpenAI())
    monkeypatch.setattr(
        main_module,
        "get_qdrant_client",
        lambda cfg: FakeQdrant(collection_exists=False, upsert_exc=upstream_exc),
    )

    with caplog.at_level("ERROR"):
        resp = client.post(
            "/internal/ingest/v1",
            json={"records": [{"content": "document"}]},
            headers=AUTH,
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["error"]["code"] == "UPSTREAM_ERROR"
    assert body["error"]["message"] == "Vector store upsert failed."
    assert secret not in resp.text
    assert secret not in caplog.text
