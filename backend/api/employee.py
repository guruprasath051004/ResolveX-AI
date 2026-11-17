"""Authenticated employee portal endpoints backed by the shared USM tables."""

from datetime import datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from backend.api.auth import require_roles
from backend.database import get_db
from backend.models import (
    Announcement,
    Approval,
    Asset,
    AssetAssignment,
    AuditLog,
    Incident,
    Notification,
    RoleEnum,
    ServiceRequest,
    SLAPolicy,
    TicketComment,
    User,
)
from backend.services.request_policy import SENSITIVE_SERVICE_REQUEST_TYPES

router = APIRouter(prefix="/employee", tags=["employee-portal"])

ServiceCategory = Literal[
    "software_installation",
    "hardware_support",
    "network_support",
    "vpn_access",
    "account_access",
    "password_reset",
    "email_support",
    "application_access",
    "it_equipment_request",
    "general_it_assistance",
]

SERVICE_CATALOG = [
    {"id": "software_installation", "name": "Software Installation"},
    {"id": "hardware_support", "name": "Hardware Support"},
    {"id": "network_support", "name": "Network Support"},
    {"id": "vpn_access", "name": "VPN Access"},
    {"id": "account_access", "name": "Account Access"},
    {"id": "password_reset", "name": "Password Reset"},
    {"id": "email_support", "name": "Email Support"},
    {"id": "application_access", "name": "Application Access"},
    {"id": "it_equipment_request", "name": "IT Equipment Requests"},
    {"id": "general_it_assistance", "name": "General IT Assistance"},
]
OPEN_STATUSES = {"open", "new", "investigating", "assigned", "pending", "pending_approval", "awaiting_approval", "approved"}
IN_PROGRESS_STATUSES = {"in_progress", "in progress"}
RESOLVED_STATUSES = {"resolved", "closed", "completed"}


class ServiceRequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: ServiceCategory
    description: str = Field(min_length=10, max_length=3000)


class TicketCommentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=3000)


class TicketFeedback(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resolved: bool


class EmployeeProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, max_length=40)


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _ticket_id(prefix: str, record_id: int) -> str:
    return f"{prefix}-{record_id:06d}"


def _serialize_incident(incident: Incident) -> dict:
    now = datetime.utcnow()
    due_dates = [due for due in (incident.response_due_at, incident.resolution_due_at) if due]
    has_breach = any(due < now for due in due_dates) and incident.status not in RESOLVED_STATUSES
    return {
        "ticket_id": _ticket_id("INC", incident.id),
        "record_id": incident.id,
        "ticket_type": "incident",
        "category": incident.category,
        "priority": incident.priority,
        "description": incident.description,
        "status": incident.status,
        "assigned_team": incident.assigned_team,
        "created_at": _iso(incident.created_at),
        "updated_at": _iso(incident.updated_at),
        "response_due_at": _iso(incident.response_due_at),
        "resolution_due_at": _iso(incident.resolution_due_at),
        "resolution_summary": incident.resolution_summary,
        "sla_status": "breached" if has_breach else ("on_track" if due_dates else None),
    }


def _serialize_service_request(request: ServiceRequest) -> dict:
    now = datetime.utcnow()
    due_dates = [due for due in (request.response_due_at, request.resolution_due_at) if due]
    has_breach = any(due < now for due in due_dates) and request.status not in RESOLVED_STATUSES
    return {
        "ticket_id": _ticket_id("SR", request.id),
        "record_id": request.id,
        "ticket_type": "service_request",
        "category": request.type,
        "priority": request.priority,
        "description": request.description,
        "status": request.status,
        "assigned_team": request.assigned_team,
        "created_at": _iso(request.created_at),
        "updated_at": _iso(request.updated_at),
        "response_due_at": _iso(request.response_due_at),
        "resolution_due_at": _iso(request.resolution_due_at),
        "resolution_summary": request.resolution_summary,
        "sla_status": "breached" if has_breach else ("on_track" if due_dates else None),
    }


