import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ContractReviewRequest(BaseModel):
    document_id: uuid.UUID
    vendor_name: str | None = None
    contract_type: str | None = None


class ContractResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    document_id: uuid.UUID
    vendor_name: str | None
    contract_type: str | None
    status: str
    created_at: datetime


class ContractRubricScoreResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    category: str
    score: Decimal
    max_score: Decimal
    explanation: str
    citation: str | None


class ContractRiskFlagResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    risk_type: str
    severity: str
    explanation: str
    citation: str | None
    suggested_fix: str | None


class ContractReviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    contract_id: uuid.UUID
    model_name: str
    flow_name: str
    total_score: Decimal
    risk_level: str
    executive_summary: str
    recommendation: str
    rubric_scores: list[ContractRubricScoreResponse]
    risk_flags: list[ContractRiskFlagResponse]
    created_at: datetime


class ContractWithReviewResponse(BaseModel):
    contract: ContractResponse
    review: ContractReviewResponse


class ContractUpdateRequest(BaseModel):
    vendor_name: str | None = None
    contract_type: str | None = None


class ContractReviewUpdateRequest(BaseModel):
    executive_summary: str | None = None
    recommendation: str | None = None
    risk_level: Literal["low", "medium", "high"] | None = None
    total_score: int | None = Field(None, ge=0, le=100)
