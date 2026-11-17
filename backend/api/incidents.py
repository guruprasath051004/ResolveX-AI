from datetime import datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import case, cast, or_, String
from sqlalchemy.orm import Session

from backend.api.auth import require_roles
from backend.database import SessionLocal, get_db
from backend.models import (
    AgentRun,
    AgentStep,
    Asset,
    AssetAssignment,
    AuditLog,
    Incident,
    IncidentHistory,
    MCPToolCall,
    Notification,
    RoleEnum,
    TicketComment,
    User,
)

router = APIRouter(prefix="/incidents", tags=["incidents"])


class IncidentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str | None = None
    priority: str | None = None
    assigned_team: str | None = None
    assigned_to_user_id: int | None = None
    asset_id: int | None = None
    resolution_summary: str | None = None
    resolution_verified: bool | None = None


class CommentCreate(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


def _sla_data(incident: Incident) -> dict:
    due = incident.resolution_due_at
    if due is None:
        return {"risk": "unknown", "minutes_remaining": None, "breached": False}
    remaining = int((due - datetime.utcnow()).total_seconds() // 60)
    if incident.status in {"resolved", "closed", "cancelled"}:
        return {"risk": "closed", "minutes_remaining": remaining, "breached": remaining < 0}
    risk = "breached" if remaining < 0 else "at_risk" if remaining <= 60 else "on_track"
    return {"risk": risk, "minutes_remaining": remaining, "breached": remaining < 0}


def _summary(incident: Incident, employee: User, db: Session) -> dict:
    assignee = db.query(User).filter(User.id == incident.assigned_to_user_id).first()
    asset = db.query(Asset).filter(Asset.id == incident.asset_id).first()
    return {
        "id": incident.id,
        "ticket_id": f"INC-{incident.id:06d}",
        "title": incident.description.splitlines()[0][:120],
        "description": incident.description,
        "status": incident.status,
        "priority": incident.priority,
        "category": incident.category,
        "assigned_team": incident.assigned_team,
        "assigned_to": (
            {
                "id": assignee.id,
                "name": assignee.full_name or assignee.email,
                "email": assignee.email,
            }
            if assignee
            else None
        ),
        "employee": {
            "id": employee.id,
            "name": employee.full_name or employee.email,
            "email": employee.email,
            "department": employee.department,
        },
        "asset": (
            {
                "id": asset.id,
                "name": asset.serial_number,
                "type": asset.type,
                "manufacturer": asset.manufacturer,
                "model": asset.model,
                "operating_system": asset.operating_system,
                "status": asset.status,
            }
            if asset
            else None
        ),
        "created_at": incident.created_at.isoformat() if incident.created_at else None,
        "updated_at": incident.updated_at.isoformat() if incident.updated_at else None,
        "first_response_at": (
            incident.first_response_at.isoformat() if incident.first_response_at else None
        ),
        "resolved_at": incident.resolved_at.isoformat() if incident.resolved_at else None,
        "response_due_at": (
            incident.response_due_at.isoformat() if incident.response_due_at else None
        ),
        "resolution_due_at": (
            incident.resolution_due_at.isoformat() if incident.resolution_due_at else None
        ),
        "resolution_summary": incident.resolution_summary,
        "lock_version": getattr(incident, "lock_version", 0),
        "sla": _sla_data(incident),
    }


@router.get("/")
def list_incidents(
    priority: str | None = None,
    category: str | None = None,
    status: str | None = None,
    team: str | None = None,
    assignment: Literal["all", "mine", "unassigned"] = "all",
    sla_risk: Literal["all", "on_track", "at_risk", "breached", "unknown"] = "all",
    search: str | None = None,
    sort_by: Literal["created_at", "priority", "resolution_due_at"] = "created_at",
    sort_order: Literal["asc", "desc"] = "desc",
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.support_engineer, RoleEnum.administrator)),
):
    query = db.query(Incident, User).join(User, Incident.owner_id == User.id)
    if priority:
        query = query.filter(Incident.priority == priority)
    if category:
        query = query.filter(Incident.category == category)
    if status:
        query = query.filter(Incident.status == status)
    if team:
        query = query.filter(Incident.assigned_team == team)
    if assignment == "mine":
        query = query.filter(Incident.assigned_to_user_id == current_user.id)
    elif assignment == "unassigned":
        query = query.filter(
            Incident.assigned_to_user_id.is_(None), Incident.assigned_team.is_(None)
        )
    if search:
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                cast(Incident.id, String).ilike(term),
                Incident.description.ilike(term),
                Incident.category.ilike(term),
                User.full_name.ilike(term),
                User.email.ilike(term),
            )
        )
    if sla_risk != "all":
        now = datetime.utcnow()
        active = Incident.status.notin_(["resolved", "closed", "cancelled"])
        if sla_risk == "unknown":
            query = query.filter(Incident.resolution_due_at.is_(None))
        elif sla_risk == "breached":
            query = query.filter(active, Incident.resolution_due_at < now)
        elif sla_risk == "at_risk":
            query = query.filter(
                active,
                Incident.resolution_due_at >= now,
                Incident.resolution_due_at <= now + timedelta(minutes=60),
            )
        else:
            query = query.filter(active, Incident.resolution_due_at > now + timedelta(minutes=60))

    total = query.count()
    column = {
        "created_at": Incident.created_at,
        "priority": case(
            (Incident.priority.in_(["critical", "p1"]), 1),
            (Incident.priority.in_(["high", "p2"]), 2),
            (Incident.priority.in_(["medium", "p3"]), 3),
            else_=4,
        ),
        "resolution_due_at": Incident.resolution_due_at,
    }[sort_by]
    query = query.order_by(column.asc() if sort_order == "asc" else column.desc())
    records = query.offset(offset).limit(limit).all()
    return {
        "items": [_summary(incident, employee, db) for incident, employee in records],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/support-users")
def list_support_users(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(RoleEnum.support_engineer, RoleEnum.administrator)),
):
    users = (
        db.query(User)
        .filter(User.role == RoleEnum.support_engineer)
        .order_by(User.full_name, User.email)
        .all()
    )
    return [{"id": user.id, "name": user.full_name or user.email, "email": user.email} for user in users]


