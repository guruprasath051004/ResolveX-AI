"""ResolveX MCP Server implementing all 10 tools using official MCP SDK."""
import json
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from mcp.server.mcpserver import MCPServer
from backend.database import SessionLocal
from backend.models import (
    Incident,
    Asset,
    AssetAssignment,
    KnowledgeDocument,
    User,
    RoleEnum,
    SLAPolicy,
    Notification,
    IncidentHistory,
    AuditLog,
    Approval,
)

mcp_server = MCPServer(
    name="resolvex-mcp",
    instructions="ResolveX Unified Service Management (USM) Diagnostic & Ticketing MCP Server",
)

# Role permission mappings for tools
TOOL_PERMISSIONS = {
    "create_ticket": ["employee", "support_engineer", "administrator"],
    "get_ticket": ["employee", "support_engineer", "administrator"],
    "update_ticket": ["support_engineer", "administrator"],
    "check_network_status": ["support_engineer", "administrator"],
    "check_server_health": ["support_engineer", "administrator"],
    "search_employee_assets": ["employee", "support_engineer", "administrator"],
    "search_knowledge_base": ["employee", "support_engineer", "administrator"],
    "assign_support_team": ["support_engineer", "administrator"],
    "escalate_incident": ["administrator"],
    "update_incident_status": ["support_engineer", "administrator"],
    "assign_incident_engineer": ["support_engineer", "administrator"],
    "check_engineer_availability": ["employee", "support_engineer", "administrator"],
    "reassign_incident": ["support_engineer", "administrator"],
}

def verify_permission(tool_name: str, user_role: str):
    allowed_roles = TOOL_PERMISSIONS.get(tool_name, [])
    if user_role not in allowed_roles:
        raise PermissionError(
            f"Permission denied: role '{user_role}' is not authorized to execute tool '{tool_name}'. Allowed roles: {allowed_roles}"
        )

# 1. create_ticket
@mcp_server.tool(
    name="create_ticket",
    description="Create a new support incident or service request ticket in the ResolveX USM database.",
)
def create_ticket(
    title: str,
    description: str,
    category: str = "general",
    priority: str = "medium",
    employee_id: int = 1,
    user_role: str = "employee",
) -> Dict[str, Any]:
    verify_permission("create_ticket", user_role)
    if not title or not title.strip():
        raise ValueError("Title cannot be empty")
    if not description or not description.strip():
        raise ValueError("Description cannot be empty")
    if priority not in ["low", "medium", "high", "critical"]:
        raise ValueError(f"Invalid priority '{priority}'. Allowed: low, medium, high, critical")

    db = SessionLocal()
    try:
        combined_desc = f"[{title.strip()}] {description.strip()}"
        incident = Incident(
            category=category,
            priority=priority,
            description=combined_desc,
            status="open",
            owner_id=employee_id,
        )
        policy_code = {"critical": "P1", "high": "P2", "medium": "P3", "low": "P4"}[priority]
        policy = db.query(SLAPolicy).filter(SLAPolicy.name.ilike(f"%{policy_code}%")).first()
        if policy:
            now = datetime.utcnow()
            incident.response_due_at = now + timedelta(minutes=policy.response_minutes)
            incident.resolution_due_at = now + timedelta(minutes=policy.resolution_minutes)
        db.add(incident)
        db.flush()
        db.add(
            IncidentHistory(
                incident_id=incident.id,
                event_type="created",
                to_value=incident.status,
                details="Incident created through MCP ticket tool",
            )
        )
        db.add(
            AuditLog(
                action="incident.created",
                table_name="incidents",
                record_id=incident.id,
                details="Incident created through MCP ticket tool",
            )
        )
        db.commit()
        db.refresh(incident)
        return {
            "ticket_id": incident.id,
            "title": title.strip(),
            "category": incident.category,
            "priority": incident.priority,
            "status": incident.status,
            "owner_id": incident.owner_id,
            "created_at": incident.created_at.isoformat() if incident.created_at else None,
            "message": "Ticket created successfully in USM database",
        }
    finally:
        db.close()

