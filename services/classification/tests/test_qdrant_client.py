"""Offline Qdrant credential forwarding regression tests."""
from __future__ import annotations

from app.clients import qdrant_client


def test_unauthenticated_qdrant_client_omits_api_key(monkeypatch):
    received: dict[str, object] = {}

    def fake_client(**kwargs):
        received.update(kwargs)
        return object()

    qdrant_client._cached_client.cache_clear()
    monkeypatch.setattr(qdrant_client, "AsyncQdrantClient", fake_client)

    qdrant_client._cached_client("http://qdrant:6333", None, 12.5)

    assert received == {"url": "http://qdrant:6333", "timeout": 12.5}


def test_authenticated_qdrant_client_attaches_api_key(monkeypatch):
    received: dict[str, object] = {}

    def fake_client(**kwargs):
        received.update(kwargs)
        return object()

    qdrant_client._cached_client.cache_clear()
    monkeypatch.setattr(qdrant_client, "AsyncQdrantClient", fake_client)

    qdrant_client._cached_client("http://qdrant:6333", "scoped-token", 12.5)

    assert received == {
        "url": "http://qdrant:6333",
        "timeout": 12.5,
        "api_key": "scoped-token",
    }
