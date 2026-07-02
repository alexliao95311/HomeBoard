"""add user preferred_model

Revision ID: 20260701_0005
Revises: 20260701_0004
Create Date: 2026-07-01

"""
from alembic import op
import sqlalchemy as sa

revision = "20260701_0005"
down_revision = "20260701_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "preferred_model",
            sa.String(length=128),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "preferred_model")