# 2. get_ticket
@mcp_server.tool(
    name="get_ticket",
    description="Retrieve details for an existing ticket/incident by ID from the USM database.",
)
def get_ticket(
    ticket_id: int,
    user_role: str = "employee",
) -> Dict[str, Any]:
    verify_permission("get_ticket", user_role)
    if ticket_id <= 0:
        raise ValueError("ticket_id must be a positive integer")

    db = SessionLocal()
    try:
        incident = db.query(Incident).filter(Incident.id == ticket_id).first()
        if not incident:
            raise ValueError(f"Ticket with ID {ticket_id} not found")
        return {
            "ticket_id": incident.id,
            "category": incident.category,
            "priority": incident.priority,
            "status": incident.status,
            "description": incident.description,
            "owner_id": incident.owner_id,
            "created_at": incident.created_at.isoformat() if incident.created_at else None,
            "updated_at": incident.updated_at.isoformat() if incident.updated_at else None,
        }
    finally:
        db.close()

# 3. update_ticket
@mcp_server.tool(
    name="update_ticket",
    description="Update fields on an existing ticket/incident (status, priority, or description).",
)
def update_ticket(
    ticket_id: int,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    description: Optional[str] = None,
    user_role: str = "support_engineer",
) -> Dict[str, Any]:
    verify_permission("update_ticket", user_role)
    if ticket_id <= 0:
        raise ValueError("ticket_id must be a positive integer")

    db = SessionLocal()
    try:
        incident = db.query(Incident).filter(Incident.id == ticket_id).first()
        if not incident:
            raise ValueError(f"Ticket with ID {ticket_id} not found")

        old_status = incident.status
        old_priority = incident.priority
        old_description = incident.description
        if status:
            if status in {"resolved", "closed"}:
                raise ValueError("Use the verified resolution workflow to resolve or close an incident")
            incident.status = status
        if priority:
            if priority not in ["low", "medium", "high", "critical"]:
                raise ValueError(f"Invalid priority '{priority}'")
            incident.priority = priority
        if description:
            incident.description = description

        if status and old_status != incident.status:
            db.add(
                IncidentHistory(
                    incident_id=incident.id,
                    event_type="status",
                    from_value=old_status,
                    to_value=incident.status,
                )
            )
        if priority and old_priority != incident.priority:
            db.add(
                IncidentHistory(
                    incident_id=incident.id,
                    event_type="priority",
                    from_value=old_priority,
                    to_value=incident.priority,
                )
            )
        if description and old_description != incident.description:
            db.add(
                IncidentHistory(
                    incident_id=incident.id,
                    event_type="description",
                    details="Incident description updated",
                )
            )
        db.add(
            AuditLog(
                action="incident.updated",
                table_name="incidents",
                record_id=incident.id,
                details="Incident fields updated through MCP ticket tool",
            )
        )
        db.commit()
        db.refresh(incident)
        return {
            "ticket_id": incident.id,
            "status": incident.status,
            "priority": incident.priority,
            "description": incident.description,
            "updated_at": incident.updated_at.isoformat() if incident.updated_at else None,
        }
    finally:
        db.close()

# 4. check_network_status
@mcp_server.tool(
    name="check_network_status",
    description="Perform simulated network diagnostic check against corporate portal, DNS, and gateway.",
)
def check_network_status(
    target_host: str = "portal.internal.corp",
    user_role: str = "support_engineer",
) -> Dict[str, Any]:
    verify_permission("check_network_status", user_role)
    if not target_host or not target_host.strip():
        raise ValueError("target_host cannot be empty")

    return {
        "target": target_host,
        "dns_resolution": "success",
        "gateway_reachable": True,
        "latency_ms": 14,
        "packet_loss_pct": 0.0,
        "vpn_tunnel_active": False,
        "status": "online",
        "details": "Gateway and internal DNS responding normally. Corporate portal reachable.",
        "simulated": True,
    }

