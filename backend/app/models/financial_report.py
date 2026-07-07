import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, JSON, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class FinancialReport(Base):
    __tablename__ = "financial_reports"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    report_json: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
