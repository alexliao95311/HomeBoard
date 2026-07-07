import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Budget(Base):
    __tablename__ = "budgets"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    fiscal_year: Mapped[int] = mapped_column(Integer, index=True)
    source_document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class BudgetLine(Base):
    __tablename__ = "budget_lines"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    budget_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("budgets.id", ondelete="CASCADE"), index=True
    )
    category: Mapped[str] = mapped_column(String(128))
    monthly_budget: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    annual_budget: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    fund_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