# 5. check_server_health
@mcp_server.tool(
    name="check_server_health",
    description="Perform simulated production server health and performance metrics diagnostic.",
)
def check_server_health(
    server_id: str = "srv-prod-app-01",
    user_role: str = "support_engineer",
) -> Dict[str, Any]:
    verify_permission("check_server_health", user_role)
    if not server_id or not server_id.strip():
        raise ValueError("server_id cannot be empty")

    return {
        "server_id": server_id,
        "cpu_usage_pct": 89.2,
        "memory_usage_pct": 94.6,
        "disk_free_gb": 12.4,
        "load_average": [4.12, 3.85, 3.20],
        "active_processes": 142,
        "service_status": "degraded",
        "root_cause_hint": "Memory exhaustion due to uncollected worker process leak",
        "simulated": True,
    }

# 6. search_employee_assets
@mcp_server.tool(
    name="search_employee_assets",
    description="Search hardware and software assets assigned to an employee in ResolveX USM CMDB.",
)
def search_employee_assets(
    employee_id: int,
    user_role: str = "employee",
) -> Dict[str, Any]:
    verify_permission("search_employee_assets", user_role)
    if employee_id <= 0:
        raise ValueError("employee_id must be a positive integer")

    db = SessionLocal()
    try:
        assignments = (
            db.query(AssetAssignment)
            .filter(AssetAssignment.user_id == employee_id)
            .all()
        )
        assets_list = []
        for assign in assignments:
            if assign.asset:
                assets_list.append({
                    "asset_id": assign.asset.id,
                    "serial_number": assign.asset.serial_number,
                    "type": assign.asset.type,
                    "model": assign.asset.model,
                    "assigned_at": assign.assigned_at.isoformat() if assign.assigned_at else None,
                })
        return {
            "employee_id": employee_id,
            "assigned_assets": assets_list,
            "total_assets": len(assets_list),
        }
    finally:
        db.close()

# 7. search_knowledge_base
@mcp_server.tool(
    name="search_knowledge_base",
    description="Search the USM knowledge base documents and runbooks for troubleshooting guidelines.",
)
def search_knowledge_base(
    query: str,
    category: Optional[str] = None,
    user_role: str = "employee",
) -> Dict[str, Any]:
    verify_permission("search_knowledge_base", user_role)
    if not query or not query.strip():
        raise ValueError("Search query cannot be empty")

    db = SessionLocal()
    try:
        q = db.query(KnowledgeDocument)
        if category:
            q = q.filter(KnowledgeDocument.category == category)
        docs = q.all()
        results = []
        search_terms = query.lower().split()
        for doc in docs:
            score = 0
            content = doc.content or ""
            doc_text = f"{doc.title} {content}".lower()
            for term in search_terms:
                if term in doc_text:
                    score += 1
            if score > 0 or not search_terms:
                results.append({
                    "id": str(doc.id),
                    "title": doc.title,
                    "snippet": content[:200] + ("..." if len(content) > 200 else ""),
                    "file_path": doc.file_path or doc.source_path,
                    "doc_type": doc.doc_type,
                    "relevance_score": score,
                })
        results.sort(key=lambda x: x["relevance_score"], reverse=True)
        return {
            "query": query,
            "category": category,
            "total_matches": len(results),
            "results": results[:5],
        }
    finally:
        db.close()

