from datetime import datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import backend.database as database
from backend.api import agent, approvals, auth, incidents, mcp_monitor, sla, stats
from backend.database.migrations import upgrade_database
from backend.mcp_server import client as mcp_client_module
from backend.mcp_server import server as mcp_server_module
from backend.models import (
    AgentRun,
    Approval,
    Asset,
    AssetAssignment,
    Incident,
    IncidentHistory,
    RoleEnum,
    SLAPolicy,
    User,
)


@pytest.fixture
def support_client(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "support-workspace-test-secret")
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    upgrade_database(engine)
    test_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    monkeypatch.setattr(database, "SessionLocal", test_session)
    monkeypatch.setattr(auth, "SessionLocal", test_session)
    monkeypatch.setattr(incidents, "SessionLocal", test_session)
    monkeypatch.setattr(approvals, "SessionLocal", test_session)
    monkeypatch.setattr(agent, "SessionLocal", test_session)
    monkeypatch.setattr(mcp_client_module, "SessionLocal", test_session)
    monkeypatch.setattr(mcp_server_module, "SessionLocal", test_session)

    now = datetime.utcnow()
    db = test_session()
    db.add_all(
        [
            User(
                email="reporter@example.test",
                hashed_password=auth._hash_password("reporter-password"),
                role=RoleEnum.employee,
                full_name="Reporter One",
                department="Finance",
            ),
            User(
                email="support@example.test",
                hashed_password=auth._hash_password("support-password"),
                role=RoleEnum.support_engineer,
                full_name="Support One",
            ),
            User(
                email="support.two@example.test",
                hashed_password=auth._hash_password("support-password"),
                role=RoleEnum.support_engineer,
                full_name="Support Two",
            ),
            User(
                email="admin@example.test",
                hashed_password=auth._hash_password("admin-password"),
                role=RoleEnum.administrator,
                full_name="Administrator",
            ),
        ]
    )
    db.commit()
    asset = Asset(
        serial_number="LAP-100",
        type="laptop",
        manufacturer="Example",
        model="Pro 14",
        operating_system="Windows",
        status="in_service",
    )
    db.add(asset)
    db.commit()
    db.add(AssetAssignment(asset_id=asset.id, user_id=1))
    db.add_all(
        [
            SLAPolicy(
                name="Critical Severity (P1)",
                response_minutes=15,
                resolution_minutes=60,
            ),
            SLAPolicy(
                name="High Severity (P2)",
                response_minutes=30,
                resolution_minutes=240,
            ),
            SLAPolicy(
                name="Medium Severity (P3)",
                response_minutes=120,
                resolution_minutes=480,
            ),
            SLAPolicy(
                name="Low Severity (P4)",
                response_minutes=240,
                resolution_minutes=1440,
            ),
            Incident(
                category="network",
                priority="critical",
                description="Portal is unavailable",
                status="in_progress",
                owner_id=1,
                assigned_team="Network Operations",
                assigned_to_user_id=2,
                asset_id=asset.id,
                created_at=now - timedelta(minutes=20),
                response_due_at=now - timedelta(minutes=5),
                first_response_at=now - timedelta(minutes=10),
                resolution_due_at=now + timedelta(minutes=30),
            ),
            Incident(
                category="hardware",
                priority="high",
                description="Laptop screen flickers",
                status="resolved",
                owner_id=1,
                created_at=now - timedelta(minutes=60),
                response_due_at=now - timedelta(minutes=30),
                first_response_at=now - timedelta(minutes=35),
                resolved_at=now - timedelta(minutes=30),
                resolution_due_at=now - timedelta(minutes=40),
                resolution_summary="Replaced display cable.",
            ),
            Incident(
                category="server",
                priority="low",
                description="Internal server health check is degraded",
                status="investigating",
                owner_id=1,
                created_at=now - timedelta(minutes=80),
                response_due_at=now - timedelta(minutes=20),
                resolution_due_at=now - timedelta(minutes=5),
            ),
            Approval(request_type="software_installation", requester_id=1),
        ]
    )
    db.commit()
    db.add(
        AgentRun(
            agent_name="ResolveX USM Multi-Agent System",
            incident_id=2,
            status="completed",
            started_at=now - timedelta(minutes=40),
            finished_at=now - timedelta(minutes=30),
        )
    )
    db.commit()
    db.close()

    app = FastAPI()
    for router in (auth.router, incidents.router, stats.router, approvals.router, agent.router, mcp_monitor.router, sla.router):
        app.include_router(router, prefix="/api")
    with TestClient(app) as client:
        login = client.post(
            "/api/auth/login",
            json={
                "email": "support@example.test",
                "password": "support-password",
                "role": "support_engineer",
            },
        )
        client.headers.update({"Authorization": f"Bearer {login.json()['access_token']}"})
        yield client, test_session, login.json()["access_token"]
    engine.dispose()


