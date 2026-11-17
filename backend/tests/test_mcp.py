"""Pytest suite for Phase 3 MCP tools and client."""
import pytest
from backend.mcp_server.client import MCPClient
from backend.database import SessionLocal
from backend.models import Incident, MCPToolCall
from backend.api.auth import seed_demo_users

@pytest.fixture(autouse=True)
def setup_users():
    seed_demo_users()

@pytest.mark.anyio
async def test_mcp_list_tools():
    client = MCPClient()
    tools = await client.list_tools()
    assert len(tools) >= 10
    tool_names = {t["name"] for t in tools}
    expected_tools = {
        "create_ticket",
        "get_ticket",
        "update_ticket",
        "check_network_status",
        "check_server_health",
        "search_employee_assets",
        "search_knowledge_base",
        "assign_support_team",
        "escalate_incident",
        "update_incident_status",
        "assign_incident_engineer",
        "check_engineer_availability",
        "reassign_incident",
    }
    assert expected_tools.issubset(tool_names)

@pytest.mark.anyio
async def test_mcp_create_ticket_and_diagnostics():
    client = MCPClient()
    
    # 1. create_ticket
    ticket = await client.call_tool(
        tool_name="create_ticket",
        arguments={
            "title": "Wi-Fi Gateway Timeout",
            "description": "Employee cannot resolve DNS on internal subnet",
            "category": "network",
            "priority": "high",
            "employee_id": 1,
        },
        user_role="employee",
    )
    assert ticket["ticket_id"] > 0
    assert ticket["status"] == "open"
    
    # 2. check_network_status
    net = await client.call_tool(
        tool_name="check_network_status",
        arguments={"target_host": "gateway.internal.corp"},
        user_role="support_engineer",
    )
    assert net["simulated"] is True
    assert net["status"] == "online"

    # 3. check_server_health
    srv = await client.call_tool(
        tool_name="check_server_health",
        arguments={"server_id": "srv-prod-01"},
        user_role="support_engineer",
    )
    assert srv["simulated"] is True
    assert srv["service_status"] == "degraded"

@pytest.mark.anyio
async def test_mcp_permission_denied():
    client = MCPClient()
    with pytest.raises(PermissionError) as exc_info:
        await client.call_tool(
            tool_name="check_server_health",
            arguments={"server_id": "srv-prod-01"},
            user_role="employee",
        )
    assert "Permission denied" in str(exc_info.value)

@pytest.mark.anyio
async def test_mcp_invalid_input():
    client = MCPClient()
    with pytest.raises(ValueError) as exc_info:
        await client.call_tool(
            tool_name="create_ticket",
            arguments={"title": "", "description": ""},
            user_role="employee",
        )
    assert "Title cannot be empty" in str(exc_info.value)

