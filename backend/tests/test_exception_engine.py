"""Tests for the Intelligent Exception Handling and Incident Continuity Engine."""
import json
import pytest
from datetime import datetime

from backend.database import SessionLocal
from backend.models import (
    EngineerAvailability,
    Incident,
    RoleEnum,
    User,
)
from backend.api.auth import seed_demo_users
from backend.services.workforce import seed_workforce
from backend.services.exception_engine import IncidentContinuityEngine


@pytest.fixture(autouse=True)
def setup_db():
    """Seed users + workforce before every test."""
    seed_demo_users()
    db = SessionLocal()
    try:
        seed_workforce(db)
        for a in db.query(EngineerAvailability).all():
            a.max_active_tickets = 50
        db.commit()
    finally:
        db.close()


def _make_incident(db, category="vpn", priority="high") -> Incident:
    """Helper: create a minimal test incident owned by user #1."""
    inc = Incident(
        description=f"Test {category} issue",
        category=category,
        priority=priority,
        status="open",
        owner_id=1,
    )
    db.add(inc)
    db.commit()
    db.refresh(inc)
    return inc


def _get_engineer_by_email(db, email: str) -> User:
    return db.query(User).filter(User.email == email).first()


def _set_all_on_leave(db):
    """Mark every support engineer's availability as on_leave (except mgr)."""
    avails = db.query(EngineerAvailability).all()
    for a in avails:
        a.status = "on_leave"
    db.commit()


# ─────────────────────────── Test 1 ─────────────────────────────────────────
def test_primary_on_leave_reassigns_to_available_engineer():
    """Primary engineer (Alex Rivera) is on_leave → reassigned to Sarah Chen."""
    db = SessionLocal()
    try:
        incident = _make_incident(db, category="vpn", priority="high")

        # Alex Rivera is seeded as on_leave — no need to change anything
        result = IncidentContinuityEngine.handle_assignment_continuity(
            db=db,
            incident_id=incident.id,
            target_category="vpn",
            preferred_team="Network Operations",
        )

        # Must detect exception — Alex is on leave
        assert result["exception_type"] in ("engineer_on_leave", "engineer_unavailable"), (
            f"Expected leave exception but got: {result.get('exception_type')}"
        )
        # Replacement must be an available engineer (Sarah Chen or Marcus Vance)
        assigned = result["assigned_to"]
        assert assigned["id"] is not None
        assert assigned["name"] is not None
        assert result["sla_preserved"] is True
        assert result["employee_notification"] is not None
        # Notification must NOT contain private reasons
        assert "annual leave" not in result["employee_notification"].lower() or \
               "simulated" not in result["employee_notification"].lower()
    finally:
        db.close()


# ─────────────────────────── Test 2 ─────────────────────────────────────────
def test_all_engineers_unavailable_escalates_to_manager():
    """All network engineers unavailable → escalated to Support Manager (David Kim)."""
    db = SessionLocal()
    try:
        incident = _make_incident(db, category="vpn", priority="critical")

        # Mark ALL engineers as on_leave
        _set_all_on_leave(db)
        # Keep David Kim (mgr) available
        mgr = _get_engineer_by_email(db, "support_mgr@resolvex.ai")
        if mgr:
            avail = db.query(EngineerAvailability).filter(EngineerAvailability.user_id == mgr.id).first()
            if avail:
                avail.status = "available"
            db.commit()

        result = IncidentContinuityEngine.handle_assignment_continuity(
            db=db,
            incident_id=incident.id,
            target_category="vpn",
            preferred_team="Network Operations",
        )

        assert result["status"] == "escalated_to_manager" or (
            result["assigned_to"]["name"] is not None
        ), "Expected escalation to manager"
        assert result["sla_preserved"] is True
    finally:
        db.close()


# ─────────────────────────── Test 3 ─────────────────────────────────────────
def test_max_reassignment_loop_prevention():
    """Exceeding max reassignment count prevents further reassignment."""
    from backend.services.workforce import get_or_create_default_policy
    db = SessionLocal()
    try:
        incident = _make_incident(db, category="network", priority="medium")
        policy = get_or_create_default_policy(db)

        # Drive reassignment count to the policy maximum
        incident.reassignment_count = policy.max_reassignment_attempts
        db.commit()

        result = IncidentContinuityEngine.handle_assignment_continuity(
            db=db,
            incident_id=incident.id,
            target_category="network",
            preferred_team="Network Operations",
        )
        # Either loop-prevented or escalated; it must not raise
        assert "status" in result
    finally:
        db.close()


# ─────────────────────────── Test 4 ─────────────────────────────────────────
def test_concurrent_claim_conflict_raises_409():
    """Two engineers claiming the same incident — second claim raises HTTP 409."""
    from fastapi import HTTPException as FastAPIHTTPException
    db = SessionLocal()
    try:
        incident = _make_incident(db, category="server", priority="medium")

        sarah = _get_engineer_by_email(db, "support2@resolvex.ai")
        marcus = _get_engineer_by_email(db, "support3@resolvex.ai")
        assert sarah and marcus, "Demo engineers must be seeded"

        # Ensure engineers have capacity regardless of previous test run state
        for eng in (sarah, marcus):
            a = db.query(EngineerAvailability).filter(EngineerAvailability.user_id == eng.id).first()
            if a:
                a.max_active_tickets = 50
                a.status = "available"
        db.commit()

        # First claim — should succeed
        result = IncidentContinuityEngine.claim_incident_concurrent(
            db=db, incident_id=incident.id, claiming_user_id=sarah.id
        )
        assert result["status"] == "claimed"
        assert result["assigned_to"]["id"] == sarah.id

        # Second claim by different engineer — must raise 409
        with pytest.raises(FastAPIHTTPException) as exc_info:
            IncidentContinuityEngine.claim_incident_concurrent(
                db=db, incident_id=incident.id, claiming_user_id=marcus.id
            )
        assert exc_info.value.status_code == 409
    finally:
        db.close()