def test_support_queue_filters_and_investigation_detail_are_database_backed(support_client):
    client, _, token = support_client
    own = client.get("/api/incidents/?assignment=mine&priority=critical")
    assert own.status_code == 200, own.text
    assert own.json()["total"] == 1
    assert own.json()["items"][0]["ticket_id"] == "INC-000001"

    detail = client.get("/api/incidents/1")
    assert detail.status_code == 200
    body = detail.json()
    assert body["employee"]["name"] == "Reporter One"
    assert body["employee"]["assets"][0]["name"] == "LAP-100"
    assert body["asset"]["operating_system"] == "Windows"

    denied = client.get("/api/incidents/1", headers={"Authorization": f"Bearer {client.post('/api/auth/login', json={'email': 'reporter@example.test', 'password': 'reporter-password', 'role': 'employee'}).json()['access_token']}"})
    assert denied.status_code == 403
    assert token


def test_assignment_and_resolution_require_audit_and_verification(support_client):
    client, test_session, _ = support_client
    unverified = client.patch("/api/incidents/1", json={"status": "resolved"})
    assert unverified.status_code == 422, unverified.text

    updated = client.patch(
        "/api/incidents/1",
        json={
            "assigned_to_user_id": 3,
            "assigned_team": "Platform Operations",
            "status": "resolved",
            "resolution_summary": "Verified service recovery with the reporter.",
            "resolution_verified": True,
        },
    )
    assert updated.status_code == 200
    assert updated.json()["assigned_to"]["id"] == 3
    assert updated.json()["resolved_at"] is not None

    db = test_session()
    try:
        history = db.query(IncidentHistory).filter(IncidentHistory.incident_id == 1).all()
        assert {entry.event_type for entry in history} >= {
            "assigned_to_user_id",
            "assigned_team",
            "status",
            "resolution_summary",
        }
    finally:
        db.close()


def test_investigation_uses_existing_incident_without_creating_a_ticket(
    support_client, monkeypatch
):
    client, test_session, _ = support_client
    captured = {}

    async def fake_workflow(**kwargs):
        captured.update(kwargs)
        return {
            "incident_id": kwargs["incident_id"],
            "employee_id": kwargs["employee_id"],
            "user_message": kwargs["user_message"],
            "intent": "incident",
            "category": "network",
            "priority": "critical",
            "retrieved_chunks": [],
            "diagnostics": [],
            "proposed_resolution": "Check the network gateway.",
            "requires_approval": False,
            "ticket_status": "unchanged",
            "agent_trace": [],
            "errors": [],
            "is_demo": True,
            "thread_id": kwargs["thread_id"],
        }

    monkeypatch.setattr(agent, "run_workflow", fake_workflow)
    response = client.post(
        "/api/agent/investigate/1",
        json={"message": "Please verify the gateway evidence."},
    )
    assert response.status_code == 200
    assert response.json()["incident_id"] == 1
    assert captured["read_only"] is True
    assert captured["employee_id"] == 1
    assert captured["actor_user_id"] == 2
    db = test_session()
    try:
        assert db.query(Incident).count() == 3
        assert db.query(Incident).filter(Incident.id == 1).one().status == "in_progress"
    finally:
        db.close()