# 8. assign_support_team
@mcp_server.tool(
    name="assign_support_team",
    description="Assign an incident or service request ticket to an engineering or IT support team.",
)
def assign_support_team(
    ticket_id: int,
    team_name: str,
    user_role: str = "support_engineer",
) -> Dict[str, Any]:
    verify_permission("assign_support_team", user_role)
    if ticket_id <= 0:
        raise ValueError("ticket_id must be a positive integer")
    if not team_name or not team_name.strip():
        raise ValueError("team_name cannot be empty")

    db = SessionLocal()
    try:
        incident = db.query(Incident).filter(Incident.id == ticket_id).first()
        if not incident:
            raise ValueError(f"Ticket with ID {ticket_id} not found")

        previous_team = incident.assigned_team
        previous_status = incident.status
        incident.status = "assigned"
        incident.assigned_team = team_name.strip()
        db.add(
            IncidentHistory(
                incident_id=incident.id,
                event_type="assigned_team",
                from_value=previous_team,
                to_value=team_name.strip(),
            )
        )
        if previous_status != incident.status:
            db.add(
                IncidentHistory(
                    incident_id=incident.id,
                    event_type="status",
                    from_value=previous_status,
                    to_value=incident.status,
                )
            )
        db.add(
            AuditLog(
                action="incident.assigned",
                table_name="incidents",
                record_id=incident.id,
                details=f"Assigned to {team_name.strip()} through MCP",
            )
        )
        db.add(
            Notification(
                user_id=incident.owner_id,
                title=f"INC-{incident.id:06d} assigned",
                message=f"Your incident was assigned to {team_name.strip()}.",
                notification_type="ticket_assignment",
                related_type="incident",
                related_id=incident.id,
            )
        )
        db.commit()
        db.refresh(incident)
        return {
            "ticket_id": incident.id,
            "assigned_team": team_name.strip(),
            "status": incident.status,
            "message": f"Ticket #{ticket_id} successfully assigned to team '{team_name}'",
        }
    finally:
        db.close()

# 9. escalate_incident
@mcp_server.tool(
    name="escalate_incident",
    description="Escalate an incident priority to critical and request administrative escalation approval.",
)
def escalate_incident(
    ticket_id: int,
    escalation_reason: str,
    approval_id: int,
    user_role: str = "administrator",
) -> Dict[str, Any]:
    verify_permission("escalate_incident", user_role)
    if ticket_id <= 0:
        raise ValueError("ticket_id must be a positive integer")
    if not escalation_reason or not escalation_reason.strip():
        raise ValueError("escalation_reason cannot be empty")

    db = SessionLocal()
    try:
        approval = (
            db.query(Approval)
            .filter(
                Approval.id == approval_id,
                Approval.incident_id == ticket_id,
                Approval.status == "approved",
            )
            .first()
        )
        if not approval:
            raise PermissionError("Escalation requires an approved incident approval")
        incident = db.query(Incident).filter(Incident.id == ticket_id).first()
        if not incident:
            raise ValueError(f"Ticket with ID {ticket_id} not found")

        previous_priority = incident.priority
        incident.priority = "critical"
        db.add(
            IncidentHistory(
                incident_id=incident.id,
                event_type="priority",
                from_value=previous_priority,
                to_value="critical",
                details=escalation_reason.strip(),
            )
        )
        db.add(
            AuditLog(
                action="incident.escalated",
                table_name="incidents",
                record_id=incident.id,
                details=escalation_reason.strip(),
            )
        )
        approval.execution_result = json.dumps(
            {"status": "executed", "priority": "critical"}
        )
        db.commit()
        db.refresh(incident)
        return {
            "ticket_id": incident.id,
            "priority": "critical",
            "escalated": True,
            "escalation_reason": escalation_reason.strip(),
            "requires_approval": True,
            "message": f"Incident #{ticket_id} escalated to CRITICAL priority. On-call escalation triggered.",
        }
    finally:
        db.close()

