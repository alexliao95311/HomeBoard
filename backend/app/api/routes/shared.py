import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_database_session
from app.models.contract import Contract
from app.models.contract_comparison import ContractComparison
from app.models.contract_review import ContractReview, ContractRiskFlag, ContractRubricScore
from app.schemas.contract import (
    ContractCompareResponse,
    ContractResponse,
    ContractReviewResponse,
    ContractRiskFlagResponse,
    ContractRubricScoreResponse,
    ContractWithReviewResponse,
)

router = APIRouter()


@router.get("/review/{token}", response_model=ContractWithReviewResponse)
def get_shared_review(
    token: str,
    session: Annotated[Session, Depends(get_database_session)],
) -> ContractWithReviewResponse:
    try:
        token_uuid = uuid.UUID(token)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shared review not found")

    review = session.scalar(
        select(ContractReview).where(ContractReview.share_token == token_uuid)
    )
    if review is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shared review not found")

    contract = session.scalar(select(Contract).where(Contract.id == review.contract_id))
    if contract is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shared review not found")

    rubric_scores = list(
        session.scalars(
            select(ContractRubricScore).where(ContractRubricScore.contract_review_id == review.id)
        )
    )
    risk_flags = list(
        session.scalars(
            select(ContractRiskFlag).where(ContractRiskFlag.contract_review_id == review.id)
        )
    )

    raw = review.raw_output_json or {}
    return ContractWithReviewResponse(
        contract=ContractResponse.model_validate(contract, from_attributes=True),
        review=ContractReviewResponse(
            id=review.id,
            contract_id=review.contract_id,
            model_name=review.model_name,
            flow_name=review.flow_name,
            total_score=review.total_score,
            risk_level=review.risk_level,
            executive_summary=review.executive_summary,
            recommendation=review.recommendation,
            created_at=review.created_at,
            rubric_scores=[
                ContractRubricScoreResponse.model_validate(rs, from_attributes=True)
                for rs in rubric_scores
            ],
            risk_flags=[
                ContractRiskFlagResponse.model_validate(rf, from_attributes=True)
                for rf in risk_flags
            ],
            board_questions=raw.get("board_questions", []),
            negotiation_points=raw.get("negotiation_points", []),
        ),
    )


@router.get("/comparison/{token}", response_model=ContractCompareResponse)
def get_shared_comparison(
    token: str,
    session: Annotated[Session, Depends(get_database_session)],
) -> ContractCompareResponse:
    try:
        token_uuid = uuid.UUID(token)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shared comparison not found")

    row = session.scalar(
        select(ContractComparison).where(ContractComparison.share_token == token_uuid)
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shared comparison not found")

    data = dict(row.result_json)
    data["comparison_id"] = str(row.id)
    return ContractCompareResponse.model_validate(data)