def test_dashboard_and_sla_rates_have_no_fabricated_fallbacks(support_client):
    client, _, _ = support_client
    metrics = client.get("/api/stats/dashboard").json()
    assert metrics["total_incidents"] == 3
    assert metrics["open_incidents"] == 0
    assert metrics["in_progress_incidents"] == 2
    assert metrics["resolved_incidents"] == 1
    assert metrics["critical_incidents"] == 1
    assert metrics["approaching_sla_count"] == 1
    assert metrics["average_resolution_time_min"] == 30.0
    assert metrics["sla_response_compliance_pct"] == 100.0
    assert metrics["sla_resolution_compliance_pct"] == 0.0
    assert metrics["sla_compliance_pct"] == 50.0
    assert metrics["sla_compliance_sample_count"] == 2
    assert metrics["ai_automation_rate_pct"] == 100.0
    assert {item["name"]: item["value"] for item in metrics["priority_distribution"]} == {
        "P1 Critical": 1,
        "P2 High": 1,
        "P4 Low": 1,
    }
    assert {item["name"]: item["value"] for item in metrics["status_distribution"]} == {
        "In Progress": 2,
        "Resolved": 1,
    }

    policies = client.get("/api/sla/").json()
    high_priority_policy = next(policy for policy in policies if "P2" in policy["name"])
    targets = {
        policy["priority_code"]: (
            policy["response_minutes"],
            policy["resolution_minutes"],
        )
        for policy in policies
    }
    assert targets == {
        "P1": (15, 60),
        "P2": (30, 240),
        "P3": (120, 480),
        "P4": (240, 1440),
    }
    assert high_priority_policy["response_compliance_pct"] == 100.0
    assert high_priority_policy["resolution_compliance_pct"] == 0.0
    assert high_priority_policy["compliance_rate_pct"] == 50.0
    assert high_priority_policy["sample_count"] == 1
    risks = client.get("/api/sla/breaches").json()
    assert {item["risk"] for item in risks} == {"at_risk", "breached"}
    breached = next(item for item in risks if item["risk"] == "breached")
    assert breached["response_risk"] == "breached"
    assert breached["resolution_risk"] == "breached"
    assert breached["escalation_eligible"] is True


def test_dashboard_date_filter_and_operational_insights_use_sql_records(support_client):
    client, test_session, _ = support_client
    db = test_session()
    try:
        repeated = db.query(Incident).filter(Incident.id == 3).one()
        repeated.category = "network"
        repeated.asset_id = 1
        repeated.assigned_team = "Network Operations"
        old = db.query(Incident).filter(Incident.id == 2).one()
        old.created_at = datetime.utcnow() - timedelta(days=40)
        db.commit()
    finally:
        db.close()

    today = datetime.utcnow().date().isoformat()
    filtered = client.get(
        f"/api/stats/dashboard?start_date={today}&end_date={today}"
    )
    assert filtered.status_code == 200
    body = filtered.json()
    assert body["total_incidents"] == 2
    assert len(body["trend_chart"]) == 1
    assert body["trend_chart"][0]["incidents"] == 2

    signals = client.get("/api/stats/insights").json()["insights"]
    keys = {item["key"] for item in signals}
    assert "incident-volume-increase" in keys
    assert "recurring-category-network" in keys
    assert "increasing-category-network" in keys
    assert "repeated-asset-1" in keys
    assert "sla-deadline-risk" in keys
    assert all(item["evidence"] and item["recommendation"] for item in signals)


def test_operational_insights_identify_high_unresolved_team_workload(support_client):
    client, test_session, _ = support_client
    now = datetime.utcnow()
    db = test_session()
    try:
        db.add_all(
            [
                Incident(
                    category="network",
                    priority="medium",
                    description=f"Network follow-up {index}",
                    status="open",
                    owner_id=1,
                    assigned_team="Network Operations",
                    created_at=now,
                )
                for index in range(4)
            ]
        )
        db.commit()
    finally:
        db.close()

    signals = client.get("/api/stats/insights").json()["insights"]
    workload = next(
        item for item in signals if item["key"] == "team-workload-Network Operations"
    )
    assert workload["evidence"] == {
        "team": "Network Operations",
        "active_incidents": 5,
        "threshold": 5,
    }


def test_sla_history_is_zero_filled_and_rejects_invalid_date_range(support_client):
    client, _, token = support_client
    today = datetime.utcnow().date()
    start = (today - timedelta(days=2)).isoformat()
    end = today.isoformat()

    trends = client.get(f"/api/sla/trends?start_date={start}&end_date={end}")
    assert trends.status_code == 200
    points = trends.json()["trend"]
    assert len(points) == 3
    assert points[0]["response_sample_count"] == 0
    assert points[-1]["response_compliance_pct"] == 100.0
    assert points[-1]["resolution_compliance_pct"] == 0.0
    assert set(points[-1]["by_priority"]) == {"P1", "P2", "P3", "P4"}

    invalid = client.get(f"/api/stats/dashboard?start_date={end}&end_date={start}")
    assert invalid.status_code == 422
    assert client.get(
        "/api/stats/insights",
        headers={"Authorization": f"Bearer {token}"},
    ).status_code == 200


