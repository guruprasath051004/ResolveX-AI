"""MCP tool status, execution, and persisted audit history."""

import json
import os
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import case, func, or_
from sqlalchemy.orm import Session

from backend.api.auth import require_roles
from backend.database import get_db
from backend.models import Approval, AuditLog, Incident, MCPToolCall, Notification, RoleEnum, User
from backend.mcp_server.client import MCPClient
from backend.services.observability import safe_json_summary

router = APIRouter(
    prefix="/mcp",
    tags=["mcp-monitor"],
    dependencies=[Depends(require_roles(RoleEnum.support_engineer, RoleEnum.administrator))],
)
mcp_client = MCPClient()
SIMULATED_TOOLS = {"check_network_status", "check_server_health"}


def _tool_integration_mode(tool_name: str) -> str:
    if tool_name in SIMULATED_TOOLS:
        return "simulated"
    if tool_name == "search_knowledge_base":
        return "local_rag"
    return "local_database"


class ToolExecutionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    arguments: dict[str, Any] = Field(default_factory=dict)
    incident_id: int | None = None


@router.get("/status")
async def get_mcp_status():
    tools = await mcp_client.list_tools()
    for tool in tools:
        tool["integration_mode"] = _tool_integration_mode(tool["name"])
    return {
        "server_name": "resolvex-mcp",
        "transport": "in_process",
        "status": "available",
        "remote_server_configured": bool(os.getenv("MCP_SERVER_URL")),
        "remote_server_used": False,
        "total_tools": len(tools),
        "tools": tools,
    }


@router.get("/metrics")
def get_mcp_metrics(db: Session = Depends(get_db)):
    totals = db.query(
        func.count(MCPToolCall.id),
        func.sum(case((MCPToolCall.status == "success", 1), else_=0)),
        func.sum(case((MCPToolCall.status != "success", 1), else_=0)),
        func.sum(case((MCPToolCall.permission_status == "denied", 1), else_=0)),
        func.avg(MCPToolCall.duration_ms),
    ).one()
    timeout_count = (
        db.query(func.count(MCPToolCall.id))
        .filter(MCPToolCall.output_summary.ilike("%timeout%"))
        .scalar()
    )
    tool_rows = (
        db.query(
            MCPToolCall.tool_name,
            func.count(MCPToolCall.id),
            func.sum(case((MCPToolCall.status == "success", 1), else_=0)),
            func.sum(case((MCPToolCall.status != "success", 1), else_=0)),
            func.avg(MCPToolCall.duration_ms),
        )
        .group_by(MCPToolCall.tool_name)
        .all()
    )
    agent_rows = (
        db.query(
            MCPToolCall.calling_agent,
            func.count(MCPToolCall.id),
            func.sum(case((MCPToolCall.status == "success", 1), else_=0)),
            func.sum(case((MCPToolCall.status != "success", 1), else_=0)),
        )
        .group_by(MCPToolCall.calling_agent)
        .all()
    )
    return {
        "calls": {
            "total": int(totals[0] or 0),
            "successful": int(totals[1] or 0),
            "failed": int(totals[2] or 0),
            "authorization_failures": int(totals[3] or 0),
            "authentication_failures": None,
            "authentication_failure_tracking": "not_recorded_in_mcp_tool_calls",
            "timeouts": int(timeout_count or 0),
            "average_latency_ms": round(float(totals[4]), 2) if totals[4] is not None else None,
        },
        "tools": [
            {
                "tool_name": name,
                "integration_mode": _tool_integration_mode(name),
                "total": int(total or 0),
                "successful": int(successful or 0),
                "failed": int(failed or 0),
                "average_latency_ms": (
                    round(float(avg_latency), 2) if avg_latency is not None else None
                ),
            }
            for name, total, successful, failed, avg_latency in tool_rows
        ],
        "agents": [
            {
                "agent": agent or "unattributed",
                "total": int(total or 0),
                "successful": int(successful or 0),
                "failed": int(failed or 0),
            }
            for agent, total, successful, failed in agent_rows
        ],
    }


