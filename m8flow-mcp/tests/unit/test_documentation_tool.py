"""Regression tests for tools_documentation's depth parameter.

Previously `depth` was accepted in the schema but never read in the
function body, so depth="full" and depth="quick" returned identical
output. Now depth="full" (with no topic) concatenates every guide.
"""

from __future__ import annotations

import pytest


class MockFastMCP:
    def __init__(self):
        self.tools = {}

    def tool(self, *args, name=None, description=None, **kwargs):
        def decorator(func):
            self.tools[name or func.__name__] = func
            return func

        return decorator


def _register():
    from src.mcp_tools.documentation_tool import register_documentation_tool

    mcp = MockFastMCP()
    register_documentation_tool(mcp)
    return mcp


def test_no_topic_quick_returns_short_reference_only():
    mcp = _register()
    result = mcp.tools["tools_documentation"]()

    assert "Quick Reference" in result
    assert "Troubleshooting Guide" not in result


def test_no_topic_full_returns_all_guides_concatenated():
    mcp = _register()
    result = mcp.tools["tools_documentation"](depth="full")

    assert "Quick Reference" in result
    assert "Starting Workflows - Complete Guide" in result
    assert "Completing Tasks - Complete Guide" in result
    assert "Common Patterns and Best Practices" in result
    assert "Troubleshooting Guide" in result


def test_depth_has_no_effect_when_topic_given():
    mcp = _register()
    quick = mcp.tools["tools_documentation"](topic="start_workflow", depth="quick")
    full = mcp.tools["tools_documentation"](topic="start_workflow", depth="full")

    assert quick == full
    assert "Starting Workflows - Complete Guide" in quick


@pytest.mark.parametrize(
    "topic,expected_heading",
    [
        ("start_workflow", "Starting Workflows - Complete Guide"),
        ("complete_task", "Completing Tasks - Complete Guide"),
        ("common_patterns", "Common Patterns and Best Practices"),
        ("troubleshooting", "Troubleshooting Guide"),
    ],
)
def test_each_topic_returns_its_own_guide(topic, expected_heading):
    mcp = _register()
    result = mcp.tools["tools_documentation"](topic=topic)

    assert expected_heading in result


def test_unknown_topic_returns_helpful_fallback():
    mcp = _register()
    result = mcp.tools["tools_documentation"](topic="nonexistent")

    assert "No specific documentation found" in result
    assert "nonexistent" in result
