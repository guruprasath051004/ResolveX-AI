"""SQLAlchemy models for ResolveX foundation phase"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, Enum, Index, func, text
from sqlalchemy.orm import relationship
from backend.database import Base
from backend.models.knowledge import KnowledgeDocument
from datetime import datetime
import enum

class RoleEnum(str, enum.Enum):
    employee = "employee"
    support_engineer = "support_engineer"
    administrator = "administrator"

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(Enum(RoleEnum), nullable=False)
    full_name = Column(String)
    department = Column(String)
    phone = Column(String)
    token_version = Column(Integer, nullable=False, default=0, server_default="0")
    # relationships
    incidents = relationship("Incident", back_populates="owner", foreign_keys="Incident.owner_id")
    service_requests = relationship("ServiceRequest", back_populates="owner")
    assets = relationship("AssetAssignment", back_populates="user")
    approvals = relationship(
        "Approval",
        back_populates="requester",
        foreign_keys="Approval.requester_id",
    )
    availability = relationship("EngineerAvailability", back_populates="user", uselist=False, cascade="all, delete-orphan")

class Incident(Base):
    __tablename__ = "incidents"
    id = Column(Integer, primary_key=True)
    category = Column(String, nullable=False)
    priority = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    status = Column(String, nullable=False, default="open")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    assigned_team = Column(String)
    assigned_to_user_id = Column(Integer, ForeignKey("users.id"), index=True)
    asset_id = Column(Integer, ForeignKey("assets.id"))
    response_due_at = Column(DateTime)
    resolution_due_at = Column(DateTime)
    first_response_at = Column(DateTime)
    resolved_at = Column(DateTime)
    resolution_summary = Column(Text)
    reassignment_count = Column(Integer, default=0, server_default="0", nullable=False)
    escalation_level = Column(Integer, default=0, server_default="0", nullable=False)
    current_lifecycle_phase = Column(String, default="received", server_default="received", nullable=False)
    escalated_to_user_id = Column(Integer, ForeignKey("users.id"))
    lock_version = Column(Integer, default=0, server_default="0", nullable=False)
    last_exception = Column(String)

    owner = relationship("User", back_populates="incidents", foreign_keys=[owner_id])
    escalated_to = relationship("User", foreign_keys=[escalated_to_user_id])
    exceptions = relationship("AssignmentException", back_populates="incident", cascade="all, delete-orphan")

class ServiceRequest(Base):
    __tablename__ = "service_requests"
    id = Column(Integer, primary_key=True)
    type = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    priority = Column(String, nullable=False, default="medium")
    status = Column(String, nullable=False, default="open")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    assigned_team = Column(String)
    response_due_at = Column(DateTime)
    resolution_due_at = Column(DateTime)
    resolution_summary = Column(Text)
    owner = relationship("User", back_populates="service_requests")

class SLAPolicy(Base):
    __tablename__ = "sla_policies"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    response_minutes = Column(Integer, nullable=False)
    resolution_minutes = Column(Integer, nullable=False)

class Asset(Base):
    __tablename__ = "assets"
    id = Column(Integer, primary_key=True)
    serial_number = Column(String, unique=True, nullable=False)
    type = Column(String, nullable=False)
    model = Column(String)
    manufacturer = Column(String)
    operating_system = Column(String)
    status = Column(String, nullable=False, default="in_service")
    assigned = relationship("AssetAssignment", back_populates="asset", uselist=False)


class IncidentHistory(Base):
    __tablename__ = "incident_history"
    id = Column(Integer, primary_key=True)
    incident_id = Column(Integer, ForeignKey("incidents.id"), nullable=False, index=True)
    changed_by = Column(Integer, ForeignKey("users.id"))
    event_type = Column(String, nullable=False)
    from_value = Column(Text)
    to_value = Column(Text)
    details = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

class AssetAssignment(Base):
    __tablename__ = "asset_assignments"
    id = Column(Integer, primary_key=True)
    asset_id = Column(Integer, ForeignKey("assets.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    assigned_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    asset = relationship("Asset", back_populates="assigned")
    user = relationship("User", back_populates="assets")

class Approval(Base):
    __tablename__ = "approvals"
    id = Column(Integer, primary_key=True)
    request_type = Column(String, nullable=False)
    status = Column(String, nullable=False, default="pending")
    requester_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    requester = relationship(
        "User",
        back_populates="approvals",
        foreign_keys=[requester_id],
    )
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    service_request_id = Column(Integer, ForeignKey("service_requests.id"))
    incident_id = Column(Integer, ForeignKey("incidents.id"))
    decision_reason = Column(Text)
    decided_by = Column(Integer, ForeignKey("users.id"))
    decided_at = Column(DateTime)
    thread_id = Column(String)
    execution_result = Column(Text)
    payload = Column(Text)


class Notification(Base):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    notification_type = Column(String, nullable=False)
    related_type = Column(String)
    related_id = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    read_at = Column(DateTime)


class TicketComment(Base):
    __tablename__ = "ticket_comments"
    id = Column(Integer, primary_key=True)
    incident_id = Column(Integer, ForeignKey("incidents.id"))
    service_request_id = Column(Integer, ForeignKey("service_requests.id"))
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Announcement(Base):
    __tablename__ = "announcements"
    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    active = Column(Boolean, nullable=False, default=True)
    published_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"))

class AgentRun(Base):
    __tablename__ = "agent_runs"
    id = Column(Integer, primary_key=True)
    agent_name = Column(String, nullable=False)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    finished_at = Column(DateTime)
    incident_id = Column(Integer, ForeignKey("incidents.id"))
    thread_id = Column(String)
    status = Column(String, nullable=False, default="completed")
    retry_count = Column(Integer, nullable=False, default=0, server_default="0")
    input_summary = Column(Text)
    output_summary = Column(Text)
    execution_data = Column(Text)
    error_summary = Column(Text)

    __table_args__ = (
        Index(
            "uq_agent_runs_active_thread",
            "thread_id",
            unique=True,
            postgresql_where=text("status IN ('running', 'waiting') AND thread_id IS NOT NULL"),
            sqlite_where=text("status IN ('running', 'waiting') AND thread_id IS NOT NULL"),
        ),
    )

class AgentStep(Base):
    __tablename__ = "agent_steps"
    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, ForeignKey("agent_runs.id"), nullable=False)
    step_name = Column(String, nullable=False)
    status = Column(String, nullable=False)
    summary = Column(Text)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    duration_ms = Column(Integer)

class AgentCheckpoint(Base):
    __tablename__ = "agent_checkpoints"
    id = Column(Integer, primary_key=True)
    thread_id = Column(String, index=True, nullable=False)
    checkpoint_id = Column(String, nullable=False)
    checkpoint_data = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

class MCPToolCall(Base):
    __tablename__ = "mcp_tool_calls"
    id = Column(Integer, primary_key=True)
    tool_name = Column(String, nullable=False)
    input_summary = Column(Text)
    output_summary = Column(Text)
    duration_ms = Column(Integer)
    status = Column(String, nullable=False)
    permission_status = Column(String)
    calling_agent = Column(String)
    incident_id = Column(Integer, ForeignKey("incidents.id"))
    run_id = Column(Integer, ForeignKey("agent_runs.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    action = Column(String, nullable=False)
    table_name = Column(String)
    record_id = Column(Integer)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    details = Column(Text)


class EngineerAvailability(Base):
    __tablename__ = "engineer_availability"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    status = Column(String, nullable=False, default="available", server_default="available", index=True)
    working_schedule = Column(String, nullable=False, default="09:00 - 17:00 UTC", server_default="09:00 - 17:00 UTC")
    leave_start = Column(DateTime)
    leave_end = Column(DateTime)
    max_active_tickets = Column(Integer, nullable=False, default=5, server_default="5")
    skills = Column(Text, nullable=False, default="[]", server_default="[]")
    team = Column(String, nullable=False, default="IT Service Desk", server_default="IT Service Desk", index=True)
    is_simulated = Column(Boolean, nullable=False, default=True, server_default=text("1"))
    notes = Column(Text)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="availability")


class AssignmentException(Base):
    __tablename__ = "assignment_exceptions"
    id = Column(Integer, primary_key=True)
    incident_id = Column(Integer, ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True)
    exception_type = Column(String, nullable=False, index=True)
    severity = Column(String, nullable=False, default="warning", server_default="warning")
    attempted_engineer_id = Column(Integer, ForeignKey("users.id"))
    resolved_engineer_id = Column(Integer, ForeignKey("users.id"))
    action_taken = Column(String, nullable=False)
    reason = Column(Text, nullable=False)
    details = Column(Text)
    employee_message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    incident = relationship("Incident", back_populates="exceptions")
    attempted_engineer = relationship("User", foreign_keys=[attempted_engineer_id])
    resolved_engineer = relationship("User", foreign_keys=[resolved_engineer_id])


class AssignmentPolicy(Base):
    __tablename__ = "assignment_policies"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    max_workload_per_engineer = Column(Integer, nullable=False, default=5, server_default="5")
    max_reassignment_attempts = Column(Integer, nullable=False, default=3, server_default="3")
    sla_at_risk_threshold_minutes = Column(Integer, nullable=False, default=30, server_default="30")
    auto_escalate_on_no_engineer = Column(Boolean, nullable=False, default=True, server_default=text("1"))
    require_skill_match = Column(Boolean, nullable=False, default=True, server_default=text("1"))
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)



