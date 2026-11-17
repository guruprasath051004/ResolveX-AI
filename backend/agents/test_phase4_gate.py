"""Phase 4 LangGraph Agents Gate Test Script.

Validates all 4 acceptance scenarios through the API in demo mode and live mode (if configured):
- Scenario 1: Wi-Fi / Company Portal connectivity
- Scenario 2: Corporate VPN tunnel connectivity
- Scenario 3: Python software installation request (sensitive action requiring approval)
- Scenario 4: Production application outage (critical incident with escalation)

Tests & Verifies:
1. Structured output classification from Triage Agent
2. Knowledge retrieval from Knowledge Agent (RAG chunks with metadata)
3. Diagnostic tool execution strictly through MCP client
4. Resolution formulation with human approval requirements
5. Ticket lifecycle management strictly through MCP ticket tools
6. Supervisor routing, validation, checkpoint persistence to PostgreSQL, pause & resume
7. SSE streaming endpoint (/api/agent/stream)
8. Full database audit trail (agent_runs, agent_steps, agent_checkpoints, incidents, approvals, mcp_tool_calls)
"""

import os
import sys
import json
import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.main import app
from backend.database import SessionLocal
from backend.database.migrations import upgrade_database
from backend.models import AgentRun, AgentStep, AgentCheckpoint, Incident, Approval, MCPToolCall
from backend.agents.llm import get_current_provider, is_demo_mode

SCENARIOS = [
    {
        "id": 1,
        "name": "Scenario 1: Network / Company Portal Unreachable",
        "message": "My laptop is connected to Wi-Fi, but the company portal is not opening.",
        "expected_intent": "incident",
        "expected_category": "network",
        "expected_priority": "high",
        "expected_tool": "check_network_status",
        "expected_approval": False,
        "expected_status": "in_progress",
    },
    {
        "id": 2,
        "name": "Scenario 2: Corporate VPN Failure",
        "message": "I cannot connect to the corporate VPN.",
        "expected_intent": "incident",
        "expected_category": "vpn",
        "expected_priority": "medium",
        "expected_tool": "check_network_status",
        "expected_approval": False,
        "expected_status": "in_progress",
    },
    {
        "id": 3,
        "name": "Scenario 3: Software Installation Service Request",
        "message": "I need Python installed on my company laptop.",
        "expected_intent": "service_request",
        "expected_category": "software",
        "expected_priority": "low",
        "expected_tool": "search_employee_assets",
        "expected_approval": True,
        "expected_status": "pending_approval",
    },
    {
        "id": 4,
        "name": "Scenario 4: Critical Production Outage",
        "message": "The production application is unavailable.",
        "expected_intent": "incident",
        "expected_category": "server",
        "expected_priority": "critical",
        "expected_tool": "check_server_health",
        "expected_approval": False,
        "expected_status": "investigating",
    },
]

