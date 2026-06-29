from decimal import Decimal
from typing import Annotated
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_database_session
from app.models.contract import Contract
from app.models.contract_review import (
    ContractReview,
    ContractRiskFlag,
    ContractRubricScore,
)
from app.models.document import Document
from app.schemas.contract import (
    ContractResponse,
    ContractReviewRequest,
    ContractReviewResponse,
    ContractRiskFlagResponse,
    ContractRubricScoreResponse,
    ContractWithReviewResponse,
)
from app.services.organization_service import (
    OrganizationContext,
    get_current_organization,
)

router = APIRouter()

_RUBRIC_ITEMS = [
    (
        "Price / Value",
        "14",
        "20",
        "Pricing appears competitive but includes annual escalation clauses "
        "that could increase costs by up to 5% per year without board approval.",
    ),
    (
        "Scope Clarity",
        "11",
        "15",
        "The scope of work is generally described but lacks specific performance "
        "standards, response-time guarantees, and measurable service outcomes.",
    ),
    (
        "Term / Cancellation",
        "10",
        "15",
        "The contract requires 90 days written notice to terminate, which limits "
        "the HOA's ability to respond quickly to poor vendor performance.",
    ),
    (
        "Liability / Insurance",
        "11",
        "15",
        "Vendor carries general liability coverage, but the indemnification clause "
        "is one-sided and the liability cap is set at one month's service fee.",
    ),
    (
        "Payment Terms",
        "8",
        "10",
        "Payment terms are standard net-30 with a 1.5% monthly late fee. "
        "No early-payment discounts or disputed-invoice procedures are defined.",
    ),
]

_RISK_FLAGS = [
    (
        "Excessive Termination Notice",
        "medium",
        "The contract requires 90 days written notice to terminate for convenience. "
        "This significantly limits HOA flexibility to respond to poor vendor performance "
        "or to change vendors at the end of a budget cycle.",
        "Negotiate to reduce the termination-for-convenience notice period to 30 days "
        "and add a 10-day termination-for-cause clause.",
    ),
    (
        "Liability Cap Too Low",
        "high",
        "Vendor liability is capped at one month's service fee. This amount is unlikely "
        "to cover property damage, injury, or significant service failures on HOA common "
        "areas. The HOA retains substantial uninsured risk.",
        "Request a higher liability cap equal to the total annual contract value. "
        "Verify the vendor carries at least $1M general liability and $500K workers' "
        "compensation coverage and request certificates of insurance.",
    ),
]


def _get_org_contract(
    session: Session,
    contract_id: uuid.UUID,
    organization_id: uuid.UUID,
) -> Contract:
    contract = session.scalar(
        select(Contract).where(
            Contract.id == contract_id,
            Contract.organization_id == organization_id,
        )
    )
    if contract is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contract not found")
    return contract


def _build_review_response(
    review: ContractReview,
    rubric_scores: list[ContractRubricScore],
    risk_flags: list[ContractRiskFlag],
) -> ContractReviewResponse:
    return ContractReviewResponse(
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
    )


@router.post(
    "/review",
    response_model=ContractWithReviewResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_contract_review(
    request: ContractReviewRequest,
    organization: Annotated[OrganizationContext, Depends(get_current_organization)],
    session: Annotated[Session, Depends(get_database_session)],
) -> ContractWithReviewResponse:
    document = session.scalar(
        select(Document).where(
            Document.id == request.document_id,
            Document.organization_id == organization.organization_id,
        )
    )
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    if document.status != "processed":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Document must be processed before review. "
                f"Current status: '{document.status}'. "
                f"Use POST /documents/{document.id}/process first."
            ),
        )

    contract = Contract(
        organization_id=organization.organization_id,
        document_id=document.id,
        vendor_name=request.vendor_name,
        contract_type=request.contract_type,
        status="reviewed",
    )
    session.add(contract)
    session.flush()

    review = ContractReview(
        contract_id=contract.id,
        model_name="placeholder",
        flow_name="fake_reviewer_v1",
        total_score=Decimal("75"),
        risk_level="medium",
        executive_summary=(
            "This is a placeholder review generated by the fake reviewer. "
            "The contract appears to be a standard service agreement with moderate risk. "
            "Key areas requiring board attention include the termination clause, "
            "the vendor liability cap, and the annual price escalation terms. "
            "A qualified reviewer should assess all contract terms before the board votes."
        ),
        recommendation=(
            "Conditionally approve pending negotiation of the termination notice period "
            "and the liability cap. Request updated certificates of insurance before signing. "
            "This recommendation is a placeholder and must be replaced by a real AI review "
            "before board use."
        ),
        raw_output_json={"mode": "placeholder", "version": "fake_reviewer_v1"},
    )
    session.add(review)
    session.flush()

    rubric_scores: list[ContractRubricScore] = []
    for category, score, max_score, explanation in _RUBRIC_ITEMS:
        rs = ContractRubricScore(
            contract_review_id=review.id,
            category=category,
            score=Decimal(score),
            max_score=Decimal(max_score),
            explanation=explanation,
            citation=None,
        )
        session.add(rs)
        rubric_scores.append(rs)

    risk_flags: list[ContractRiskFlag] = []
    for risk_type, severity, explanation, suggested_fix in _RISK_FLAGS:
        rf = ContractRiskFlag(
            contract_review_id=review.id,
            risk_type=risk_type,
            severity=severity,
            explanation=explanation,
            citation=None,
            suggested_fix=suggested_fix,
        )
        session.add(rf)
        risk_flags.append(rf)

    session.commit()
    session.refresh(contract)
    session.refresh(review)
    for rs in rubric_scores:
        session.refresh(rs)
    for rf in risk_flags:
        session.refresh(rf)

    return ContractWithReviewResponse(
        contract=ContractResponse.model_validate(contract, from_attributes=True),
        review=_build_review_response(review, rubric_scores, risk_flags),
    )


@router.get("", response_model=list[ContractResponse])
def list_contracts(
    organization: Annotated[OrganizationContext, Depends(get_current_organization)],
    session: Annotated[Session, Depends(get_database_session)],
) -> list[Contract]:
    return list(
        session.scalars(
            select(Contract)
            .where(Contract.organization_id == organization.organization_id)
            .order_by(Contract.created_at.desc())
        )
    )


@router.get("/{contract_id}", response_model=ContractResponse)
def get_contract(
    contract_id: uuid.UUID,
    organization: Annotated[OrganizationContext, Depends(get_current_organization)],
    session: Annotated[Session, Depends(get_database_session)],
) -> Contract:
    return _get_org_contract(session, contract_id, organization.organization_id)


@router.get("/{contract_id}/review", response_model=ContractReviewResponse)
def get_contract_review(
    contract_id: uuid.UUID,
    organization: Annotated[OrganizationContext, Depends(get_current_organization)],
    session: Annotated[Session, Depends(get_database_session)],
) -> ContractReviewResponse:
    _get_org_contract(session, contract_id, organization.organization_id)

    review = session.scalar(
        select(ContractReview)
        .where(ContractReview.contract_id == contract_id)
        .order_by(ContractReview.created_at.desc())
    )
    if review is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No review found for this contract",
        )

    rubric_scores = list(
        session.scalars(
            select(ContractRubricScore).where(
                ContractRubricScore.contract_review_id == review.id
            )
        )
    )
    risk_flags = list(
        session.scalars(
            select(ContractRiskFlag).where(
                ContractRiskFlag.contract_review_id == review.id
            )
        )
    )

    return _build_review_response(review, rubric_scores, risk_flags)
