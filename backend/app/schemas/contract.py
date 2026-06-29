import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer


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
    board_questions: list[dict] = []
    negotiation_points: list[dict] = []
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


class ContractCompareRequest(BaseModel):
    contract_ids: list[uuid.UUID] = Field(..., min_length=2, max_length=5)


class RankedContract(BaseModel):
    rank: int
    contract_id: uuid.UUID
    vendor_name: str | None
    contract_type: str | None
    total_score: Decimal
    risk_level: str


class SideBySideRow(BaseModel):
    category: str
    scores: dict[str, Decimal]
    max_score: Decimal

    @field_serializer("scores")
    def serialize_scores(self, v: dict[str, Decimal]) -> dict[str, float]:
        return {k: float(val) for k, val in v.items()}


class AiPerContractNote(BaseModel):
    contract_id: str
    strengths: list[str]
    weaknesses: list[str]
    verdict: str


class ContractCompareResponse(BaseModel):
    comparison_id: uuid.UUID
    ai_summary: str
    ai_model: str
    ai_per_contract: list[AiPerContractNote]
    ai_critical_differences: list[str]
    ranked_contracts: list[RankedContract]
    side_by_side_table: list[SideBySideRow]
    best_overall: str
    lowest_risk: str
    best_value: str
    key_differences: list[str]


class ContractComparisonListItem(BaseModel):
    id: uuid.UUID
    vendor_names: list[str]
    ai_model: str
    best_overall_vendor: str | None
    created_at: datetime
