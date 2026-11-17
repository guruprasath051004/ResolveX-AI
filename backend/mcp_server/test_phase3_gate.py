"""Phase 3 MCP Gate Test Script.

Validates:
1. Lists all 10 tools through the official MCP protocol.
2. Calls create_ticket, check_network_status, and check_server_health through the client.
3. Tests permission-denied failure (employee calling restricted diagnostic/server health tool).
4. Tests invalid-input failure (invalid/empty fields failing cleanly).
5. Shows created DB rows in incidents and mcp_tool_calls tables.
"""

import asyncio
import json
import os
import sys

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.database import SessionLocal
from backend.models import Incident, MCPToolCall
from backend.mcp_server.client import MCPClient

async def run_gate_tests():
    print("=" * 70)
    print("RESOLVEX AI - PHASE 3 MCP GATE VERIFICATION")
    print("=" * 70)

    client = MCPClient()

    # 1. List tools through MCP protocol
    print("\n--- 1. LISTING TOOLS OVER MCP PROTOCOL ---")
    tools = await client.list_tools()
    print(f"Total registered MCP tools: {len(tools)}")
    for idx, tool in enumerate(tools, 1):
        print(f"  {idx:2d}. {tool['name']:25s} - {tool['description']}")
    assert len(tools) == 10, f"Expected 10 tools, found {len(tools)}"

    # 2. Call create_ticket through client
    print("\n--- 2. CALLING create_ticket VIA MCP CLIENT ---")
    ticket_payload = {
        "title": "Corporate Portal Unreachable on Wi-Fi",
        "description": "User cannot reach intranet portal from office Wi-Fi network.",
        "category": "network",
        "priority": "high",
        "employee_id": 1,
    }
    created_ticket = await client.call_tool(
        tool_name="create_ticket",
        arguments=ticket_payload,
        user_role="employee",
        calling_agent="diagnostic_agent",
    )
    print("create_ticket response:")
    print(json.dumps(created_ticket, indent=2))
    ticket_id = created_ticket["ticket_id"]
    assert ticket_id > 0, "Ticket ID should be greater than 0"

    # 3. Call check_network_status through client
    print("\n--- 3. CALLING check_network_status VIA MCP CLIENT ---")
    net_diag = await client.call_tool(
        tool_name="check_network_status",
        arguments={"target_host": "portal.internal.corp"},
        user_role="support_engineer",
        calling_agent="diagnostic_agent",
    )
    print("check_network_status response:")
    print(json.dumps(net_diag, indent=2))
    assert net_diag.get("simulated") is True, "Simulated flag must be True"

    # 4. Call check_server_health through client
    print("\n--- 4. CALLING check_server_health VIA MCP CLIENT ---")
    srv_diag = await client.call_tool(
        tool_name="check_server_health",
        arguments={"server_id": "srv-prod-app-01"},
        user_role="support_engineer",
        calling_agent="diagnostic_agent",
    )
    print("check_server_health response:")
    print(json.dumps(srv_diag, indent=2))
    assert srv_diag.get("simulated") is True, "Simulated flag must be True"

    # 5. Permission-denied test: employee calling check_server_health
    print("\n--- 5. PERMISSION-DENIED CALL TEST (Employee -> check_server_health) ---")
    perm_denied_caught = False
    try:
        await client.call_tool(
            tool_name="check_server_health",
            arguments={"server_id": "srv-prod-app-01"},
            user_role="employee",
            calling_agent="triage_agent",
        )
    except Exception as e:
        perm_denied_caught = True
        print(f"Cleanly caught expected permission error: {type(e).__name__}: {e}")
    assert perm_denied_caught, "Expected permission-denied exception was not raised"

    # 6. Invalid-input test: missing title / empty description
    print("\n--- 6. INVALID-INPUT CALL TEST (create_ticket with empty title) ---")
    invalid_input_caught = False
    try:
        await client.call_tool(
            tool_name="create_ticket",
            arguments={"title": "", "description": ""},
            user_role="employee",
            calling_agent="triage_agent",
        )
    except Exception as e:
        invalid_input_caught = True
        print(f"Cleanly caught expected invalid-input error: {type(e).__name__}: {e}")
    assert invalid_input_caught, "Expected invalid-input exception was not raised"

    # 7. Show created database rows
    print("\n--- 7. DATABASE VERIFICATION (incidents & mcp_tool_calls) ---")
    db = SessionLocal()
    try:
        incidents = db.query(Incident).filter(Incident.id == ticket_id).all()
        print(f"\n[Table: incidents] Row created for ticket_id={ticket_id}:")
        for inc in incidents:
            print(f"  ID: {inc.id} | Priority: {inc.priority} | Status: {inc.status} | Owner ID: {inc.owner_id}")
            print(f"  Description: {inc.description}")

        calls = db.query(MCPToolCall).order_by(MCPToolCall.id.desc()).limit(5).all()
        print(f"\n[Table: mcp_tool_calls] Last {len(calls)} logged tool executions:")
        for call in reversed(calls):
            print(f"  ID: {call.id:2d} | Tool: {call.tool_name:22s} | Status: {call.status:7s} | Perm: {call.permission_status:7s} | Duration: {call.duration_ms:2d}ms")
            print(f"      Input : {call.input_summary}")
            print(f"      Output: {call.output_summary}")
    finally:
        db.close()

    print("\n" + "=" * 70)
    print("PHASE 3 MCP GATE TEST PASSED SUCCESSFULLY!")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(run_gate_tests())
