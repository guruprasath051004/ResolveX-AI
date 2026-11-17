"""Service Requests API router."""
from datetime import datetime
from typing import Optional, Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from backend.database import SessionLocal
from backend.api.auth import require_roles
from backend.models import (
    Approval,
    AuditLog,
    Notification,
    RoleEnum,
    ServiceRequest,
    TicketComment,
    User,
)
from backend.services.request_policy import SENSITIVE_SERVICE_REQUEST_TYPES

router = APIRouter(
    prefix="/service_requests",
    tags=["service_requests"],
    dependencies=[Depends(require_roles(RoleEnum.support_engineer, RoleEnum.administrator))],
)

class ServiceRequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=10, max_length=3000)


class ServiceRequestUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Optional[Literal["open", "pending_approval", "approved", "in_progress", "resolved", "closed", "rejected", "cancelled"]] = None
    assigned_team: Optional[str] = Field(default=None, max_length=120)
    resolution_summary: Optional[str] = Field(default=None, max_length=3000)


class ServiceRequestCommentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=3000)


@router.get("/")
def list_service_requests():
    db = SessionLocal()
    try:
        reqs = db.query(ServiceRequest).order_by(ServiceRequest.id.desc()).all()
        return [
            {
                "id": r.id,
                "type": r.type,
                "description": r.description,
                "status": r.status,
                "priority": r.priority,
                "assigned_team": r.assigned_team,
                "resolution_summary": r.resolution_summary,
                "owner_id": r.owner_id,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            }
            for r in reqs
        ]
    finally:
        db.close()


@router.get("/{service_request_id}")
def get_service_request(service_request_id: int):
    db = SessionLocal()
    try:
        request = db.query(ServiceRequest).filter(ServiceRequest.id == service_request_id).first()
        if request is None:
            raise HTTPException(status_code=404, detail="Service request not found")
        return {
            "id": request.id,
            "type": request.type,
            "description": request.description,
            "status": request.status,
            "priority": request.priority,
            "assigned_team": request.assigned_team,
            "resolution_summary": request.resolution_summary,
            "owner_id": request.owner_id,
            "created_at": request.created_at.isoformat() if request.created_at else None,
            "updated_at": request.updated_at.isoformat() if request.updated_at else None,
        }
    finally:
        db.close()


@router.patch("/{service_request_id}")
def update_service_request(
    service_request_id: int,
    payload: ServiceRequestUpdate,
    reviewer: User = Depends(require_roles(RoleEnum.support_engineer, RoleEnum.administrator)),
):
    db = SessionLocal()
    try:
        request = db.query(ServiceRequest).filter(ServiceRequest.id == service_request_id).first()
        if request is None:
            raise HTTPException(status_code=404, detail="Service request not found")
        fields = payload.model_dump(exclude_unset=True)
        if not fields:
            raise HTTPException(status_code=422, detail="Provide at least one field to update")
        old_status = request.status
        if payload.status is not None:
            request.status = payload.status
            if payload.status in {"resolved", "closed"}:
                request.resolution_summary = payload.resolution_summary or request.resolution_summary
        if payload.assigned_team is not None:
            request.assigned_team = payload.assigned_team.strip() or None
        if payload.resolution_summary is not None:
            request.resolution_summary = payload.resolution_summary.strip() or None
        request.updated_at = datetime.utcnow()
        if old_status != request.status:
            db.add(
                Notification(
                    user_id=request.owner_id,
                    title=f"SR-{request.id:06d} updated",
                    message=f"Your service request is now {request.status.replace('_', ' ')}.",
                    notification_type="ticket_status",
                    related_type="service_request",
                    related_id=request.id,
                )
            )
        if payload.assigned_team is not None:
            db.add(
                Notification(
                    user_id=request.owner_id,
                    title=f"SR-{request.id:06d} assigned",
                    message=f"Your service request was assigned to {request.assigned_team or 'the service desk'}.",
                    notification_type="ticket_assignment",
                    related_type="service_request",
                    related_id=request.id,
                )
            )
        db.add(
            AuditLog(
                user_id=reviewer.id,
                action="UPDATE_SERVICE_REQUEST",
                table_name="service_requests",
                record_id=request.id,
                details=f"Updated service request fields: {', '.join(sorted(fields))}",
            )
        )
        db.commit()
        db.refresh(request)
        return {
            "id": request.id,
            "status": request.status,
            "assigned_team": request.assigned_team,
            "resolution_summary": request.resolution_summary,
            "updated_at": request.updated_at.isoformat(),
        }
    finally:
        db.close()


@router.post("/{service_request_id}/comments", status_code=201)
def add_service_request_comment(
    service_request_id: int,
    payload: ServiceRequestCommentCreate,
    reviewer: User = Depends(require_roles(RoleEnum.support_engineer, RoleEnum.administrator)),
):
    db = SessionLocal()
    try:
        request = db.query(ServiceRequest).filter(ServiceRequest.id == service_request_id).first()
        if request is None:
            raise HTTPException(status_code=404, detail="Service request not found")
        message = payload.message.strip()
        if not message:
            raise HTTPException(status_code=422, detail="Comment cannot be blank")
        comment = TicketComment(
            service_request_id=request.id,
            author_id=reviewer.id,
            message=message,
        )
        db.add(comment)
        db.add(
            Notification(
                user_id=request.owner_id,
                title=f"Support updated SR-{request.id:06d}",
                message=message,
                notification_type="support_comment",
                related_type="service_request",
                related_id=request.id,
            )
        )
        db.add(
            AuditLog(
                user_id=reviewer.id,
                action="ADD_SUPPORT_COMMENT",
                table_name="ticket_comments",
                record_id=request.id,
                details=f"Added a support comment to service request #{request.id}",
            )
        )
        db.commit()
        db.refresh(comment)
        return {"id": comment.id, "message": comment.message, "created_at": comment.created_at.isoformat()}
    finally:
        db.close()


@router.post("/")
def create_service_request(
    payload: ServiceRequestCreate,
    requester: User = Depends(
        require_roles(RoleEnum.support_engineer, RoleEnum.administrator)
    ),
):
    db = SessionLocal()
    try:
        request_type = payload.type.strip().lower()
        description = payload.description.strip()
        if not request_type or len(description) < 10:
            raise HTTPException(
                status_code=422,
                detail="Service request type and at least 10 characters of description are required",
            )
        requires_approval = request_type in SENSITIVE_SERVICE_REQUEST_TYPES
        sr = ServiceRequest(
            type=request_type,
            description=description,
            status="pending_approval" if requires_approval else "open",
            owner_id=requester.id,
        )
        db.add(sr)
        db.flush()
        approval = None
        if requires_approval:
            approval = Approval(
                request_type=sr.type,
                status="pending",
                requester_id=requester.id,
                service_request_id=sr.id,
            )
            db.add(approval)
            db.flush()
            db.add(
                Notification(
                    user_id=requester.id,
                    title=f"Approval pending for SR-{sr.id:06d}",
                    message="This sensitive request requires approval before fulfillment.",
                    notification_type="approval",
                    related_type="approval",
                    related_id=approval.id,
                )
            )
        db.add(
            AuditLog(
                user_id=requester.id,
                action="CREATE_SERVICE_REQUEST",
                table_name="service_requests",
                record_id=sr.id,
                details=f"Created service request: {sr.type}",
            )
        )
        db.commit()
        db.refresh(sr)
        return {
            "id": sr.id,
            "type": sr.type,
            "status": sr.status,
            "owner_id": sr.owner_id,
            "approval_id": approval.id if approval else None,
        }
    finally:
        db.close()

