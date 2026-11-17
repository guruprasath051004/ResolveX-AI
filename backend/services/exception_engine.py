"""Intelligent Edge Case Handling and Incident Continuity Engine for ResolveX AI.

Follows the enterprise ITSM operational cycle:
Detect -> Understand -> Decide -> Act -> Verify -> Communicate -> Audit
"""
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException
from sqlalchemy.orm import Session

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
from backend.services.workforce import (
    find_eligible_engineers,
    get_engineer_workload,
    get_or_create_default_policy,
    is_engineer_available,
    seed_workforce,
)


class IncidentContinuityEngine:
    """Enterprise Incident Continuity Engine that detects operational exceptions,
    orchestrates intelligent reassignments, enforces concurrency protection,
    preserves SLA history, and produces transparent communications.
    """

    @staticmethod
    def handle_assignment_continuity(
        db: Session,
        incident_id: int,
        target_category: Optional[str] = None,
        preferred_team: Optional[str] = None,
        candidate_engineer_id: Optional[int] = None,
        actor_user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Execute the 7-step continuity cycle for incident assignment and exception recovery:
        1. Detect: Check if target/primary engineer is unavailable, on leave, or overloaded.
        2. Understand: Assess impact, skills required, and priority.
        3. Decide: Identify eligible replacement with skill match, workload balance, and loop prevention.
        4. Act: Execute atomic DB mutation preserving SLA clocks and timestamps.
        5. Verify: Confirm new ownership and persisted state.
        6. Communicate: Dispatch transparent, privacy-safe notifications to employee and engineer.
        7. Audit: Record full audit log and exception tracking row.
        """
        # Ensure workforce records are seeded
        seed_workforce(db)
        policy = get_or_create_default_policy(db)

        incident = db.query(Incident).filter(Incident.id == incident_id).first()
        if not incident:
            raise ValueError(f"Incident #{incident_id} not found")
        if incident.status in ("resolved", "closed"):
            raise ValueError(f"Cannot assign or reassign closed/resolved incident #{incident_id} (status: {incident.status})")

        category = target_category or incident.category or "general"
        team = preferred_team or incident.assigned_team or "IT Service Desk"
        now = datetime.utcnow()

        # Step 1: Detect
        # Determine candidate primary engineer
        primary_eng = None
        if candidate_engineer_id:
            primary_eng = db.query(User).filter(User.id == candidate_engineer_id).first()
        elif incident.assigned_to_user_id:
            primary_eng = db.query(User).filter(User.id == incident.assigned_to_user_id).first()
        else:
            # Find default primary engineer for team (e.g. Alex Rivera for Network Operations)
            primary_eng = (
                db.query(User)
                .join(EngineerAvailability, EngineerAvailability.user_id == User.id)
                .filter(
                    User.role == RoleEnum.support_engineer,
                    EngineerAvailability.team == team,
                )
                .order_by(User.id.asc())
                .first()
            )
            if not primary_eng:
                primary_eng = (
                    db.query(User)
                    .filter(User.role == RoleEnum.support_engineer)
                    .order_by(User.id.asc())
                    .first()
                )

        # Check availability of primary engineer
        exception_type = None
        exception_reason = None
        if primary_eng:
            is_avail, reason, avail = is_engineer_available(db, primary_eng.id, now=now)
            if not is_avail:
                exception_type = "engineer_on_leave" if "leave" in reason.lower() else "engineer_unavailable"
                exception_reason = reason

        # Step 2: Understand
        # If primary engineer is available and no exception, perform standard assignment
        if primary_eng and not exception_type:
            incident.assigned_to_user_id = primary_eng.id
            incident.assigned_team = team
            incident.current_lifecycle_phase = "assigned"
            db.commit()
            return {
                "status": "assigned_directly",
                "incident_id": incident.id,
                "assigned_to": {
                    "id": primary_eng.id,
                    "name": primary_eng.full_name or primary_eng.email,
                    "email": primary_eng.email,
                },
                "exception_handled": False,
                "sla_preserved": True,
            }

        # Step 3: Decide (Intelligent Replacement Search & Loop Prevention)
        # Collect previously attempted engineers for this incident to prevent loops
        attempted_ids = {
            row[0]
            for row in db.query(AssignmentException.attempted_engineer_id)
            .filter(
                AssignmentException.incident_id == incident.id,
                AssignmentException.attempted_engineer_id.isnot(None),
            )
            .all()
        }
        if primary_eng:
            attempted_ids.add(primary_eng.id)
        if incident.assigned_to_user_id:
            attempted_ids.add(incident.assigned_to_user_id)

        # Loop prevention check
        if incident.reassignment_count >= policy.max_reassignment_attempts:
            exception_type = "reassignment_loop_prevented"
            exception_reason = f"Maximum reassignment attempts ({policy.max_reassignment_attempts}) reached"

        eligible_replacements = []
        if exception_type != "reassignment_loop_prevented":
            eligible_replacements = find_eligible_engineers(
                db,
                category=category,
                priority=incident.priority,
                exclude_user_ids=list(attempted_ids),
                preferred_team=team,
                now=now,
            )

        replacement_eng = None
        action_taken = "reassigned"

        if eligible_replacements:
            top_candidate = eligible_replacements[0]
            replacement_eng = db.query(User).filter(User.id == top_candidate["user_id"]).first()
            new_team = top_candidate["team"]
        else:
            # No eligible engineer found in team: Escalate to Support Manager
            action_taken = "escalated_to_manager"
            mgr = (
                db.query(User)
                .filter(
                    User.role == RoleEnum.support_engineer,
                    User.department == "Support Management",
                )
                .first()
            )
            if not mgr:
                mgr = db.query(User).filter(User.role == RoleEnum.administrator).first()
            replacement_eng = mgr
            new_team = "Support Management"
            if not exception_type:
                exception_type = "no_eligible_engineer"
                exception_reason = "No available engineer matched required skills and workload limits"

        # Step 4: Act (Atomic DB Mutation Preserving SLA Clocks)
        prev_engineer_id = incident.assigned_to_user_id or (primary_eng.id if primary_eng else None)
        prev_engineer_name = (
            db.query(User.full_name).filter(User.id == prev_engineer_id).scalar()
            if prev_engineer_id
            else "Initial Assignee"
        )
        prev_team = incident.assigned_team

        incident.assigned_to_user_id = replacement_eng.id if replacement_eng else None
        incident.assigned_team = new_team
        incident.reassignment_count += 1
        incident.current_lifecycle_phase = "escalated" if action_taken == "escalated_to_manager" else "reassigned"
        incident.last_exception = exception_type
        if action_taken == "escalated_to_manager" and replacement_eng:
            incident.escalated_to_user_id = replacement_eng.id
            incident.escalation_level += 1

        # CRITICAL: Preserve original created_at, response_due_at, resolution_due_at, and priority
        incident.updated_at = now
        if incident.first_response_at is None:
            incident.first_response_at = now

        db.flush()

        # Step 5: Verify
        db.refresh(incident)
        if replacement_eng and incident.assigned_to_user_id != replacement_eng.id:
            db.rollback()
            raise RuntimeError("Verification failed: incident assignment state did not persist correctly")

        # Step 6: Communicate (Transparent, Contextual, Privacy-Safe Messages)
        ticket_code = f"INC-{incident.id:06d}"
        specialist_title = f"{category.upper()} Support Engineer" if category in ("vpn", "network") else "Support Engineer"

        if action_taken == "escalated_to_manager":
            employee_message = (
                f"Your incident {ticket_code} has been registered successfully. All primary support "
                f"engineers for this category are currently unavailable or at maximum workload. ResolveX AI has "
                f"escalated your incident to the Support Management Team ({replacement_eng.full_name if replacement_eng else 'Lead'}). "
                f"Your incident remains active, and its SLA tracking continues without interruption."
            )
        else:
            employee_message = (
                f"Your incident {ticket_code} has been registered successfully. The support engineer "
                f"initially selected for your issue is currently unavailable. ResolveX AI has identified "
                f"and reassigned your incident to an available {specialist_title} ({replacement_eng.full_name}). "
                f"Your incident remains active, and its SLA tracking continues."
            )

        # Notify employee (with duplicate notification guard)
        existing_emp_notif = (
            db.query(Notification.id)
            .filter(
                Notification.user_id == incident.owner_id,
                Notification.related_type == "incident",
                Notification.related_id == incident.id,
                Notification.notification_type == "ticket_reassignment",
                Notification.message == employee_message,
            )
            .first()
        )
        if not existing_emp_notif:
            db.add(
                Notification(
                    user_id=incident.owner_id,
                    title=f"Incident {ticket_code} reassigned",
                    message=employee_message,
                    notification_type="ticket_reassignment",
                    related_type="incident",
                    related_id=incident.id,
                    created_at=now,
                )
            )

        # Notify replacement engineer (with duplicate notification guard)
        if replacement_eng:
            eng_message = (
                f"Incident {ticket_code} ({incident.priority.upper()}) was reassigned to you due to "
                f"primary engineer unavailability. Category: {category}."
            )
            existing_eng_notif = (
                db.query(Notification.id)
                .filter(
                    Notification.user_id == replacement_eng.id,
                    Notification.related_type == "incident",
                    Notification.related_id == incident.id,
                    Notification.notification_type == "ticket_assignment",
                    Notification.message == eng_message,
                )
                .first()
            )
            if not existing_eng_notif:
                db.add(
                    Notification(
                        user_id=replacement_eng.id,
                        title=f"New incident assigned: {ticket_code}",
                        message=eng_message,
                        notification_type="ticket_assignment",
                        related_type="incident",
                        related_id=incident.id,
                        created_at=now,
                    )
                )

        # Record timeline event in incident_history
        db.add(
            IncidentHistory(
                incident_id=incident.id,
                changed_by=actor_user_id or (replacement_eng.id if replacement_eng else None),
                event_type="reassigned",
                from_value=f"{prev_engineer_name} ({prev_team})",
                to_value=f"{replacement_eng.full_name if replacement_eng else 'Unassigned'} ({new_team})",
                details=f"Reason: {exception_reason or 'Continuity Reassignment'}. Preserved original SLA.",
                created_at=now,
            )
        )

        # Step 7: Audit
        exception_record = AssignmentException(
            incident_id=incident.id,
            exception_type=exception_type or "engineer_unavailable",
            severity="high" if action_taken == "escalated_to_manager" else "warning",
            attempted_engineer_id=primary_eng.id if primary_eng else None,
            resolved_engineer_id=replacement_eng.id if replacement_eng else None,
            action_taken=action_taken,
            reason=exception_reason or "Intelligent continuity assignment triggered",
            details=json.dumps({
                "category": category,
                "priority": incident.priority,
                "previous_engineer": prev_engineer_name,
                "replacement_engineer": replacement_eng.full_name if replacement_eng else None,
                "reassignment_count": incident.reassignment_count,
                "sla_preserved": True,
            }),
            employee_message=employee_message,
            created_at=now,
        )
        db.add(exception_record)

        db.add(
            AuditLog(
                user_id=actor_user_id or (primary_eng.id if primary_eng else None),
                action="incident.continuity_reassigned",
                table_name="incidents",
                record_id=incident.id,
                timestamp=now,
                details=(
                    f"Exception '{exception_type}' handled: reassigned from {prev_engineer_name} "
                    f"to {replacement_eng.full_name if replacement_eng else 'Manager'}. SLA clocks preserved."
                ),
            )
        )

        db.commit()
        db.refresh(incident)
        db.refresh(exception_record)

        return {
            "status": action_taken,
            "incident_id": incident.id,
            "ticket_code": ticket_code,
            "exception_id": exception_record.id,
            "exception_type": exception_record.exception_type,
            "previous_engineer": prev_engineer_name,
            "assigned_to": {
                "id": replacement_eng.id if replacement_eng else None,
                "name": replacement_eng.full_name if replacement_eng else None,
                "email": replacement_eng.email if replacement_eng else None,
                "team": new_team,
            },
            "reassignment_count": incident.reassignment_count,
            "sla_preserved": True,
            "employee_notification": employee_message,
        }

    @staticmethod
    def claim_incident_concurrent(
        db: Session,
        incident_id: int,
        claiming_user_id: int,
        expected_lock_version: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Claim an unassigned or assigned incident with concurrency lock protection.
        Prevents race conditions where two engineers claim the same incident simultaneously.
        """
        now = datetime.utcnow()
        user = db.query(User).filter(User.id == claiming_user_id).first()
        if not user or user.role != RoleEnum.support_engineer:
            raise HTTPException(403, "Only support engineers can claim incidents")

        # Check availability
        is_avail, reason, avail = is_engineer_available(db, claiming_user_id, now=now)
        if not is_avail:
            raise HTTPException(422, f"Cannot claim ticket: {reason}")

        # Use row lock or lock version check
        incident = (
            db.query(Incident)
            .filter(Incident.id == incident_id)
            .with_for_update()
            .first()
        )
        if not incident:
            raise HTTPException(404, "Incident not found")

        # Concurrency conflict detection:
        # If another engineer has already claimed it
        if incident.assigned_to_user_id and incident.assigned_to_user_id != claiming_user_id:
            assignee = db.query(User).filter(User.id == incident.assigned_to_user_id).first()
            assignee_name = assignee.full_name or assignee.email if assignee else "another engineer"

            # Record exception
            db.add(
                AssignmentException(
                    incident_id=incident.id,
                    exception_type="concurrent_claim_conflict",
                    severity="warning",
                    attempted_engineer_id=claiming_user_id,
                    resolved_engineer_id=incident.assigned_to_user_id,
                    action_taken="claim_rejected_conflict",
                    reason=f"Concurrent claim attempt rejected. Ticket already assigned to {assignee_name}.",
                    employee_message=None,
                    created_at=now,
                )
            )
            db.add(
                AuditLog(
                    user_id=claiming_user_id,
                    action="incident.claim_conflict",
                    table_name="incidents",
                    record_id=incident.id,
                    timestamp=now,
                    details=f"Claim collision: attempted by {user.full_name}, already owned by {assignee_name}.",
                )
            )
            db.commit()
            raise HTTPException(
                status_code=409,
                detail=f"Conflict: Incident INC-{incident.id:06d} was just claimed by {assignee_name}. Refreshing view.",
            )

        # Version check if supplied
        if expected_lock_version is not None and incident.lock_version != expected_lock_version:
            raise HTTPException(
                status_code=409,
                detail=f"Incident INC-{incident.id:06d} was modified concurrently. Please refresh and try again.",
            )

        prev_owner_id = incident.assigned_to_user_id
        incident.assigned_to_user_id = claiming_user_id
        incident.status = "in_progress" if incident.status == "open" else incident.status
        incident.current_lifecycle_phase = "assigned"
        incident.lock_version += 1
        incident.updated_at = now
        if incident.first_response_at is None:
            incident.first_response_at = now

        db.add(
            IncidentHistory(
                incident_id=incident.id,
                changed_by=claiming_user_id,
                event_type="claimed",
                from_value=str(prev_owner_id) if prev_owner_id else "unassigned",
                to_value=user.full_name or user.email,
                details="Incident claimed by support engineer",
                created_at=now,
            )
        )
        db.add(
            AuditLog(
                user_id=claiming_user_id,
                action="incident.claimed",
                table_name="incidents",
                record_id=incident.id,
                timestamp=now,
                details=f"Claimed by {user.full_name or user.email}",
            )
        )
        db.commit()
        db.refresh(incident)

        return {
            "status": "claimed",
            "incident_id": incident.id,
            "ticket_code": f"INC-{incident.id:06d}",
            "assigned_to": {
                "id": user.id,
                "name": user.full_name or user.email,
                "email": user.email,
            },
            "lock_version": incident.lock_version,
        }

    @staticmethod
    def reject_assignment(
        db: Session,
        incident_id: int,
        engineer_id: int,
        reason: str,
    ) -> Dict[str, Any]:
        """Support engineer rejects an assignment; triggers immediate continuity reassignment."""
        now = datetime.utcnow()
        incident = db.query(Incident).filter(Incident.id == incident_id).first()
        if not incident:
            raise HTTPException(404, "Incident not found")

        rejecting_user = db.query(User).filter(User.id == engineer_id).first()
        engineer_name = rejecting_user.full_name if rejecting_user else f"User #{engineer_id}"

        # Record rejection exception
        db.add(
            AssignmentException(
                incident_id=incident.id,
                exception_type="assignment_rejected",
                severity="warning",
                attempted_engineer_id=engineer_id,
                action_taken="reassign_on_rejection",
                reason=reason or "Engineer rejected assignment",
                employee_message=None,
                created_at=now,
            )
        )
        db.add(
            IncidentHistory(
                incident_id=incident.id,
                changed_by=engineer_id,
                event_type="assignment_rejected",
                from_value=engineer_name,
                to_value="unassigned",
                details=f"Assignment rejected by engineer: {reason}",
                created_at=now,
            )
        )
        incident.assigned_to_user_id = None
        incident.current_lifecycle_phase = "reassignment_in_progress"
        db.flush()

        # Trigger automatic continuity reassignment excluding the rejecting engineer
        result = IncidentContinuityEngine.handle_assignment_continuity(
            db,
            incident_id=incident.id,
            target_category=incident.category,
            preferred_team=incident.assigned_team,
            candidate_engineer_id=None,
            actor_user_id=engineer_id,
        )
        return result

    @staticmethod
    def handle_resolution_feedback(
        db: Session,
        incident_id: int,
        reporter_id: int,
        resolved: bool,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Handle employee feedback on proposed resolution (e.g. 'Issue still exists' / Not Resolved)."""
        now = datetime.utcnow()
        incident = db.query(Incident).filter(Incident.id == incident_id).first()
        if not incident:
            raise HTTPException(404, "Incident not found")
        if incident.owner_id != reporter_id:
            raise HTTPException(403, "Only the incident reporter can submit resolution confirmation")

        ticket_code = f"INC-{incident.id:06d}"

        if resolved:
            incident.status = "resolved"
            incident.current_lifecycle_phase = "verified_and_resolved"
            incident.resolved_at = now
            db.add(
                IncidentHistory(
                    incident_id=incident.id,
                    changed_by=reporter_id,
                    event_type="resolution_confirmed",
                    from_value=incident.status,
                    to_value="resolved",
                    details=f"Resolution confirmed by employee. Notes: {notes or 'Confirmed resolved'}.",
                    created_at=now,
                )
            )
            db.add(
                AuditLog(
                    user_id=reporter_id,
                    action="incident.resolution_confirmed",
                    table_name="incidents",
                    record_id=incident.id,
                    timestamp=now,
                    details="Employee confirmed issue is resolved.",
                )
            )
            message = f"Thank you for confirming. Incident {ticket_code} is now verified and closed."
        else:
            # Employee reports issue still exists: reopen and escalate
            incident.status = "investigating"
            incident.current_lifecycle_phase = "reopened_by_employee"
            incident.resolved_at = None
            if incident.priority == "medium":
                incident.priority = "high"
            elif incident.priority == "high":
                incident.priority = "critical"

            db.add(
                AssignmentException(
                    incident_id=incident.id,
                    exception_type="solution_unsuccessful",
                    severity="high",
                    attempted_engineer_id=incident.assigned_to_user_id,
                    action_taken="reopened_and_priority_bumped",
                    reason=f"Employee verified issue still persists: {notes or 'No details provided'}",
                    employee_message=(
                        f"We understand the issue still persists. Incident {ticket_code} has been reopened, "
                        f"its priority adjusted to {incident.priority.upper()}, and the assigned support team "
                        f"has been alerted for immediate in-depth investigation."
                    ),
                    created_at=now,
                )
            )
            db.add(
                IncidentHistory(
                    incident_id=incident.id,
                    changed_by=reporter_id,
                    event_type="solution_rejected",
                    from_value="resolved",
                    to_value="investigating",
                    details=f"Employee reports issue still exists: {notes or 'Reopened for investigation'}",
                    created_at=now,
                )
            )
            db.add(
                Notification(
                    user_id=incident.owner_id,
                    title=f"Incident {ticket_code} reopened",
                    message=(
                        f"Your incident {ticket_code} has been reopened and prioritized for further "
                        f"investigation. The support team has been notified."
                    ),
                    notification_type="ticket_status",
                    related_type="incident",
                    related_id=incident.id,
                    created_at=now,
                )
            )
            if incident.assigned_to_user_id:
                db.add(
                    Notification(
                        user_id=incident.assigned_to_user_id,
                        title=f"Incident {ticket_code} reopened by employee",
                        message=f"Employee reported issue still exists: {notes or 'Investigation required'}",
                        notification_type="ticket_status",
                        related_type="incident",
                        related_id=incident.id,
                        created_at=now,
                    )
                )
            message = (
                f"We received your feedback that the issue is not resolved. Incident {ticket_code} "
                f"is reopened as {incident.priority.upper()} priority for priority engineering investigation."
            )

        db.commit()
        db.refresh(incident)
        return {
            "incident_id": incident.id,
            "ticket_code": ticket_code,
            "status": incident.status,
            "priority": incident.priority,
            "current_lifecycle_phase": incident.current_lifecycle_phase,
            "message": message,
        }
