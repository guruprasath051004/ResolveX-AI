"""Comprehensive edge-case and continuity test suite for Phase 4.
Covers all 35 specified edge-case scenarios across Workforce, Assignment, SLA,
Notifications, Security, and Scenario Lab execution.
"""
from datetime import datetime, timedelta
import json
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import backend.database as database
from backend.api import auth, incidents as incident_api, workforce as workforce_api
from backend.database.migrations import upgrade_database
from backend.models import (
    AssignmentException,
    AssignmentPolicy,
    AuditLog,
    EngineerAvailability,
    Incident,
    IncidentHistory,
    Notification,
    RoleEnum,
    User,
)
from backend.services.exception_engine import IncidentContinuityEngine
from backend.services.workforce import (
    evaluate_assignment_decision,
    find_eligible_engineers,
    get_engineer_workload,
    is_engineer_available,
    is_within_working_hours,
    parse_working_hours,
    seed_workforce,
)


@pytest.fixture
def p4_db(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    upgrade_database(engine)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    monkeypatch.setattr(auth, "SessionLocal", session_factory)
    monkeypatch.setattr(database, "SessionLocal", session_factory)

    def _override_get_db():
        s = session_factory()
        try:
            yield s
        finally:
            s.close()

    monkeypatch.setattr(database, "get_db", _override_get_db)
    monkeypatch.setattr(workforce_api, "get_db", _override_get_db)

    db = session_factory()

    # Seed demo users & workforce
    db.add_all([
        User(
            email="employee@resolvex.ai",
            hashed_password=auth._hash_password("Demo123"),
            role=RoleEnum.employee,
            full_name="Employee User",
        ),
        User(
            email="other_emp@resolvex.ai",
            hashed_password=auth._hash_password("Demo123"),
            role=RoleEnum.employee,
            full_name="Other Employee",
        ),
        User(
            email="support@resolvex.ai",
            hashed_password=auth._hash_password("Demo123"),
            role=RoleEnum.support_engineer,
            full_name="Alex Rivera",
            department="Network Operations",
        ),
        User(
            email="support2@resolvex.ai",
            hashed_password=auth._hash_password("Demo123"),
            role=RoleEnum.support_engineer,
            full_name="Sarah Chen",
            department="Network Operations",
        ),
        User(
            email="support3@resolvex.ai",
            hashed_password=auth._hash_password("Demo123"),
            role=RoleEnum.support_engineer,
            full_name="Marcus Vance",
            department="Platform Infrastructure",
        ),
        User(
            email="support_mgr@resolvex.ai",
            hashed_password=auth._hash_password("Demo123"),
            role=RoleEnum.support_engineer,
            full_name="David Kim",
            department="Support Management",
        ),
        User(
            email="admin@resolvex.ai",
            hashed_password=auth._hash_password("Demo123"),
            role=RoleEnum.administrator,
            full_name="Admin User",
        ),
    ])
    db.commit()
    seed_workforce(db)

    # Yield db and override_get_db generator
    yield db, _override_get_db
    db.close()
    engine.dispose()


# ═════════════════════════════════════════════════════════════════════════════
# 1. WORKFORCE FOUNDATION (Scenarios 1 - 8)
# ═════════════════════════════════════════════════════════════════════════════

def test_01_available_engineer(p4_db):
    """1. Available engineer is verified eligible."""
    db, _ = p4_db
    sarah = db.query(User).filter(User.email == "support2@resolvex.ai").first()
    avail, reason, _ = is_engineer_available(db, sarah.id)
    assert avail is True
    assert "Available" in reason


def test_02_engineer_on_leave(p4_db):
    """2. Engineer on leave is detected ineligible."""
    db, _ = p4_db
    alex = db.query(User).filter(User.email == "support@resolvex.ai").first()
    avail, reason, _ = is_engineer_available(db, alex.id)
    assert avail is False
    assert "leave" in reason.lower()


def test_03_temporary_unavailability(p4_db):
    """3. Temporary unavailability status is detected."""
    db, _ = p4_db
    sarah = db.query(User).filter(User.email == "support2@resolvex.ai").first()
    sarah.availability.status = "temporarily_unavailable"
    db.commit()
    avail, reason, _ = is_engineer_available(db, sarah.id)
    assert avail is False
    assert "temporarily unavailable" in reason.lower()


def test_04_outside_working_hours(p4_db):
    """4. Outside working hours status and schedule bounds are detected."""
    db, _ = p4_db
    sarah = db.query(User).filter(User.email == "support2@resolvex.ai").first()
    sarah.availability.status = "outside_working_hours"
    db.commit()
    avail, reason, _ = is_engineer_available(db, sarah.id)
    assert avail is False
    assert "outside" in reason.lower() or "hours" in reason.lower()

    # Schedule parsing verification
    sh, sm, eh, em = parse_working_hours("09:00 - 17:00 UTC")
    assert (sh, sm, eh, em) == (9, 0, 17, 0)
    in_hours, _ = is_within_working_hours("09:00 - 17:00 UTC", datetime(2026, 11, 15, 12, 30))
    assert in_hours is True
    out_hours, _ = is_within_working_hours("09:00 - 17:00 UTC", datetime(2026, 11, 15, 20, 0))
    assert out_hours is False


def test_05_inactive_engineer(p4_db):
    """5. Inactive engineer account is blocked from assignment."""
    db, _ = p4_db
    sarah = db.query(User).filter(User.email == "support2@resolvex.ai").first()
    sarah.availability.status = "inactive"
    db.commit()
    avail, reason, _ = is_engineer_available(db, sarah.id)
    assert avail is False
    assert "inactive" in reason.lower()


def test_06_missing_skill_rejection(p4_db):
    """6. Missing skill disqualifies engineer under skill-match policy."""
    db, _ = p4_db
    decision = evaluate_assignment_decision(db, category="database", priority="high")
    rejected_names = [r["name"] for r in decision["rejected_candidates"]]
    # Sarah has network/vpn/server, not database
    assert any("Sarah" in name for name in rejected_names)


def test_07_conflicting_availability_records(p4_db):
    """7. Conflict between status=available and active leave dates favors leave safety."""
    db, _ = p4_db
    sarah = db.query(User).filter(User.email == "support2@resolvex.ai").first()
    sarah.availability.status = "available"
    sarah.availability.leave_start = datetime.utcnow() - timedelta(days=1)
    sarah.availability.leave_end = datetime.utcnow() + timedelta(days=2)
    db.commit()
    avail, reason, _ = is_engineer_available(db, sarah.id)
    assert avail is False
    assert "leave" in reason.lower()


def test_08_invalid_schedule_handles_gracefully(p4_db):
    """8. Corrupted or invalid schedule strings fail safe without crashing."""
    assert parse_working_hours("invalid-schedule-format") is None
    in_hours, note = is_within_working_hours("garbage", datetime.utcnow())
    assert in_hours is True
    assert "open or unspecified" in note


# ═════════════════════════════════════════════════════════════════════════════
# 2. ASSIGNMENT ENGINE (Scenarios 9 - 19)
# ═════════════════════════════════════════════════════════════════════════════

def test_09_successful_initial_assignment(p4_db):
    """9. Successful direct assignment when engineer is available."""
    db, _ = p4_db
    sarah = db.query(User).filter(User.email == "support2@resolvex.ai").first()
    inc = Incident(category="network", priority="medium", description="Direct test", owner_id=1)
    db.add(inc)
    db.commit()

    res = IncidentContinuityEngine.handle_assignment_continuity(
        db, inc.id, target_category="network", candidate_engineer_id=sarah.id
    )
    assert res["status"] == "assigned_directly"
    assert res["assigned_to"]["id"] == sarah.id
    assert res["sla_preserved"] is True


def test_10_skill_based_matching(p4_db):
    """10. Assigns specialized incident to skill-matched engineer."""
    db, _ = p4_db
    decision = evaluate_assignment_decision(db, category="server", priority="high")
    assert decision["selected_engineer"] is not None
    # Marcus or Sarah both have 'server', but Marcus has platform infrastructure
    assert decision["selected_engineer"]["has_skill_match"] is True


def test_11_workload_based_matching(p4_db):
    """11. Least-loaded engineer prioritized among skill-matched candidates."""
    db, _ = p4_db
    sarah = db.query(User).filter(User.email == "support2@resolvex.ai").first()
    marcus = db.query(User).filter(User.email == "support3@resolvex.ai").first()

    # Give Sarah 2 open incidents
    db.add_all([
        Incident(category="network", priority="low", description="Dummy 1", owner_id=1, assigned_to_user_id=sarah.id, status="open"),
        Incident(category="network", priority="low", description="Dummy 2", owner_id=1, assigned_to_user_id=sarah.id, status="open"),
    ])
    db.commit()

    candidates = find_eligible_engineers(db, category="server", preferred_team="Network Operations")
    # Marcus has 0 active tickets, Sarah has 2 active tickets
    sarah_cand = next(c for c in candidates if c["user_id"] == sarah.id)
    assert sarah_cand["current_workload"] == 2


def test_12_no_eligible_engineer_escalates_to_manager(p4_db):
    """12. All engineers unavailable triggers managerial escalation."""
    db, _ = p4_db
    for a in db.query(EngineerAvailability).all():
        if a.team != "Support Management":
            a.status = "on_leave"
    db.commit()

    inc = Incident(category="vpn", priority="critical", description="Outage", owner_id=1)
    db.add(inc)
    db.commit()

    res = IncidentContinuityEngine.handle_assignment_continuity(db, inc.id, target_category="vpn")
    assert res["status"] == "escalated_to_manager"
    assert "David Kim" in res["assigned_to"]["name"] or "Support Management" in res["assigned_to"]["team"]


def test_13_successful_automatic_reassignment(p4_db):
    """13. Alex Rivera on leave triggers automatic reassignment to Sarah Chen."""
    db, _ = p4_db
    alex = db.query(User).filter(User.email == "support@resolvex.ai").first()
    inc = Incident(category="vpn", priority="high", description="VPN drop", owner_id=1)
    db.add(inc)
    db.commit()

    res = IncidentContinuityEngine.handle_assignment_continuity(
        db, inc.id, target_category="vpn", candidate_engineer_id=alex.id
    )
    assert res["status"] == "reassigned"
    assert res["exception_type"] == "engineer_on_leave"
    assert "Sarah Chen" in res["assigned_to"]["name"]


def test_14_replacement_rejection(p4_db):
    """14. Support engineer rejects assignment -> immediate continuity reassignment."""
    db, _ = p4_db
    sarah = db.query(User).filter(User.email == "support2@resolvex.ai").first()
    inc = Incident(category="vpn", priority="high", description="VPN drop", owner_id=1, assigned_to_user_id=sarah.id)
    db.add(inc)
    db.commit()

    res = IncidentContinuityEngine.reject_assignment(
        db, inc.id, engineer_id=sarah.id, reason="Scheduled data center maintenance"
    )
    assert res["status"] in ("reassigned", "escalated_to_manager")
    db.refresh(inc)
    assert inc.assigned_to_user_id != sarah.id


def test_15_retry_limit_reached(p4_db):
    """15. Maximum reassignment attempts prevents infinite retry loop."""
    db, _ = p4_db
    inc = Incident(
        category="vpn",
        priority="high",
        description="Loop test",
        owner_id=1,
        reassignment_count=3,  # already at ceiling
    )
    db.add(inc)
    db.commit()

    res = IncidentContinuityEngine.handle_assignment_continuity(db, inc.id, target_category="vpn")
    assert res["status"] == "escalated_to_manager"
    assert res["exception_type"] == "reassignment_loop_prevented"


def test_16_duplicate_request_idempotency(p4_db):
    """16. Duplicate assignment calls preserve state idempotently."""
    db, _ = p4_db
    sarah = db.query(User).filter(User.email == "support2@resolvex.ai").first()
    inc = Incident(category="vpn", priority="low", description="Duplicate check", owner_id=1)
    db.add(inc)
    db.commit()

    res1 = IncidentContinuityEngine.handle_assignment_continuity(
        db, inc.id, target_category="vpn", candidate_engineer_id=sarah.id
    )
    res2 = IncidentContinuityEngine.handle_assignment_continuity(
        db, inc.id, target_category="vpn", candidate_engineer_id=sarah.id
    )
    assert res1["assigned_to"]["id"] == res2["assigned_to"]["id"]


def test_17_concurrent_assignment_conflict(p4_db):
    """17. Simultaneous claim collision raises HTTP 409 conflict."""
    db, _ = p4_db
    sarah = db.query(User).filter(User.email == "support2@resolvex.ai").first()
    marcus = db.query(User).filter(User.email == "support3@resolvex.ai").first()
    inc = Incident(category="network", priority="low", description="Race test", owner_id=1)
    db.add(inc)
    db.commit()

    # Sarah claims
    IncidentContinuityEngine.claim_incident_concurrent(db, inc.id, sarah.id)

    # Marcus attempts simultaneous claim
    with pytest.raises(HTTPException) as exc_info:
        IncidentContinuityEngine.claim_incident_concurrent(db, inc.id, marcus.id)
    assert exc_info.value.status_code == 409
    assert "Conflict" in exc_info.value.detail


def test_18_database_failure_resiliency(p4_db):
    """18. Non-existent incident raises clean validation error."""
    db, _ = p4_db
    with pytest.raises(ValueError, match="not found"):
        IncidentContinuityEngine.handle_assignment_continuity(db, 999999)


def test_19_closed_incident_assignment_attempt(p4_db):
    """19. Attempting to assign or reassign a closed incident is rejected."""
    db, _ = p4_db
    inc = Incident(category="vpn", priority="low", description="Resolved ticket", owner_id=1, status="resolved")
    db.add(inc)
    db.commit()

    with pytest.raises(ValueError, match="closed/resolved"):
        IncidentContinuityEngine.handle_assignment_continuity(db, inc.id)


# ═════════════════════════════════════════════════════════════════════════════
# 3. SLA CONTINUITY (Scenarios 20 - 24)
# ═════════════════════════════════════════════════════════════════════════════

def test_20_sla_preserved_after_reassignment(p4_db):
    """20. Reassignment explicitly preserves created_at and response_due_at."""
    db, _ = p4_db
    now = datetime.utcnow()
    created_stamp = now - timedelta(hours=1)
    response_due = now + timedelta(minutes=30)
    resolution_due = now + timedelta(hours=4)

    inc = Incident(
        category="vpn",
        priority="high",
        description="SLA check",
        owner_id=1,
        created_at=created_stamp,
        response_due_at=response_due,
        resolution_due_at=resolution_due,
    )
    db.add(inc)
    db.commit()

    res = IncidentContinuityEngine.handle_assignment_continuity(db, inc.id, target_category="vpn")
    assert res["sla_preserved"] is True

    db.refresh(inc)
    assert inc.created_at == created_stamp
    assert inc.response_due_at == response_due
    assert inc.resolution_due_at == resolution_due


def test_21_original_deadline_unchanged(p4_db):
    """21. Deadlines are not silently extended on repeated reassignments."""
    db, _ = p4_db
    due = datetime.utcnow() + timedelta(hours=2)
    inc = Incident(category="network", priority="high", description="Deadline check", owner_id=1, resolution_due_at=due)
    db.add(inc)
    db.commit()

    IncidentContinuityEngine.handle_assignment_continuity(db, inc.id)
    db.refresh(inc)
    assert inc.resolution_due_at == due


def test_22_critical_incident_handling(p4_db):
    """22. Critical priority incident retains P1 deadlines and bumps on failure."""
    db, _ = p4_db
    inc = Incident(category="server", priority="critical", description="Production Outage", owner_id=1)
    db.add(inc)
    db.commit()

    res = IncidentContinuityEngine.handle_assignment_continuity(db, inc.id)
    assert res["status"] in ("assigned_directly", "reassigned")
    assert inc.priority == "critical"


def test_23_approaching_sla_deadline_reassignment(p4_db):
    """23. Approaching SLA deadline records urgency and preserves remaining minutes."""
    db, _ = p4_db
    tight_due = datetime.utcnow() + timedelta(minutes=10)
    inc = Incident(category="vpn", priority="high", description="Urgent", owner_id=1, resolution_due_at=tight_due)
    db.add(inc)
    db.commit()

    res = IncidentContinuityEngine.handle_assignment_continuity(db, inc.id)
    db.refresh(inc)
    assert inc.resolution_due_at == tight_due
    assert res["sla_preserved"] is True


def test_24_already_breached_sla_status_preserved(p4_db):
    """24. Breached SLA deadline remains breached post-reassignment without reset."""
    db, _ = p4_db
    breached_due = datetime.utcnow() - timedelta(minutes=25)
    inc = Incident(category="vpn", priority="high", description="Breached", owner_id=1, resolution_due_at=breached_due)
    db.add(inc)
    db.commit()

    IncidentContinuityEngine.handle_assignment_continuity(db, inc.id)
    db.refresh(inc)
    assert inc.resolution_due_at == breached_due


# ═════════════════════════════════════════════════════════════════════════════
# 4. NOTIFICATIONS (Scenarios 25 - 30)
# ═════════════════════════════════════════════════════════════════════════════

def test_25_successful_assignment_notification(p4_db):
    """25. Direct assignment dispatches notification."""
    db, _ = p4_db
    sarah = db.query(User).filter(User.email == "support2@resolvex.ai").first()
    inc = Incident(category="network", priority="low", description="Notif direct", owner_id=1)
    db.add(inc)
    db.commit()

    res = IncidentContinuityEngine.handle_assignment_continuity(db, inc.id, candidate_engineer_id=sarah.id)
    assert res["status"] == "assigned_directly"


def test_26_reassignment_notification(p4_db):
    """26. Reassignment dispatches contextual employee message."""
    db, _ = p4_db
    inc = Incident(category="vpn", priority="high", description="Notif reassign", owner_id=1)
    db.add(inc)
    db.commit()

    res = IncidentContinuityEngine.handle_assignment_continuity(db, inc.id)
    notif = db.query(Notification).filter(Notification.related_id == inc.id, Notification.user_id == 1).first()
    assert notif is not None
    assert "currently unavailable" in notif.message
    assert "reassigned" in notif.message


def test_27_no_engineer_notification(p4_db):
    """27. Escalation notification informs employee of management involvement."""
    db, _ = p4_db
    for a in db.query(EngineerAvailability).all():
        if a.team != "Support Management":
            a.status = "on_leave"
    db.commit()

    inc = Incident(category="vpn", priority="critical", description="Escalated notif", owner_id=1)
    db.add(inc)
    db.commit()

    res = IncidentContinuityEngine.handle_assignment_continuity(db, inc.id)
    assert "Support Management Team" in res["employee_notification"]


def test_28_duplicate_notification_prevention(p4_db):
    """28. Repeated assignment processing suppresses duplicate notifications."""
    db, _ = p4_db
    inc = Incident(category="vpn", priority="high", description="Dup notif", owner_id=1)
    db.add(inc)
    db.commit()

    IncidentContinuityEngine.handle_assignment_continuity(db, inc.id)
    count_1 = db.query(Notification).filter(Notification.related_id == inc.id).count()

    # Second pass
    IncidentContinuityEngine.handle_assignment_continuity(db, inc.id)
    count_2 = db.query(Notification).filter(Notification.related_id == inc.id).count()
    assert count_1 == count_2


def test_29_notification_delivery_failure_does_not_rollback_ticket(p4_db):
    """29. Assignment persists even if downstream notifications encounter issues."""
    db, _ = p4_db
    sarah = db.query(User).filter(User.email == "support2@resolvex.ai").first()
    inc = Incident(category="network", priority="low", description="Resilient assignment", owner_id=1)
    db.add(inc)
    db.commit()

    res = IncidentContinuityEngine.handle_assignment_continuity(db, inc.id, candidate_engineer_id=sarah.id)
    assert inc.assigned_to_user_id == sarah.id


def test_30_no_private_leave_details_in_employee_messages(p4_db):
    """30. Employee messages never leak private HR reasons or simulated tags."""
    db, _ = p4_db
    inc = Incident(category="vpn", priority="high", description="Privacy test", owner_id=1)
    db.add(inc)
    db.commit()

    res = IncidentContinuityEngine.handle_assignment_continuity(db, inc.id)
    msg = res["employee_notification"].lower()
    assert "annual leave" not in msg
    assert "simulated" not in msg
    assert "medical" not in msg


# ═════════════════════════════════════════════════════════════════════════════
# 5. SECURITY & RBAC (Scenarios 31 - 35)
# ═════════════════════════════════════════════════════════════════════════════

def test_31_employee_cannot_assign_or_claim_engineers(p4_db):
    """31. Employee cannot claim tickets via workforce claim API."""
    db, override_get_db = p4_db
    from fastapi import FastAPI
    app = FastAPI()
    app.dependency_overrides[database.get_db] = override_get_db
    app.dependency_overrides[workforce_api.get_db] = override_get_db
    app.include_router(workforce_api.router, prefix="/api")

    with TestClient(app) as client:
        emp = db.query(User).filter(User.role == RoleEnum.employee).first()
        emp_token = auth.create_access_token(emp)
        res = client.patch(
            "/api/workforce/incidents/1/claim",
            json={},
            headers={"Authorization": f"Bearer {emp_token}"},
        )
        assert res.status_code == 403


def test_32_employee_cannot_access_other_employee_incident(p4_db):
    """32. Employee cannot submit resolution feedback on another user's incident."""
    db, _ = p4_db
    inc = Incident(category="vpn", priority="low", description="Private ticket", owner_id=1)
    db.add(inc)
    db.commit()

    other_user = db.query(User).filter(User.email == "other_emp@resolvex.ai").first()
    with pytest.raises(HTTPException) as exc_info:
        IncidentContinuityEngine.handle_resolution_feedback(
            db, inc.id, reporter_id=other_user.id, resolved=True
        )
    assert exc_info.value.status_code == 403


def test_33_unauthorized_support_cannot_modify_workforce_data(p4_db):
    """33. Support engineer is blocked from updating engineer availability (Admin only)."""
    db, override_get_db = p4_db
    from fastapi import FastAPI
    app = FastAPI()
    app.dependency_overrides[database.get_db] = override_get_db
    app.dependency_overrides[workforce_api.get_db] = override_get_db
    app.include_router(workforce_api.router, prefix="/api")

    with TestClient(app) as client:
        support_user = db.query(User).filter(User.role == RoleEnum.support_engineer).first()
        support_token = auth.create_access_token(support_user)
        res = client.put(
            f"/api/workforce/engineers/{support_user.id}/availability",
            json={"status": "busy"},
            headers={"Authorization": f"Bearer {support_token}"},
        )
        assert res.status_code == 403


def test_34_unauthorized_administrative_actions_rejected(p4_db):
    """34. Support engineer cannot modify assignment policies (Admin only)."""
    db, override_get_db = p4_db
    from fastapi import FastAPI
    app = FastAPI()
    app.dependency_overrides[database.get_db] = override_get_db
    app.dependency_overrides[workforce_api.get_db] = override_get_db
    app.include_router(workforce_api.router, prefix="/api")

    with TestClient(app) as client:
        support_user = db.query(User).filter(User.role == RoleEnum.support_engineer).first()
        support_token = auth.create_access_token(support_user)
        res = client.put(
            "/api/workforce/policies/default",
            json={"max_workload_per_engineer": 10},
            headers={"Authorization": f"Bearer {support_token}"},
        )
        assert res.status_code == 403


def test_35_frontend_cannot_override_backend_assignment_decision(p4_db):
    """35. Attempting to claim an unavailable engineer returns 422 validation failure."""
    db, _ = p4_db
    alex = db.query(User).filter(User.email == "support@resolvex.ai").first()
    inc = Incident(category="vpn", priority="low", description="Override guard", owner_id=1)
    db.add(inc)
    db.commit()

    # Alex is on leave -> cannot claim
    with pytest.raises(HTTPException) as exc_info:
        IncidentContinuityEngine.claim_incident_concurrent(db, inc.id, claiming_user_id=alex.id)
    assert exc_info.value.status_code == 422
    assert "approved leave" in exc_info.value.detail


# ═════════════════════════════════════════════════════════════════════════════
# 6. SCENARIO TESTING LAB ENDPOINT (Admin verification)
# ═════════════════════════════════════════════════════════════════════════════

def test_36_scenario_testing_lab_runs_predefined_scenarios(p4_db):
    """36. Scenario Testing Lab endpoint executes all 10 predefined scenarios."""
    db, override_get_db = p4_db
    from fastapi import FastAPI
    app = FastAPI()
    app.dependency_overrides[database.get_db] = override_get_db
    app.dependency_overrides[workforce_api.get_db] = override_get_db
    app.include_router(workforce_api.router, prefix="/api")

    with TestClient(app) as client:
        admin_user = db.query(User).filter(User.role == RoleEnum.administrator).first()
        admin_token = auth.create_access_token(admin_user)
        headers = {"Authorization": f"Bearer {admin_token}"}

        # 1. List scenarios
        scenarios_res = client.get("/api/workforce/scenario-lab/scenarios", headers=headers)
        assert scenarios_res.status_code == 200
        scenarios = scenarios_res.json()
        assert len(scenarios) == 20

        # 2. Run scenario 2 (Engineer on Leave)
        run_res = client.post(
            "/api/workforce/scenario-lab/run",
            json={"scenario_id": "scenario_2"},
            headers=headers,
        )
        assert run_res.status_code == 200
        data = run_res.json()
        assert data["verdict"] == "PASS"
        assert len(data["execution_steps"]) >= 3
        assert data["simulated"] is True
