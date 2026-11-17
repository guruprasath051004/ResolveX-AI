"""Add intelligent exceptions, engineer availability, and incident continuity models.

Revision ID: 0006_exceptions_continuity
Revises: 0005_exec_knowledge_obs
Create Date: 2026-11-14
"""

from alembic import op
import sqlalchemy as sa


revision = "0006_exceptions_continuity"
down_revision = "0005_exec_knowledge_obs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Enhance incidents table for lifecycle and concurrency using batch_alter_table with named foreign key
    with op.batch_alter_table("incidents") as batch_op:
        batch_op.add_column(sa.Column("reassignment_count", sa.Integer(), server_default="0", nullable=False))
        batch_op.add_column(sa.Column("escalation_level", sa.Integer(), server_default="0", nullable=False))
        batch_op.add_column(sa.Column("current_lifecycle_phase", sa.String(), server_default="received", nullable=False))
        batch_op.add_column(sa.Column("escalated_to_user_id", sa.Integer(), sa.ForeignKey("users.id", name="fk_incidents_escalated_to_user_id"), nullable=True))
        batch_op.add_column(sa.Column("lock_version", sa.Integer(), server_default="0", nullable=False))
        batch_op.add_column(sa.Column("last_exception", sa.String(), nullable=True))

    # 2. Create engineer_availability table
    op.create_table(
        "engineer_availability",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", name="fk_engineer_availability_user_id", ondelete="CASCADE"), unique=True, nullable=False),
        sa.Column("status", sa.String(), server_default="available", nullable=False),
        sa.Column("working_schedule", sa.String(), server_default="09:00 - 17:00 UTC", nullable=False),
        sa.Column("leave_start", sa.DateTime(), nullable=True),
        sa.Column("leave_end", sa.DateTime(), nullable=True),
        sa.Column("max_active_tickets", sa.Integer(), server_default="5", nullable=False),
        sa.Column("skills", sa.Text(), server_default="[]", nullable=False),
        sa.Column("team", sa.String(), server_default="IT Service Desk", nullable=False),
        sa.Column("is_simulated", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index("ix_engineer_availability_user_id", "engineer_availability", ["user_id"])
    op.create_index("ix_engineer_availability_status", "engineer_availability", ["status"])
    op.create_index("ix_engineer_availability_team", "engineer_availability", ["team"])

    # 3. Create assignment_exceptions table
    op.create_table(
        "assignment_exceptions",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("incident_id", sa.Integer(), sa.ForeignKey("incidents.id", name="fk_assignment_exceptions_incident_id", ondelete="CASCADE"), nullable=False),
        sa.Column("exception_type", sa.String(), nullable=False),
        sa.Column("severity", sa.String(), server_default="warning", nullable=False),
        sa.Column("attempted_engineer_id", sa.Integer(), sa.ForeignKey("users.id", name="fk_assignment_exceptions_attempted_user_id"), nullable=True),
        sa.Column("resolved_engineer_id", sa.Integer(), sa.ForeignKey("users.id", name="fk_assignment_exceptions_resolved_user_id"), nullable=True),
        sa.Column("action_taken", sa.String(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("employee_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index("ix_assignment_exceptions_incident_id", "assignment_exceptions", ["incident_id"])
    op.create_index("ix_assignment_exceptions_type", "assignment_exceptions", ["exception_type"])

    # 4. Create assignment_policies table
    op.create_table(
        "assignment_policies",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("name", sa.String(), unique=True, nullable=False),
        sa.Column("max_workload_per_engineer", sa.Integer(), server_default="5", nullable=False),
        sa.Column("max_reassignment_attempts", sa.Integer(), server_default="3", nullable=False),
        sa.Column("sla_at_risk_threshold_minutes", sa.Integer(), server_default="30", nullable=False),
        sa.Column("auto_escalate_on_no_engineer", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("require_skill_match", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("assignment_policies")
    op.drop_index("ix_assignment_exceptions_type", table_name="assignment_exceptions")
    op.drop_index("ix_assignment_exceptions_incident_id", table_name="assignment_exceptions")
    op.drop_table("assignment_exceptions")
    op.drop_index("ix_engineer_availability_team", table_name="engineer_availability")
    op.drop_index("ix_engineer_availability_status", table_name="engineer_availability")
    op.drop_index("ix_engineer_availability_user_id", table_name="engineer_availability")
    op.drop_table("engineer_availability")
    with op.batch_alter_table("incidents") as batch_op:
        batch_op.drop_column("last_exception")
        batch_op.drop_column("lock_version")
        batch_op.drop_column("escalated_to_user_id")
        batch_op.drop_column("current_lifecycle_phase")
        batch_op.drop_column("escalation_level")
        batch_op.drop_column("reassignment_count")
