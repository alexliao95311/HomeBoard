import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AnomalyAlert(Base):
    __tablename__ = "anomaly_alerts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("transactions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    alert_type: Mapped[str] = mapped_column(String(64), index=True)
    severity: Mapped[str] = mapped_column(String(32), index=True)
    explanation: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="open", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
