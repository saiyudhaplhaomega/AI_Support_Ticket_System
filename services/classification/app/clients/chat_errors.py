"""Shared timeout/API error types raised by any chat-completion provider client."""
from __future__ import annotations


class ChatTimeoutError(RuntimeError):
    pass


class ChatAPIError(RuntimeError):
    pass