@router.get("/{incident_id}")
def get_incident(
    incident_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(RoleEnum.support_engineer, RoleEnum.administrator)),
):
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(404, "Incident not found")
    employee = db.query(User).filter(User.id == incident.owner_id).first()
    response = _summary(incident, employee, db)
    assignments = (
        db.query(Asset)
        .join(AssetAssignment, AssetAssignment.asset_id == Asset.id)
        .filter(AssetAssignment.user_id == incident.owner_id)
        .all()
    )
    response["employee"]["assets"] = [
        {
            "id": asset.id,
            "name": asset.serial_number,
            "type": asset.type,
            "manufacturer": asset.manufacturer,
            "model": asset.model,
            "operating_system": asset.operating_system,
            "status": asset.status,
        }
        for asset in assignments
    ]
    response["history"] = [
        {
            "event_type": entry.event_type,
            "from_value": entry.from_value,
            "to_value": entry.to_value,
            "details": entry.details,
            "created_at": entry.created_at.isoformat() if entry.created_at else None,
            "actor": (
                db.query(User.full_name).filter(User.id == entry.changed_by).scalar()
                if entry.changed_by
                else None
            ),
        }
        for entry in (
            db.query(IncidentHistory)
            .filter(IncidentHistory.incident_id == incident.id)
            .order_by(IncidentHistory.created_at.desc())
            .limit(50)
            .all()
        )
    ]
    response["comments"] = [
        {
            "content": comment.message,
            "created_at": comment.created_at.isoformat() if comment.created_at else None,
            "author": (
                db.query(User.full_name).filter(User.id == comment.author_id).scalar()
                if comment.author_id
                else "System"
            ),
        }
        for comment in (
            db.query(TicketComment)
            .filter(TicketComment.incident_id == incident.id)
            .order_by(TicketComment.created_at.asc())
            .all()
        )
    ]
    response["related_incidents"] = [
        {
            "id": related.id,
            "ticket_id": f"INC-{related.id:06d}",
            "title": related.description.splitlines()[0][:120],
            "status": related.status,
        }
        for related in (
            db.query(Incident)
            .filter(
                Incident.id != incident.id,
                or_(
                    Incident.asset_id == incident.asset_id if incident.asset_id else False,
                    Incident.category == incident.category,
                ),
            )
            .order_by(Incident.created_at.desc())
            .limit(10)
            .all()
        )
    ]
    response["agent_runs"] = [
        {
            "id": run.id,
            "agent_name": run.agent_name,
            "status": run.status,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "finished_at": run.finished_at.isoformat() if run.finished_at else None,
            "steps": [
                {"step_name": step.step_name, "status": step.status, "summary": step.summary}
                for step in db.query(AgentStep).filter(AgentStep.run_id == run.id).order_by(AgentStep.started_at).all()
            ],
        }
        for run in (
            db.query(AgentRun)
            .filter(AgentRun.incident_id == incident.id)
            .order_by(AgentRun.started_at.desc())
            .limit(10)
            .all()
        )
    ]
    response["mcp_calls"] = [
        {
            "id": call.id,
            "tool_name": call.tool_name,
            "calling_agent": call.calling_agent,
            "status": call.status,
            "duration_ms": call.duration_ms,
            "permission_status": call.permission_status,
            "created_at": call.created_at.isoformat() if call.created_at else None,
        }
        for call in (
            db.query(MCPToolCall)
            .filter(MCPToolCall.incident_id == incident.id)
            .order_by(MCPToolCall.created_at.desc())
            .limit(50)
            .all()
        )
    ]
    return response


