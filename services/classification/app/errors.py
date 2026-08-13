"""Shared error envelope — capability-module-architecture.md §5.

Every module in the company (regardless of family) uses this exact envelope
shape so a consumer only ever needs to branch on `ok`, never on
module-specific error formats.
"""
from __future__ import annotations

from enum import Enum
from typing import Any


class ErrorCode(str, Enum):
    VALIDATION_ERROR = "VALIDATION_ERROR"
    UPSTREAM_TIMEOUT = "UPSTREAM_TIMEOUT"
    UPSTREAM_ERROR = "UPSTREAM_ERROR"
    AUTH_ERROR = "AUTH_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class ModuleError(Exception):
    """Raised by service/route code; converted to the error envelope by the
    FastAPI exception handler registered in main.py. Never let a raw
    exception reach the client — this is the one blessed way to fail.
    """

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        *,
        interface_id: str,
        version: str = "v1",
        http_status: int = 200,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.interface_id = interface_id
        self.version = version
        # 200 by default: per the architecture doc, timeout/model failures
        # must come back as a *parseable envelope*, not an HTTP-level throw,
        # so the n8n caller can branch on `ok` without special-casing status
        # codes. AUTH_ERROR is the one exception — see README "HTTP status
        # codes" section for the rationale.
        self.http_status = http_status


def error_envelope(
    code: ErrorCode,
    message: str,
    *,
    interface_id: str,
    version: str,
    correlation_id: str,
) -> dict[str, Any]:
    return {
        "ok": False,
        "error": {
            "code": code.value,
            "message": message,
            "interface_id": interface_id,
            "version": version,
            "correlation_id": correlation_id,
        },
    }


def success_envelope(data: dict[str, Any]) -> dict[str, Any]:
    return {"ok": True, "data": data}
