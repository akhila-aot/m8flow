"""Tests for the merged ObservabilityMiddleware.

Covers what used to be split across a live (weak-context) middleware and an
unused richer duplicate: request-scoped correlation ids, allowlisted log
context (method/tool name/tenant), detecting a tool's "swallowed" error
result (no exception raised) via the shared error envelope's outcome
ContextVar, and clearing request-scoped context after every call so it can't
leak into whatever request runs next on the same task.
"""

from __future__ import annotations

import logging

import pytest
from fastmcp.server.middleware import MiddlewareContext

from src.errors import NotFoundError, to_error_envelope
from src.middleware.observability_middleware import ObservabilityMiddleware
from src.utils.context import clear_context, get_correlation_id, get_tenant_id, set_tenant_id


class _FakeMessage:
    def __init__(self, name: str):
        self.name = name


def _context(name: str = "list_tasks", method: str = "tools/call") -> MiddlewareContext:
    return MiddlewareContext(message=_FakeMessage(name), method=method)


@pytest.fixture(autouse=True)
def _reset_context():
    clear_context()
    yield
    clear_context()


@pytest.mark.asyncio
async def test_successful_call_logs_success_outcome(caplog):
    middleware = ObservabilityMiddleware()

    async def call_next(_ctx):
        return {"ok": True}

    with caplog.at_level(logging.INFO, logger="src.middleware.observability_middleware"):
        result = await middleware.on_message(_context(), call_next)

    assert result == {"ok": True}
    record = caplog.records[-1]
    assert record.outcome == "success"
    assert record.tool_name == "list_tasks"
    assert record.method == "tools/call"
    assert hasattr(record, "duration_ms")
    assert hasattr(record, "correlation_id")


@pytest.mark.asyncio
async def test_swallowed_tool_error_is_logged_as_error_outcome(caplog):
    """A tool that catches its own exception and returns an error envelope
    (rather than raising) must still show up as a failure in the logs."""
    middleware = ObservabilityMiddleware()

    async def call_next(_ctx):
        return to_error_envelope(NotFoundError("process model x"))

    with caplog.at_level(logging.WARNING, logger="src.middleware.observability_middleware"):
        result = await middleware.on_message(_context(), call_next)

    assert result["ok"] is False
    record = caplog.records[-1]
    assert record.outcome == "error"
    assert record.error_category == "not_found"


@pytest.mark.asyncio
async def test_raised_exception_is_logged_as_error_and_reraised(caplog):
    middleware = ObservabilityMiddleware()

    async def call_next(_ctx):
        raise RuntimeError("boom")

    with (
        caplog.at_level(logging.ERROR, logger="src.middleware.observability_middleware"),
        pytest.raises(RuntimeError),
    ):
        await middleware.on_message(_context(), call_next)

    record = caplog.records[-1]
    assert record.outcome == "error"


@pytest.mark.asyncio
async def test_previous_swallowed_error_does_not_leak_into_next_successful_call(caplog):
    """Regression test: last_error_outcome must be reset per-call, or a
    failure from one request would incorrectly mark the next one as failed."""
    middleware = ObservabilityMiddleware()

    async def failing_call_next(_ctx):
        return to_error_envelope(NotFoundError("x"))

    async def successful_call_next(_ctx):
        return {"ok": True}

    await middleware.on_message(_context(), failing_call_next)

    with caplog.at_level(logging.INFO, logger="src.middleware.observability_middleware"):
        await middleware.on_message(_context(), successful_call_next)

    record = caplog.records[-1]
    assert record.outcome == "success"


@pytest.mark.asyncio
async def test_context_cleared_after_call_does_not_leak_tenant_to_next_task():
    """Regression test: tenant/correlation context set during one request
    must not still be visible after that request's middleware call returns."""
    middleware = ObservabilityMiddleware()

    async def call_next(_ctx):
        set_tenant_id("acme-corp")
        assert get_tenant_id() == "acme-corp"
        assert get_correlation_id() is not None
        return {"ok": True}

    await middleware.on_message(_context(), call_next)

    assert get_tenant_id() is None
    assert get_correlation_id() is None


@pytest.mark.asyncio
async def test_each_call_gets_a_distinct_correlation_id():
    middleware = ObservabilityMiddleware()
    seen = []

    async def call_next(_ctx):
        seen.append(get_correlation_id())
        return {"ok": True}

    await middleware.on_message(_context(), call_next)
    await middleware.on_message(_context(), call_next)

    assert len(seen) == 2
    assert seen[0] != seen[1]
    assert all(seen)
