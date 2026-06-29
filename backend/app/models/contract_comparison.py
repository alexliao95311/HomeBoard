import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ContractComparison(Base):
    __tablename__ = "contract_comparisons"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    contract_ids: Mapped[list[str]] = mapped_column(JSON)
    vendor_names: Mapped[list[str]] = mapped_column(JSON)
    ai_model: Mapped[str] = mapped_column(String(128))
    best_overall_vendor: Mapped[str | None] = mapped_column(String(255), nullable=True)
    result_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
