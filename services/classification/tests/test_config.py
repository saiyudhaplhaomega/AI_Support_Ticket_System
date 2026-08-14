"""Configuration contract tests for authenticated and unauthenticated Qdrant."""
from __future__ import annotations

import pytest

from app.config import ConfigError, load_settings


def test_unauthenticated_qdrant_allows_omitted_api_key(monkeypatch):
    monkeypatch.setenv("AI_QDRANT_AUTH_ENABLED", "false")
    monkeypatch.delenv("AI_QDRANT_API_KEY", raising=False)

    settings = load_settings()

    assert settings.qdrant_auth_enabled is False
    assert settings.qdrant_api_key is None


def test_authenticated_qdrant_uses_injected_api_key(monkeypatch):
    monkeypatch.setenv("AI_QDRANT_AUTH_ENABLED", "true")
    monkeypatch.setenv("AI_QDRANT_API_KEY", "collection-scoped-token")

    settings = load_settings()

    assert settings.qdrant_auth_enabled is True
    assert settings.qdrant_api_key == "collection-scoped-token"


def test_authenticated_qdrant_requires_api_key(monkeypatch):
    monkeypatch.setenv("AI_QDRANT_AUTH_ENABLED", "true")
    monkeypatch.delenv("AI_QDRANT_API_KEY", raising=False)

    with pytest.raises(ConfigError, match="AI_QDRANT_API_KEY"):
        load_settings()


def test_qdrant_auth_mode_rejects_invalid_boolean(monkeypatch):
    monkeypatch.setenv("AI_QDRANT_AUTH_ENABLED", "sometimes")

    with pytest.raises(ConfigError, match="AI_QDRANT_AUTH_ENABLED"):
        load_settings()
