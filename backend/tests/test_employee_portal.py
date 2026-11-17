import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import backend.database as database
from backend.api import auth, employee, incidents, approvals, knowledge, service_requests, stats
from backend.database.migrations import upgrade_database
from backend.models import Approval, AuditLog, Incident, RoleEnum, ServiceRequest, User


@pytest.fixture
def portal_client(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "employee-portal-test-secret")
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
    monkeypatch.setattr(service_requests, "SessionLocal", test_session)

    db = test_session()
    db.add_all(
        [
            User(
                email="employee.one@example.test",
                hashed_password=auth._hash_password("employee-one-password"),
                role=RoleEnum.employee,
                full_name="Employee One",
            ),
            User(
                email="employee.two@example.test",
                hashed_password=auth._hash_password("employee-two-password"),
                role=RoleEnum.employee,
            ),
            User(
                email="support@example.test",
                hashed_password=auth._hash_password("support-password"),
                role=RoleEnum.support_engineer,
            ),
            User(
                email="admin@example.test",
                hashed_password=auth._hash_password("admin-password"),
                role=RoleEnum.administrator,
            ),
        ]
    )
    db.commit()
    db.add_all(
        [
            Incident(
                category="network",
                priority="high",
                description="Employee one's portal issue",
                status="in_progress",
                owner_id=1,
                assigned_team="Network Operations",
            ),
            Incident(
                category="hardware",
                priority="medium",
                description="Employee two's laptop issue",
                status="open",
                owner_id=2,
            ),
        ]
    )
    db.commit()
    db.close()

    app = FastAPI()
    app.include_router(auth.router, prefix="/api")
    app.include_router(stats.router, prefix="/api")
    app.include_router(employee.router, prefix="/api")
    app.include_router(employee.admin_router, prefix="/api")
    app.include_router(incidents.router, prefix="/api")
    app.include_router(approvals.router, prefix="/api")
    app.include_router(service_requests.router, prefix="/api")
    app.include_router(knowledge.router)
    with TestClient(app) as client:
        employee_login = client.post(
            "/api/auth/login",
            json={
                "email": "employee.one@example.test",
                "password": "employee-one-password",
                "role": "employee",
            },
        )
        other_login = client.post(
            "/api/auth/login",
            json={
                "email": "employee.two@example.test",
                "password": "employee-two-password",
                "role": "employee",
            },
        )
        support_login = client.post(
            "/api/auth/login",
            json={
                "email": "support@example.test",
                "password": "support-password",
                "role": "support_engineer",
            },
        )
        client.headers.update(
            {"Authorization": f"Bearer {employee_login.json()['access_token']}"}
        )
        yield client, employee_login.json()["access_token"], other_login.json()["access_token"], support_login.json()["access_token"], test_session
    engine.dispose()


def test_employee_portal_requires_login_and_blocks_unauthorized_role(portal_client):
    client, employee_token, _, _, _ = portal_client
    client.headers.pop("Authorization")
    assert client.get("/api/employee/dashboard").status_code == 401
    assert client.get("/admin/knowledge/").status_code == 401
    assert client.post(
        "/api/admin/announcements/",
        json={"title": "Maintenance", "message": "Service window scheduled."},
        headers={"Authorization": f"Bearer {employee_token}"},
    ).status_code == 403
    me = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {employee_token}"},
    )
    assert me.status_code == 200
    assert me.json()["id"] == 1


def test_admin_only_endpoints_and_shared_support_visibility(portal_client):
    client, employee_token, _, support_token, _ = portal_client
    admin_login = client.post(
        "/api/auth/login",
        json={
            "email": "admin@example.test",
            "password": "admin-password",
            "role": "administrator",
        },
    )
    admin_token = admin_login.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    for token in (employee_token, support_token):
        headers = {"Authorization": f"Bearer {token}"}
        assert client.get("/admin/knowledge/", headers=headers).status_code == 403
        assert client.post(
            "/api/admin/announcements/",
            json={"title": "Maintenance", "message": "Service window scheduled."},
            headers=headers,
        ).status_code == 403

    employee_claims = jwt.get_unverified_claims(employee_token)
    employee_claims["role"] = "administrator"
    forged_role_token = jwt.encode(
        employee_claims,
        "employee-portal-test-secret",
        algorithm="HS256",
    )
    assert client.get(
        "/admin/knowledge/",
        headers={"Authorization": f"Bearer {forged_role_token}"},
    ).status_code == 403

    assert client.get("/admin/knowledge/", headers=admin_headers).status_code == 200
    assert client.get(
        "/api/incidents/",
        headers={"Authorization": f"Bearer {employee_token}"},
    ).status_code == 403
    support_incidents = client.get(
        "/api/incidents/",
        headers={"Authorization": f"Bearer {support_token}"},
    )
    admin_incidents = client.get("/api/incidents/", headers=admin_headers)
    assert support_incidents.status_code == admin_incidents.status_code == 200
    assert support_incidents.json()["total"] == admin_incidents.json()["total"] == 2
    assert client.get("/api/stats/dashboard", headers=admin_headers).json()["total_incidents"] == 2


