"""Inbound auth for this HTTP service.

Per capability-module-architecture.md §3.1/§3.2, consumers never call
Qdrant/OpenAI directly — they call this module's endpoints. Since this is an
HTTP service (not an in-process n8n sub-workflow), it needs its own inbound
auth: callers present `AI_CLASSIFY_API_KEY` as a bearer token. This is the
same env var name Infra already wired into docker-compose.yml/.env.example
for the n8n service, so the value the workflow calls with is the value this
service checks against — no new secret name introduced.
"""
from __future__ import annotations

import hmac

from app.errors import ErrorCode, ModuleError


def verify_bearer_token(authorization: str | None, expected_key: str, *, interface_id: str) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        raise ModuleError(
            ErrorCode.AUTH_ERROR,
            "Missing or malformed Authorization header; expected 'Bearer <AI_CLASSIFY_API_KEY>'.",
            interface_id=interface_id,
            http_status=401,
        )
    presented = authorization.removeprefix("Bearer ").strip()
    if not presented or not hmac.compare_digest(presented, expected_key):
        raise ModuleError(
            ErrorCode.AUTH_ERROR,
            "Invalid bearer token.",
            interface_id=interface_id,
            http_status=401,
        )
