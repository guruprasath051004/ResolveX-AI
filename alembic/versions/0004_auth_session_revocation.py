"""Add per-user access-token revocation version."""

from alembic import op
import sqlalchemy as sa


revision = "0004_auth_session_revocation"
down_revision = "0003_support_workspace"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("token_version", sa.Integer(), server_default="0", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("users", "token_version")
