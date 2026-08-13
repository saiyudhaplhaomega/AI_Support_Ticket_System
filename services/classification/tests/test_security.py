import pytest

from app.errors import ErrorCode, ModuleError
from app.security import verify_bearer_token


def test_missing_header_raises_auth_error():
    with pytest.raises(ModuleError) as exc_info:
        verify_bearer_token(None, "secret", interface_id="auth")
    assert exc_info.value.code == ErrorCode.AUTH_ERROR
    assert exc_info.value.http_status == 401


def test_malformed_header_raises_auth_error():
    with pytest.raises(ModuleError):
        verify_bearer_token("secret", "secret", interface_id="auth")  # missing "Bearer " prefix


def test_wrong_token_raises_auth_error():
    with pytest.raises(ModuleError):
        verify_bearer_token("Bearer wrong", "secret", interface_id="auth")


def test_correct_token_passes():
    verify_bearer_token("Bearer secret", "secret", interface_id="auth")  # should not raise
