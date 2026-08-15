import typing

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


def test_authorization_annotation_resolves_to_optional_string():
    """Lock down the readiness-audit contract: the authorization parameter
    must be typed as a string-or-None union so the FastAPI Header(default=None)
    dependency signature matches the verification helper. Anything else
    (plain str, plain None, or a non-string type) would let FastAPI reject the
    missing-header case as a 422 instead of routing it through the auth path
    we test above."""
    hints = typing.get_type_hints(verify_bearer_token)
    assert hints["authorization"] == str | None


def test_empty_string_authorization_raises_auth_error():
    """An empty Authorization header (`""`) is not the same as a missing one
    but must produce the same AUTH_ERROR result: the audit contract is
    'no usable bearer token', regardless of how the absence is expressed."""
    with pytest.raises(ModuleError) as exc_info:
        verify_bearer_token("", "secret", interface_id="auth")
    assert exc_info.value.code == ErrorCode.AUTH_ERROR
    assert exc_info.value.http_status == 401
