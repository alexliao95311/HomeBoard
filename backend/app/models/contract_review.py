import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ContractReview(Base):
    __tablename__ = "contract_reviews"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    contract_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("contracts.id", ondelete="CASCADE"), index=True
    )
    model_name: Mapped[str] = mapped_column(String(128))
    flow_name: Mapped[str] = mapped_column(String(128))
    total_score: Mapped[Decimal] = mapped_column(Numeric(7, 2))
    risk_level: Mapped[str] = mapped_column(String(32), index=True)
    executive_summary: Mapped[str] = mapped_column(Text)
    recommendation: Mapped[str] = mapped_column(Text)
    raw_output_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    share_token: Mapped[uuid.UUID | None] = mapped_column(unique=True, nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class ContractRubricScore(Base):
    __tablename__ = "contract_rubric_scores"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    contract_review_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("contract_reviews.id", ondelete="CASCADE"), index=True
    )
    category: Mapped[str] = mapped_column(String(128))
    score: Mapped[Decimal] = mapped_column(Numeric(7, 2))
    max_score: Mapped[Decimal] = mapped_column(Numeric(7, 2))
    explanation: Mapped[str] = mapped_column(Text)
    citation: Mapped[str | None] = mapped_column(Text)


class ContractRiskFlag(Base):
    __tablename__ = "contract_risk_flags"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    contract_review_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("contract_reviews.id", ondelete="CASCADE"), index=True
    )
    risk_type: Mapped[str] = mapped_column(String(128))
    severity: Mapped[str] = mapped_column(String(32), index=True)
    explanation: Mapped[str] = mapped_column(Text)
    citation: Mapped[str | None] = mapped_column(Text)
    suggested_fix: Mapped[str | None] = mapped_column(Text)
