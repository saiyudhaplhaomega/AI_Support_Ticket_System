"""Structured (JSON) logging — qa.validation-and-logging.v1 §3.4.

Every log line carries: ts, module, interface_id, version, correlation_id,
level, message. `correlation_id` is threaded through from the caller (n8n
workflow ingestion) via the `X-Correlation-Id` header, or generated here if
absent, so one ticket's path is traceable across module calls.
"""
from __future__ import annotations

import json
import logging
import sys
import time
from typing import Any

MODULE_NAME = "ai-classification-service"


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)),
            "module": MODULE_NAME,
            "level": record.levelname.lower(),
            "message": record.getMessage(),
        }
        for key in ("interface_id", "version", "correlation_id"):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        extra = getattr(record, "extra_fields", None)
        if extra:
            payload.update(extra)
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: str = "info") -> None:
    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))


def log_event(
    logger: logging.Logger,
    level: str,
    message: str,
    *,
    interface_id: str,
    version: str = "v1",
    correlation_id: str,
    **extra_fields: Any,
) -> None:
    logger.log(
        getattr(logging, level.upper(), logging.INFO),
        message,
        extra={
            "interface_id": interface_id,
            "version": version,
            "correlation_id": correlation_id,
            "extra_fields": extra_fields,
        },
    )
