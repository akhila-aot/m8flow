"""Regression test for error management tools (bug #8).

The tools must resolve the model id and call the model-qualified show route,
not the bare /process-instances/{id} path that returned 405.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

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
    from src.mcp_tools.error_management import register_error_tools

    mcp = MockFastMCP()
    register_error_tools(mcp)
    return mcp


FIND_BY_ID = {
    "process_instance": {
        "id": 42,
        "status": "error",
        "process_model_identifier": "finance/expense-approval",
    }
}


@pytest.mark.asyncio
async def test_get_error_details_uses_find_by_id_only():
    """find-by-id returns the serialized instance, so no second GET is needed."""
    mcp = _register()
    with (
        patch("src.mcp_tools.error_management.get_auth_token", return_value="Bearer t"),
        patch("src.mcp_tools.error_management.client.get", new_callable=AsyncMock) as mock_get,
    ):
        mock_get.return_value = FIND_BY_ID

        result = await mcp.tools["get_error_details"](42)

        mock_get.assert_awaited_once()
        assert mock_get.call_args_list[0].args[0] == "/v1.0/process-instances/find-by-id/42"
        assert result["status"] == "error"


def _instance(status: str, instance_id: int = 638) -> dict:
    return {
        "id": instance_id,
        "status": status,
        "process_model_identifier": "external-trigger-process-group/review-appointment-rev-1",
        "start_in_seconds": 1719000000,
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["error", "suspended", "waiting", "complete", "user_input_required"])
async def test_diagnose_workflow_interpolates_no_literal_placeholders(status):
    """Regression test: every branch must substitute real values, never leak `{process_instance_id}`/`{status}`."""
    mcp = _register()
    with (
        patch("src.mcp_tools.error_management.get_auth_token", return_value="Bearer t"),
        patch("src.mcp_tools.error_management.client.get", new_callable=AsyncMock) as mock_get,
    ):
        mock_get.return_value = {"process_instance": _instance(status)}

        diagnosis = await mcp.tools["diagnose_workflow"](638)

        assert "{process_instance_id}" not in diagnosis
        assert "{status}" not in diagnosis
        assert "638" in diagnosis


@pytest.mark.asyncio
async def test_diagnose_workflow_suspended_shows_real_instance_id_in_list_tasks_hint():
    mcp = _register()
    with (
        patch("src.mcp_tools.error_management.get_auth_token", return_value="Bearer t"),
        patch("src.mcp_tools.error_management.client.get", new_callable=AsyncMock) as mock_get,
    ):
        mock_get.return_value = {"process_instance": _instance("suspended")}

        diagnosis = await mcp.tools["diagnose_workflow"](638)

        assert "list_tasks(process_instance_id=638)" in diagnosis


@pytest.mark.asyncio
async def test_diagnose_workflow_unknown_status_shows_real_status_and_resource_uri():
    mcp = _register()
    with (
        patch("src.mcp_tools.error_management.get_auth_token", return_value="Bearer t"),
        patch("src.mcp_tools.error_management.client.get", new_callable=AsyncMock) as mock_get,
    ):
        mock_get.return_value = {"process_instance": _instance("user_input_required")}

        diagnosis = await mcp.tools["diagnose_workflow"](638)

        assert "Status is 'user_input_required'" in diagnosis
        assert "workflow://638" in diagnosis
