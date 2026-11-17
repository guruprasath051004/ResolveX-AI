"""LangGraph Agent nodes for ResolveX USM workflow."""
import time
from datetime import datetime
from typing import Any, Dict, List

from backend.agents.state import AgentState
from backend.agents.llm import classify_triage, generate_resolution, is_demo_mode
from backend.rag.retriever import retrieve_knowledge
from backend.mcp_server.client import MCPClient
from backend.database import SessionLocal
from backend.models import Approval, Incident, User
from backend.services.exception_engine import IncidentContinuityEngine

mcp_client = MCPClient()

async def triage_node(state: AgentState) -> Dict[str, Any]:
    """Triage Agent: structured classification of intent, category, and priority."""
    start = time.perf_counter()
    started_at = datetime.utcnow()
    msg = state.get("user_message", "")
    
    classification = await classify_triage(msg)
    intent = classification.get("intent", "incident")
    category = classification.get("category", "general")
    priority = classification.get("priority", "medium")
    
    category_skills_map = {
        "vpn": ["vpn", "network"],
        "network": ["network"],
        "server": ["server", "infrastructure"],
        "software": ["software", "applications"],
        "hardware": ["hardware", "desktop"],
        "general": ["service_desk"],
    }
    required_skills = category_skills_map.get(category.lower(), [category.lower()])

    duration = int((time.perf_counter() - start) * 1000)
    trace_entry = {
        "agent": "Triage Agent",
        "summary": f"Classified intent as '{intent}', category as '{category}', priority as '{priority}' ({classification.get('reason', '')}). Required skills: {', '.join(required_skills)}",
        "started_at": started_at.isoformat(),
        "duration_ms": duration,
        "status": "completed",
    }
    
    current_trace = list(state.get("agent_trace", []))
    current_trace.append(trace_entry)
    
    return {
        "intent": intent,
        "category": category,
        "priority": priority,
        "required_skills": required_skills,
        "lifecycle_phase": "classification_completed",
        "agent_trace": current_trace,
        "is_demo": is_demo_mode(),
    }

async def knowledge_node(state: AgentState) -> Dict[str, Any]:
    """Knowledge Agent: RAG query with category metadata filtering."""
    start = time.perf_counter()
    started_at = datetime.utcnow()
    msg = state.get("user_message", "")
    category = state.get("category", "general")
    
    rag_diagnostics: Dict[str, Any] = {}
    chunks = retrieve_knowledge(
        query=msg,
        category=category,
        top_k=3,
        diagnostics=rag_diagnostics,
    )
    duration = int((time.perf_counter() - start) * 1000)
    
    doc_titles = [c.get("doc", "Document") for c in chunks]
    trace_entry = {
        "agent": "Knowledge Agent",
        "summary": (
            f"Retrieved {len(chunks)} indexed knowledge chunks: "
            f"{', '.join(doc_titles) if doc_titles else 'None'}"
            + (
                "; relevance scores unavailable for the existing zero-vector embeddings"
                if rag_diagnostics.get("method") == "chroma"
                and not rag_diagnostics.get("relevance_scores_available")
                else ""
            )
        ),
        "started_at": started_at.isoformat(),
        "duration_ms": duration,
        "status": "completed",
    }
    
    current_trace = list(state.get("agent_trace", []))
    current_trace.append(trace_entry)
    
    return {
        "retrieved_chunks": chunks,
        "rag_diagnostics": rag_diagnostics,
        "agent_trace": current_trace,
    }