# 10. update_incident_status
@mcp_server.tool(
    name="update_incident_status",
    description="Update the lifecycle status of an incident (open, investigating, in_progress, pending_approval, resolved, closed).",
)
def update_incident_status(
    ticket_id: int,
    new_status: str,
    notes: Optional[str] = None,
    resolution_verified: bool = False,
    user_role: str = "support_engineer",
) -> Dict[str, Any]:
    verify_permission("update_incident_status", user_role)
    if ticket_id <= 0:
        raise ValueError("ticket_id must be a positive integer")
    allowed_statuses = ["open", "investigating", "in_progress", "pending_approval", "resolved", "closed"]
    if new_status not in allowed_statuses:
        raise ValueError(f"Invalid status '{new_status}'. Allowed statuses: {allowed_statuses}")
    if new_status in {"resolved", "closed"} and (
        resolution_verified is not True or not notes or not notes.strip()
    ):
        raise ValueError("Resolution requires a verified outcome and resolution notes")

    db = SessionLocal()
    try:
        incident = db.query(Incident).filter(Incident.id == ticket_id).first()
        if not incident:
            raise ValueError(f"Ticket with ID {ticket_id} not found")

        old_status = incident.status
        incident.status = new_status
        now = datetime.utcnow()
        if new_status in {"in_progress", "resolved", "closed"} and incident.first_response_at is None:
            incident.first_response_at = now
        if new_status in {"resolved", "closed"}:
            incident.resolved_at = now
            if notes:
                incident.resolution_summary = notes.strip()
        if old_status != new_status:
            db.add(
                IncidentHistory(
                    incident_id=incident.id,
                    event_type="status",
                    from_value=old_status,
                    to_value=new_status,
                    details=notes,
                )
            )
            db.add(
                AuditLog(
                    action="incident.status_updated",
                    table_name="incidents",
                    record_id=incident.id,
                    details=f"{old_status} -> {new_status}",
                )
            )
            db.add(
                Notification(
                    user_id=incident.owner_id,
                    title=f"INC-{incident.id:06d} status updated",
                    message=f"Your incident is now {new_status.replace('_', ' ')}.",
                    notification_type="ticket_status",
                    related_type="incident",
                    related_id=incident.id,
                )
            )
        db.commit()
        db.refresh(incident)
        return {
            "ticket_id": incident.id,
            "previous_status": old_status,
            "new_status": incident.status,
            "notes": notes,
            "updated_at": incident.updated_at.isoformat() if incident.updated_at else None,
        }
    finally:
        db.close()

# 11. assign_incident_engineer
@mcp_server.tool(
    name="assign_incident_engineer",
    description="Assign an incident to a specific support engineer after verifying availability and workload.",
)
def assign_incident_engineer(
    ticket_id: int,
    engineer_id: int,
    reason: str = "Standard engineering assignment",
    user_role: str = "support_engineer",
) -> Dict[str, Any]:
    verify_permission("assign_incident_engineer", user_role)
    if ticket_id <= 0:
        raise ValueError("ticket_id must be a positive integer")
    if engineer_id <= 0:
        raise ValueError("engineer_id must be a positive integer")

    from backend.services.workforce import is_engineer_available, seed_workforce
    db = SessionLocal()
    try:
        seed_workforce(db)
        incident = db.query(Incident).filter(Incident.id == ticket_id).first()
        if not incident:
            raise ValueError(f"Ticket with ID {ticket_id} not found")

        engineer = db.query(User).filter(User.id == engineer_id).first()
        if not engineer or engineer.role != RoleEnum.support_engineer:
            raise ValueError(f"User ID {engineer_id} is not an authorized support engineer")

        is_avail, avail_reason, _ = is_engineer_available(db, engineer_id)
        if not is_avail:
            raise ValueError(f"Engineer {engineer.full_name} is unavailable: {avail_reason}")

        old_assignee_id = incident.assigned_to_user_id
        old_assignee_name = db.query(User.full_name).filter(User.id == old_assignee_id).scalar() if old_assignee_id else "Unassigned"

        incident.assigned_to_user_id = engineer.id
        incident.current_lifecycle_phase = "assigned"
        now = datetime.utcnow()
        incident.updated_at = now
        if incident.first_response_at is None:
            incident.first_response_at = now

        db.add(
            IncidentHistory(
                incident_id=incident.id,
                event_type="assigned_to_user",
                from_value=old_assignee_name,
                to_value=engineer.full_name,
                details=reason,
                created_at=now,
            )
        )
        db.add(
            AuditLog(
                action="incident.assigned_engineer",
                table_name="incidents",
                record_id=incident.id,
                timestamp=now,
                details=f"Assigned to {engineer.full_name} via MCP. Reason: {reason}",
            )
        )
        db.add(
            Notification(
                user_id=incident.owner_id,
                title=f"INC-{incident.id:06d} assigned to support engineer",
                message=f"Support engineer {engineer.full_name} has taken ownership of your incident.",
                notification_type="ticket_assignment",
                related_type="incident",
                related_id=incident.id,
                created_at=now,
            )
        )
        db.commit()
        db.refresh(incident)
        return {
            "ticket_id": incident.id,
            "assigned_to": {
                "id": engineer.id,
                "name": engineer.full_name,
                "email": engineer.email,
            },
            "status": incident.status,
            "message": f"Successfully assigned Incident #{ticket_id} to {engineer.full_name}",
        }
    finally:
        db.close()

