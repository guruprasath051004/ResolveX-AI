"""FastAPI Router for LangGraph Multi-Agent workflow."""
import json
import os
from uuid import uuid4
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import case, func, or_

from backend.api.auth import get_current_user, require_roles
from backend.agents.supervisor import (
    ActiveAgentRunError,
    run_workflow,
    resume_workflow,
    stream_workflow_events,
)
from backend.database import SessionLocal
from backend.models import (
    AgentRun,
    AgentStep,
    Approval,
    Incident,
    IncidentHistory,
    MCPToolCall,
    Notification,
    RoleEnum,
    TicketComment,
    User,
)
from backend.services.observability import redact_sensitive, safe_json_summary, safe_text_summary

router = APIRouter(prefix="/agent", tags=["agent"])

class AgentRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(
        ...,
        json_schema_extra={"example": "My laptop is connected to Wi-Fi, but the company portal is not opening."},
    )
    thread_id: Optional[str] = Field(default=None, json_schema_extra={"example": "thread_123"})

class AgentRunResponse(BaseModel):
    incident_id: Optional[int] = None
    employee_id: int
    user_message: str
    intent: str
    category: str
    priority: str
    retrieved_chunks: List[Dict[str, Any]]
    diagnostics: List[Dict[str, Any]]
    proposed_resolution: Optional[str] = None
    requires_approval: bool
    approval_id: Optional[int] = None
    ticket_status: str
    agent_trace: List[Dict[str, Any]]
    errors: List[str]
    is_demo: bool
    thread_id: Optional[str] = None
    # Continuity Engine fields
    assigned_engineer_id: Optional[int] = None
    assigned_engineer_name: Optional[str] = None
    assigned_team: Optional[str] = None
    lifecycle_phase: Optional[str] = None
    exceptions: List[Dict[str, Any]] = []
    employee_notification: Optional[str] = None

class ResumeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approved: bool = Field(default=True, json_schema_extra={"example": True})

class InvestigationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str | None = Field(default=None, max_length=4000)

@router.post("/run", response_model=AgentRunResponse)
async def run_agent_workflow(
    payload: AgentRunRequest,
    current_user: User = Depends(get_current_user),
):
    """Execute the multi-agent system on an employee's issue."""
    if not payload.message or not payload.message.strip():
        raise HTTPException(status_code=400, detail="User message cannot be empty")
    thread_id = payload.thread_id
    if current_user.role == RoleEnum.employee:
        thread_prefix = f"employee_{current_user.id}_"
        if thread_id and not thread_id.startswith(thread_prefix):
            raise HTTPException(status_code=403, detail="Conversation does not belong to this employee")
        if thread_id is None:
            thread_id = f"{thread_prefix}{uuid4().hex}"

    try:
        result_state = await run_workflow(
            user_message=payload.message.strip(),
            employee_id=current_user.id,
            is_demo=os.getenv("LLM_PROVIDER", "demo").lower() == "demo",
            thread_id=thread_id,
        )
        incident_id = result_state.get("incident_id")
        if incident_id:
            db = SessionLocal()
            try:
                incident = (
                    db.query(Incident)
                    .filter(Incident.id == incident_id, Incident.owner_id == current_user.id)
                    .first()
                )
                if incident:
                    db.add(
                        TicketComment(
                            incident_id=incident.id,
                            author_id=current_user.id,
                            message=payload.message.strip(),
                        )
                    )
                    db.add(
                        Notification(
                            user_id=current_user.id,
                            title=f"INC-{incident.id:06d} updated",
                            message=f"Your IT issue is now {incident.status.replace('_', ' ')}.",
                            notification_type="ticket_status",
                            related_type="incident",
                            related_id=incident.id,
                        )
                    )
                    approval_id = result_state.get("approval_id")
                    run_record = (
                        db.query(AgentRun)
                        .filter(AgentRun.thread_id == result_state.get("thread_id"))
                        .first()
                    )
                    if run_record:
                        run_record.incident_id = incident.id
                        (
                            db.query(MCPToolCall)
                            .filter(
                                MCPToolCall.run_id == run_record.id,
                                MCPToolCall.incident_id.is_(None),
                            )
                            .update(
                                {MCPToolCall.incident_id: incident.id},
                                synchronize_session=False,
                            )
                        )
                    if approval_id:
                        approval = db.query(Approval).filter(Approval.id == approval_id).first()
                        if approval and approval.requester_id == current_user.id:
                            approval.incident_id = incident.id
                            approval.thread_id = result_state.get("thread_id")
                            existing_notification = (
                                db.query(Notification)
                                .filter(
                                    Notification.user_id == current_user.id,
                                    Notification.notification_type == "approval",
                                    Notification.related_id == approval.id,
                                )
                                .first()
                            )
                            if existing_notification is None:
                                db.add(
                                    Notification(
                                        user_id=current_user.id,
                                        title=f"Approval #{approval.id} pending",
                                        message="This sensitive action needs Support Engineer or Administrator approval.",
                                        notification_type="approval",
                                        related_type="approval",
                                        related_id=approval.id,
                                    )
                                )
                    db.commit()
            except Exception:
                db.rollback()
                raise
            finally:
                db.close()
        return AgentRunResponse(
            incident_id=incident_id,
            employee_id=result_state.get("employee_id", current_user.id),
            user_message=result_state.get("user_message", payload.message),
            intent=result_state.get("intent", "incident"),
            category=result_state.get("category", "general"),
            priority=result_state.get("priority", "medium"),
            retrieved_chunks=result_state.get("retrieved_chunks", []),
            diagnostics=result_state.get("diagnostics", []),
            proposed_resolution=result_state.get("proposed_resolution"),
            requires_approval=result_state.get("requires_approval", False),
            approval_id=result_state.get("approval_id"),
            ticket_status=result_state.get("ticket_status", "open"),
            agent_trace=result_state.get("agent_trace", []),
            errors=result_state.get("errors", []),
            is_demo=result_state.get("is_demo", True),
            thread_id=result_state.get("thread_id"),
            assigned_engineer_id=result_state.get("assigned_engineer_id"),
            assigned_engineer_name=result_state.get("assigned_engineer_name"),
            assigned_team=result_state.get("assigned_team"),
            lifecycle_phase=result_state.get("lifecycle_phase"),
            exceptions=result_state.get("exceptions", []),
            employee_notification=result_state.get("employee_notification"),
        )
    except ActiveAgentRunError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent workflow error: {str(e)}")