def test_sla_response_without_recorded_first_response_counts_as_missed(support_client):
    client, test_session, _ = support_client
    now = datetime.utcnow()
    db = test_session()
    try:
        db.add(
            Incident(
                category="security",
                priority="p1",
                description="Unanswered critical incident",
                status="resolved",
                owner_id=1,
                created_at=now - timedelta(hours=2),
                response_due_at=now - timedelta(hours=1),
                resolved_at=now - timedelta(minutes=10),
                resolution_due_at=now + timedelta(minutes=10),
            )
        )
        db.commit()
    finally:
        db.close()

    p1_policy = next(
        item for item in client.get("/api/sla/").json() if item["priority_code"] == "P1"
    )
    assert p1_policy["response_sample_count"] == 1
    assert p1_policy["response_compliance_pct"] == 0.0
    assert p1_policy["resolution_compliance_pct"] == 100.0


def test_sla_risks_are_ordered_by_the_next_unmet_deadline(support_client):
    client, test_session, _ = support_client
    now = datetime.utcnow()
    db = test_session()
    try:
        stale_response = Incident(
            category="network",
            priority="medium",
            description="Timely response with a later resolution deadline",
            status="in_progress",
            owner_id=1,
            created_at=now - timedelta(hours=2),
            response_due_at=now - timedelta(minutes=120),
            first_response_at=now - timedelta(minutes=125),
            resolution_due_at=now + timedelta(minutes=30),
        )
        upcoming_response = Incident(
            category="network",
            priority="medium",
            description="Unanswered incident with the nearest deadline",
            status="in_progress",
            owner_id=1,
            created_at=now - timedelta(minutes=10),
            response_due_at=now + timedelta(minutes=20),
            resolution_due_at=now + timedelta(minutes=60),
        )
        db.add_all([stale_response, upcoming_response])
        db.commit()
        stale_response_id = stale_response.id
        upcoming_response_id = upcoming_response.id
    finally:
        db.close()

    risks = client.get("/api/sla/breaches?window_minutes=180").json()
    positions = {item["incident_id"]: index for index, item in enumerate(risks)}
    assert positions[upcoming_response_id] < positions[stale_response_id]


def test_metrics_and_sla_endpoints_keep_existing_role_permissions(support_client):
    client, _, _ = support_client
    employee_login = client.post(
        "/api/auth/login",
        json={
            "email": "reporter@example.test",
            "password": "reporter-password",
            "role": "employee",
        },
    )
    employee_headers = {
        "Authorization": f"Bearer {employee_login.json()['access_token']}"
    }
    assert client.get("/api/stats/dashboard", headers=employee_headers).status_code == 403
    assert client.get("/api/stats/insights", headers=employee_headers).status_code == 403
    assert client.get("/api/sla/", headers=employee_headers).status_code == 403
    assert client.get("/api/sla/trends", headers=employee_headers).status_code == 403

    admin_login = client.post(
        "/api/auth/login",
        json={
            "email": "admin@example.test",
            "password": "admin-password",
            "role": "administrator",
        },
    )
    admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}
    assert client.get("/api/stats/dashboard", headers=admin_headers).status_code == 200
    assert client.get("/api/sla/trends", headers=admin_headers).status_code == 200


def test_escalation_is_queued_then_executed_only_after_admin_approval(support_client):
    client, test_session, _ = support_client
    requested = client.post(
        "/api/mcp/tools/escalate_incident/execute",
        json={
            "incident_id": 3,
            "arguments": {"escalation_reason": "Confirmed production impact"},
        },
    )
    assert requested.status_code == 200
    approval_id = requested.json()["approval_id"]
    db = test_session()
    try:
        assert db.query(Incident).filter(Incident.id == 3).one().priority == "low"
    finally:
        db.close()

    self_approval = client.post(f"/api/approvals/{approval_id}/approve", json={})
    assert self_approval.status_code == 403

    admin_login = client.post(
        "/api/auth/login",
        json={
            "email": "admin@example.test",
            "password": "admin-password",
            "role": "administrator",
        },
    )
    approved = client.post(
        f"/api/approvals/{approval_id}/approve",
        json={"reason": "Impact confirmed; escalation authorized."},
        headers={"Authorization": f"Bearer {admin_login.json()['access_token']}"},
    )
    assert approved.status_code == 200
    assert approved.json()["execution_result"]
    db = test_session()
    try:
        assert db.query(Incident).filter(Incident.id == 3).one().priority == "critical"
        assert db.query(Approval).filter(Approval.id == approval_id).one().status == "approved"
    finally:
        db.close()