@router.get("/calls")
def list_tool_calls(
    limit: int = Query(default=50, ge=1, le=500),
    incident_id: int | None = None,
    tool_name: str | None = None,
    calling_agent: str | None = None,
    status: str | None = None,
    search: str | None = Query(default=None, max_length=200),
    db: Session = Depends(get_db),
):
    query = db.query(MCPToolCall)
    if incident_id is not None:
        query = query.filter(MCPToolCall.incident_id == incident_id)
    if tool_name:
        query = query.filter(MCPToolCall.tool_name == tool_name)
    if calling_agent:
        query = query.filter(MCPToolCall.calling_agent == calling_agent)
    if status:
        query = query.filter(MCPToolCall.status == status)
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                MCPToolCall.tool_name.ilike(term),
                MCPToolCall.calling_agent.ilike(term),
                MCPToolCall.input_summary.ilike(term),
                MCPToolCall.output_summary.ilike(term),
            )
        )
    calls = query.order_by(MCPToolCall.created_at.desc()).limit(limit).all()
    return [
        {
            "id": call.id,
            "tool_name": call.tool_name,
            "calling_agent": call.calling_agent,
            "incident_id": call.incident_id,
            "run_id": call.run_id,
            "user_id": call.user_id,
            "input_summary": safe_json_summary(call.input_summary, 1000),
            "output_summary": safe_json_summary(call.output_summary, 1000),
            "duration_ms": call.duration_ms,
            "status": call.status,
            "permission_status": call.permission_status,
            "integration_mode": _tool_integration_mode(call.tool_name),
            "created_at": call.created_at.isoformat() if call.created_at else None,
        }
        for call in calls
    ]


@router.post("/tools/{tool_name}/execute")
async def execute_tool(
    tool_name: str,
    payload: ToolExecutionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(RoleEnum.support_engineer, RoleEnum.administrator)
    ),
):
    if "user_role" in payload.arguments:
        raise HTTPException(422, "The caller role is derived from the authenticated session")

    tools = await mcp_client.list_tools()
    if tool_name not in {tool["name"] for tool in tools}:
        raise HTTPException(404, "MCP tool not found")

    incident = None
    if payload.incident_id is not None:
        incident = db.query(Incident).filter(Incident.id == payload.incident_id).first()
        if incident is None:
            raise HTTPException(404, "Incident not found")

    arguments = dict(payload.arguments)
    if incident:
        if "ticket_id" in arguments:
            try:
                argument_ticket_id = int(arguments["ticket_id"])
            except (TypeError, ValueError) as exc:
                raise HTTPException(422, "Tool ticket_id must be an integer") from exc
            if argument_ticket_id != incident.id:
                raise HTTPException(422, "Tool ticket_id must match incident_id")
        arguments["ticket_id"] = incident.id
    if tool_name == "escalate_incident":
        if incident is None:
            raise HTTPException(422, "Escalation requires an incident_id")
        reason = arguments.get("escalation_reason")
        if not isinstance(reason, str) or not reason.strip():
            raise HTTPException(422, "Escalation requires a reason")
        approval = Approval(
            request_type="mcp_tool",
            requester_id=current_user.id,
            incident_id=incident.id,
            payload=json.dumps(
                {
                    "tool_name": tool_name,
                    "arguments": arguments,
                }
            ),
        )
        db.add(approval)
        db.flush()
        db.add(
            AuditLog(
                user_id=current_user.id,
                action="approval.requested",
                table_name="approvals",
                details=f"Escalation approval requested for incident {incident.id}",
            )
        )
        db.add(
            Notification(
                user_id=current_user.id,
                title=f"Approval #{approval.id} requested",
                message=f"Escalation of incident INC-{incident.id:06d} is pending administrator approval.",
                notification_type="approval",
                related_type="approval",
                related_id=approval.id,
            )
        )
        db.commit()
        db.refresh(approval)
        return {
            "status": "pending_approval",
            "approval_id": approval.id,
            "incident_id": incident.id,
            "message": "Escalation has not run. It requires administrator approval.",
        }

    if tool_name == "update_incident_status" and arguments.get("new_status") in {
        "resolved",
        "closed",
    }:
        raise HTTPException(
            409,
            "Resolution must use the incident resolution workflow with verification and notes",
        )

    started = time.perf_counter()
    try:
        result = await mcp_client.call_tool(
            tool_name=tool_name,
            arguments=arguments,
            user_role=current_user.role.value,
            calling_agent=current_user.role.value,
            incident_id=incident.id if incident else None,
            user_id=current_user.id,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"MCP tool execution failed: {exc}") from exc

    return {
        "tool_name": tool_name,
        "incident_id": incident.id if incident else None,
        "status": "success",
        "duration_ms": int((time.perf_counter() - started) * 1000),
        "simulated": result.get("simulated", False) if isinstance(result, dict) else False,
        "result": result,
    }
