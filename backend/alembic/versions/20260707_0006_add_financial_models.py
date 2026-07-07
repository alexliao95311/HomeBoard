"""Add financial models: bank_accounts, transactions, budgets, budget_lines, financial_reports, anomaly_alerts.

Revision ID: 20260707_0006
Revises: 20260701_0005
Create Date: 2026-07-07
"""

from alembic import op
import sqlalchemy as sa

revision = "20260707_0006"
down_revision = "20260701_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    existing = inspector.get_table_names()

    if "bank_accounts" not in existing:
        op.create_table(
            "bank_accounts",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("organization_id", sa.UUID(), nullable=False),
            sa.Column("account_name", sa.String(255), nullable=False),
            sa.Column("account_type", sa.String(64), nullable=True),
            sa.Column("fund_type", sa.String(64), nullable=True),
            sa.Column("last_four", sa.String(4), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_bank_accounts_organization_id", "bank_accounts", ["organization_id"])
        op.create_index("ix_bank_accounts_created_at", "bank_accounts", ["created_at"])

    if "transactions" not in existing:
        op.create_table(
            "transactions",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("organization_id", sa.UUID(), nullable=False),
            sa.Column("bank_account_id", sa.UUID(), nullable=True),
            sa.Column("source_document_id", sa.UUID(), nullable=True),
            sa.Column("date", sa.Date(), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("amount", sa.Numeric(12, 2), nullable=False),
            sa.Column("transaction_type", sa.String(32), nullable=False),
            sa.Column("vendor_name", sa.String(255), nullable=True),
            sa.Column("category", sa.String(128), nullable=True),
            sa.Column("fund_type", sa.String(64), nullable=True),
            sa.Column("confidence_score", sa.Numeric(4, 3), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["bank_account_id"], ["bank_accounts.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["source_document_id"], ["documents.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_transactions_organization_id", "transactions", ["organization_id"])
        op.create_index("ix_transactions_bank_account_id", "transactions", ["bank_account_id"])
        op.create_index("ix_transactions_date", "transactions", ["date"])
        op.create_index("ix_transactions_transaction_type", "transactions", ["transaction_type"])
        op.create_index("ix_transactions_category", "transactions", ["category"])
        op.create_index("ix_transactions_created_at", "transactions", ["created_at"])

    if "budgets" not in existing:
        op.create_table(
            "budgets",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("organization_id", sa.UUID(), nullable=False),
            sa.Column("fiscal_year", sa.Integer(), nullable=False),
            sa.Column("source_document_id", sa.UUID(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["source_document_id"], ["documents.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_budgets_organization_id", "budgets", ["organization_id"])
        op.create_index("ix_budgets_fiscal_year", "budgets", ["fiscal_year"])
        op.create_index("ix_budgets_created_at", "budgets", ["created_at"])

    if "budget_lines" not in existing:
        op.create_table(
            "budget_lines",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("budget_id", sa.UUID(), nullable=False),
            sa.Column("category", sa.String(128), nullable=False),
            sa.Column("monthly_budget", sa.Numeric(12, 2), nullable=True),
            sa.Column("annual_budget", sa.Numeric(12, 2), nullable=True),
            sa.Column("fund_type", sa.String(64), nullable=True),
            sa.ForeignKeyConstraint(["budget_id"], ["budgets.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_budget_lines_budget_id", "budget_lines", ["budget_id"])

    if "financial_reports" not in existing:
        op.create_table(
            "financial_reports",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("organization_id", sa.UUID(), nullable=False),
            sa.Column("period_start", sa.Date(), nullable=False),
            sa.Column("period_end", sa.Date(), nullable=False),
            sa.Column("report_json", sa.JSON(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_financial_reports_organization_id", "financial_reports", ["organization_id"])
        op.create_index("ix_financial_reports_created_at", "financial_reports", ["created_at"])

    if "anomaly_alerts" not in existing:
        op.create_table(
            "anomaly_alerts",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("organization_id", sa.UUID(), nullable=False),
            sa.Column("transaction_id", sa.UUID(), nullable=True),
            sa.Column("alert_type", sa.String(64), nullable=False),
            sa.Column("severity", sa.String(32), nullable=False),
            sa.Column("explanation", sa.Text(), nullable=False),
            sa.Column("status", sa.String(32), nullable=False, server_default="open"),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["transaction_id"], ["transactions.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_anomaly_alerts_organization_id", "anomaly_alerts", ["organization_id"])
        op.create_index("ix_anomaly_alerts_transaction_id", "anomaly_alerts", ["transaction_id"])
        op.create_index("ix_anomaly_alerts_alert_type", "anomaly_alerts", ["alert_type"])
        op.create_index("ix_anomaly_alerts_severity", "anomaly_alerts", ["severity"])
        op.create_index("ix_anomaly_alerts_status", "anomaly_alerts", ["status"])
        op.create_index("ix_anomaly_alerts_created_at", "anomaly_alerts", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_anomaly_alerts_created_at", table_name="anomaly_alerts")
    op.drop_index("ix_anomaly_alerts_status", table_name="anomaly_alerts")
    op.drop_index("ix_anomaly_alerts_severity", table_name="anomaly_alerts")
    op.drop_index("ix_anomaly_alerts_alert_type", table_name="anomaly_alerts")
    op.drop_index("ix_anomaly_alerts_transaction_id", table_name="anomaly_alerts")
    op.drop_index("ix_anomaly_alerts_organization_id", table_name="anomaly_alerts")
    op.drop_table("anomaly_alerts")

    op.drop_index("ix_financial_reports_created_at", table_name="financial_reports")
    op.drop_index("ix_financial_reports_organization_id", table_name="financial_reports")
    op.drop_table("financial_reports")

    op.drop_index("ix_budget_lines_budget_id", table_name="budget_lines")
    op.drop_table("budget_lines")

    op.drop_index("ix_budgets_created_at", table_name="budgets")
    op.drop_index("ix_budgets_fiscal_year", table_name="budgets")
    op.drop_index("ix_budgets_organization_id", table_name="budgets")
    op.drop_table("budgets")

    op.drop_index("ix_transactions_created_at", table_name="transactions")
    op.drop_index("ix_transactions_category", table_name="transactions")
    op.drop_index("ix_transactions_transaction_type", table_name="transactions")
    op.drop_index("ix_transactions_date", table_name="transactions")
    op.drop_index("ix_transactions_bank_account_id", table_name="transactions")
    op.drop_index("ix_transactions_organization_id", table_name="transactions")
    op.drop_table("transactions")

    op.drop_index("ix_bank_accounts_created_at", table_name="bank_accounts")
    op.drop_index("ix_bank_accounts_organization_id", table_name="bank_accounts")
    op.drop_table("bank_accounts")