# 12. check_engineer_availability
@mcp_server.tool(
    name="check_engineer_availability",
    description="Check support engineer availability, schedule, leave status, and active workload.",
)
def check_engineer_availability(
    engineer_id: Optional[int] = None,
    team: Optional[str] = None,
    category: Optional[str] = None,
    user_role: str = "support_engineer",
) -> Dict[str, Any]:
    verify_permission("check_engineer_availability", user_role)
    from backend.services.workforce import seed_workforce, is_engineer_available, get_engineer_workload, find_eligible_engineers
    db = SessionLocal()
    try:
        seed_workforce(db)
        if engineer_id:
            user = db.query(User).filter(User.id == engineer_id).first()
            if not user:
                raise ValueError(f"Engineer ID {engineer_id} not found")
            is_avail, reason, avail = is_engineer_available(db, engineer_id)
            workload = get_engineer_workload(db, engineer_id)
            skills = json.loads(avail.skills) if avail and avail.skills else []
            return {
                "engineer_id": user.id,
                "name": user.full_name or user.email,
                "available": is_avail,
                "status": avail.status if avail else ("available" if is_avail else "unavailable"),
                "reason": reason,
                "team": avail.team if avail else user.department,
                "current_workload": workload,
                "max_workload": avail.max_active_tickets if avail else 5,
                "skills": skills,
                "simulated": True,
            }

        eligible = find_eligible_engineers(db, category=category or "general", preferred_team=team)
        return {
            "category": category,
            "preferred_team": team,
            "eligible_engineers_count": len(eligible),
            "eligible_engineers": eligible,
            "simulated": True,
        }
    finally:
        db.close()

# 13. reassign_incident
@mcp_server.tool(
    name="reassign_incident",
    description="Execute authorized exception reassignment for an incident with continuity preservation.",
)
def reassign_incident(
    ticket_id: int,
    reason: str = "Engineer unavailable / continuity reassignment",
    category: Optional[str] = None,
    preferred_team: Optional[str] = None,
    user_role: str = "support_engineer",
) -> Dict[str, Any]:
    verify_permission("reassign_incident", user_role)
    if ticket_id <= 0:
        raise ValueError("ticket_id must be a positive integer")

    from backend.services.exception_engine import IncidentContinuityEngine
    db = SessionLocal()
    try:
        result = IncidentContinuityEngine.handle_assignment_continuity(
            db=db,
            incident_id=ticket_id,
            target_category=category,
            preferred_team=preferred_team,
        )
        return result
    finally:
        db.close()

# Starlette app for streamable HTTP transport
app = mcp_server.streamable_http_app()
