"""Unit tests for MCP prompts.

Registers the real prompts against a real FastMCP instance and renders
each one, since the defect these tests guard against (prompts returning
a shape FastMCP's Prompt.convert_result rejects) only shows up when the
prompt is actually rendered through the framework, not by inspecting
the Python source.
"""

import os

import pytest
from fastmcp import FastMCP

from src.mcp_tools.prompts import register_prompts

os.environ.setdefault("M8FLOW_API_URL", "http://test.local")
os.environ.setdefault("M8FLOW_BEARER_TOKEN", "test_token")

EXPECTED_PROMPTS = {
    "browse_workflows": [],
    "start_workflow": [],
    "check_my_tasks": [],
    "complete_task": [],
    "workflow_status": ["instance_id"],
    "understand_bpmn": [],
    "create_workflow": [],
    "troubleshoot_workflow": ["instance_id"],
}


@pytest.fixture
def mcp():
    server = FastMCP("test")
    register_prompts(server)
    return server


@pytest.mark.asyncio
async def test_all_prompts_registered(mcp):
    prompts = await mcp.list_prompts()
    assert {p.name for p in prompts} == set(EXPECTED_PROMPTS)


@pytest.mark.asyncio
async def test_required_arguments_match(mcp):
    prompts = {p.name: p for p in await mcp.list_prompts()}
    for name, expected_required in EXPECTED_PROMPTS.items():
        actual_required = [a.name for a in (prompts[name].arguments or []) if a.required]
        assert actual_required == expected_required, name


@pytest.mark.asyncio
@pytest.mark.parametrize("name", list(EXPECTED_PROMPTS))
async def test_prompt_renders_without_error(mcp, name):
    args = dict.fromkeys(EXPECTED_PROMPTS[name], "TEST123")
    result = await mcp.render_prompt(name, args)
    assert result.messages
    text = result.messages[0].content.text
    assert isinstance(text, str)
    assert text


@pytest.mark.asyncio
async def test_required_argument_is_interpolated(mcp):
    for name in ("workflow_status", "troubleshoot_workflow"):
        result = await mcp.render_prompt(name, {"instance_id": "TEST123"})
        text = result.messages[0].content.text
        first_line = text.splitlines()[0]
        assert "TEST123" in first_line
        assert "{instance_id}" not in first_line
