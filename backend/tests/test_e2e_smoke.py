"""
ResolveX AI – End-to-End Smoke Test
====================================
Runs all 4 acceptance scenarios through the FastAPI TestClient
and verifies the full pipeline: triage → knowledge → diagnostic → resolution → ticket.

Usage:
    python -m pytest backend/tests/test_e2e_smoke.py -v
"""

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.database import SessionLocal
from backend.api.auth import DEMO_ACCOUNTS

client = TestClient(app)
role_tokens = {}

# ── Helpers ──

def _seed_users():
    """Ensure demo users exist."""
    for email, role, password in DEMO_ACCOUNTS:
        response = client.post(
            "/api/auth/login",
            json={"email": email, "password": password, "role": role.value},
        )
        assert response.status_code == 200, response.text
        role_tokens[role.value] = response.json()["access_token"]
    client.headers.update({"Authorization": f"Bearer {role_tokens['employee']}"})


def _run_scenario(message: str) -> dict:
    """Post a message through the agent pipeline and return the response."""
    resp = client.post(
        "/api/agent/run",
        json={"message": message},
    )
    assert resp.status_code == 200, f"Agent run failed: {resp.text}"
    return resp.json()


# ── Setup ──

@pytest.fixture(scope="module", autouse=True)
def setup():
    global client
    with TestClient(app) as test_client:
        client = test_client
        _seed_users()
        yield


# ── Scenario 1: Wi-Fi / Portal ──

class TestScenario1_WiFiPortal:
    """My laptop is connected to Wi-Fi, but the company portal is not opening."""

    PROMPT = "My laptop is connected to Wi-Fi, but the company portal is not opening."

    @pytest.fixture(scope="class")
    @classmethod
    def result(cls):
        return _run_scenario(cls.PROMPT)

    def test_incident_created(self, result):
        assert result.get("incident_id") is not None or result.get("ticket_status")

    def test_priority_assigned(self, result):
        assert result["priority"] in ("P1", "P2", "P3", "P4", "critical", "high", "medium", "low")

    def test_category_classified(self, result):
        assert result["category"]

    def test_knowledge_retrieved(self, result):
        assert len(result["retrieved_chunks"]) > 0

    def test_diagnostics_run(self, result):
        assert len(result["diagnostics"]) > 0
        for d in result["diagnostics"]:
            assert d["simulated"] is True

    def test_resolution_proposed(self, result):
        assert result.get("proposed_resolution")

    def test_agent_trace_complete(self, result):
        agents_seen = {s["agent"].lower().replace(" agent", "") for s in result["agent_trace"]}
        assert "triage" in agents_seen
        assert "knowledge" in agents_seen

    def test_demo_mode_flagged(self, result):
        assert result["is_demo"] is True


# ── Scenario 2: VPN Failure ──

class TestScenario2_VPN:
    """I cannot connect to the corporate VPN."""

    PROMPT = "I cannot connect to the corporate VPN."

    @pytest.fixture(scope="class")
    @classmethod
    def result(cls):
        return _run_scenario(cls.PROMPT)

    def test_incident_created(self, result):
        assert result.get("incident_id") is not None or result.get("ticket_status")

    def test_vpn_category(self, result):
        assert result["category"].lower() in ("network", "vpn", "connectivity")

    def test_knowledge_retrieved(self, result):
        assert len(result["retrieved_chunks"]) > 0

    def test_diagnostics_simulated(self, result):
        for d in result["diagnostics"]:
            assert d["simulated"] is True

    def test_resolution_proposed(self, result):
        assert result.get("proposed_resolution")

    def test_continuity_assignment_selects_available_engineer(self, result):
        # Alex Rivera is on approved leave; Sarah Chen (or David Kim mgr) must be assigned
        assert result.get("assigned_engineer_name") is not None
        assert result["assigned_engineer_name"] != "Alex Rivera"

    def test_continuity_employee_notification(self, result):
        # Employee notification communicates operational reality without private leave details
        notification = result.get("employee_notification")
        assert notification is not None
        assert "INC-" in notification
        assert "annual leave" not in notification.lower()

    def test_continuity_exceptions_recorded(self, result):
        # Exception was detected and recorded
        exceptions = result.get("exceptions", [])
        assert len(exceptions) > 0
        assert any(e.get("type") in ("engineer_on_leave", "engineer_unavailable") for e in exceptions)


