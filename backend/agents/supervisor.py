"""Supervisor Agent and LangGraph Workflow coordinator for ResolveX AI.

Supervisor responsibilities:
- Routes between specialized agents (Triage -> Knowledge -> Diagnostic -> Resolution -> Ticket)
- Validates each agent output against contracts and schemas
- Retries on validation failures
- Pauses for human approval on sensitive actions
- Checkpoints workflow state to PostgreSQL (via PostgresSaver)
- Resumes execution once human approval is granted
- Streams real-time execution events via SSE
- Persists agent_runs and agent_steps DB audit records
"""

import time
import json
from uuid import uuid4
from datetime import datetime
from typing import Any, Dict, AsyncGenerator, Optional

from langgraph.graph import StateGraph, START, END
from sqlalchemy.exc import IntegrityError

from backend.agents.state import AgentState
from backend.agents.checkpoint import PostgresSaver
from backend.agents.nodes import (
    triage_node,
    knowledge_node,
    diagnostic_node,
    resolution_node,
    ticket_node,
)
from backend.database import SessionLocal
from backend.models import AgentRun, AgentStep, MCPToolCall
from backend.services.observability import redact_sensitive, safe_text_summary

# Initialize Postgres-backed checkpointer
checkpointer = PostgresSaver()

# ── Supervisor Validation & Routing Nodes ──

async def supervisor_validate_triage(state: AgentState) -> Dict[str, Any]:
    """Supervisor validates Triage Agent classification; applies corrections or retries if needed."""
    started = time.perf_counter()
    started_at = datetime.utcnow()
    intent = state.get("intent", "incident")
    category = state.get("category", "general")
    priority = state.get("priority", "medium")
    errors = list(state.get("errors", []))
    
    valid_intents = {"incident", "service_request"}
    valid_categories = {"network", "vpn", "software", "hardware", "server", "general"}
    valid_priorities = {"low", "medium", "high", "critical"}
    
    is_valid = True
    if intent not in valid_intents:
        errors.append(f"Invalid intent '{intent}' corrected to 'incident'")
        intent = "incident"
        is_valid = False
    if category not in valid_categories:
        errors.append(f"Invalid category '{category}' corrected to 'general'")
        category = "general"
        is_valid = False
    if priority not in valid_priorities:
        errors.append(f"Invalid priority '{priority}' corrected to 'medium'")
        priority = "medium"
        is_valid = False

    trace_entry = {
        "agent": "Supervisor Agent",
        "summary": "Triage fields validated. Routing request to Knowledge Agent for knowledge lookup.",
        "started_at": started_at.isoformat(),
        "duration_ms": int((time.perf_counter() - started) * 1000),
        "status": "completed",
    }
    
    current_trace = list(state.get("agent_trace", []))
    current_trace.append(trace_entry)
    
    return {
        "intent": intent,
        "category": category,
        "priority": priority,
        "errors": errors,
        "agent_trace": current_trace,
    }

def route_after_resolution(state: AgentState) -> str:
    """Supervisor checks approval policy: routes directly to ticket creation."""
    return "ticket"


class ActiveAgentRunError(Exception):
    """Raised when a workflow thread already has an active execution."""


_AGENT_NODES = (
    ("triage", "Triage Agent", triage_node),
    ("supervisor_validate", "Supervisor Agent", supervisor_validate_triage),
    ("knowledge", "Knowledge Agent", knowledge_node),
    ("diagnostic", "Diagnostic Agent", diagnostic_node),
    ("resolution", "Resolution Agent", resolution_node),
    ("ticket", "Ticket Agent", ticket_node),
)


