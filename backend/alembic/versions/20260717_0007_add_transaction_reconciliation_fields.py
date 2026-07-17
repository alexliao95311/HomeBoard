"""Add reconciliation-tracking fields to transactions: source_type, external_ref,
external_account_number. Lets future imports match new rows against previously
committed transactions (invoice-to-bank-payment, internal transfers, and
cross-import exact duplicates), not just other files in the same import batch.

Revision ID: 20260717_0007
Revises: 20260707_0006
Create Date: 2026-07-17

"""
from alembic import op
import sqlalchemy as sa

revision = "20260717_0007"
down_revision = "20260707_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("transactions", sa.Column("source_type", sa.String(length=32), nullable=True))
    op.add_column("transactions", sa.Column("external_ref", sa.String(length=128), nullable=True))
    op.add_column("transactions", sa.Column("external_account_number", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("transactions", "external_account_number")
    op.drop_column("transactions", "external_ref")
    op.drop_column("transactions", "source_type")