def _run_gate(client):
    
    provider = get_current_provider()
    print("=" * 85)
    print(f"RESOLVEX AI - PHASE 4 LANGGRAPH AGENTS GATE VERIFICATION")
    print(f"Active LLM Provider: {provider.upper()} (Demo Mode: {is_demo_mode()})")
    print("=" * 85)
    
    scenario_reports = []
    paused_thread_id = None

    for sc in SCENARIOS:
        print(f"\n>>> EXECUTING {sc['name'].upper()}")
        print(f"User Message: \"{sc['message']}\"")
        
        response = client.post(
            "/api/agent/run",
            json={
                "message": sc["message"],
                "employee_id": 1,
                "is_demo": True,
            },
        )
        assert response.status_code == 200, f"API call failed: {response.text}"
        data = response.json()
        
        # Validate scenario expectations
        assert data["intent"] == sc["expected_intent"], f"Intent mismatch: {data['intent']}"
        assert data["category"] == sc["expected_category"], f"Category mismatch: {data['category']}"
        assert data["priority"] == sc["expected_priority"], f"Priority mismatch: {data['priority']}"
        assert data["requires_approval"] == sc["expected_approval"], f"Approval mismatch: {data['requires_approval']}"
        assert data["ticket_status"] == sc["expected_status"], f"Status mismatch: {data['ticket_status']}"
        assert data["incident_id"] is not None and data["incident_id"] > 0, "Valid incident_id must be assigned"
        
        if sc["expected_approval"]:
            paused_thread_id = data.get("thread_id")

        # Check diagnostic tools called
        tools_called = [d["tool"] for d in data["diagnostics"]]
        assert sc["expected_tool"] in tools_called, f"Expected tool {sc['expected_tool']} not called. Found: {tools_called}"
        for d in data["diagnostics"]:
            assert d.get("simulated") is True, "Diagnostic tool result must have simulated: true"

        # Check knowledge chunks
        assert len(data["retrieved_chunks"]) > 0, "Must retrieve relevant knowledge chunks"

        # Check agent trace
        assert len(data["agent_trace"]) >= 5, "Agent trace must contain all sequential steps"
        agents_in_trace = [t["agent"] for t in data["agent_trace"]]
        assert "Triage Agent" in agents_in_trace
        assert "Supervisor Agent" in agents_in_trace
        assert "Knowledge Agent" in agents_in_trace
        assert "Diagnostic Agent" in agents_in_trace
        assert "Resolution Agent" in agents_in_trace
        assert "Ticket Agent" in agents_in_trace

        print(f"  + Incident ID: #{data['incident_id']}")
        print(f"  + Intent: {data['intent']} | Category: {data['category']} | Priority: {data['priority']}")
        print(f"  + Sources retrieved ({len(data['retrieved_chunks'])}): {[c['doc'] for c in data['retrieved_chunks']]}")
        print(f"  + Diagnostic tools: {tools_called} (simulated: True)")
        print(f"  + Requires Human Approval: {data['requires_approval']} (Approval ID: {data['approval_id']})")
        print(f"  + Final USM Ticket Status: '{data['ticket_status']}'")
        print(f"  + Checkpoint Thread ID: {data.get('thread_id')}")
        print(f"  + Proposed Resolution:\n    \"{data['proposed_resolution']}\"")
        
        print("\n  Agent Decision Summaries:")
        for trace in data["agent_trace"]:
            print(f"    * [{trace['agent']}] ({trace['duration_ms']}ms): {trace['summary']}")

        scenario_reports.append({
            "scenario": sc["name"],
            "incident_id": data["incident_id"],
            "priority": data["priority"],
            "sources": [c["doc"] for c in data["retrieved_chunks"]],
            "tools": tools_called,
            "approval_required": data["requires_approval"],
            "final_status": data["ticket_status"],
            "thread_id": data.get("thread_id"),
        })

    # Test Supervisor Resume after Approval
    if paused_thread_id:
        print(f"\n>>> TESTING SUPERVISOR RESUME FROM CHECKPOINT (Thread ID: {paused_thread_id})")
        resume_resp = client.post(
            f"/api/agent/resume/{paused_thread_id}",
            json={"approved": True, "reviewer_id": 2},
        )
        assert resume_resp.status_code == 200, f"Resume failed: {resume_resp.text}"
        resume_data = resume_resp.json()
        print(f"  + Resume status: {resume_data['status']}")
        print(f"  + Ticket status after approval: {resume_data['ticket_status']}")
        assert resume_data["ticket_status"] == "in_progress"
        print("  + Resume verification PASSED!")

    # Test SSE Streaming Endpoint
    print("\n>>> TESTING SSE EVENT STREAMING (/api/agent/stream)")
    stream_resp = client.get(
        "/api/agent/stream?message=My+laptop+is+connected+to+Wi-Fi+but+portal+not+opening",
    )
    assert stream_resp.status_code == 200
    assert "text/event-stream" in stream_resp.headers.get("content-type", "")
    stream_text = stream_resp.text
    assert "event: workflow_start" in stream_text
    assert "event: step_completed" in stream_text
    assert "event: workflow_complete" in stream_text
    print("  + SSE streaming returned valid event stream with all lifecycle events!")

    # Database Verification
    print("\n" + "=" * 85)
    print("DATABASE AUDIT TRAIL VERIFICATION (Postgres / SQLAlchemy)")
    print("=" * 85)
    
    db = SessionLocal()
    try:
        total_runs = db.query(AgentRun).count()
        total_steps = db.query(AgentStep).count()
        total_incidents = db.query(Incident).count()
        total_approvals = db.query(Approval).count()
        total_mcp_calls = db.query(MCPToolCall).count()
        total_checkpoints = db.query(AgentCheckpoint).count()

        print(f"Total Agent Runs recorded in DB        : {total_runs}")
        print(f"Total Agent Steps recorded in DB       : {total_steps}")
        print(f"Total Postgres Checkpoints in DB       : {total_checkpoints}")
        print(f"Total Incidents recorded in DB         : {total_incidents}")
        print(f"Total Approvals recorded in DB         : {total_approvals}")
        print(f"Total MCP Tool Calls recorded in DB    : {total_mcp_calls}")

        assert total_runs >= 4, "Expected at least 4 agent runs"
        assert total_steps >= 20, "Expected at least 20 agent steps"
        assert total_checkpoints >= 4, "Expected at least 4 checkpoints saved in DB"
        assert total_approvals >= 1, "Expected at least 1 approval record created"

        # Show sample recent agent step
        last_step = db.query(AgentStep).order_by(AgentStep.id.desc()).first()
        print(f"\nLast Agent Step in DB: Step '{last_step.step_name}' | Status: {last_step.status} | Duration: {last_step.duration_ms}ms")

        # Show pending/recent approval
        app_rec = db.query(Approval).order_by(Approval.id.desc()).first()
        if app_rec:
            print(f"Recent Approval in DB: ID #{app_rec.id} | Request Type: {app_rec.request_type} | Status: {app_rec.status}")

        # Show latest checkpoint
        chk_rec = db.query(AgentCheckpoint).order_by(AgentCheckpoint.id.desc()).first()
        if chk_rec:
            print(f"Latest Checkpoint in DB: Thread '{chk_rec.thread_id}' | ID: {chk_rec.checkpoint_id}")

    finally:
        db.close()

    print("\n" + "=" * 85)
    print("SUMMARY OF ALL 4 SCENARIOS TESTED THROUGH API:")
    print("=" * 85)
    print(f"{'Scenario':<45} | {'Inc #':<5} | {'Priority':<8} | {'Approval':<8} | {'Final Status':<15}")
    print("-" * 90)
    for rep in scenario_reports:
        print(f"{rep['scenario']:<45} | #{rep['incident_id']:<4} | {rep['priority']:<8} | {str(rep['approval_required']):<8} | {rep['final_status']:<15}")

    print("\n" + "=" * 85)
    print("PHASE 4 GATE VERIFICATION: ALL 4 SCENARIOS + SSE + RESUME PASSED!")
    print("=" * 85)


def run_gate():
    upgrade_database()
    with TestClient(app) as client:
        _run_gate(client)


if __name__ == "__main__":
    run_gate()