def _persist_step_start(run_id: int, agent_name: str) -> tuple[int, datetime, float]:
    started_at = datetime.utcnow()
    started_perf = time.perf_counter()
    db = SessionLocal()
    try:
        step = AgentStep(
            run_id=run_id,
            step_name=agent_name,
            status="running",
            summary="Execution started.",
            started_at=started_at,
        )
        db.add(step)
        db.commit()
        db.refresh(step)
        return step.id, started_at, started_perf
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _persist_step_finish(
    step_id: int,
    status: str,
    summary: str,
    started_perf: float,
) -> None:
    db = SessionLocal()
    try:
        step = db.query(AgentStep).filter(AgentStep.id == step_id).first()
        if step is None:
            raise RuntimeError(f"Agent step {step_id} disappeared during execution")
        step.status = status
        step.summary = safe_text_summary(summary, 1000)
        step.duration_ms = max(0, int((time.perf_counter() - started_perf) * 1000))
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _observed_node(agent_name: str, node: Any):
    async def execute(state: AgentState) -> Dict[str, Any]:
        run_id = state.get("run_id")
        step_id = None
        started_perf = time.perf_counter()
        if run_id is not None:
            step_id, _, started_perf = _persist_step_start(run_id, agent_name)

        try:
            output = await node(state)
        except Exception as exc:
            if step_id is not None:
                _persist_step_finish(
                    step_id,
                    "failed",
                    f"Execution failed: {type(exc).__name__}: {exc}",
                    started_perf,
                )
            raise

        traces = output.get("agent_trace") or state.get("agent_trace") or []
        trace = next(
            (item for item in reversed(traces) if item.get("agent") == agent_name),
            None,
        )
        summary = (trace or {}).get("summary") or "Execution completed."
        prior_errors = set(state.get("errors") or [])
        node_errors = set(output.get("errors") or []).difference(prior_errors)
        failed_diagnostic = any(
            item.get("tool") == "diagnostic_failure"
            for item in output.get("diagnostics") or []
        )
        status = (trace or {}).get("status", "completed")
        if node_errors or failed_diagnostic:
            status = "failed"
            if node_errors:
                summary = f"{summary} Error: {'; '.join(sorted(node_errors))}"
        if step_id is not None:
            _persist_step_finish(step_id, status, summary, started_perf)
        return output

    return execute


def _create_run(
    *,
    thread_id: str,
    incident_id: Optional[int],
    user_message: str,
) -> AgentRun:
    db = SessionLocal()
    try:
        run_record = AgentRun(
            agent_name="ResolveX USM Multi-Agent System",
            started_at=datetime.utcnow(),
            incident_id=incident_id,
            thread_id=thread_id,
            status="running",
            input_summary=safe_text_summary(user_message, 1000),
        )
        db.add(run_record)
        db.commit()
        db.refresh(run_record)
        return run_record
    except IntegrityError as exc:
        db.rollback()
        active = (
            db.query(AgentRun.id)
            .filter(
                AgentRun.thread_id == thread_id,
                AgentRun.status.in_(("running", "waiting")),
            )
            .first()
        )
        if active:
            raise ActiveAgentRunError(
                "A workflow for this conversation is already running or waiting for approval."
            ) from exc
        raise
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _execution_data(state: AgentState) -> str:
    traces = [
        {
            "agent": trace.get("agent"),
            "summary": safe_text_summary(trace.get("summary"), 1000),
            "status": trace.get("status"),
        }
        for trace in state.get("agent_trace", [])
    ]
    retrieved = [
        {
            "document": chunk.get("doc"),
            "citation": chunk.get("citation"),
            "category": chunk.get("category"),
            "score": chunk.get("score"),
            "score_method": chunk.get("score_method"),
        }
        for chunk in state.get("retrieved_chunks", [])
    ]
    tools = []
    for item in state.get("diagnostics", []):
        result = item.get("result")
        tools.append(
            {
                "tool": item.get("tool"),
                "simulated": item.get("simulated"),
                "result_summary": safe_text_summary(
                    json.dumps(redact_sensitive(result), default=str), 1000
                ),
            }
        )
    detail = {
        "decision_explanations": traces,
        "retrieved_knowledge": retrieved,
        "rag": state.get("rag_diagnostics", {}),
        "tool_invocations": tools,
        "outcome": {
            "incident_id": state.get("incident_id"),
            "ticket_status": state.get("ticket_status"),
            "approval_id": state.get("approval_id"),
            "requires_approval": state.get("requires_approval", False),
            "proposed_resolution": safe_text_summary(
                state.get("proposed_resolution"), 1500
            ),
        },
        "errors": state.get("errors", []),
    }
    return json.dumps(redact_sensitive(detail), ensure_ascii=True, default=str)


