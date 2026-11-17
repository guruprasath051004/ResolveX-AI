"""Persist agent execution summaries and knowledge indexing metadata."""

from alembic import op
import sqlalchemy as sa


revision = "0005_exec_knowledge_obs"
down_revision = "0004_auth_session_revocation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("agent_runs", sa.Column("retry_count", sa.Integer(), server_default="0", nullable=False))
    op.add_column("agent_runs", sa.Column("input_summary", sa.Text(), nullable=True))
    op.add_column("agent_runs", sa.Column("output_summary", sa.Text(), nullable=True))
    op.add_column("agent_runs", sa.Column("execution_data", sa.Text(), nullable=True))
    op.add_column("agent_runs", sa.Column("error_summary", sa.Text(), nullable=True))
    op.create_index(
        "uq_agent_runs_active_thread",
        "agent_runs",
        ["thread_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('running', 'waiting') AND thread_id IS NOT NULL"),
        sqlite_where=sa.text("status IN ('running', 'waiting') AND thread_id IS NOT NULL"),
    )

    op.add_column("knowledge_documents", sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False))
    op.add_column("knowledge_documents", sa.Column("version_number", sa.Integer(), server_default="1", nullable=False))
    op.add_column("knowledge_documents", sa.Column("content_hash", sa.String(length=64), nullable=True))
    op.add_column("knowledge_documents", sa.Column("index_status", sa.String(), server_default="not_indexed", nullable=False))
    op.execute(
        "UPDATE knowledge_documents SET index_status = 'legacy_unverified'"
    )
    op.add_column("knowledge_documents", sa.Column("index_error", sa.Text(), nullable=True))
    op.add_column("knowledge_documents", sa.Column("chunk_count", sa.Integer(), server_default="0", nullable=False))
    op.add_column("knowledge_documents", sa.Column("embedding_model", sa.String(), nullable=True))
    op.add_column("knowledge_documents", sa.Column("indexed_at", sa.DateTime(), nullable=True))
    op.create_index("ix_knowledge_documents_content_hash", "knowledge_documents", ["content_hash"])

    op.create_table(
        "knowledge_document_versions",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column(
            "document_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("knowledge_documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("source_path", sa.Text(), nullable=False),
        sa.Column("doc_type", sa.String(), nullable=True),
        sa.Column("index_status", sa.String(), nullable=False),
        sa.Column("chunk_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("embedding_model", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.UniqueConstraint("document_id", "version_number", name="uq_knowledge_document_version"),
    )
    op.create_index(
        "ix_knowledge_document_versions_document_id",
        "knowledge_document_versions",
        ["document_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_knowledge_document_versions_document_id", table_name="knowledge_document_versions")
    op.drop_table("knowledge_document_versions")
    op.drop_index("ix_knowledge_documents_content_hash", table_name="knowledge_documents")
    op.drop_column("knowledge_documents", "indexed_at")
    op.drop_column("knowledge_documents", "embedding_model")
    op.drop_column("knowledge_documents", "chunk_count")
    op.drop_column("knowledge_documents", "index_error")
    op.drop_column("knowledge_documents", "index_status")
    op.drop_column("knowledge_documents", "content_hash")
    op.drop_column("knowledge_documents", "version_number")
    op.drop_column("knowledge_documents", "updated_at")
    op.drop_index("uq_agent_runs_active_thread", table_name="agent_runs")
    op.drop_column("agent_runs", "error_summary")
    op.drop_column("agent_runs", "execution_data")
    op.drop_column("agent_runs", "output_summary")
    op.drop_column("agent_runs", "input_summary")
    op.drop_column("agent_runs", "retry_count")
