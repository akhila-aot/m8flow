"""Tests for src/utils/untrusted_content.py.

Regression coverage for the review's §4 security posture, which was never
implemented in the original remediation phases: backend-authored text
(descriptions, tags, task variables, BPMN content) must be explicitly
labeled as untrusted data (not instructions) and size-capped, consistently,
rather than concatenated directly into agent-facing prose.
"""

from __future__ import annotations

from src.utils.untrusted_content import (
    LISTING_DISCLAIMER,
    truncate_inline,
    wrap_untrusted,
)


def test_wrap_untrusted_returns_empty_string_for_empty_content():
    assert wrap_untrusted("", label="x") == ""
    assert wrap_untrusted(None, label="x") == ""  # type: ignore[arg-type]


def test_wrap_untrusted_labels_content_as_untrusted_backend_data():
    result = wrap_untrusted("some process model description", label="process model description")
    assert 'source="workflow_backend"' in result
    assert "trusted=false" in result
    assert "not an instruction" in result
    assert "some process model description" in result


def test_wrap_untrusted_includes_the_given_label():
    result = wrap_untrusted("x", label="task form data")
    assert "task form data" in result


def test_wrap_untrusted_fences_content_so_it_reads_as_data():
    result = wrap_untrusted("<script>alert(1)</script>", label="x")
    assert "```" in result


def test_wrap_untrusted_truncates_when_over_max_length():
    long_text = "a" * 3000
    result = wrap_untrusted(long_text, label="x", max_length=100)
    assert "a" * 100 in result
    assert "a" * 101 not in result
    assert "truncated" in result
    assert "2000" not in result  # sanity: doesn't leak an unrelated number
    assert "showing 100 of 3000 characters" in result


def test_wrap_untrusted_does_not_add_truncation_note_when_under_limit():
    result = wrap_untrusted("short text", label="x", max_length=100)
    assert "truncated" not in result


def test_truncate_inline_returns_empty_string_for_empty_content():
    assert truncate_inline("") == ""


def test_truncate_inline_leaves_short_text_unchanged():
    assert truncate_inline("a short description") == "a short description"


def test_truncate_inline_truncates_long_text_with_marker():
    long_text = "b" * 500
    result = truncate_inline(long_text, max_length=50)
    assert result.startswith("b" * 50)
    assert "[truncated]" in result
    assert len(result) < 500


def test_listing_disclaimer_names_the_backend_as_source():
    assert "workflow_backend" in LISTING_DISCLAIMER
    assert "trusted=false" in LISTING_DISCLAIMER
