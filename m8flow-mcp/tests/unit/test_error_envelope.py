"""Unit tests for the shared error envelope (src/errors/envelope.py).

Every category in the closed set must map to a stable, safe envelope shape —
this is what lets tools stop discarding the typed exception's category/status
into a bare str(e).
"""

from __future__ import annotations

from src.errors import (
    AuthenticationError,
    AuthorizationError,
    M8flowAPIError,
    NetworkError,
    NotFoundError,
    ServerError,
    TenantError,
    TimeoutError,
    to_error_envelope,
)
from src.errors.envelope import last_error_outcome


def test_authentication_error_envelope():
    envelope = to_error_envelope(AuthenticationError())
    assert envelope["ok"] is False
    assert envelope["error"]["category"] == "authentication"
    assert envelope["error"]["status_code"] == 401
    assert envelope["error"]["retryable"] is False
    assert envelope["error"]["action"] == "reauthenticate"


def test_authorization_error_envelope():
    envelope = to_error_envelope(AuthorizationError())
    assert envelope["error"]["category"] == "authorization"
    assert envelope["error"]["status_code"] == 403
    assert envelope["error"]["retryable"] is False
    assert envelope["error"]["action"] == "check_permissions"


def test_tenant_error_envelope_has_select_tenant_action():
    envelope = to_error_envelope(TenantError())
    assert envelope["error"]["category"] == "tenant"
    assert envelope["error"]["status_code"] == 400
    assert envelope["error"]["action"] == "select_tenant"
    assert envelope["error"]["retryable"] is False


def test_not_found_error_envelope():
    envelope = to_error_envelope(NotFoundError("process model finance/expense"))
    assert envelope["error"]["category"] == "not_found"
    assert envelope["error"]["status_code"] == 404
    assert envelope["error"]["retryable"] is False


def test_server_error_envelope_is_retryable():
    envelope = to_error_envelope(ServerError(502, "bad gateway"))
    assert envelope["error"]["category"] == "server_error"
    assert envelope["error"]["status_code"] == 502
    assert envelope["error"]["retryable"] is True
    assert envelope["error"]["action"] == "retry_later"


def test_network_error_envelope_is_retryable():
    envelope = to_error_envelope(NetworkError())
    assert envelope["error"]["category"] == "network"
    assert envelope["error"]["status_code"] is None
    assert envelope["error"]["retryable"] is True


def test_timeout_error_envelope_is_retryable():
    envelope = to_error_envelope(TimeoutError())
    assert envelope["error"]["category"] == "timeout"
    assert envelope["error"]["retryable"] is True


def test_generic_400_api_error_maps_to_validation():
    envelope = to_error_envelope(M8flowAPIError(400, "bad request"))
    assert envelope["error"]["category"] == "validation"
    assert envelope["error"]["action"] == "check_input"
    assert envelope["error"]["retryable"] is False


def test_generic_unhandled_status_maps_to_unknown():
    envelope = to_error_envelope(M8flowAPIError(418, "teapot"))
    assert envelope["error"]["category"] == "unknown"
    assert envelope["error"]["status_code"] == 418


def test_plain_exception_maps_to_unknown_with_no_status():
    envelope = to_error_envelope(RuntimeError("something broke"))
    assert envelope["error"]["category"] == "unknown"
    assert envelope["error"]["status_code"] is None
    assert envelope["error"]["action"] is None


def test_never_leaks_raw_exception_message_into_safe_message():
    """The safe message must be a normalized string, not str(exc), so backend
    response bodies/internals never reach the agent by default."""
    secret_detail = "internal-db-connection-string=postgres://user:hunter2@host"
    envelope = to_error_envelope(ServerError(500, secret_detail))
    assert secret_detail not in envelope["error"]["message"]


def test_correlation_id_included_when_provided():
    envelope = to_error_envelope(NotFoundError("x"), correlation_id="req-123")
    assert envelope["error"]["correlation_id"] == "req-123"


def test_correlation_id_omitted_when_not_provided():
    envelope = to_error_envelope(NotFoundError("x"))
    assert "correlation_id" not in envelope["error"]


def test_records_last_error_outcome_for_middleware_to_observe():
    to_error_envelope(AuthorizationError())
    recorded = last_error_outcome.get()
    assert recorded is not None
    assert recorded["category"] == "authorization"