async def diagnostic_node(state: AgentState) -> Dict[str, Any]:
    """Diagnostic Agent: selects and executes MCP diagnostic tools."""
    start = time.perf_counter()
    started_at = datetime.utcnow()
    category = state.get("category", "general")
    employee_id = state.get("employee_id", 1)
    actor_user_id = state.get("actor_user_id", employee_id)
    
    diagnostics = []
    
    try:
        if category in ["network", "vpn"]:
            res = await mcp_client.call_tool(
                tool_name="check_network_status",
                arguments={"target_host": "portal.internal.corp" if category == "network" else "vpn.corp.com"},
                user_role="support_engineer",
                calling_agent="diagnostic_agent",
                incident_id=state.get("incident_id"),
                run_id=state.get("run_id"),
                user_id=actor_user_id,
            )
            diagnostics.append({"tool": "check_network_status", "result": res, "simulated": res.get("simulated", False)})

        elif category == "server":
            res = await mcp_client.call_tool(
                tool_name="check_server_health",
                arguments={"server_id": "srv-prod-app-01"},
                user_role="support_engineer",
                calling_agent="diagnostic_agent",
                incident_id=state.get("incident_id"),
                run_id=state.get("run_id"),
                user_id=actor_user_id,
            )
            diagnostics.append({"tool": "check_server_health", "result": res, "simulated": res.get("simulated", False)})

        elif category in ["software", "hardware"] or state.get("intent") == "service_request":
            res = await mcp_client.call_tool(
                tool_name="search_employee_assets",
                arguments={"employee_id": employee_id},
                user_role="support_engineer",
                calling_agent="diagnostic_agent",
                incident_id=state.get("incident_id"),
                run_id=state.get("run_id"),
                user_id=actor_user_id,
            )
            diagnostics.append({"tool": "search_employee_assets", "result": res, "simulated": res.get("simulated", False)})

        else:
            res = await mcp_client.call_tool(
                tool_name="check_network_status",
                arguments={"target_host": "gateway.internal"},
                user_role="support_engineer",
                calling_agent="diagnostic_agent",
                incident_id=state.get("incident_id"),
                run_id=state.get("run_id"),
                user_id=actor_user_id,
            )
            diagnostics.append({"tool": "check_network_status", "result": res, "simulated": res.get("simulated", False)})

    except Exception as e:
        diagnostics.append({"tool": "diagnostic_failure", "result": {"error": str(e)}, "simulated": True})
        errors = list(state.get("errors", []))
        errors.append(f"Diagnostic execution failed: {e}")
    else:
        errors = list(state.get("errors", []))
    
    duration = int((time.perf_counter() - start) * 1000)
    tools_called = [d["tool"] for d in diagnostics]
    trace_entry = {
        "agent": "Diagnostic Agent",
        "summary": f"Executed MCP diagnostic tool(s): {', '.join(tools_called)} with simulated diagnostics",
        "started_at": started_at.isoformat(),
        "duration_ms": duration,
        "status": "completed",
    }
    
    current_trace = list(state.get("agent_trace", []))
    current_trace.append(trace_entry)
    
    return {
        "diagnostics": diagnostics,
        "agent_trace": current_trace,
        "errors": errors,
    }

async def resolution_node(state: AgentState) -> Dict[str, Any]:
    """Resolution Agent: analyzes evidence and checks human approval requirements."""
    start = time.perf_counter()
    started_at = datetime.utcnow()
    msg = state.get("user_message", "")
    intent = state.get("intent", "incident")
    category = state.get("category", "general")
    priority = state.get("priority", "medium")
    retrieved_chunks = state.get("retrieved_chunks", [])
    diagnostics = state.get("diagnostics", [])
    employee_id = state.get("employee_id", 1)
    
    # Check sensitive actions: software installation, server restart, escalation, password reset
    is_sensitive = False
    if intent == "service_request" or category in ["software", "hardware"]:
        is_sensitive = True
    elif any(
        kw in msg.lower()
        for kw in ["install", "permission", "password reset", "reboot", "restart server", "escalate"]
    ):
        is_sensitive = True

    approval_id = None
    if is_sensitive and not state.get("read_only"):
        db = SessionLocal()
        try:
            approval = Approval(
                request_type=f"{intent}:{category}",
                status="pending",
                requester_id=employee_id,
            )
            db.add(approval)
            db.commit()
            db.refresh(approval)
            approval_id = approval.id
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    resolution_text = await generate_resolution(
        user_message=msg,
        intent=intent,
        category=category,
        priority=priority,
        retrieved_chunks=retrieved_chunks,
        diagnostics=diagnostics,
        requires_approval=is_sensitive,
    )
    
    duration = int((time.perf_counter() - start) * 1000)
    approval_str = f"Approval required (ID: {approval_id}, status: PENDING)" if is_sensitive else "Direct resolution without approval"
    trace_entry = {
        "agent": "Resolution Agent",
        "summary": f"Formulated resolution based on retrieved context and diagnostics. {approval_str}",
        "started_at": started_at.isoformat(),
        "duration_ms": duration,
        "status": "completed",
    }
    
    current_trace = list(state.get("agent_trace", []))
    current_trace.append(trace_entry)
    
    return {
        "proposed_resolution": resolution_text,
        "requires_approval": is_sensitive,
        "approval_id": approval_id,
        "agent_trace": current_trace,
    }