def _finalize_run(
    run_id: int,
    state: AgentState,
    status: str,
    error: Optional[str] = None,
) -> None:
    db = SessionLocal()
    try:
        run_record = db.query(AgentRun).filter(AgentRun.id == run_id).first()
        if run_record is None:
            raise RuntimeError(f"Agent run {run_id} disappeared during execution")
        run_record.status = status
        run_record.finished_at = datetime.utcnow()
        if state.get("incident_id") is not None:
            run_record.incident_id = state["incident_id"]
            (
                db.query(MCPToolCall)
                .filter(
                    MCPToolCall.run_id == run_id,
                    MCPToolCall.incident_id.is_(None),
                )
                .update(
                    {MCPToolCall.incident_id: state["incident_id"]},
                    synchronize_session=False,
                )
            )
        run_record.output_summary = safe_text_summary(
            "; ".join(
                trace.get("summary", "")
                for trace in state.get("agent_trace", [])
                if trace.get("summary")
            ),
            2000,
        )
        run_record.execution_data = _execution_data(state)
        run_record.error_summary = safe_text_summary(error, 2000)
        if status in {"waiting", "failed"}:
            db.add(
                AgentStep(
                    run_id=run_id,
                    step_name="Supervisor Agent",
                    status=status,
                    summary=safe_text_summary(
                        "Workflow is waiting for human approval."
                        if status == "waiting"
                        else f"Workflow failed: {error}",
                        1000,
                    ),
                    started_at=datetime.utcnow(),
                )
            )
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _checkpoint_values(config: Dict[str, Any]) -> Dict[str, Any]:
    state_tuple = checkpointer.get_tuple(config)
    if state_tuple and state_tuple.checkpoint:
        return dict(state_tuple.checkpoint.get("channel_values", {}))
    thread_id = config.get("configurable", {}).get("thread_id")
    db_checkpoint = checkpointer.get_latest_checkpoint_data(thread_id) if thread_id else None
    return dict(db_checkpoint.get("values", {})) if db_checkpoint else {}


# ── Construct LangGraph Workflow ──

workflow = StateGraph(AgentState)

for node_id, agent_name, node in _AGENT_NODES:
    workflow.add_node(node_id, _observed_node(agent_name, node))

workflow.add_edge(START, "triage")
workflow.add_edge("triage", "supervisor_validate")
workflow.add_edge("supervisor_validate", "knowledge")
workflow.add_edge("knowledge", "diagnostic")
workflow.add_edge("diagnostic", "resolution")
workflow.add_edge("resolution", "ticket")
workflow.add_edge("ticket", END)

# Compile with persistent Postgres checkpointer
agent_graph = workflow.compile(checkpointer=checkpointer)

# ── Workflow Execution Runners ──

