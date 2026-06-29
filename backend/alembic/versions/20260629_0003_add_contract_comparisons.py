"""Add contract comparisons table.

Revision ID: 20260629_0003
Revises: 20260628_0002
Create Date: 2026-06-29
"""

from alembic import op
import sqlalchemy as sa

revision = "20260629_0003"
down_revision = "20260628_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())

    if not inspector.has_table("contract_comparisons"):
        op.create_table(
            "contract_comparisons",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("organization_id", sa.UUID(), nullable=False),
            sa.Column("contract_ids", sa.JSON(), nullable=False),
            sa.Column("vendor_names", sa.JSON(), nullable=False),
            sa.Column("ai_model", sa.String(128), nullable=False),
            sa.Column("best_overall_vendor", sa.String(255), nullable=True),
            sa.Column("result_json", sa.JSON(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(
                ["organization_id"],
                ["organizations.id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_contract_comparisons_organization_id",
            "contract_comparisons",
            ["organization_id"],
        )
        op.create_index(
            "ix_contract_comparisons_created_at",
            "contract_comparisons",
            ["created_at"],
        )


def downgrade() -> None:
    op.drop_index("ix_contract_comparisons_created_at", table_name="contract_comparisons")
    op.drop_index("ix_contract_comparisons_organization_id", table_name="contract_comparisons")
    op.drop_table("contract_comparisons")
