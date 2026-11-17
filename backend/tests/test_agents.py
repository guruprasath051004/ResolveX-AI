"""Pytest suite for Phase 4 LangGraph agents."""
import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.api.auth import DEMO_ACCOUNTS

@pytest.fixture
def api_client():
    with TestClient(app) as client:
        email, role, password = DEMO_ACCOUNTS[0]
        response = client.post(
            "/api/auth/login",
            json={"email": email, "password": password, "role": role.value},
        )
        assert response.status_code == 200
        client.headers.update({"Authorization": f"Bearer {response.json()['access_token']}"})
        yield client

def test_scenario_1_portal_unreachable(api_client):
    res = api_client.post(
        "/api/agent/run",
        json={"message": "My laptop is connected to Wi-Fi, but the company portal is not opening."},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["intent"] == "incident"
    assert data["category"] == "network"
    assert data["priority"] == "high"
    assert data["ticket_status"] == "in_progress"
    assert any(d["tool"] == "check_network_status" for d in data["diagnostics"])
    assert data["requires_approval"] is False
    assert len(data["agent_trace"]) >= 5
    assert data.get("thread_id") is not None

def test_scenario_2_vpn_failure(api_client):
    res = api_client.post(
        "/api/agent/run",
        json={"message": "I cannot connect to the corporate VPN."},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["intent"] == "incident"
    assert data["category"] == "vpn"
    assert data["priority"] == "medium"
    assert data["ticket_status"] == "in_progress"
    assert data["requires_approval"] is False
    assert len(data["retrieved_chunks"]) > 0

def test_scenario_3_software_request_approval(api_client):
    res = api_client.post(
        "/api/agent/run",
        json={"message": "I need Python installed on my company laptop."},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["intent"] == "service_request"
    assert data["category"] == "software"
    assert data["requires_approval"] is True
    assert data["approval_id"] is not None
    assert data["ticket_status"] == "pending_approval"

def test_scenario_4_production_outage(api_client):
    res = api_client.post(
        "/api/agent/run",
        json={"message": "The production application is unavailable."},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["intent"] == "incident"
    assert data["category"] == "server"
    assert data["priority"] == "critical"
    assert data["ticket_status"] == "investigating"
    assert any(d["tool"] == "check_server_health" for d in data["diagnostics"])

def test_sse_streaming_endpoint(api_client):
    res = api_client.get(
        "/api/agent/stream?message=VPN+connection+issue",
    )
    assert res.status_code == 200
    assert "text/event-stream" in res.headers.get("content-type", "")
    content = res.text
    assert "event: workflow_start" in content
    assert "event: step_completed" in content
    assert "event: workflow_complete" in content

def test_supervisor_resume(api_client):
    # Run scenario 3 to create a pending, thread-linked approval.
    run_res = api_client.post(
        "/api/agent/run",
        json={"message": "I need Python installed on my company laptop."},
    )
    assert run_res.status_code == 200
    result = run_res.json()
    approval_id = result.get("approval_id")
    thread_id = result.get("thread_id")
    assert approval_id is not None
    assert thread_id is not None

    # The approval decision authorizes and resumes the workflow.
    support_email, support_role, support_password = DEMO_ACCOUNTS[1]
    support_login = api_client.post(
        "/api/auth/login",
        json={"email": support_email, "password": support_password, "role": support_role.value},
    )
    support_headers = {"Authorization": f"Bearer {support_login.json()['access_token']}"}
    bypass_res = api_client.post(
        f"/api/agent/resume/{thread_id}",
        json={"approved": True},
        headers=support_headers,
    )
    assert bypass_res.status_code == 409

    resume_res = api_client.post(
        f"/api/approvals/{approval_id}/approve",
        json={"reason": "Support reviewed the request."},
        headers=support_headers,
    )
    assert resume_res.status_code == 200
    resume_data = resume_res.json()
    assert resume_data["status"] == "approved"
    assert '"status": "workflow_resumed"' in resume_data["execution_result"]
