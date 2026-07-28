"""Tests for the correlation-id context helpers in src/utils/context.py."""

from __future__ import annotations

import pytest

from src.utils import context


@pytest.fixture(autouse=True)
def _reset():
    context.clear_context()
    yield
    context.clear_context()


def test_correlation_id_defaults_to_none():
    assert context.get_correlation_id() is None


def test_set_and_get_correlation_id():
    context.set_correlation_id("req-123")
    assert context.get_correlation_id() == "req-123"


def test_clear_context_resets_correlation_id():
    context.set_correlation_id("req-123")
    context.set_tenant_id("acme")

    context.clear_context()

    assert context.get_correlation_id() is None
    assert context.get_tenant_id() is None
