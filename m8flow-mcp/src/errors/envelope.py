"""Shared error envelope — the one place that converts any exception into the
agent-facing error shape.

Tools currently catch the typed exceptions raised by M8flowAPIClient and
discard everything but ``str(e)``, so the category/status/retryability
information the exception carried never reaches the caller. This module is
the single conversion point tools should call instead, so every tool reports
errors the same way.
"""

from __future__ import annotations

import contextvars
from typing import Any, Literal

from src.errors.exceptions import (
    AuthenticationError,
    AuthorizationError,
    M8flowAPIError,
    NetworkError,
    NotFoundError,
    ServerError,
    TenantError,
    TimeoutError,
)

ErrorCategory = Literal[
    "authentication",
    "authorization",
    "not_found",
    "tenant",
    "validation",
    "server_error",
    "network",
    "timeout",
    "unknown",
]

_RETRYABLE_CATEGORIES: frozenset[ErrorCategory] = frozenset({"server_error", "network", "timeout"})

_CATEGORY_ACTIONS: dict[ErrorCategory, str | None] = {
    "authentication": "reauthenticate",
    "authorization": "check_permissions",
    "not_found": "check_identifier",
    "tenant": "select_tenant",
    "validation": "check_input",
    "server_error": "retry_later",
    "network": "retry_later",
    "timeout": "retry_later",
    "unknown": None,
}

# Set by every to_error_envelope() call so middleware can observe a tool's
# failure outcome even though the tool itself never lets the exception
# propagate. Reset per-request by whatever sets up request-scoped context
# (see src/middleware/context_middleware.py).
last_error_outcome: contextvars.ContextVar[dict[str, Any] | None] = contextvars.ContextVar(
    "last_error_outcome", default=None
)


def _classify(exc: Exception) -> tuple[ErrorCategory, int | None, str]:
    """Return (category, status_code, safe_message) for a given exception."""
    if isinstance(exc, AuthenticationError):
        return "authentication", exc.status_code, "Authentication failed. Your token may be invalid or expired."
    if isinstance(exc, AuthorizationError):
        return "authorization", exc.status_code, "You don't have permission to access this resource."
    if isinstance(exc, TenantError):
        return "tenant", exc.status_code, "Tenant context is missing or invalid. Select a tenant and retry."
    if isinstance(exc, NotFoundError):
        return "not_found", exc.status_code, "The requested resource was not found."
    if isinstance(exc, ServerError):
        return "server_error", exc.status_code, "The m8flow backend encountered a server error."
    if isinstance(exc, NetworkError):
        return "network", None, "Could not reach the m8flow backend."
    if isinstance(exc, TimeoutError):
        return "timeout", None, "The request to the m8flow backend timed out."
    if isinstance(exc, M8flowAPIError):
        if exc.status_code in (400, 422):
            return "validation", exc.status_code, "The request was rejected as invalid."
        return "unknown", exc.status_code, "An unexpected error occurred while calling the m8flow backend."
    return "unknown", None, "An unexpected error occurred."


def to_error_envelope(exc: Exception, *, correlation_id: str | None = None) -> dict[str, Any]:
    """Convert any exception into the shared, agent-facing error envelope.

    Never includes the raw backend response body — only a safe, normalized
    message. Also records the outcome in ``last_error_outcome`` so middleware
    can observe the failure even though it's returned, not raised.
    """
    category, status_code, message = _classify(exc)

    error: dict[str, Any] = {
        "category": category,
        "message": message,
        "status_code": status_code,
        "retryable": category in _RETRYABLE_CATEGORIES,
        "action": _CATEGORY_ACTIONS[category],
    }
    if correlation_id is not None:
        error["correlation_id"] = correlation_id

    last_error_outcome.set(error)
    return {"ok": False, "error": error}