@router.post("/investigate/{incident_id}", response_model=AgentRunResponse)
async def investigate_incident(
    incident_id: int,
    payload: InvestigationRequest | None = None,
    current_user: User = Depends(
        require_roles(RoleEnum.support_engineer, RoleEnum.administrator)
    ),
):
    db = SessionLocal()
    try:
        incident = db.query(Incident).filter(Incident.id == incident_id).first()
        if incident is None:
            raise HTTPException(status_code=404, detail="Incident not found")
        investigation_message = incident.description
        if payload and payload.message and payload.message.strip():
            investigation_message = f"{incident.description}\n\nEngineer notes: {payload.message.strip()}"
        owner_id = incident.owner_id
    finally:
        db.close()

    thread_id = f"incident_{incident_id}_{uuid4().hex}"
    try:
        result_state = await run_workflow(
            user_message=investigation_message,
            employee_id=owner_id,
            actor_user_id=current_user.id,
            is_demo=os.getenv("LLM_PROVIDER", "demo").lower() == "demo",
            thread_id=thread_id,
            incident_id=incident_id,
            read_only=True,
        )
        db = SessionLocal()
        try:
            approval_id = result_state.get("approval_id")
            if approval_id:
                approval = db.query(Approval).filter(Approval.id == approval_id).first()
                if approval and approval.requester_id == owner_id:
                    approval.incident_id = incident_id
                    approval.thread_id = thread_id
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
        return AgentRunResponse(
            incident_id=incident_id,
            employee_id=owner_id,
            user_message=investigation_message,
            intent=result_state.get("intent", "incident"),
            category=result_state.get("category", "general"),
            priority=result_state.get("priority", "medium"),
            retrieved_chunks=result_state.get("retrieved_chunks", []),
            diagnostics=result_state.get("diagnostics", []),
            proposed_resolution=result_state.get("proposed_resolution"),
            requires_approval=result_state.get("requires_approval", False),
            approval_id=result_state.get("approval_id"),
            ticket_status=result_state.get("ticket_status", "unchanged"),
            agent_trace=result_state.get("agent_trace", []),
            errors=result_state.get("errors", []),
            is_demo=result_state.get("is_demo", True),
            thread_id=thread_id,
            assigned_engineer_id=result_state.get("assigned_engineer_id"),
            assigned_engineer_name=result_state.get("assigned_engineer_name"),
            assigned_team=result_state.get("assigned_team"),
            lifecycle_phase=result_state.get("lifecycle_phase"),
            exceptions=result_state.get("exceptions", []),
            employee_notification=result_state.get("employee_notification"),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Incident investigation failed: {e}") from e

@router.get("/stream")
async def stream_agent_get(
    message: str,
    current_user: User = Depends(get_current_user),
):
    """Stream multi-agent workflow execution events via SSE (Server-Sent Events)."""
    if not message or not message.strip():
        raise HTTPException(status_code=400, detail="User message cannot be empty")
    return StreamingResponse(
        stream_workflow_events(
            message.strip(),
            employee_id=current_user.id,
            is_demo=os.getenv("LLM_PROVIDER", "demo").lower() == "demo",
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

@router.post("/stream")
async def stream_agent_post(
    payload: AgentRunRequest,
    current_user: User = Depends(get_current_user),
):
    """Stream multi-agent workflow execution events via SSE (POST variant)."""
    if not payload.message or not payload.message.strip():
        raise HTTPException(status_code=400, detail="User message cannot be empty")
    return StreamingResponse(
        stream_workflow_events(
            payload.message.strip(),
            employee_id=current_user.id,
            is_demo=os.getenv("LLM_PROVIDER", "demo").lower() == "demo",
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

@router.post("/resume/{thread_id}")
async def resume_agent_workflow(
    thread_id: str,
    payload: ResumeRequest,
    reviewer: User = Depends(
        require_roles(RoleEnum.support_engineer, RoleEnum.administrator)
    ),
):
    """Resume only a workflow whose linked approval was already decided."""
    db = SessionLocal()
    try:
        approval = (
            db.query(Approval)
            .filter(Approval.thread_id == thread_id)
            .with_for_update()
            .first()
        )
        if approval is None:
            raise HTTPException(status_code=404, detail="No approval is linked to this workflow")
        if approval.requester_id == reviewer.id:
            raise HTTPException(status_code=403, detail="Requesters cannot review their own actions")
        expected_status = "approved" if payload.approved else "rejected"
        if approval.status != expected_status:
            raise HTTPException(
                status_code=409,
                detail="Approval decision does not match the linked approval record",
            )
        if approval.execution_result:
            raise HTTPException(status_code=409, detail="The linked workflow has already been resumed")
        approval.execution_result = json.dumps({"status": "workflow_resuming"})
        db.commit()
    finally:
        db.close()
    try:
        updated_state = await resume_workflow(
            thread_id=thread_id,
            approved=payload.approved,
            reviewer_id=reviewer.id,
            reviewer_role=reviewer.role.value,
        )
        db = SessionLocal()
        try:
            approval = db.query(Approval).filter(Approval.thread_id == thread_id).first()
            if approval:
                approval.execution_result = json.dumps(
                    {
                        "status": "workflow_resumed",
                        "ticket_status": updated_state.get("ticket_status"),
                    }
                )
                db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
        return {
            "status": "resumed",
            "thread_id": thread_id,
            "approved": payload.approved,
            "ticket_status": updated_state.get("ticket_status"),
            "agent_trace": updated_state.get("agent_trace", []),
        }
    except Exception as e:
        db = SessionLocal()
        try:
            approval = db.query(Approval).filter(Approval.thread_id == thread_id).first()
            if approval:
                approval.execution_result = json.dumps(
                    {"status": "execution_failed", "error": str(e)}
                )
                db.commit()
        finally:
            db.close()
        raise HTTPException(status_code=500, detail=f"Failed to resume workflow: {str(e)}")

@router.get("/runs/metrics", dependencies=[Depends(require_roles(RoleEnum.support_engineer, RoleEnum.administrator))])
def get_agent_run_metrics():
    """Return execution and per-agent statistics aggregated from persisted rows."""
    db = SessionLocal()
    try:
        run_counts = {
            status: count
            for status, count in db.query(AgentRun.status, func.count(AgentRun.id))
            .group_by(AgentRun.status)
            .all()
        }
        run_total = sum(run_counts.values())
        step_rows = (
            db.query(
                AgentStep.step_name,
                func.count(AgentStep.id),
                func.sum(case((AgentStep.status == "completed", 1), else_=0)),
                func.sum(case((AgentStep.status == "failed", 1), else_=0)),
                func.avg(AgentStep.duration_ms),
            )
            .group_by(AgentStep.step_name)
            .all()
        )
        agents = [
            {
                "agent": name,
                "executions": int(executions or 0),
                "completed": int(completed or 0),
                "failed": int(failed or 0),
                "average_duration_ms": (
                    round(float(avg_duration), 2) if avg_duration is not None else None
                ),
            }
            for name, executions, completed, failed, avg_duration in step_rows
        ]
        return {
            "runs": {
                "total": run_total,
                "running": run_counts.get("running", 0),
                "waiting": run_counts.get("waiting", 0),
                "completed": run_counts.get("completed", 0),
                "failed": run_counts.get("failed", 0),
            },
            "agents": agents,
        }
    finally:
        db.close()


@router.get("/runs", dependencies=[Depends(require_roles(RoleEnum.support_engineer, RoleEnum.administrator))])
def list_agent_runs(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    status: Optional[str] = None,
    incident_id: Optional[int] = None,
):
    """List recent agent execution runs with persisted step details."""
    db = SessionLocal()
    try:
        query = db.query(AgentRun)
        if status:
            query = query.filter(AgentRun.status == status)
        if incident_id is not None:
            query = query.filter(AgentRun.incident_id == incident_id)
        runs = query.order_by(AgentRun.id.desc()).offset(offset).limit(limit).all()
        run_ids = [run.id for run in runs]
        steps_by_run: dict[int, list[AgentStep]] = {run_id: [] for run_id in run_ids}
        if run_ids:
            steps = (
                db.query(AgentStep)
                .filter(AgentStep.run_id.in_(run_ids))
                .order_by(AgentStep.started_at, AgentStep.id)
                .all()
            )
            for step in steps:
                steps_by_run[step.run_id].append(step)
        output = []
        for r in runs:
            output.append({
                "run_id": r.id,
                "agent_name": r.agent_name,
                "incident_id": r.incident_id,
                "thread_id": r.thread_id,
                "status": r.status,
                "started_at": r.started_at.isoformat() if r.started_at else None,
                "finished_at": r.finished_at.isoformat() if r.finished_at else None,
                "input_summary": safe_text_summary(r.input_summary, 1000),
                "output_summary": safe_text_summary(r.output_summary, 2000),
                "retry_count": r.retry_count,
                "steps": [
                    {
                        "step_id": s.id,
                        "step_name": s.step_name,
                        "status": s.status,
                        "summary": safe_text_summary(s.summary, 1000),
                        "started_at": s.started_at.isoformat() if s.started_at else None,
                        "duration_ms": s.duration_ms,
                    }
                    for s in steps_by_run[r.id]
                ],
            })
        return output
    finally:
        db.close()


@router.get("/runs/{run_id}", dependencies=[Depends(require_roles(RoleEnum.support_engineer, RoleEnum.administrator))])
def get_agent_run_detail(run_id: int):
    """Return a safe execution inspection view for one persisted run."""
    db = SessionLocal()
    try:
        run = db.query(AgentRun).filter(AgentRun.id == run_id).first()
        if run is None:
            raise HTTPException(status_code=404, detail="Agent run not found")
        steps = (
            db.query(AgentStep)
            .filter(AgentStep.run_id == run.id)
            .order_by(AgentStep.started_at, AgentStep.id)
            .all()
        )
        tool_calls = (
            db.query(MCPToolCall)
            .filter(MCPToolCall.run_id == run.id)
            .order_by(MCPToolCall.created_at, MCPToolCall.id)
            .all()
        )
        try:
            execution_data = redact_sensitive(json.loads(run.execution_data or "{}"))
        except (TypeError, ValueError):
            execution_data = {"summary": safe_json_summary(run.execution_data)}
        return {
            "run_id": run.id,
            "agent_name": run.agent_name,
            "incident_id": run.incident_id,
            "thread_id": run.thread_id,
            "status": run.status,
            "retry_count": run.retry_count,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "finished_at": run.finished_at.isoformat() if run.finished_at else None,
            "input_summary": safe_text_summary(run.input_summary, 1000),
            "output_summary": safe_text_summary(run.output_summary, 2000),
            "error_summary": safe_text_summary(run.error_summary, 2000),
            "execution": execution_data,
            "steps": [
                {
                    "step_id": step.id,
                    "agent": step.step_name,
                    "status": step.status,
                    "summary": safe_text_summary(step.summary, 1000),
                    "started_at": step.started_at.isoformat() if step.started_at else None,
                    "duration_ms": step.duration_ms,
                }
                for step in steps
            ],
            "tool_invocations": [
                {
                    "call_id": call.id,
                    "tool": call.tool_name,
                    "agent": call.calling_agent,
                    "status": call.status,
                    "permission_status": call.permission_status,
                    "duration_ms": call.duration_ms,
                    "input_summary": safe_json_summary(call.input_summary, 1000),
                    "output_summary": safe_json_summary(call.output_summary, 1000),
                    "timestamp": call.created_at.isoformat() if call.created_at else None,
                }
                for call in tool_calls
            ],
        }
    finally:
        db.close()


@router.get("/runs/timeline/{incident_id}", dependencies=[Depends(require_roles(RoleEnum.support_engineer, RoleEnum.administrator))])
def get_incident_execution_timeline(
    incident_id: int,
    limit: int = Query(default=200, ge=1, le=500),
):
    """Join incident history with persisted agent, MCP, and approval events."""
    db = SessionLocal()
    try:
        if db.query(Incident.id).filter(Incident.id == incident_id).first() is None:
            raise HTTPException(status_code=404, detail="Incident not found")
        runs = (
            db.query(AgentRun)
            .filter(AgentRun.incident_id == incident_id)
            .order_by(AgentRun.started_at)
            .all()
        )
        run_ids = [run.id for run in runs]
        run_by_thread = {run.thread_id: run.id for run in runs if run.thread_id}
        events: list[dict[str, Any]] = []

        for run in runs:
            events.append({
                "event_id": f"agent_run:{run.id}",
                "event_type": "agent_run",
                "event_ref": run.id,
                "run_id": run.id,
                "incident_id": incident_id,
                "status": run.status,
                "summary": safe_text_summary(run.output_summary or run.input_summary, 500),
                "timestamp": run.started_at.isoformat() if run.started_at else None,
            })
        if run_ids:
            steps = (
                db.query(AgentStep)
                .filter(AgentStep.run_id.in_(run_ids))
                .all()
            )
            for step in steps:
                events.append({
                    "event_id": f"agent_step:{step.id}",
                    "event_type": "agent_step",
                    "event_ref": step.id,
                    "run_id": step.run_id,
                    "incident_id": incident_id,
                    "agent": step.step_name,
                    "status": step.status,
                    "summary": safe_text_summary(step.summary, 500),
                    "duration_ms": step.duration_ms,
                    "timestamp": step.started_at.isoformat() if step.started_at else None,
                })
        mcp_query = db.query(MCPToolCall).filter(
            or_(
                MCPToolCall.incident_id == incident_id,
                MCPToolCall.run_id.in_(run_ids) if run_ids else False,
            )
        )
        for call in mcp_query.all():
            events.append({
                "event_id": f"mcp_call:{call.id}",
                "event_type": "mcp_call",
                "event_ref": call.id,
                "run_id": call.run_id,
                "incident_id": call.incident_id or incident_id,
                "tool": call.tool_name,
                "agent": call.calling_agent,
                "status": call.status,
                "permission_status": call.permission_status,
                "duration_ms": call.duration_ms,
                "summary": safe_json_summary(call.output_summary, 500),
                "timestamp": call.created_at.isoformat() if call.created_at else None,
            })
        approvals_query = db.query(Approval).filter(
            or_(
                Approval.incident_id == incident_id,
                Approval.thread_id.in_(list(run_by_thread))
                if run_by_thread
                else False,
            )
        )
        for approval in approvals_query.all():
            events.append({
                "event_id": f"approval:{approval.id}:created",
                "event_type": "approval",
                "event_ref": approval.id,
                "run_id": run_by_thread.get(approval.thread_id),
                "incident_id": approval.incident_id or incident_id,
                "status": approval.status,
                "summary": f"{approval.request_type} approval {approval.status}.",
                "timestamp": approval.created_at.isoformat() if approval.created_at else None,
            })
            if approval.decided_at:
                events.append({
                    "event_id": f"approval:{approval.id}:decision",
                    "event_type": "approval_decision",
                    "event_ref": approval.id,
                    "run_id": run_by_thread.get(approval.thread_id),
                    "incident_id": approval.incident_id or incident_id,
                    "status": approval.status,
                    "summary": safe_text_summary(approval.decision_reason, 500)
                    or f"Approval was {approval.status}.",
                    "timestamp": approval.decided_at.isoformat(),
                })
        histories = (
            db.query(IncidentHistory)
            .filter(IncidentHistory.incident_id == incident_id)
            .all()
        )
        for history in histories:
            events.append({
                "event_id": f"incident_history:{history.id}",
                "event_type": history.event_type,
                "event_ref": history.id,
                "incident_id": incident_id,
                "status": None,
                "summary": safe_text_summary(history.details, 500),
                "timestamp": history.created_at.isoformat() if history.created_at else None,
            })
        events.sort(key=lambda event: event["timestamp"] or "")
        return events[-limit:]
    finally:
        db.close()
