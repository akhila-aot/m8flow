"""Logging utilities for m8flow MCP server."""

from __future__ import annotations

import json
import logging
import re
import sys
from typing import Any

from src.config import settings

# Redacts secret-shaped substrings out of every log message, regardless of
# which of the many call sites produced it — a single, centrally-owned
# control rather than something each `logger.error(f"...: {e}")` call site
# would otherwise need to remember to do itself (backend error messages can
# echo request content, so `str(exc)` is not inherently safe to log verbatim).
_REDACT_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # Bearer <token>
    (re.compile(r"Bearer\s+[A-Za-z0-9\-_.]+", re.IGNORECASE), "Bearer ***REDACTED***"),
    # JWT-shaped strings (header.payload.signature, base64url segments)
    (re.compile(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]*"), "***REDACTED_JWT***"),
    # Authorization header: value may itself contain spaces (e.g. "Basic xyz"),
    # so capture through to a clear delimiter instead of stopping at whitespace.
    (
        re.compile(r'(authorization["\']?\s*[:=]\s*["\']?)([^"\'\n,}]+)', re.IGNORECASE),
        r"\1***REDACTED***",
    ),
    # Single-token secrets: stop at the first whitespace/quote/delimiter.
    (
        re.compile(
            r'((?:api[_-]?key|token|password|secret|cookie|client_secret)["\']?\s*[:=]\s*["\']?)([^\s"\',}]+)',
            re.IGNORECASE,
        ),
        r"\1***REDACTED***",
    ),
]

# Backend response bodies / submitted form data tend to be large; short
# operational messages never need to be this long. Truncating is a blunt but
# effective, pattern-independent guard against a large payload ending up
# verbatim in the logs.
_MAX_MESSAGE_LENGTH = 1000


def _redact(text: str) -> str:
    for pattern, replacement in _REDACT_PATTERNS:
        text = pattern.sub(replacement, text)
    if len(text) > _MAX_MESSAGE_LENGTH:
        text = f"{text[:_MAX_MESSAGE_LENGTH]}...[truncated, {len(text)} chars total]"
    return text


class RedactingFilter(logging.Filter):
    """Redacts secrets and truncates oversized text in every log record.

    Applied once, at the handler level, so it covers all current and future
    log statements — not just the ones that happen to route through the
    shared error envelope.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = _redact(record.getMessage())
        record.args = ()
        return True


# The only `extra` fields a log record is allowed to carry. This is what
# keeps arbitrary tool arguments (which may contain tokens, form data, or
# other sensitive content) out of the logs — callers should only ever pass
# this fixed, safe summary shape as `extra`, never raw request/response bodies.
ALLOWED_LOG_FIELDS = frozenset(
    {
        "method",
        "tool_name",
        "duration_ms",
        "outcome",
        "correlation_id",
        "tenant_id",
        "error_category",
    }
)


class _RedactingFormatterMixin:
    """Redacts a formatted traceback the same way RedactingFilter redacts messages.

    ``record.msg`` is redacted by the filter, but a traceback's last line
    (``ExceptionType: str(exc)``) carries the same backend-derived text and
    goes through ``formatException`` instead, which the filter doesn't touch.
    """

    def formatException(self, exc_info: Any) -> str:  # noqa: N802 (overrides logging.Formatter's stdlib name)
        return _redact(super().formatException(exc_info))  # type: ignore[misc]


class JsonFormatter(_RedactingFormatterMixin, logging.Formatter):
    """Formats log records as JSON, using only the allowlisted extra fields.

    Python's standard ``logging.Formatter`` only serializes what's in its
    format string — ``extra={...}`` values are attached to the record but
    silently dropped unless the format string names them individually. This
    formatter instead emits every allowlisted field that's present, plus the
    standard timestamp/level/logger/message, as a single JSON object.
    """

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field in ALLOWED_LOG_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


class TextFormatter(_RedactingFormatterMixin, logging.Formatter):
    """Plain-text formatter with the same traceback redaction as JsonFormatter."""


def _build_formatter() -> logging.Formatter:
    if settings.log_format == "json":
        return JsonFormatter()
    return TextFormatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")


def setup_logging() -> None:
    """Configure logging for the application."""
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    # Configure root logger.
    # IMPORTANT: Use stderr for stdio mode to not interfere with MCP protocol.
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(_build_formatter())
    handler.addFilter(RedactingFilter())

    logging.basicConfig(level=log_level, handlers=[handler], force=True)

    # Set level for all existing loggers (in case they were created before setup)
    logging.getLogger().setLevel(log_level)
    for logger_name in list(logging.Logger.manager.loggerDict.keys()):
        existing_logger = logging.getLogger(logger_name)
        existing_logger.setLevel(log_level)


def get_logger(name: str | None = None) -> logging.Logger:
    """Get a logger instance.

    Args:
        name: Logger name. If None, returns root logger.

    Returns:
        Logger instance.
    """
    if name is None:
        name = "m8flow-mcp"
    return logging.getLogger(name)


def with_params(params: dict[str, Any]) -> dict[str, Any]:
    """Format parameters for structured logging.

    Args:
        params: Dictionary of parameters to log.

    Returns:
        Formatted parameters dictionary.
    """
    return {"extra": params} if params else {}


# Create default logger instance for direct import
logger = get_logger("m8flow-mcp")
