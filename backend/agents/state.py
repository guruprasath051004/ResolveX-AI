"""Shared typed state definition for ResolveX LangGraph workflow."""
from typing import Any, Dict, List, Optional
from typing_extensions import TypedDict

class AgentTrace(TypedDict, total=False):
    agent: str
    summary: str
    started_at: str
    duration_ms: int
    status: str

class DiagnosticItem(TypedDict, total=False):
    tool: str
    result: Dict[str, Any]
    simulated: bool

class RetrievedChunk(TypedDict, total=False):
    doc: str
    chunk: str
    score: Optional[float]
    score_method: Optional[str]
    citation: str
    category: Optional[str]

class AgentState(TypedDict, total=False):
    incident_id: Optional[int]
    run_id: Optional[int]
    actor_user_id: Optional[int]
    thread_id: Optional[str]
    read_only: bool
    employee_id: int
    user_message: str
    intent: str  # "incident" | "service_request"
    category: str
    priority: str  # "low" | "medium" | "high" | "critical"
    retrieved_chunks: List[Dict[str, Any]]
    rag_diagnostics: Dict[str, Any]
    diagnostics: List[Dict[str, Any]]
    proposed_resolution: Optional[str]
    requires_approval: bool
    approval_id: Optional[int]
    ticket_status: str
    required_skills: List[str]
    assigned_engineer_id: Optional[int]
    assigned_engineer_name: Optional[str]
    assigned_team: Optional[str]
    lifecycle_phase: Optional[str]
    exceptions: List[Dict[str, Any]]
    employee_notification: Optional[str]
    sla_status: Optional[Dict[str, Any]]
    agent_trace: List[Dict[str, Any]]
    errors: List[str]
    is_demo: bool

