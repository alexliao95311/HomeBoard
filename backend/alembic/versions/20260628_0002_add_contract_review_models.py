"""Add contract review models.

Revision ID: 20260628_0002
Revises: 20260628_0001
Create Date: 2026-06-28
"""

from alembic import op
import sqlalchemy as sa

revision = "20260628_0002"
down_revision = "20260628_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())

    if not inspector.has_table("contracts"):
        op.create_table(
            "contracts",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("organization_id", sa.Uuid(), nullable=False),
            sa.Column("document_id", sa.Uuid(), nullable=False),
            sa.Column("vendor_name", sa.String(length=255), nullable=True),
            sa.Column("contract_type", sa.String(length=64), nullable=True),
            sa.Column("start_date", sa.Date(), nullable=True),
            sa.Column("end_date", sa.Date(), nullable=True),
            sa.Column("total_cost", sa.Numeric(precision=14, scale=2), nullable=True),
            sa.Column(
                "status",
                sa.String(length=32),
                server_default="draft",
                nullable=False,
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(
                ["document_id"], ["documents.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(
                ["organization_id"], ["organizations.id"], ondelete="CASCADE"
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_contracts_created_at", "contracts", ["created_at"])
        op.create_index("ix_contracts_document_id", "contracts", ["document_id"])
        op.create_index(
            "ix_contracts_organization_id", "contracts", ["organization_id"]
        )
        op.create_index("ix_contracts_status", "contracts", ["status"])

    if not inspector.has_table("contract_reviews"):
        op.create_table(
            "contract_reviews",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("contract_id", sa.Uuid(), nullable=False),
            sa.Column("model_name", sa.String(length=128), nullable=False),
            sa.Column("flow_name", sa.String(length=128), nullable=False),
            sa.Column(
                "total_score",
                sa.Numeric(precision=7, scale=2),
                nullable=False,
            ),
            sa.Column("risk_level", sa.String(length=32), nullable=False),
            sa.Column("executive_summary", sa.Text(), nullable=False),
            sa.Column("recommendation", sa.Text(), nullable=False),
            sa.Column("raw_output_json", sa.JSON(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(
                ["contract_id"], ["contracts.id"], ondelete="CASCADE"
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_contract_reviews_contract_id", "contract_reviews", ["contract_id"]
        )
        op.create_index(
            "ix_contract_reviews_created_at", "contract_reviews", ["created_at"]
        )
        op.create_index(
            "ix_contract_reviews_risk_level", "contract_reviews", ["risk_level"]
        )

    if not inspector.has_table("contract_rubric_scores"):
        op.create_table(
            "contract_rubric_scores",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("contract_review_id", sa.Uuid(), nullable=False),
            sa.Column("category", sa.String(length=128), nullable=False),
            sa.Column("score", sa.Numeric(precision=7, scale=2), nullable=False),
            sa.Column("max_score", sa.Numeric(precision=7, scale=2), nullable=False),
            sa.Column("explanation", sa.Text(), nullable=False),
            sa.Column("citation", sa.Text(), nullable=True),
            sa.ForeignKeyConstraint(
                ["contract_review_id"],
                ["contract_reviews.id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_contract_rubric_scores_contract_review_id",
            "contract_rubric_scores",
            ["contract_review_id"],
        )

    if not inspector.has_table("contract_risk_flags"):
        op.create_table(
            "contract_risk_flags",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("contract_review_id", sa.Uuid(), nullable=False),
            sa.Column("risk_type", sa.String(length=128), nullable=False),
            sa.Column("severity", sa.String(length=32), nullable=False),
            sa.Column("explanation", sa.Text(), nullable=False),
            sa.Column("citation", sa.Text(), nullable=True),
            sa.Column("suggested_fix", sa.Text(), nullable=True),
            sa.ForeignKeyConstraint(
                ["contract_review_id"],
                ["contract_reviews.id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_contract_risk_flags_contract_review_id",
            "contract_risk_flags",
            ["contract_review_id"],
        )
        op.create_index(
            "ix_contract_risk_flags_severity",
            "contract_risk_flags",
            ["severity"],
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())

    if inspector.has_table("contract_risk_flags"):
        op.drop_index(
            "ix_contract_risk_flags_severity",
            table_name="contract_risk_flags",
        )
        op.drop_index(
            "ix_contract_risk_flags_contract_review_id",
            table_name="contract_risk_flags",
        )
        op.drop_table("contract_risk_flags")

    if inspector.has_table("contract_rubric_scores"):
        op.drop_index(
            "ix_contract_rubric_scores_contract_review_id",
            table_name="contract_rubric_scores",
        )
        op.drop_table("contract_rubric_scores")

    if inspector.has_table("contract_reviews"):
        op.drop_index(
            "ix_contract_reviews_risk_level",
            table_name="contract_reviews",
        )
        op.drop_index(
            "ix_contract_reviews_created_at",
            table_name="contract_reviews",
        )
        op.drop_index(
            "ix_contract_reviews_contract_id",
            table_name="contract_reviews",
        )
        op.drop_table("contract_reviews")

    if inspector.has_table("contracts"):
        op.drop_index("ix_contracts_status", table_name="contracts")
        op.drop_index("ix_contracts_organization_id", table_name="contracts")
        op.drop_index("ix_contracts_document_id", table_name="contracts")
        op.drop_index("ix_contracts_created_at", table_name="contracts")
        op.drop_table("contracts")