# ── Scenario 3: Software Install (requires approval) ──

class TestScenario3_SoftwareInstall:
    """I need Python installed on my company laptop."""

    PROMPT = "I need Python installed on my company laptop."

    @pytest.fixture(scope="class")
    @classmethod
    def result(cls):
        return _run_scenario(cls.PROMPT)

    def test_classified_as_service_request(self, result):
        # Might be intent=service_request or category=software
        cat = result["category"].lower()
        intent = result.get("intent", "").lower()
        assert "software" in cat or "service" in intent or "install" in cat

    def test_requires_approval(self, result):
        assert result["requires_approval"] is True

    def test_approval_id_assigned(self, result):
        assert result.get("approval_id") is not None

    def test_ticket_status_pending(self, result):
        status = result.get("ticket_status", "").lower()
        assert "pending" in status or "open" in status or "awaiting" in status


# ── Scenario 4: Production Outage (critical) ──

class TestScenario4_ProductionOutage:
    """The production application is unavailable."""

    PROMPT = "The production application is unavailable."

    @pytest.fixture(scope="class")
    @classmethod
    def result(cls):
        return _run_scenario(cls.PROMPT)

    def test_critical_priority(self, result):
        assert result["priority"] in ("P1", "critical")

    def test_server_health_checked(self, result):
        tool_names = [d["tool"] for d in result["diagnostics"]]
        assert any("server" in t.lower() or "health" in t.lower() for t in tool_names)

    def test_diagnostics_simulated(self, result):
        for d in result["diagnostics"]:
            assert d["simulated"] is True

    def test_resolution_proposed(self, result):
        assert result.get("proposed_resolution")

    def test_agent_trace_has_all_stages(self, result):
        agents_seen = {s["agent"].lower().replace(" agent", "") for s in result["agent_trace"]}
        assert "triage" in agents_seen
        assert "diagnostic" in agents_seen


# ── Cross-cutting: DB verification ──

class TestDatabaseIntegrity:
    """Verify DB rows were created by the pipeline runs."""

    def test_incidents_exist(self):
        resp = client.get(
            "/api/incidents/",
            headers={"Authorization": f"Bearer {role_tokens['support_engineer']}"},
        )
        assert resp.status_code == 200
        incidents = resp.json()
        assert len(incidents["items"]) >= 3  # at least 3 scenarios create incidents

    def test_agent_runs_logged(self):
        resp = client.get(
            "/api/agent/runs",
            headers={"Authorization": f"Bearer {role_tokens['support_engineer']}"},
        )
        assert resp.status_code == 200
        runs = resp.json()
        assert len(runs) >= 4

    def test_mcp_calls_logged(self):
        resp = client.get(
            "/api/mcp/calls",
            headers={"Authorization": f"Bearer {role_tokens['support_engineer']}"},
        )
        assert resp.status_code == 200
        calls = resp.json()
        assert len(calls) >= 8  # each scenario does multiple MCP calls

    def test_approvals_exist(self):
        resp = client.get(
            "/api/approvals/",
            headers={"Authorization": f"Bearer {role_tokens['support_engineer']}"},
        )
        assert resp.status_code == 200
        approvals = resp.json()
        # At least the software install scenario creates one
        assert len(approvals) >= 1

    def test_dashboard_stats_computed(self):
        resp = client.get(
            "/api/stats/dashboard",
            headers={"Authorization": f"Bearer {role_tokens['support_engineer']}"},
        )
        assert resp.status_code == 200
        stats = resp.json()
        assert stats.get("total_incidents", 0) >= 3

    def test_health_endpoint(self):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
