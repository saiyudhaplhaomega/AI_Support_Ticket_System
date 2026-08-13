from app.errors import ErrorCode, ModuleError, error_envelope, success_envelope


def test_success_envelope_shape():
    env = success_envelope({"category": "billing"})
    assert env == {"ok": True, "data": {"category": "billing"}}


def test_error_envelope_shape():
    env = error_envelope(
        ErrorCode.VALIDATION_ERROR,
        "bad input",
        interface_id="ai.classify-ticket",
        version="v1",
        correlation_id="abc-123",
    )
    assert env["ok"] is False
    assert env["error"] == {
        "code": "VALIDATION_ERROR",
        "message": "bad input",
        "interface_id": "ai.classify-ticket",
        "version": "v1",
        "correlation_id": "abc-123",
    }


def test_module_error_defaults_to_200_except_auth():
    assert ModuleError(ErrorCode.UPSTREAM_TIMEOUT, "x", interface_id="i").http_status == 200
    assert ModuleError(ErrorCode.AUTH_ERROR, "x", interface_id="i", http_status=401).http_status == 401