def _owned_ticket(db: Session, user_id: int, ticket_id: str):
    try:
        prefix, raw_id = ticket_id.split("-", 1)
        record_id = int(raw_id)
    except (ValueError, AttributeError) as exc:
        raise HTTPException(status_code=404, detail="Ticket not found") from exc

    if prefix == "INC":
        record = (
            db.query(Incident)
            .filter(Incident.id == record_id, Incident.owner_id == user_id)
            .first()
        )
        return "incident", record
    if prefix == "SR":
        record = (
            db.query(ServiceRequest)
            .filter(ServiceRequest.id == record_id, ServiceRequest.owner_id == user_id)
            .first()
        )
        return "service_request", record
    raise HTTPException(status_code=404, detail="Ticket not found")


def _ticket_comments(db: Session, kind: str, record_id: int) -> list[dict]:
    column = TicketComment.incident_id if kind == "incident" else TicketComment.service_request_id
    comments = (
        db.query(TicketComment, User)
        .join(User, TicketComment.author_id == User.id)
        .filter(column == record_id)
        .order_by(TicketComment.created_at.asc(), TicketComment.id.asc())
        .all()
    )
    return [
        {
            "id": comment.id,
            "message": comment.message,
            "author": author.full_name or author.email,
            "author_role": author.role.value,
            "created_at": _iso(comment.created_at),
        }
        for comment, author in comments
    ]


@router.get("/dashboard")
def get_employee_dashboard(
    user: User = Depends(require_roles(RoleEnum.employee)),
    db: Session = Depends(get_db),
):
    incidents = db.query(Incident).filter(Incident.owner_id == user.id)
    service_requests = db.query(ServiceRequest).filter(ServiceRequest.owner_id == user.id)
    total_incidents = incidents.count()
    total_requests = service_requests.count()
    open_tickets = incidents.filter(Incident.status.in_(OPEN_STATUSES)).count() + service_requests.filter(
        ServiceRequest.status.in_(OPEN_STATUSES)
    ).count()
    in_progress_tickets = incidents.filter(Incident.status.in_(IN_PROGRESS_STATUSES)).count() + service_requests.filter(
        ServiceRequest.status.in_(IN_PROGRESS_STATUSES)
    ).count()
    resolved_tickets = incidents.filter(Incident.status.in_(RESOLVED_STATUSES)).count() + service_requests.filter(
        ServiceRequest.status.in_(RESOLVED_STATUSES)
    ).count()
    pending_requests = service_requests.filter(
        ServiceRequest.status.in_({"open", "pending", "pending_approval", "awaiting_approval", "approved"})
    ).count()

    recent_incidents = incidents.order_by(Incident.updated_at.desc()).limit(5).all()
    recent_requests = service_requests.order_by(ServiceRequest.updated_at.desc()).limit(5).all()
    recent_tickets = sorted(
        [_serialize_incident(item) for item in recent_incidents]
        + [_serialize_service_request(item) for item in recent_requests],
        key=lambda item: item["updated_at"] or item["created_at"] or "",
        reverse=True,
    )[:6]

    activity = (
        db.query(Notification)
        .filter(Notification.user_id == user.id)
        .order_by(Notification.created_at.desc(), Notification.id.desc())
        .limit(6)
        .all()
    )
    approvals = (
        db.query(Approval)
        .filter(Approval.requester_id == user.id, Approval.status == "pending")
        .order_by(Approval.created_at.desc())
        .limit(5)
        .all()
    )
    approval_history = (
        db.query(Approval)
        .filter(Approval.requester_id == user.id)
        .order_by(Approval.created_at.desc())
        .limit(10)
        .all()
    )
    assignments = (
        db.query(AssetAssignment, Asset)
        .join(Asset, AssetAssignment.asset_id == Asset.id)
        .filter(AssetAssignment.user_id == user.id)
        .order_by(AssetAssignment.assigned_at.desc())
        .all()
    )
    service_usage = (
        db.query(ServiceRequest.type, func.count(ServiceRequest.id))
        .filter(ServiceRequest.owner_id == user.id)
        .group_by(ServiceRequest.type)
        .order_by(func.count(ServiceRequest.id).desc(), ServiceRequest.type.asc())
        .limit(5)
        .all()
    )
    announcements = (
        db.query(Announcement)
        .filter(Announcement.active.is_(True))
        .order_by(Announcement.published_at.desc())
        .limit(5)
        .all()
    )

    recommendations = []
    if open_tickets:
        recommendations.append(
            f"You have {open_tickets} open ticket(s). Check their status before submitting a duplicate request."
        )
    if approvals:
        recommendations.append(f"{len(approvals)} request(s) are waiting for an approval decision.")
    if not recommendations:
        recommendations.append("Describe an IT issue in AI Support or choose a service from the catalog.")

    return {
        "profile": {
            "id": user.id,
            "email": user.email,
            "role": user.role.value,
            "full_name": user.full_name,
            "department": user.department,
            "phone": user.phone,
        },
        "metrics": {
            "total_tickets": total_incidents + total_requests,
            "open_tickets": open_tickets,
            "in_progress_tickets": in_progress_tickets,
            "resolved_tickets": resolved_tickets,
            "pending_service_requests": pending_requests,
            "pending_approvals": db.query(Approval)
            .filter(Approval.requester_id == user.id, Approval.status == "pending")
            .count(),
        },
        "recent_tickets": recent_tickets,
        "recent_activity": [
            {
                "id": item.id,
                "title": item.title,
                "message": item.message,
                "notification_type": item.notification_type,
                "created_at": _iso(item.created_at),
                "read": item.read_at is not None,
            }
            for item in activity
        ],
        "announcements": [
            {"id": item.id, "title": item.title, "message": item.message, "published_at": _iso(item.published_at)}
            for item in announcements
        ],
        "frequently_used_services": [
            {"category": category, "request_count": count}
            for category, count in service_usage
        ],
        "service_catalog": SERVICE_CATALOG,
        "recommendations": recommendations,
        "pending_approvals": [
            {
                "id": item.id,
                "request_type": item.request_type,
                "status": item.status,
                "created_at": _iso(item.created_at),
                "decision_reason": item.decision_reason,
            }
            for item in approvals
        ],
        "approvals": [
            {
                "id": item.id,
                "request_type": item.request_type,
                "requested_action": (
                    db.query(ServiceRequest.description)
                    .filter(ServiceRequest.id == item.service_request_id)
                    .scalar()
                    if item.service_request_id
                    else (
                        db.query(Incident.description)
                        .filter(Incident.id == item.incident_id)
                        .scalar()
                        if item.incident_id
                        else None
                    )
                ),
                "status": item.status,
                "created_at": _iso(item.created_at),
                "decided_at": _iso(item.decided_at),
                "decision_reason": item.decision_reason,
                "ticket_id": _ticket_id("SR", item.service_request_id)
                if item.service_request_id
                else (_ticket_id("INC", item.incident_id) if item.incident_id else None),
            }
            for item in approval_history
        ],
        "assigned_assets": [
            {
                "id": asset.id,
                "type": asset.type,
                "model": asset.model,
                "serial_number": asset.serial_number,
                "assigned_at": _iso(assignment.assigned_at),
            }
            for assignment, asset in assignments
        ],
    }


