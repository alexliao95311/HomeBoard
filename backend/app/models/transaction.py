import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    bank_account_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("bank_accounts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    source_document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )
    date: Mapped[date] = mapped_column(Date, index=True)
    description: Mapped[str] = mapped_column(Text)
    amount: Mapped[float] = mapped_column(Numeric(12, 2))
    transaction_type: Mapped[str] = mapped_column(String(32), index=True)
    vendor_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    category: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    fund_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Numeric(4, 3), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
