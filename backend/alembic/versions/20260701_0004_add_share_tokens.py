"""Add share tokens to contract reviews and comparisons.

Revision ID: 20260701_0004
Revises: 20260629_0003
Create Date: 2026-07-01
"""

from alembic import op
import sqlalchemy as sa

revision = "20260701_0004"
down_revision = "20260629_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())

    columns = {c["name"] for c in inspector.get_columns("contract_reviews")}
    if "share_token" not in columns:
        op.add_column("contract_reviews", sa.Column("share_token", sa.UUID(), nullable=True))
        op.create_index(
            "ix_contract_reviews_share_token",
            "contract_reviews",
            ["share_token"],
            unique=True,
        )

    columns = {c["name"] for c in inspector.get_columns("contract_comparisons")}
    if "share_token" not in columns:
        op.add_column("contract_comparisons", sa.Column("share_token", sa.UUID(), nullable=True))
        op.create_index(
            "ix_contract_comparisons_share_token",
            "contract_comparisons",
            ["share_token"],
            unique=True,
        )


def downgrade() -> None:
    op.drop_index("ix_contract_comparisons_share_token", table_name="contract_comparisons")
    op.drop_column("contract_comparisons", "share_token")
    op.drop_index("ix_contract_reviews_share_token", table_name="contract_reviews")
    op.drop_column("contract_reviews", "share_token")
