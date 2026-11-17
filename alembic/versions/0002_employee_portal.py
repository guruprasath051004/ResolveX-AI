"""Add employee portal profile, ticket activity, and notification data."""

from alembic import op
import sqlalchemy as sa


revision = "0002_employee_portal"
down_revision = "add_knowledge_category"
branch_labels = None
depends_on = None


def upgrade() -> None:
    sla_policies = sa.table(
        "sla_policies",
        sa.column("name", sa.String()),
        sa.column("response_minutes", sa.Integer()),
        sa.column("resolution_minutes", sa.Integer()),
    )
    if op.get_bind().execute(sa.select(sa.func.count()).select_from(sla_policies)).scalar_one() == 0:
        op.bulk_insert(
            sla_policies,
            [
                {"name": "Critical Severity (P1)", "response_minutes": 15, "resolution_minutes": 60},
                {"name": "High Severity (P2)", "response_minutes": 30, "resolution_minutes": 240},
                {"name": "Medium Severity (P3)", "response_minutes": 120, "resolution_minutes": 480},
                {"name": "Low Severity (P4)", "response_minutes": 240, "resolution_minutes": 1440},
            ],
        )

    op.add_column("users", sa.Column("full_name", sa.String(), nullable=True))
    op.add_column("users", sa.Column("department", sa.String(), nullable=True))
    op.add_column("users", sa.Column("phone", sa.String(), nullable=True))

    for table in ("incidents", "service_requests"):
        op.add_column(table, sa.Column("assigned_team", sa.String(), nullable=True))
        op.add_column(table, sa.Column("response_due_at", sa.DateTime(), nullable=True))
        op.add_column(table, sa.Column("resolution_due_at", sa.DateTime(), nullable=True))
        op.add_column(table, sa.Column("resolution_summary", sa.Text(), nullable=True))
    op.add_column(
        "service_requests",
        sa.Column("priority", sa.String(), server_default="medium", nullable=False),
    )
    op.add_column("incidents", sa.Column("first_response_at", sa.DateTime(), nullable=True))
    op.add_column("incidents", sa.Column("resolved_at", sa.DateTime(), nullable=True))
    op.add_column(
        "service_requests",
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )

    with op.batch_alter_table("approvals") as batch_op:
        batch_op.add_column(sa.Column("service_request_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("incident_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("decision_reason", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("decided_by", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("decided_at", sa.DateTime(), nullable=True))
        batch_op.create_foreign_key(
            "fk_approvals_service_request_id_service_requests",
            "service_requests",
            ["service_request_id"],
            ["id"],
        )
        batch_op.create_foreign_key(
            "fk_approvals_incident_id_incidents",
            "incidents",
            ["incident_id"],
            ["id"],
        )
        batch_op.create_foreign_key(
            "fk_approvals_decided_by_users",
            "users",
            ["decided_by"],
            ["id"],
        )

    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("notification_type", sa.String(), nullable=False),
        sa.Column("related_type", sa.String(), nullable=True),
        sa.Column("related_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("read_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])

    op.create_table(
        "ticket_comments",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("incident_id", sa.Integer(), sa.ForeignKey("incidents.id"), nullable=True),
        sa.Column("service_request_id", sa.Integer(), sa.ForeignKey("service_requests.id"), nullable=True),
        sa.Column("author_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_table(
        "announcements",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("published_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("announcements")
    op.drop_table("ticket_comments")
    op.drop_index("ix_notifications_user_id", table_name="notifications")
    op.drop_table("notifications")

    with op.batch_alter_table("approvals") as batch_op:
        batch_op.drop_constraint("fk_approvals_decided_by_users", type_="foreignkey")
        batch_op.drop_constraint("fk_approvals_incident_id_incidents", type_="foreignkey")
        batch_op.drop_constraint("fk_approvals_service_request_id_service_requests", type_="foreignkey")
        batch_op.drop_column("decided_at")
        batch_op.drop_column("decided_by")
        batch_op.drop_column("decision_reason")
        batch_op.drop_column("incident_id")
        batch_op.drop_column("service_request_id")

    op.drop_column("service_requests", "updated_at")
    op.drop_column("incidents", "resolved_at")
    op.drop_column("incidents", "first_response_at")
    for table in ("service_requests", "incidents"):
        op.drop_column(table, "resolution_summary")
        op.drop_column(table, "resolution_due_at")
        op.drop_column(table, "response_due_at")
        op.drop_column(table, "assigned_team")
    op.drop_column("service_requests", "priority")
    op.drop_column("users", "phone")
    op.drop_column("users", "department")
    op.drop_column("users", "full_name")