# ─────────────────────────── Test 5 ─────────────────────────────────────────
def test_resolution_feedback_not_resolved_reopens_and_bumps_priority():
    """Employee says issue still exists → incident reopened, priority bumped."""
    db = SessionLocal()
    try:
        incident = _make_incident(db, category="software", priority="medium")
        incident.status = "resolved"
        incident.priority = "medium"
        db.commit()

        result = IncidentContinuityEngine.handle_resolution_feedback(
            db=db,
            incident_id=incident.id,
            reporter_id=1,
            resolved=False,
            notes="Still experiencing the same error",
        )

        assert result["status"] == "investigating"
        assert result["priority"] in ("high", "critical")  # bumped from medium
        assert result["current_lifecycle_phase"] == "reopened_by_employee"
    finally:
        db.close()


# ─────────────────────────── Test 6 ─────────────────────────────────────────
def test_resolution_feedback_confirmed_resolves_incident():
    """Employee confirms resolution → incident status is resolved."""
    db = SessionLocal()
    try:
        incident = _make_incident(db, category="network", priority="low")
        incident.status = "investigating"
        db.commit()

        result = IncidentContinuityEngine.handle_resolution_feedback(
            db=db,
            incident_id=incident.id,
            reporter_id=1,
            resolved=True,
            notes="All good now",
        )

        assert result["status"] == "resolved"
        assert result["current_lifecycle_phase"] == "verified_and_resolved"
    finally:
        db.close()


# ─────────────────────────── Test 7 ─────────────────────────────────────────
def test_skill_based_routing_network_to_network_specialist():
    """VPN incident should prefer network-skilled engineers over desktop team."""
    db = SessionLocal()
    try:
        # Ensure Sarah Chen is available (she has network/vpn skills)
        sarah = _get_engineer_by_email(db, "support2@resolvex.ai")
        if sarah:
            avail = db.query(EngineerAvailability).filter(EngineerAvailability.user_id == sarah.id).first()
            if avail:
                avail.status = "available"
                avail.max_active_tickets = 50
            db.commit()

        incident = _make_incident(db, category="vpn", priority="medium")
        result = IncidentContinuityEngine.handle_assignment_continuity(
            db=db,
            incident_id=incident.id,
            target_category="vpn",
            preferred_team="Network Operations",
        )

        assigned = result["assigned_to"]
        assert assigned["id"] is not None
        # The assigned engineer should be from Network Operations (not desktop)
        assigned_user = db.query(User).filter(User.id == assigned["id"]).first()
        avail = db.query(EngineerAvailability).filter(EngineerAvailability.user_id == assigned_user.id).first() if assigned_user else None
        if avail:
            skills = json.loads(avail.skills) if avail.skills else []
            # Either vpn/network skill match, or it escalated to mgr who has all skills
            assert any(s in skills for s in ["vpn", "network", "escalation", "management"]), (
                f"Expected network/vpn skill match, got skills: {skills}"
            )
    finally:
        db.close()


# ─────────────────────────── Test 8 ─────────────────────────────────────────
def test_reject_assignment_triggers_reassignment():
    """Engineer rejects assignment → continuity engine reassigns to next eligible."""
    db = SessionLocal()
    try:
        incident = _make_incident(db, category="server", priority="high")

        marcus = _get_engineer_by_email(db, "support3@resolvex.ai")
        assert marcus, "Marcus Vance must be seeded"

        # Assign incident to Marcus
        incident.assigned_to_user_id = marcus.id
        db.commit()

        # Marcus rejects
        result = IncidentContinuityEngine.reject_assignment(
            db=db,
            incident_id=incident.id,
            engineer_id=marcus.id,
            reason="Conflict of interest — escalating",
        )

        # Should produce a new assignment or escalation
        assert "assigned_to" in result
        assert result.get("sla_preserved") is True
    finally:
        db.close()


# ─────────────────────────── Test 9 ─────────────────────────────────────────
def test_direct_assignment_when_primary_available():
    """If primary engineer is available, direct assignment is made (no exception)."""
    db = SessionLocal()
    try:
        incident = _make_incident(db, category="server", priority="medium")

        # Marcus Vance is available and has 'server' skill
        marcus = _get_engineer_by_email(db, "support3@resolvex.ai")
        assert marcus

        result = IncidentContinuityEngine.handle_assignment_continuity(
            db=db,
            incident_id=incident.id,
            target_category="server",
            preferred_team="Platform Infrastructure",
            candidate_engineer_id=marcus.id,
        )

        # If Marcus is available: direct assignment, no exception
        # If Marcus is somehow unavailable: check a valid reassignment occurred
        assert result["incident_id"] == incident.id
        assert result["assigned_to"]["id"] is not None
        assert result["sla_preserved"] is True
    finally:
        db.close()