@router.get("/tickets")
def list_employee_tickets(
    status: str | None = None,
    search: str | None = Query(default=None, max_length=200),
    user: User = Depends(require_roles(RoleEnum.employee)),
    db: Session = Depends(get_db),
):
    incident_query = db.query(Incident).filter(Incident.owner_id == user.id)
    request_query = db.query(ServiceRequest).filter(ServiceRequest.owner_id == user.id)
    if status:
        incident_query = incident_query.filter(Incident.status == status)
        request_query = request_query.filter(ServiceRequest.status == status)
    if search:
        pattern = f"%{search.strip()}%"
        incident_query = incident_query.filter(
            or_(Incident.description.ilike(pattern), Incident.category.ilike(pattern))
        )
        request_query = request_query.filter(
            or_(ServiceRequest.description.ilike(pattern), ServiceRequest.type.ilike(pattern))
        )
    tickets = [
        *[_serialize_incident(item) for item in incident_query.order_by(Incident.updated_at.desc()).all()],
        *[_serialize_service_request(item) for item in request_query.order_by(ServiceRequest.updated_at.desc()).all()],
    ]
    return sorted(tickets, key=lambda item: item["updated_at"] or item["created_at"] or "", reverse=True)


@router.get("/tickets/{ticket_id}")
def get_employee_ticket(
    ticket_id: str,
    user: User = Depends(require_roles(RoleEnum.employee)),
    db: Session = Depends(get_db),
):
    kind, record = _owned_ticket(db, user.id, ticket_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    ticket = _serialize_incident(record) if kind == "incident" else _serialize_service_request(record)
    ticket["conversation_history"] = _ticket_comments(db, kind, record.id)
    return ticket


@router.post("/tickets/{ticket_id}/comments", status_code=201)
def add_ticket_comment(
    ticket_id: str,
    payload: TicketCommentCreate,
    user: User = Depends(require_roles(RoleEnum.employee)),
    db: Session = Depends(get_db),
):
    kind, record = _owned_ticket(db, user.id, ticket_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=422, detail="Comment cannot be blank")
    comment = TicketComment(
        incident_id=record.id if kind == "incident" else None,
        service_request_id=record.id if kind == "service_request" else None,
        author_id=user.id,
        message=message,
    )
    db.add(comment)
    db.add(
        AuditLog(
            user_id=user.id,
            action="ADD_TICKET_COMMENT",
            table_name="ticket_comments",
            details=f"Added a comment to {ticket_id}",
        )
    )
    db.commit()
    db.refresh(comment)
    return {"id": comment.id, "message": comment.message, "created_at": _iso(comment.created_at)}


@router.post("/tickets/{ticket_id}/reopen")
def reopen_employee_ticket(
    ticket_id: str,
    user: User = Depends(require_roles(RoleEnum.employee)),
    db: Session = Depends(get_db),
):
    kind, record = _owned_ticket(db, user.id, ticket_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if record.status not in RESOLVED_STATUSES:
        raise HTTPException(status_code=409, detail="Only resolved tickets can be reopened")
    record.status = "open"
    if kind == "incident":
        record.resolved_at = None
    record.updated_at = datetime.utcnow()
    db.add(
        Notification(
            user_id=user.id,
            title=f"{ticket_id} reopened",
            message="Your request has been reopened for support follow-up.",
            notification_type="ticket_status",
            related_type=kind,
            related_id=record.id,
        )
    )
    db.add(
        AuditLog(
            user_id=user.id,
            action="REOPEN_TICKET",
            table_name="incidents" if kind == "incident" else "service_requests",
            record_id=record.id,
            details=f"Reopened {ticket_id}",
        )
    )
    db.commit()
    return {"ticket_id": ticket_id, "status": record.status}


@router.post("/tickets/{ticket_id}/feedback")
def record_ticket_feedback(
    ticket_id: str,
    payload: TicketFeedback,
    user: User = Depends(require_roles(RoleEnum.employee)),
    db: Session = Depends(get_db),
):
    kind, record = _owned_ticket(db, user.id, ticket_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Ticket not found")

    if kind == "incident":
        from backend.services.exception_engine import IncidentContinuityEngine
        cont_res = IncidentContinuityEngine.handle_resolution_feedback(
            db=db,
            incident_id=record.id,
            reporter_id=user.id,
            resolved=payload.resolved,
            notes="Employee confirmed resolution." if payload.resolved else "Employee reported issue is not resolved.",
        )
        return {
            "ticket_id": ticket_id,
            "status": cont_res.get("status", record.status),
            "priority": cont_res.get("priority", record.priority),
            "feedback_recorded": True,
        }

    now = datetime.utcnow()
    if payload.resolved:
        record.status = "resolved"
        if kind == "incident":
            record.resolved_at = now
    elif record.status in RESOLVED_STATUSES:
        record.status = "open"
        if kind == "incident":
            record.resolved_at = None
    record.updated_at = now
    feedback = "Employee confirmed the request is resolved." if payload.resolved else "Employee reported the issue is not resolved."
    db.add(
        TicketComment(
            incident_id=record.id if kind == "incident" else None,
            service_request_id=record.id if kind == "service_request" else None,
            author_id=user.id,
            message=feedback,
        )
    )
    db.add(
        AuditLog(
            user_id=user.id,
            action="TICKET_RESOLUTION_FEEDBACK",
            table_name="incidents" if kind == "incident" else "service_requests",
            record_id=record.id,
            details=feedback,
        )
    )
    support_users = db.query(User).filter(User.role == RoleEnum.support_engineer).all()
    if not payload.resolved:
        db.add_all(
            [
                Notification(
                    user_id=support_user.id,
                    title=f"{ticket_id} needs follow-up",
                    message=feedback,
                    notification_type="ticket_feedback",
                    related_type=kind,
                    related_id=record.id,
                )
                for support_user in support_users
            ]
        )
    db.commit()
    return {"ticket_id": ticket_id, "status": record.status, "feedback_recorded": True}


@router.get("/service-requests")
def list_employee_service_requests(
    user: User = Depends(require_roles(RoleEnum.employee)),
    db: Session = Depends(get_db),
):
    requests = (
        db.query(ServiceRequest)
        .filter(ServiceRequest.owner_id == user.id)
        .order_by(ServiceRequest.updated_at.desc())
        .all()
    )
    return [_serialize_service_request(item) for item in requests]


@router.post("/service-requests", status_code=201)
def create_employee_service_request(
    payload: ServiceRequestCreate,
    user: User = Depends(require_roles(RoleEnum.employee)),
    db: Session = Depends(get_db),
):
    category = payload.category
    description = payload.description.strip()
    if len(description) < 10:
        raise HTTPException(status_code=422, detail="Please provide at least 10 characters of request details")

    requires_approval = category in SENSITIVE_SERVICE_REQUEST_TYPES
    request = ServiceRequest(
        type=category,
        description=description,
        status="pending_approval" if requires_approval else "open",
        priority="medium",
        owner_id=user.id,
    )
    policy = db.query(SLAPolicy).filter(SLAPolicy.name.ilike("%P3%")).first()
    if policy:
        now = datetime.utcnow()
        request.response_due_at = now + timedelta(minutes=policy.response_minutes)
        request.resolution_due_at = now + timedelta(minutes=policy.resolution_minutes)
    db.add(request)
    db.flush()

    approval = None
    if requires_approval:
        approval = Approval(
            request_type=category,
            status="pending",
            requester_id=user.id,
            service_request_id=request.id,
        )
        db.add(approval)
        db.flush()

    ticket_id = _ticket_id("SR", request.id)
    db.add(
        Notification(
            user_id=user.id,
            title=f"{ticket_id} submitted",
            message="Your service request was recorded.",
            notification_type="service_request",
            related_type="service_request",
            related_id=request.id,
        )
    )
    if approval:
        db.add(
            Notification(
                user_id=user.id,
                title=f"Approval pending for {ticket_id}",
                message="This request needs Support Engineer or Administrator approval before fulfillment.",
                notification_type="approval",
                related_type="approval",
                related_id=approval.id,
            )
        )
    db.add(
        AuditLog(
            user_id=user.id,
            action="CREATE_SERVICE_REQUEST",
            table_name="service_requests",
            record_id=request.id,
            details=f"Submitted {category}",
        )
    )
    db.commit()
    db.refresh(request)
    return {
        **_serialize_service_request(request),
        "approval_id": approval.id if approval else None,
        "requires_approval": requires_approval,
    }


@router.get("/approvals")
def list_employee_approvals(
    user: User = Depends(require_roles(RoleEnum.employee)),
    db: Session = Depends(get_db),
):
    approvals = (
        db.query(Approval)
        .filter(Approval.requester_id == user.id)
        .order_by(Approval.created_at.desc())
        .all()
    )
    return [
        {
            "id": item.id,
            "request_type": item.request_type,
            "requested_action": (
                db.query(ServiceRequest.description)
                .filter(ServiceRequest.id == item.service_request_id)
                .scalar()
                if item.service_request_id
                else (
                    db.query(Incident.description)
                    .filter(Incident.id == item.incident_id)
                    .scalar()
                    if item.incident_id
                    else None
                )
            ),
            "status": item.status,
            "created_at": _iso(item.created_at),
            "decision_reason": item.decision_reason,
            "ticket_id": _ticket_id("SR", item.service_request_id) if item.service_request_id else (
                _ticket_id("INC", item.incident_id) if item.incident_id else None
            ),
        }
        for item in approvals
    ]


@router.get("/profile")
def get_employee_profile(
    user: User = Depends(require_roles(RoleEnum.employee)),
):
    return {
        "id": user.id,
        "email": user.email,
        "role": user.role.value,
        "full_name": user.full_name,
        "department": user.department,
        "phone": user.phone,
    }


@router.patch("/profile")
def update_employee_profile(
    payload: EmployeeProfileUpdate,
    user: User = Depends(require_roles(RoleEnum.employee)),
    db: Session = Depends(get_db),
):
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=422, detail="Provide at least one profile field to update")
    db_user = db.query(User).filter(User.id == user.id).first()
    if db_user is None:
        raise HTTPException(status_code=401, detail="User no longer exists")
    for field, value in changes.items():
        setattr(db_user, field, value.strip() if value else None)
    db.add(
        AuditLog(
            user_id=user.id,
            action="UPDATE_EMPLOYEE_PROFILE",
            table_name="users",
            record_id=db_user.id,
            details=f"Updated profile fields: {', '.join(sorted(changes))}",
        )
    )
    db.commit()
    db.refresh(db_user)
    return get_employee_profile(db_user)


@router.get("/assets")
def list_employee_assets(
    user: User = Depends(require_roles(RoleEnum.employee)),
    db: Session = Depends(get_db),
):
    assignments = (
        db.query(AssetAssignment, Asset)
        .join(Asset, AssetAssignment.asset_id == Asset.id)
        .filter(AssetAssignment.user_id == user.id)
        .order_by(AssetAssignment.assigned_at.desc())
        .all()
    )
    return [
        {
            "id": asset.id,
            "type": asset.type,
            "model": asset.model,
            "serial_number": asset.serial_number,
            "assigned_at": _iso(assignment.assigned_at),
        }
        for assignment, asset in assignments
    ]


@router.get("/notifications")
def list_employee_notifications(
    limit: int = Query(default=30, ge=1, le=100),
    user: User = Depends(require_roles(RoleEnum.employee)),
    db: Session = Depends(get_db),
):
    notifications = (
        db.query(Notification)
        .filter(Notification.user_id == user.id)
        .order_by(Notification.created_at.desc(), Notification.id.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": item.id,
            "title": item.title,
            "message": item.message,
            "notification_type": item.notification_type,
            "related_type": item.related_type,
            "related_id": item.related_id,
            "created_at": _iso(item.created_at),
            "read": item.read_at is not None,
        }
        for item in notifications
    ]


@router.post("/notifications/{notification_id}/read")
def mark_notification_read(
    notification_id: int,
    user: User = Depends(require_roles(RoleEnum.employee)),
    db: Session = Depends(get_db),
):
    notification = (
        db.query(Notification)
        .filter(Notification.id == notification_id, Notification.user_id == user.id)
        .first()
    )
    if notification is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    if notification.read_at is None:
        notification.read_at = datetime.utcnow()
        db.add(
            AuditLog(
                user_id=user.id,
                action="READ_NOTIFICATION",
                table_name="notifications",
                record_id=notification.id,
            )
        )
        db.commit()
    return {"id": notification.id, "read": True}


@router.get("/announcements")
def list_employee_announcements(
    user: User = Depends(require_roles(RoleEnum.employee)),
    db: Session = Depends(get_db),
):
    announcements = (
        db.query(Announcement)
        .filter(Announcement.active.is_(True))
        .order_by(Announcement.published_at.desc())
        .limit(20)
        .all()
    )
    return [
        {
            "id": item.id,
            "title": item.title,
            "message": item.message,
            "published_at": _iso(item.published_at),
        }
        for item in announcements
    ]


class AnnouncementCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=3, max_length=160)
    message: str = Field(min_length=5, max_length=3000)


admin_router = APIRouter(
    prefix="/admin/announcements",
    tags=["announcements"],
    dependencies=[Depends(require_roles(RoleEnum.administrator))],
)


@admin_router.post("/", status_code=201)
def create_announcement(
    payload: AnnouncementCreate,
    admin: User = Depends(require_roles(RoleEnum.administrator)),
    db: Session = Depends(get_db),
):
    announcement = Announcement(
        title=payload.title.strip(),
        message=payload.message.strip(),
        created_by=admin.id,
    )
    db.add(announcement)
    db.flush()
    employees = db.query(User).filter(User.role == RoleEnum.employee).all()
    db.add_all(
        [
            Notification(
                user_id=employee.id,
                title=announcement.title,
                message=announcement.message,
                notification_type="announcement",
                related_type="announcement",
                related_id=announcement.id,
            )
            for employee in employees
        ]
    )
    db.add(
        AuditLog(
            user_id=admin.id,
            action="CREATE_ANNOUNCEMENT",
            table_name="announcements",
            record_id=announcement.id,
        )
    )
    db.commit()
    db.refresh(announcement)
    return {
        "id": announcement.id,
        "title": announcement.title,
        "message": announcement.message,
        "published_at": _iso(announcement.published_at),
    }
