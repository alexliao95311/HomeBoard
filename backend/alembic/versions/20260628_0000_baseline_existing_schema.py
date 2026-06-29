"""Baseline the existing application schema.

Revision ID: 20260628_0000
Revises:
Create Date: 2026-06-28
"""

from alembic import op
import sqlalchemy as sa

revision = "20260628_0000"
down_revision = None
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def upgrade() -> None:
    if not _has_table("users"):
        op.create_table(
            "users",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("firebase_uid", sa.String(128), nullable=False),
            sa.Column("email", sa.String(320), nullable=True),
            sa.Column("name", sa.String(255), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_users_firebase_uid",
            "users",
            ["firebase_uid"],
            unique=True,
        )

    if not _has_table("organizations"):
        op.create_table(
            "organizations",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.PrimaryKeyConstraint("id"),
        )

    if not _has_table("organization_memberships"):
        op.create_table(
            "organization_memberships",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("organization_id", sa.Uuid(), nullable=False),
            sa.Column("user_id", sa.Uuid(), nullable=False),
            sa.Column("role", sa.String(32), nullable=False),
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
            sa.ForeignKeyConstraint(
                ["user_id"],
                ["users.id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "organization_id",
                "user_id",
                name="uq_org_membership",
            ),
        )
        op.create_index(
            "ix_organization_memberships_organization_id",
            "organization_memberships",
            ["organization_id"],
        )
        op.create_index(
            "ix_organization_memberships_user_id",
            "organization_memberships",
            ["user_id"],
        )

    if not _has_table("documents"):
        op.create_table(
            "documents",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("organization_id", sa.Uuid(), nullable=False),
            sa.Column("uploaded_by_id", sa.Uuid(), nullable=False),
            sa.Column("document_type", sa.String(64), nullable=False),
            sa.Column("status", sa.String(32), nullable=False),
            sa.Column("original_filename", sa.String(512), nullable=False),
            sa.Column("safe_filename", sa.String(255), nullable=False),
            sa.Column("content_type", sa.String(255), nullable=False),
            sa.Column("size_bytes", sa.BigInteger(), nullable=False),
            sa.Column("sha256", sa.String(64), nullable=False),
            sa.Column("storage_path", sa.String(1024), nullable=False),
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
            sa.ForeignKeyConstraint(["uploaded_by_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        for column in (
            "organization_id",
            "document_type",
            "status",
            "sha256",
            "created_at",
        ):
            op.create_index(f"ix_documents_{column}", "documents", [column])

    if not _has_table("audit_logs"):
        op.create_table(
            "audit_logs",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("organization_id", sa.Uuid(), nullable=False),
            sa.Column("actor_user_id", sa.Uuid(), nullable=False),
            sa.Column("action", sa.String(128), nullable=False),
            sa.Column("resource_type", sa.String(64), nullable=False),
            sa.Column("resource_id", sa.String(128), nullable=False),
            sa.Column("event_data", sa.JSON(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
            sa.ForeignKeyConstraint(
                ["organization_id"],
                ["organizations.id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        for column in ("organization_id", "action", "resource_id", "created_at"):
            op.create_index(f"ix_audit_logs_{column}", "audit_logs", [column])


def downgrade() -> None:
    for table_name in (
        "audit_logs",
        "documents",
        "organization_memberships",
        "organizations",
        "users",
    ):
        if _has_table(table_name):
            op.drop_table(table_name)
