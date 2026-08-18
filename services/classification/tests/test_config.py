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


def test_chat_provider_defaults_to_openai(monkeypatch):
    monkeypatch.delenv("AI_CHAT_PROVIDER", raising=False)
    monkeypatch.delenv("AI_CHAT_MODEL", raising=False)

    settings = load_settings()

    assert settings.chat_provider == "openai"
    assert settings.chat_model == "gpt-4o-mini"


def test_chat_provider_minimax_defaults_to_minimax_model(monkeypatch):
    monkeypatch.setenv("AI_CHAT_PROVIDER", "minimax")
    monkeypatch.delenv("AI_CHAT_MODEL", raising=False)

    settings = load_settings()

    assert settings.chat_provider == "minimax"
    assert settings.chat_model == "MiniMax-M3"


def test_chat_model_env_var_overrides_provider_default(monkeypatch):
    monkeypatch.setenv("AI_CHAT_PROVIDER", "openai")
    monkeypatch.setenv("AI_CHAT_MODEL", "gpt-4o")

    settings = load_settings()

    assert settings.chat_model == "gpt-4o"


def test_chat_provider_rejects_unknown_value(monkeypatch):
    monkeypatch.setenv("AI_CHAT_PROVIDER", "anthropic")

    with pytest.raises(ConfigError, match="AI_CHAT_PROVIDER"):
        load_settings()


def test_minimax_api_key_not_required_when_provider_is_openai(monkeypatch):
    monkeypatch.setenv("AI_CHAT_PROVIDER", "openai")
    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)

    settings = load_settings()

    assert settings.chat_provider == "openai"
    assert settings.minimax_api_key == ""


def test_minimax_api_key_required_when_provider_is_minimax(monkeypatch):
    monkeypatch.setenv("AI_CHAT_PROVIDER", "minimax")
    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)

    with pytest.raises(ConfigError, match="MINIMAX_API_KEY"):
        load_settings()
