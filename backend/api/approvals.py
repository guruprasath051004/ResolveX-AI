"""Approval review and fulfillment for sensitive USM actions."""

import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from backend.agents.supervisor import resume_workflow
from backend.api.auth import require_roles
from backend.database import SessionLocal, get_db
from backend.models import (
    Approval,
    AuditLog,
    Incident,
    IncidentHistory,
    Notification,
    RoleEnum,
    ServiceRequest,
    User,
)
from backend.mcp_server.client import MCPClient

router = APIRouter(
    prefix="/approvals",
    tags=["approvals"],
    dependencies=[Depends(require_roles(RoleEnum.support_engineer, RoleEnum.administrator))],
)


class ApprovalDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str | None = Field(default=None, max_length=1000)


def _approval_response(approval: Approval, db: Session) -> dict:
    requester = db.query(User).filter(User.id == approval.requester_id).first()
    reviewer = db.query(User).filter(User.id == approval.decided_by).first()
    incident = (
        db.query(Incident).filter(Incident.id == approval.incident_id).first()
        if approval.incident_id
        else None
    )
    service_request = (
        db.query(ServiceRequest)
        .filter(ServiceRequest.id == approval.service_request_id)
        .first()
        if approval.service_request_id
        else None
    )
    requested_action = None
    if approval.payload:
        try:
            requested_action = json.loads(approval.payload)
        except json.JSONDecodeError:
            requested_action = {"error": "Stored approval payload is invalid"}
    return {
        "id": approval.id,
        "request_type": approval.request_type,
        "status": approval.status,
        "requester_id": approval.requester_id,
        "requester_name": (
            (requester.full_name or requester.email) if requester else "Unknown requester"
        ),
        "created_at": approval.created_at.isoformat() if approval.created_at else None,
        "requested_action": requested_action,
        "details": (
            {
                "incident_id": incident.id,
                "ticket_id": f"INC-{incident.id:06d}",
                "description": incident.description,
                "status": incident.status,
                "priority": incident.priority,
            }
            if incident
            else (
                {
                    "service_request_id": service_request.id,
                    "type": service_request.type,
                    "description": service_request.description,
                    "status": service_request.status,
                }
                if service_request
                else None
            )
        ),
        "decided_by": (
            {"id": reviewer.id, "name": reviewer.full_name or reviewer.email}
            if reviewer
            else None
        ),
        "decided_at": approval.decided_at.isoformat() if approval.decided_at else None,
        "decision_reason": approval.decision_reason,
        "execution_result": approval.execution_result,
    }


