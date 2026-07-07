import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class BankAccount(Base):
    __tablename__ = "bank_accounts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    account_name: Mapped[str] = mapped_column(String(255))
    account_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    fund_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_four: Mapped[str | None] = mapped_column(String(4), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
