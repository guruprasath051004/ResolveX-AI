"""Add incident investigation, assignment, and execution audit data."""

from alembic import op
import sqlalchemy as sa


revision = "0003_support_workspace"
down_revision = "0002_employee_portal"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("incidents") as batch_op:
        batch_op.add_column(sa.Column("assigned_to_user_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_incidents_assigned_to_user_id_users",
            "users",
            ["assigned_to_user_id"],
            ["id"],
        )
    op.create_index("ix_incidents_assigned_to_user_id", "incidents", ["assigned_to_user_id"])
    with op.batch_alter_table("incidents") as batch_op:
        batch_op.add_column(sa.Column("asset_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_incidents_asset_id_assets",
            "assets",
            ["asset_id"],
            ["id"],
        )

    op.add_column("assets", sa.Column("manufacturer", sa.String(), nullable=True))
    op.add_column("assets", sa.Column("operating_system", sa.String(), nullable=True))
    op.add_column("assets", sa.Column("status", sa.String(), server_default="in_service", nullable=False))

    with op.batch_alter_table("agent_runs") as batch_op:
        batch_op.add_column(sa.Column("incident_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_agent_runs_incident_id_incidents",
            "incidents",
            ["incident_id"],
            ["id"],
        )
        batch_op.add_column(sa.Column("thread_id", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("status", sa.String(), server_default="completed", nullable=False))
    op.add_column("agent_steps", sa.Column("summary", sa.Text(), nullable=True))

    with op.batch_alter_table("mcp_tool_calls") as batch_op:
        batch_op.add_column(sa.Column("calling_agent", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("incident_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_mcp_tool_calls_incident_id_incidents",
            "incidents",
            ["incident_id"],
            ["id"],
        )
        batch_op.add_column(sa.Column("run_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_mcp_tool_calls_run_id_agent_runs",
            "agent_runs",
            ["run_id"],
            ["id"],
        )
        batch_op.add_column(sa.Column("user_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_mcp_tool_calls_user_id_users",
            "users",
            ["user_id"],
            ["id"],
        )
        batch_op.add_column(
            sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False)
        )

    op.add_column("approvals", sa.Column("thread_id", sa.String(), nullable=True))
    op.add_column("approvals", sa.Column("execution_result", sa.Text(), nullable=True))
    op.add_column("approvals", sa.Column("payload", sa.Text(), nullable=True))

    op.create_table(
        "incident_history",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("incident_id", sa.Integer(), sa.ForeignKey("incidents.id"), nullable=False),
        sa.Column("changed_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("from_value", sa.Text(), nullable=True),
        sa.Column("to_value", sa.Text(), nullable=True),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index("ix_incident_history_incident_id", "incident_history", ["incident_id"])


def downgrade() -> None:
    op.drop_index("ix_incident_history_incident_id", table_name="incident_history")
    op.drop_table("incident_history")
    op.drop_column("approvals", "payload")
    op.drop_column("approvals", "execution_result")
    op.drop_column("approvals", "thread_id")
    with op.batch_alter_table("mcp_tool_calls") as batch_op:
        batch_op.drop_constraint("fk_mcp_tool_calls_user_id_users", type_="foreignkey")
        batch_op.drop_constraint("fk_mcp_tool_calls_run_id_agent_runs", type_="foreignkey")
        batch_op.drop_constraint("fk_mcp_tool_calls_incident_id_incidents", type_="foreignkey")
        batch_op.drop_column("created_at")
        batch_op.drop_column("user_id")
        batch_op.drop_column("run_id")
        batch_op.drop_column("incident_id")
        batch_op.drop_column("calling_agent")
    op.drop_column("agent_steps", "summary")
    with op.batch_alter_table("agent_runs") as batch_op:
        batch_op.drop_constraint("fk_agent_runs_incident_id_incidents", type_="foreignkey")
        batch_op.drop_column("status")
        batch_op.drop_column("thread_id")
        batch_op.drop_column("incident_id")
    op.drop_column("assets", "status")
    op.drop_column("assets", "operating_system")
    op.drop_column("assets", "manufacturer")
    with op.batch_alter_table("incidents") as batch_op:
        batch_op.drop_constraint("fk_incidents_asset_id_assets", type_="foreignkey")
        batch_op.drop_column("asset_id")
    op.drop_index("ix_incidents_assigned_to_user_id", table_name="incidents")
    with op.batch_alter_table("incidents") as batch_op:
        batch_op.drop_constraint("fk_incidents_assigned_to_user_id_users", type_="foreignkey")
        batch_op.drop_column("assigned_to_user_id")