@router.get("/")
def list_approvals(
    status: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(Approval)
    if status:
        query = query.filter(Approval.status == status)
    return [
        _approval_response(approval, db)
        for approval in query.order_by(Approval.created_at.desc()).all()
    ]


@router.post("/{approval_id}/approve")
async def approve_request(
    approval_id: int,
    payload: ApprovalDecision | None = None,
    db: Session = Depends(get_db),
    reviewer: User = Depends(
        require_roles(RoleEnum.support_engineer, RoleEnum.administrator)
    ),
):
    approval = db.query(Approval).filter(Approval.id == approval_id).first()
    if approval is None:
        raise HTTPException(status_code=404, detail="Approval not found")
    if approval.status != "pending":
        raise HTTPException(status_code=409, detail="Approval has already been decided")
    if approval.requester_id == reviewer.id:
        raise HTTPException(status_code=403, detail="Requesters cannot approve their own actions")
    action = {}
    if approval.payload:
        try:
            action = json.loads(approval.payload)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=409, detail="Approval action payload is invalid") from exc
    if action.get("tool_name") == "escalate_incident" and reviewer.role != RoleEnum.administrator:
        raise HTTPException(
            status_code=403,
            detail="Only an administrator can execute an approved escalation",
        )

    approval.status = "approved"
    approval.decided_by = reviewer.id
    approval.decided_at = datetime.utcnow()
    approval.decision_reason = payload.reason.strip() if payload and payload.reason else None
    service_request = (
        db.query(ServiceRequest)
        .filter(ServiceRequest.id == approval.service_request_id)
        .first()
        if approval.service_request_id
        else None
    )
    if service_request:
        service_request.status = "approved"
        service_request.updated_at = datetime.utcnow()
    db.add(
        AuditLog(
            user_id=reviewer.id,
            action="approval.approved",
            table_name="approvals",
            record_id=approval.id,
            details=approval.decision_reason or "Approval decision recorded",
        )
    )
    db.add(
        Notification(
            user_id=approval.requester_id,
            title=f"Approval #{approval.id} approved",
            message=approval.decision_reason or "Your request was approved.",
            notification_type="approval",
            related_type="approval",
            related_id=approval.id,
        )
    )
    db.commit()

    try:
        if action.get("tool_name"):
            arguments = dict(action.get("arguments", {}))
            if action["tool_name"] == "escalate_incident":
                arguments["approval_id"] = approval.id
            result = await MCPClient().call_tool(
                tool_name=action["tool_name"],
                arguments=arguments,
                user_role=reviewer.role.value,
                calling_agent="approval_workflow",
                incident_id=approval.incident_id,
                user_id=reviewer.id,
            )
            approval.execution_result = json.dumps({"status": "executed", "result": result})
            if approval.incident_id:
                db.add(
                    IncidentHistory(
                        incident_id=approval.incident_id,
                        changed_by=reviewer.id,
                        event_type="approved_action_executed",
                        details=f"Approved MCP action '{action['tool_name']}' executed.",
                    )
                )
        elif approval.thread_id:
            result = await resume_workflow(
                thread_id=approval.thread_id,
                approved=True,
                reviewer_id=reviewer.id,
                reviewer_role=reviewer.role.value,
            )
            approval.execution_result = json.dumps(
                {
                    "status": "workflow_resumed",
                    "ticket_status": result.get("ticket_status"),
                }
            )
        else:
            approval.execution_result = json.dumps(
                {"status": "approved", "fulfillment": "No linked execution workflow"}
            )
        db.commit()
    except Exception as exc:
        db.rollback()
        failed = db.query(Approval).filter(Approval.id == approval_id).first()
        if failed:
            failed.execution_result = json.dumps(
                {"status": "execution_failed", "error": str(exc)}
            )
            db.commit()
        raise HTTPException(
            status_code=502,
            detail=f"Approval was recorded, but the approved action failed: {exc}",
        ) from exc

    return _approval_response(approval, db)


@router.post("/{approval_id}/reject")
async def reject_request(
    approval_id: int,
    payload: ApprovalDecision | None = None,
    db: Session = Depends(get_db),
    reviewer: User = Depends(
        require_roles(RoleEnum.support_engineer, RoleEnum.administrator)
    ),
):
    approval = db.query(Approval).filter(Approval.id == approval_id).first()
    if approval is None:
        raise HTTPException(status_code=404, detail="Approval not found")
    if approval.status != "pending":
        raise HTTPException(status_code=409, detail="Approval has already been decided")
    if approval.requester_id == reviewer.id:
        raise HTTPException(status_code=403, detail="Requesters cannot reject their own actions")
    approval.status = "rejected"
    approval.decided_by = reviewer.id
    approval.decided_at = datetime.utcnow()
    approval.decision_reason = payload.reason.strip() if payload and payload.reason else None
    service_request = (
        db.query(ServiceRequest)
        .filter(ServiceRequest.id == approval.service_request_id)
        .first()
        if approval.service_request_id
        else None
    )
    if service_request:
        service_request.status = "rejected"
        service_request.updated_at = datetime.utcnow()
    db.add(
        AuditLog(
            user_id=reviewer.id,
            action="approval.rejected",
            table_name="approvals",
            record_id=approval.id,
            details=approval.decision_reason or "Approval decision recorded",
        )
    )
    db.add(
        Notification(
            user_id=approval.requester_id,
            title=f"Approval #{approval.id} rejected",
            message=approval.decision_reason or "Your request was rejected.",
            notification_type="approval",
            related_type="approval",
            related_id=approval.id,
        )
    )
    db.commit()

    if approval.thread_id:
        try:
            result = await resume_workflow(
                thread_id=approval.thread_id,
                approved=False,
                reviewer_id=reviewer.id,
                reviewer_role=reviewer.role.value,
            )
            approval.execution_result = json.dumps(
                {"status": "workflow_cancelled", "ticket_status": result.get("ticket_status")}
            )
            db.commit()
        except Exception as exc:
            db.rollback()
            raise HTTPException(
                status_code=502,
                detail=f"Rejection was recorded, but workflow cancellation failed: {exc}",
            ) from exc
    return _approval_response(approval, db)