async def ticket_node(state: AgentState) -> Dict[str, Any]:
    """Ticket Agent: manages ticket lifecycle strictly through MCP ticket tools."""
    start = time.perf_counter()
    started_at = datetime.utcnow()
    msg = state.get("user_message", "")
    category = state.get("category", "general")
    priority = state.get("priority", "medium")
    employee_id = state.get("employee_id", 1)
    requires_approval = state.get("requires_approval", False)
    
    ticket_id = state.get("incident_id")
    if state.get("read_only") and ticket_id:
        trace_entry = {
            "agent": "Ticket Agent",
            "summary": f"Investigation completed for existing incident #{ticket_id}; no ticket mutation was performed.",
            "started_at": started_at.isoformat(),
            "duration_ms": int((time.perf_counter() - start) * 1000),
            "status": "completed",
        }
        return {
            "incident_id": ticket_id,
            "ticket_status": state.get("ticket_status", "unchanged"),
            "agent_trace": list(state.get("agent_trace", [])) + [trace_entry],
        }
    
    # 1. Create ticket via MCP if not already created
    if not ticket_id:
        title = msg[:60] + ("..." if len(msg) > 60 else "")
        ticket_res = await mcp_client.call_tool(
            tool_name="create_ticket",
            arguments={
                "title": title,
                "description": msg,
                "category": category,
                "priority": priority,
                "employee_id": employee_id,
            },
            user_role="employee",
            calling_agent="ticket_agent",
            run_id=state.get("run_id"),
            user_id=state.get("actor_user_id", employee_id),
        )
        ticket_id = ticket_res.get("ticket_id")

    # 2. Team routing via MCP
    assigned_team = "IT Service Desk"
    required_skills = state.get("required_skills", [])
    if category == "server" or priority == "critical":
        assigned_team = "Platform Infrastructure"
    elif category in ["network", "vpn"]:
        assigned_team = "Network Operations"
    elif requires_approval or category == "software":
        assigned_team = "IT Desktop Support"

    if ticket_id:
        await mcp_client.call_tool(
            tool_name="assign_support_team",
            arguments={"ticket_id": ticket_id, "team_name": assigned_team},
            user_role="support_engineer",
            calling_agent="ticket_agent",
            incident_id=ticket_id,
            run_id=state.get("run_id"),
            user_id=state.get("actor_user_id", employee_id),
        )

    # 3. Status synchronization via MCP
    final_status = "investigating"
    if requires_approval and not state.get("approved"):
        final_status = "pending_approval"
    elif requires_approval and state.get("approved"):
        final_status = "in_progress"
    elif priority == "critical":
        final_status = "investigating"
    else:
        final_status = "in_progress"

    if ticket_id:
        await mcp_client.call_tool(
            tool_name="update_incident_status",
            arguments={"ticket_id": ticket_id, "new_status": final_status},
            user_role="support_engineer",
            calling_agent="ticket_agent",
            incident_id=ticket_id,
            run_id=state.get("run_id"),
            user_id=state.get("actor_user_id", employee_id),
        )

    # 4. Intelligent assignment continuity (exception engine)
    assigned_engineer_id = None
    assigned_engineer_name = None
    employee_notification = None
    continuity_exceptions = []
    lifecycle_phase = "assigned"
    exception_type = None

    if ticket_id and not state.get("read_only"):
        db = SessionLocal()
        try:
            continuity_result = IncidentContinuityEngine.handle_assignment_continuity(
                db=db,
                incident_id=ticket_id,
                target_category=category,
                preferred_team=assigned_team,
                candidate_engineer_id=None,
                actor_user_id=state.get("actor_user_id", employee_id),
            )
            eng_info = continuity_result.get("assigned_to", {})
            assigned_engineer_id = eng_info.get("id")
            assigned_engineer_name = eng_info.get("name")
            employee_notification = continuity_result.get("employee_notification")
            exception_type = continuity_result.get("exception_type")
            lifecycle_phase = continuity_result.get("status", "assigned")
            if exception_type:
                continuity_exceptions.append({
                    "type": exception_type,
                    "exception_id": continuity_result.get("exception_id"),
                    "action": continuity_result.get("status"),
                    "previous_engineer": continuity_result.get("previous_engineer"),
                    "reassignment_count": continuity_result.get("reassignment_count", 0),
                    "message": employee_notification,
                    "sla_preserved": continuity_result.get("sla_preserved", True),
                })
        except Exception as ce:
            continuity_exceptions.append({"type": "continuity_error", "error": str(ce)})
        finally:
            db.close()

    duration = int((time.perf_counter() - start) * 1000)
    eng_summary = f" → {assigned_engineer_name}" if assigned_engineer_name else ""
    exc_summary = f" [Exception: {exception_type}]" if exception_type else ""
    trace_entry = {
        "agent": "Ticket Agent",
        "summary": (
            f"Created USM Ticket #{ticket_id}, assigned to team '{assigned_team}'{eng_summary}, "
            f"status '{final_status}' via MCP tools.{exc_summary}"
        ),
        "started_at": started_at.isoformat(),
        "duration_ms": duration,
        "status": "completed",
    }

    current_trace = list(state.get("agent_trace", []))
    current_trace.append(trace_entry)

    return {
        "incident_id": ticket_id,
        "ticket_status": final_status,
        "assigned_engineer_id": assigned_engineer_id,
        "assigned_engineer_name": assigned_engineer_name,
        "assigned_team": assigned_team,
        "lifecycle_phase": lifecycle_phase,
        "employee_notification": employee_notification,
        "exceptions": list(state.get("exceptions", [])) + continuity_exceptions,
        "agent_trace": current_trace,
    }