@router.patch("/{incident_id}")
def update_incident(
    incident_id: int,
    update: IncidentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.support_engineer, RoleEnum.administrator)),
):
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(404, "Incident not found")

    requested = update.model_dump(exclude_unset=True)
    verified = requested.pop("resolution_verified", None)
    changes = {
        key: value
        for key, value in requested.items()
        if value is not None or key in {"assigned_team", "assigned_to_user_id", "asset_id"}
    }
    if not changes:
        raise HTTPException(422, "At least one incident field must be updated")
    allowed_statuses = {
        "open", "assigned", "investigating", "in_progress", "pending_approval",
        "resolved", "closed", "cancelled",
    }
    if "status" in changes and changes["status"] not in allowed_statuses:
        raise HTTPException(422, "Unsupported incident status")
    if "priority" in changes and changes["priority"] not in {
        "critical", "high", "medium", "low", "p1", "p2", "p3", "p4"
    }:
        raise HTTPException(422, "Unsupported incident priority")
    if changes.get("status") in {"resolved", "closed"}:
        if verified is not True or not changes.get("resolution_summary", incident.resolution_summary):
            raise HTTPException(
                422,
                "Resolution requires a verified outcome and resolution summary",
            )
    if changes.get("assigned_to_user_id") is not None:
        assignee = db.query(User).filter(User.id == changes["assigned_to_user_id"]).first()
        if not assignee or assignee.role != RoleEnum.support_engineer:
            raise HTTPException(422, "Assignee must be a support engineer")
    if "asset_id" in changes:
        assignment = (
            db.query(AssetAssignment)
            .filter(
                AssetAssignment.asset_id == changes["asset_id"],
                AssetAssignment.user_id == incident.owner_id,
            )
            .first()
        )
        if changes["asset_id"] is not None and not assignment:
            raise HTTPException(422, "The selected asset is not assigned to the incident reporter")

    audit_changes = []
    for field, new_value in changes.items():
        old_value = getattr(incident, field)
        if old_value == new_value:
            continue
        if (
            field in {"status", "assigned_to_user_id", "assigned_team"}
            and new_value
            and incident.first_response_at is None
        ):
            incident.first_response_at = datetime.utcnow()
        if field == "resolution_summary":
            incident.resolved_at = (
                datetime.utcnow() if changes.get("status") == "resolved" else incident.resolved_at
            )
        if field == "status" and new_value in {"resolved", "closed"}:
            incident.resolved_at = datetime.utcnow()
        if field == "status" and new_value not in {"resolved", "closed"}:
            incident.resolved_at = None
        setattr(incident, field, new_value)
        db.add(
            IncidentHistory(
                incident_id=incident.id,
                changed_by=current_user.id,
                event_type=field,
                from_value=str(old_value) if old_value is not None else None,
                to_value=str(new_value) if new_value is not None else None,
            )
        )
        if field in {"status", "assigned_to_user_id", "assigned_team"}:
            db.add(
                Notification(
                    user_id=incident.owner_id,
                    title=f"Incident INC-{incident.id:06d} {field.replace('_', ' ')} updated",
                    message=f"{field.replace('_', ' ').capitalize()} changed to {new_value or 'unassigned'}.",
                    notification_type=(
                        "ticket_assignment"
                        if field in {"assigned_to_user_id", "assigned_team"}
                        else "ticket_status"
                    ),
                    related_type="incident",
                    related_id=incident.id,
                )
            )
        audit_changes.append(f"{field}: {old_value!s} -> {new_value!s}")
    if audit_changes:
        db.add(
            AuditLog(
                user_id=current_user.id,
                action="incident.updated",
                table_name="incidents",
                record_id=incident.id,
                details="; ".join(audit_changes),
            )
        )
    db.commit()
    db.refresh(incident)
    employee = db.query(User).filter(User.id == incident.owner_id).first()
    return _summary(incident, employee, db)


@router.post("/{incident_id}/comments")
def add_comment(
    incident_id: int,
    comment: CommentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.support_engineer, RoleEnum.administrator)),
):
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(404, "Incident not found")
    record = TicketComment(
        incident_id=incident.id,
        author_id=current_user.id,
        message=comment.content.strip(),
    )
    db.add(record)
    db.add(
        AuditLog(
            user_id=current_user.id,
            action="incident.comment_added",
            table_name="incidents",
            record_id=incident.id,
            details="Support engineer added a comment",
        )
    )
    db.add(
        Notification(
            user_id=incident.owner_id,
            title=f"New support update on INC-{incident.id:06d}",
            message="A support engineer added a comment to your incident.",
            notification_type="support_comment",
            related_type="incident",
            related_id=incident.id,
        )
    )
    db.commit()
    db.refresh(record)
    return {
        "id": record.id,
        "content": record.message,
        "created_at": record.created_at.isoformat() if record.created_at else None,
    }
