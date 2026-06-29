"""Add document text chunks.

Revision ID: 20260628_0001
Revises:
Create Date: 2026-06-28
"""

from alembic import op
import sqlalchemy as sa

revision = "20260628_0001"
down_revision = "20260628_0000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("document_text_chunks"):
        return

    op.create_table(
        "document_text_chunks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "document_id",
            "chunk_index",
            name="uq_document_text_chunk_index",
        ),
    )
    op.create_index(
        "ix_document_text_chunks_document_id",
        "document_text_chunks",
        ["document_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_document_text_chunks_document_id",
        table_name="document_text_chunks",
    )
    op.drop_table("document_text_chunks")