def test_employee_tickets_and_dashboard_are_scoped_to_authenticated_owner(portal_client):
    client, employee_token, other_token, support_token, _ = portal_client
    response = client.get("/api/employee/tickets")
    assert response.status_code == 200
    assert [ticket["ticket_id"] for ticket in response.json()] == ["INC-000001"]
    assert client.get("/api/employee/tickets/INC-000002").status_code == 404

    dashboard = client.get("/api/employee/dashboard").json()
    assert dashboard["metrics"]["total_tickets"] == 1
    assert dashboard["metrics"]["in_progress_tickets"] == 1
    assert dashboard["recent_tickets"][0]["assigned_team"] == "Network Operations"

    assignment = client.patch(
        "/api/incidents/1",
        json={"assigned_team": "Enterprise Network"},
        headers={"Authorization": f"Bearer {support_token}"},
    )
    assert assignment.status_code == 200
    notifications = client.get("/api/employee/notifications").json()
    assert any(item["notification_type"] == "ticket_assignment" for item in notifications)

    admin_login = client.post(
        "/api/auth/login",
        json={
            "email": "admin@example.test",
            "password": "admin-password",
            "role": "administrator",
        },
    )
    admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}
    admin_incidents = client.get("/api/incidents/", headers=admin_headers)
    updated_incident = next(
        item for item in admin_incidents.json()["items"] if item["id"] == 1
    )
    assert updated_incident["assigned_team"] == "Enterprise Network"
    assert client.get("/api/stats/dashboard", headers=admin_headers).json()["total_incidents"] == 2

    other_response = client.get(
        "/api/employee/tickets",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert [ticket["ticket_id"] for ticket in other_response.json()] == ["INC-000002"]
    assert client.get(
        "/api/incidents/",
        headers={"Authorization": f"Bearer {employee_token}"},
    ).status_code == 403


def test_service_catalog_creates_owned_request_and_linked_pending_approval(portal_client):
    client, _, other_token, _, test_session = portal_client
    response = client.post(
        "/api/employee/service-requests",
        json={
            "category": "software_installation",
            "description": "Please install the approved Python development tools.",
        },
    )
    assert response.status_code == 201
    request = response.json()
    assert request["ticket_id"] == "SR-000001"
    assert request["status"] == "pending_approval"
    assert request["requires_approval"] is True
    assert request["approval_id"] is not None
    forged_owner = client.post(
        "/api/employee/service-requests",
        json={
            "category": "general_it_assistance",
            "description": "Please help configure this company workstation.",
            "owner_id": 2,
        },
    )
    assert forged_owner.status_code == 422

    db = test_session()
    try:
        stored_request = db.query(ServiceRequest).one()
        assert stored_request.owner_id == 1
    finally:
        db.close()

    own_approvals = client.get("/api/employee/approvals")
    assert own_approvals.status_code == 200
    assert own_approvals.json()[0]["ticket_id"] == "SR-000001"
    other_approvals = client.get(
        "/api/employee/approvals",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert other_approvals.json() == []


def test_approval_decisions_update_request_and_notify_requester(portal_client):
    client, _, _, support_token, test_session = portal_client
    request = client.post(
        "/api/employee/service-requests",
        json={
            "category": "account_access",
            "description": "Please grant access to the finance reporting application.",
        },
    ).json()
    decision = client.post(
        f"/api/approvals/{request['approval_id']}/approve",
        json={"reason": "Manager approval verified."},
        headers={"Authorization": f"Bearer {support_token}"},
    )
    assert decision.status_code == 200
    approvals = client.get("/api/employee/approvals").json()
    assert approvals[0]["status"] == "approved"
    assert approvals[0]["decision_reason"] == "Manager approval verified."
    admin_login = client.post(
        "/api/auth/login",
        json={
            "email": "admin@example.test",
            "password": "admin-password",
            "role": "administrator",
        },
    )
    admin_approvals = client.get(
        "/api/approvals/",
        headers={"Authorization": f"Bearer {admin_login.json()['access_token']}"},
    )
    assert next(item for item in admin_approvals.json() if item["id"] == request["approval_id"])[
        "status"
    ] == "approved"
    assert client.get("/api/employee/dashboard").json()["metrics"]["pending_service_requests"] == 1

    notifications = client.get("/api/employee/notifications").json()
    assert any(item["title"] == f"Approval #{request['approval_id']} approved" for item in notifications)
    assert client.get("/api/employee/approvals").json()[0]["requested_action"] == (
        "Please grant access to the finance reporting application."
    )

    updated = client.patch(
        f"/api/service_requests/{request['record_id']}",
        json={"status": "in_progress", "assigned_team": "Application Support"},
        headers={"Authorization": f"Bearer {support_token}"},
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "in_progress"
    comment = client.post(
        f"/api/service_requests/{request['record_id']}/comments",
        json={"message": "Access is being provisioned by the application team."},
        headers={"Authorization": f"Bearer {support_token}"},
    )
    assert comment.status_code == 201
    notifications = client.get("/api/employee/notifications").json()
    assert any(item["notification_type"] == "ticket_assignment" for item in notifications)
    assert any(item["notification_type"] == "support_comment" for item in notifications)
    ticket = client.get(f"/api/employee/tickets/{request['ticket_id']}")
    assert ticket.status_code == 200
    assert ticket.json()["conversation_history"][0]["author_role"] == "support_engineer"
    assert ticket.json()["assigned_team"] == "Application Support"

    db = test_session()
    try:
        stored_request = db.query(ServiceRequest).one()
        assert stored_request.status == "in_progress"
    finally:
        db.close()


def test_support_request_creation_uses_authenticated_owner_and_shared_approval(portal_client):
    client, _, _, support_token, test_session = portal_client
    support_headers = {"Authorization": f"Bearer {support_token}"}
    assert client.post(
        "/api/service_requests/",
        json={
            "type": "general_it_assistance",
            "description": "Help configure my workstation.",
        },
    ).status_code == 403
    forged_owner = client.post(
        "/api/service_requests/",
        json={
            "type": " software_installation ",
            "description": "Install the approved Python tools.",
            "owner_id": 1,
        },
        headers=support_headers,
    )
    assert forged_owner.status_code == 422

    created = client.post(
        "/api/service_requests/",
        json={
            "type": " software_installation ",
            "description": "Install the approved Python tools.",
        },
        headers=support_headers,
    )
    assert created.status_code == 200
    result = created.json()
    assert result["status"] == "pending_approval"
    assert result["approval_id"] is not None
    assert result["type"] == "software_installation"

    db = test_session()
    try:
        request = db.query(ServiceRequest).filter(ServiceRequest.id == result["id"]).one()
        approval = db.query(Approval).filter(Approval.id == result["approval_id"]).one()
        audit = (
            db.query(AuditLog)
            .filter(AuditLog.table_name == "service_requests", AuditLog.record_id == request.id)
            .one()
        )
        assert request.owner_id == 3
        assert approval.requester_id == 3
        assert approval.service_request_id == request.id
        assert approval.status == "pending"
        assert audit.user_id == 3
    finally:
        db.close()

    admin_login = client.post(
        "/api/auth/login",
        json={
            "email": "admin@example.test",
            "password": "admin-password",
            "role": "administrator",
        },
    )
    decision = client.post(
        f"/api/approvals/{result['approval_id']}/approve",
        json={"reason": "Reviewed and authorized."},
        headers={"Authorization": f"Bearer {admin_login.json()['access_token']}"},
    )
    assert decision.status_code == 200
    assert decision.json()["status"] == "approved"


def test_employee_profile_and_announcement_flow_are_persisted(portal_client):
    client, _, _, _, test_session = portal_client
    updated = client.patch(
        "/api/employee/profile",
        json={"full_name": "Employee One Updated", "phone": "+1 555 0100"},
    )
    assert updated.status_code == 200
    assert updated.json()["full_name"] == "Employee One Updated"
    assert updated.json()["phone"] == "+1 555 0100"

    admin_login = client.post(
        "/api/auth/login",
        json={"email": "admin@example.test", "password": "admin-password", "role": "administrator"},
    )
    announcement = client.post(
        "/api/admin/announcements/",
        json={"title": "Planned maintenance", "message": "Network maintenance begins at 20:00 UTC."},
        headers={"Authorization": f"Bearer {admin_login.json()['access_token']}"},
    )
    assert announcement.status_code == 201
    assert client.get("/api/employee/announcements").json()[0]["title"] == "Planned maintenance"

    db = test_session()
    try:
        profile = db.query(User).filter(User.id == 1).one()
        assert profile.department is None
    finally:
        db.close()
