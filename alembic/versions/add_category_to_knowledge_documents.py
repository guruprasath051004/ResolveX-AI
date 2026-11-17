"""Add category column to knowledge_documents table.

Revision ID: add_category_to_knowledge_documents
Revises: add_knowledge_documents
Create Date: 2026-11-13 15:12:00.000000
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_knowledge_category'
down_revision = 'add_knowledge_documents'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('knowledge_documents', sa.Column('category', sa.String(), nullable=True))
    op.execute(
        "UPDATE knowledge_documents SET category = 'uncategorized' WHERE category IS NULL"
    )
    with op.batch_alter_table('knowledge_documents') as batch_op:
        batch_op.alter_column(
            'category',
            existing_type=sa.String(),
            nullable=False,
        )

def downgrade():
    op.drop_column('knowledge_documents', 'category')