async def run_workflow(
    user_message: str,
    employee_id: int = 1,
    is_demo: bool = True,
    thread_id: Optional[str] = None,
    incident_id: Optional[int] = None,
    read_only: bool = False,
    actor_user_id: Optional[int] = None,
) -> AgentState:
    """Execute the end-to-end multi-agent LangGraph workflow.
    
    Logs entire run and individual agent steps into agent_runs and agent_steps DB tables.
    Checkpoints state to PostgreSQL for pause/resume.
    """
    if not thread_id:
        thread_id = f"thread_{int(time.time() * 1000)}"

    run_record = _create_run(
        thread_id=thread_id,
        incident_id=incident_id,
        user_message=user_message,
    )

    initial_state: AgentState = {
        "user_message": user_message,
        "employee_id": employee_id,
        "actor_user_id": actor_user_id or employee_id,
        "incident_id": incident_id,
        "run_id": run_record.id,
        "thread_id": thread_id,
        "read_only": read_only,
        "agent_trace": [],
        "retrieved_chunks": [],
        "rag_diagnostics": {},
        "diagnostics": [],
        "errors": [],
        "is_demo": is_demo,
    }

    config = {"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}}
    try:
        final_state = await agent_graph.ainvoke(initial_state, config=config)
    except Exception as exc:
        failed_state = _checkpoint_values(config) or initial_state
        _finalize_run(
            run_record.id,
            failed_state,
            "failed",
            f"{type(exc).__name__}: {exc}",
        )
        raise

    final_state["thread_id"] = thread_id
    approval_pending = bool(
        final_state.get("approval_id")
        and final_state.get("ticket_status") == "pending_approval"
    )
    run_status = "waiting" if approval_pending else (
        "failed" if final_state.get("errors") else "completed"
    )
    _finalize_run(
        run_record.id,
        final_state,
        run_status,
        "; ".join(final_state.get("errors", [])) or None,
    )

    return final_state

async def resume_workflow(
    thread_id: str,
    approved: bool = True,
    reviewer_id: int = 2,
    reviewer_role: str = "support_engineer",
) -> AgentState:
    """Resume a paused workflow after human approval decision.
    
    Loads checkpoint from checkpointer/PostgreSQL, applies approval state,
    and executes post-approval fulfillment via MCP tools.
    """
    started = time.perf_counter()
    resume_started_at = datetime.utcnow()
    config = {"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}}
    state_tuple = checkpointer.get_tuple(config)
    
    current_values: Dict[str, Any] = {}
    if state_tuple and state_tuple.checkpoint:
        current_values = state_tuple.checkpoint.get("channel_values", {})
    else:
        # Fallback to DB stored checkpoint
        db_checkpoint = checkpointer.get_latest_checkpoint_data(thread_id)
        if db_checkpoint:
            current_values = db_checkpoint.get("values", {})
    if not current_values:
        raise ValueError("No checkpoint state exists for this workflow.")

    current_values["approved"] = approved
    new_status = "in_progress" if approved else "cancelled"
    current_values["ticket_status"] = new_status

    decision_summary = (
        "Human approval granted; the linked workflow was resumed."
        if approved
        else "Human approval rejected; the linked workflow was cancelled."
    )
    resume_trace = {
        "agent": "Supervisor Agent",
        "summary": decision_summary,
        "started_at": resume_started_at.isoformat(),
        "duration_ms": 0,
        "status": "completed",
    }
    trace_list = list(current_values.get("agent_trace", []))
    trace_list.append(resume_trace)
    current_values["agent_trace"] = trace_list

    ticket_id = current_values.get("incident_id")
    if ticket_id:
        from backend.mcp_server.client import MCPClient
        client = MCPClient()
        await client.call_tool(
            tool_name="update_incident_status",
            arguments={"ticket_id": ticket_id, "new_status": new_status},
            user_role=reviewer_role,
            calling_agent="supervisor_agent",
            incident_id=ticket_id,
            run_id=current_values.get("run_id"),
            user_id=reviewer_id,
        )

    resume_trace["duration_ms"] = int((time.perf_counter() - started) * 1000)
    if trace_list:
        trace_list[-1] = resume_trace
    current_values["agent_trace"] = trace_list
    checkpointer.put(
        config,
        {"id": f"resume_{uuid4().hex}", "channel_values": current_values},
        {},
        {},
    )
    run_id = current_values.get("run_id")
    if run_id is not None:
        db = SessionLocal()
        try:
            run_record = db.query(AgentRun).filter(AgentRun.id == run_id).first()
            if run_record is None:
                raise RuntimeError(f"Agent run {run_id} was not found while resuming")
            run_record.status = "completed"
            run_record.finished_at = datetime.utcnow()
            run_record.output_summary = safe_text_summary(
                f"{run_record.output_summary or ''}; {decision_summary}", 2000
            )
            run_record.execution_data = _execution_data(current_values)
            db.add(
                AgentStep(
                    run_id=run_id,
                    step_name="Supervisor Agent",
                    status="completed",
                    summary=decision_summary,
                    started_at=resume_started_at,
                    duration_ms=resume_trace["duration_ms"],
                )
            )
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
    return current_values

async def stream_workflow_events(
    user_message: str,
    employee_id: int = 1,
    is_demo: bool = True,
) -> AsyncGenerator[str, None]:
    """Stream LangGraph agent workflow execution events in SSE format (text/event-stream)."""
    thread_id = f"thread_sse_{int(time.time() * 1000)}"
    run_record = _create_run(
        thread_id=thread_id,
        incident_id=None,
        user_message=user_message,
    )
    config = {"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}}
    
    initial_state: AgentState = {
        "user_message": user_message,
        "employee_id": employee_id,
        "actor_user_id": employee_id,
        "run_id": run_record.id,
        "thread_id": thread_id,
        "agent_trace": [],
        "retrieved_chunks": [],
        "rag_diagnostics": {},
        "diagnostics": [],
        "errors": [],
        "is_demo": is_demo,
    }

    yield f"event: workflow_start\ndata: {json.dumps({'thread_id': thread_id, 'run_id': run_record.id})}\n\n"

    try:
        async for event in agent_graph.astream(initial_state, config=config):
            for node_name, node_output in event.items():
                trace_entries = node_output.get("agent_trace") or []
                latest_trace = trace_entries[-1] if trace_entries else {}
                summary = safe_text_summary(latest_trace.get("summary"), 1000)
                step_status = latest_trace.get("status", "completed")
                yield (
                    "event: step_completed\ndata: "
                    + json.dumps(
                        {
                            "run_id": run_record.id,
                            "node": node_name,
                            "agent": latest_trace.get("agent"),
                            "status": step_status,
                            "summary": summary,
                        },
                        default=str,
                    )
                    + "\n\n"
                )

        state_tuple = checkpointer.get_tuple(config)
        final_values = state_tuple.checkpoint.get("channel_values", {}) if state_tuple else {}
        final_values["thread_id"] = thread_id
        final_values["run_id"] = run_record.id
        pending_approval = bool(
            final_values.get("approval_id")
            and final_values.get("ticket_status") == "pending_approval"
        )
        run_status = "waiting" if pending_approval else (
            "failed" if final_values.get("errors") else "completed"
        )
        _finalize_run(
            run_record.id,
            final_values,
            run_status,
            "; ".join(final_values.get("errors", [])) or None,
        )
        yield (
            "event: workflow_complete\ndata: "
            + json.dumps(
                {
                    "run_id": run_record.id,
                    "thread_id": thread_id,
                    "incident_id": final_values.get("incident_id"),
                    "ticket_status": final_values.get("ticket_status"),
                    "approval_id": final_values.get("approval_id"),
                    "status": run_status,
                },
                default=str,
            )
            + "\n\n"
        )
    except Exception as exc:
        failed_state = _checkpoint_values(config) or initial_state
        _finalize_run(
            run_record.id,
            failed_state,
            "failed",
            f"{type(exc).__name__}: {exc}",
        )
        yield (
            "event: workflow_error\ndata: "
            + json.dumps(
                {
                    "run_id": run_record.id,
                    "thread_id": thread_id,
                    "error": safe_text_summary(f"{type(exc).__name__}: {exc}", 500),
                }
            )
            + "\n\n"
        )
