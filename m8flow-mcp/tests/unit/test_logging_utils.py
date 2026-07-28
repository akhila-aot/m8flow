"""Tests for src/utils/logging.py.

Regression coverage for: LOG_FORMAT was previously accepted in settings but
never read by setup_logging(), which always used a hardcoded plain-text
format regardless of the setting. Also covers RedactingFilter — the review's
"redact tokens, cookies, secrets, authorization headers, ... backend bodies"
requirement, applied once at the handler level rather than at each of the
~70+ call sites that log an exception's message.
"""

from __future__ import annotations

import io
import json
import logging
from unittest.mock import patch

from src.utils.logging import (
    ALLOWED_LOG_FIELDS,
    JsonFormatter,
    RedactingFilter,
    TextFormatter,
    _build_formatter,
    _redact,
)


def _make_record(msg: str = "hello", **extra) -> logging.LogRecord:
    record = logging.LogRecord(
        name="test.logger",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=msg,
        args=(),
        exc_info=None,
    )
    for key, value in extra.items():
        setattr(record, key, value)
    return record


def test_json_formatter_includes_standard_fields():
    formatter = JsonFormatter()
    record = _make_record("hello world")

    payload = json.loads(formatter.format(record))

    assert payload["message"] == "hello world"
    assert payload["level"] == "INFO"
    assert payload["logger"] == "test.logger"
    assert "timestamp" in payload


def test_json_formatter_includes_allowlisted_extra_fields():
    formatter = JsonFormatter()
    record = _make_record(
        method="tools/call",
        tool_name="list_tasks",
        duration_ms=12.3,
        outcome="success",
        correlation_id="abc-123",
        tenant_id="acme",
    )

    payload = json.loads(formatter.format(record))

    assert payload["method"] == "tools/call"
    assert payload["tool_name"] == "list_tasks"
    assert payload["duration_ms"] == 12.3
    assert payload["outcome"] == "success"
    assert payload["correlation_id"] == "abc-123"
    assert payload["tenant_id"] == "acme"


def test_json_formatter_drops_non_allowlisted_fields():
    """Regression test: only ALLOWED_LOG_FIELDS may reach the output — this is
    what keeps arbitrary tool arguments (tokens, form data, ...) out of logs."""
    formatter = JsonFormatter()
    record = _make_record(
        outcome="success",
        bearer_token="super-secret",
        raw_request_body={"password": "hunter2"},
    )

    payload = json.loads(formatter.format(record))

    assert payload["outcome"] == "success"
    assert "bearer_token" not in payload
    assert "raw_request_body" not in payload
    assert "super-secret" not in json.dumps(payload)


def test_allowed_log_fields_is_a_closed_safe_set():
    assert {
        "method",
        "tool_name",
        "duration_ms",
        "outcome",
        "correlation_id",
        "tenant_id",
        "error_category",
    } == ALLOWED_LOG_FIELDS


def test_build_formatter_uses_json_formatter_when_configured():
    with patch("src.utils.logging.settings") as mock_settings:
        mock_settings.log_format = "json"
        formatter = _build_formatter()
    assert isinstance(formatter, JsonFormatter)


def test_build_formatter_uses_text_formatter_when_configured():
    with patch("src.utils.logging.settings") as mock_settings:
        mock_settings.log_format = "text"
        formatter = _build_formatter()
    assert isinstance(formatter, logging.Formatter)
    assert not isinstance(formatter, JsonFormatter)


# --- RedactingFilter -------------------------------------------------------


def test_redact_masks_bearer_token():
    assert "eyJhbGci" not in _redact("Authorization used Bearer eyJhbGciOiJSUzI1NiJ9.abc.def")
    assert "***REDACTED***" in _redact("Bearer eyJhbGciOiJSUzI1NiJ9.abc.def")


def test_redact_masks_jwt_shaped_string_even_without_bearer_prefix():
    jwt = "eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiIxMjM0In0.signature123"
    result = _redact(f"token was {jwt}")
    assert jwt not in result
    assert "***REDACTED_JWT***" in result


def test_redact_masks_authorization_header_with_multi_word_value():
    """Regression test: 'Authorization: Basic xyz' must redact the whole
    value, not just the first word (scheme), leaving the credential exposed."""
    result = _redact("failed request, Authorization: Basic dXNlcjpwYXNz")
    assert "dXNlcjpwYXNz" not in result
    assert "Basic" not in result


def test_redact_masks_password_and_secret_key_value_pairs():
    result = _redact('login failed for password=hunter2, client_secret="s3cr3t-value"')
    assert "hunter2" not in result
    assert "s3cr3t-value" not in result


def test_redact_truncates_oversized_messages():
    huge = "x" * 5000
    result = _redact(f"backend said: {huge}")
    assert len(result) < 1100
    assert "truncated" in result


def test_redact_leaves_short_safe_messages_unchanged():
    assert _redact("process model finance/expense-approval not found") == (
        "process model finance/expense-approval not found"
    )


def test_redacting_filter_applies_to_log_record_message():
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(RedactingFilter())
    logger = logging.getLogger("test.redacting.filter")
    logger.addHandler(handler)
    logger.setLevel(logging.ERROR)
    logger.propagate = False

    logger.error("token=super-secret-value should not appear")

    payload = json.loads(stream.getvalue())
    assert "super-secret-value" not in payload["message"]


def test_redacting_filter_applies_to_exception_traceback_via_formatter():
    """A traceback's last line embeds str(exc), which can carry the same
    backend-derived text as the message — this must be redacted too, not
    just the top-level message."""
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(RedactingFilter())
    logger = logging.getLogger("test.redacting.filter.exc")
    logger.addHandler(handler)
    logger.setLevel(logging.ERROR)
    logger.propagate = False

    try:
        raise ValueError("backend response: password=hunter2")
    except ValueError:
        logger.error("request failed", exc_info=True)

    payload = json.loads(stream.getvalue())
    assert "hunter2" not in payload["exc_info"]
    assert "hunter2" not in payload["message"]


def test_text_formatter_also_redacts_traceback():
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(TextFormatter("%(message)s"))
    handler.addFilter(RedactingFilter())
    logger = logging.getLogger("test.redacting.filter.text")
    logger.addHandler(handler)
    logger.setLevel(logging.ERROR)
    logger.propagate = False

    try:
        raise ValueError("token=abc123secret")
    except ValueError:
        logger.error("request failed", exc_info=True)

    assert "abc123secret" not in stream.getvalue()
