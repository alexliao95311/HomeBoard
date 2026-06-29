from decimal import Decimal
from typing import Annotated
import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import delete as sql_delete, select
from sqlalchemy.orm import Session

from app.ai.agents.contract_reviewer import (
    ContractReviewError,
    ContractReviewResult,
    run_ai_review,
    run_fake_review,
)
from app.ai.providers.openrouter_provider import OpenRouterProvider
from app.config import settings
from app.database import get_database_session
from app.models.contract import Contract
from app.models.contract_review import (
    ContractReview,
    ContractRiskFlag,
    ContractRubricScore,
)
from app.models.document import Document
from app.models.document_text_chunk import DocumentTextChunk
from app.schemas.contract import (
    ContractResponse,
    ContractReviewRequest,
    ContractReviewResponse,
    ContractReviewUpdateRequest,
    ContractRiskFlagResponse,
    ContractRubricScoreResponse,
    ContractUpdateRequest,
    ContractWithReviewResponse,
)
from app.services.organization_service import (
    OrganizationContext,
    get_current_organization,
)

router = APIRouter()


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


def _persist_review(
    session: Session,
    contract: Contract,
    result: ContractReviewResult,
    model_name: str,
    flow_name: str,
) -> tuple[ContractReview, list[ContractRubricScore], list[ContractRiskFlag]]:
    review = ContractReview(
        contract_id=contract.id,
        model_name=model_name,
        flow_name=flow_name,
        total_score=Decimal(str(result.total_score)),
        risk_level=result.risk_level,
        executive_summary=result.executive_summary,
        recommendation=result.recommendation,
        raw_output_json=result.model_dump(),
    )
    session.add(review)
    session.flush()

    rubric_scores: list[ContractRubricScore] = []
    for rs in result.rubric_scores:
        row = ContractRubricScore(
            contract_review_id=review.id,
            category=rs.category,
            score=Decimal(str(rs.score)),
            max_score=Decimal(str(rs.max_score)),
            explanation=rs.explanation,
            citation=rs.citation,
        )
        session.add(row)
        rubric_scores.append(row)

    risk_flags: list[ContractRiskFlag] = []
    for rf in result.risk_flags:
        row = ContractRiskFlag(
            contract_review_id=review.id,
            risk_type=rf.risk_type,
            severity=rf.severity,
            explanation=rf.explanation,
            citation=rf.citation,
            suggested_fix=rf.suggested_fix,
        )
        session.add(row)
        risk_flags.append(row)

    return review, rubric_scores, risk_flags


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

    if settings.use_fake_ai:
        result = run_fake_review()
        model_name = "placeholder"
        flow_name = "fake_reviewer_v1"
    else:
        if not settings.openrouter_api_key:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="OPENROUTER_API_KEY is not configured. Set USE_FAKE_AI=true or add the key.",
            )
        chunks = list(
            session.scalars(
                select(DocumentTextChunk)
                .where(DocumentTextChunk.document_id == document.id)
                .order_by(DocumentTextChunk.chunk_index)
            )
        )
        try:
            result = run_ai_review(
                text_chunks=[c.text for c in chunks],
                vendor_name=request.vendor_name,
                contract_type=request.contract_type,
                provider=OpenRouterProvider(api_key=settings.openrouter_api_key),
                model=settings.default_model,
            )
        except ContractReviewError as exc:
            session.rollback()
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"AI review failed: {exc}",
            ) from exc
        model_name = settings.default_model
        flow_name = "openrouter_v1"

    review, rubric_scores, risk_flags = _persist_review(
        session, contract, result, model_name, flow_name
    )

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


@router.patch("/{contract_id}", response_model=ContractResponse)
def update_contract(
    contract_id: uuid.UUID,
    request: ContractUpdateRequest,
    organization: Annotated[OrganizationContext, Depends(get_current_organization)],
    session: Annotated[Session, Depends(get_database_session)],
) -> Contract:
    contract = _get_org_contract(session, contract_id, organization.organization_id)
    for field in request.model_fields_set:
        setattr(contract, field, getattr(request, field))
    session.commit()
    session.refresh(contract)
    return contract


@router.patch("/{contract_id}/review", response_model=ContractReviewResponse)
def update_contract_review(
    contract_id: uuid.UUID,
    request: ContractReviewUpdateRequest,
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

    for field in request.model_fields_set:
        value = getattr(request, field)
        if field == "total_score" and value is not None:
            value = Decimal(str(value))
        setattr(review, field, value)

    session.commit()
    session.refresh(review)

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


@router.delete("/{contract_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_contract(
    contract_id: uuid.UUID,
    organization: Annotated[OrganizationContext, Depends(get_current_organization)],
    session: Annotated[Session, Depends(get_database_session)],
) -> Response:
    _get_org_contract(session, contract_id, organization.organization_id)
    session.execute(
        sql_delete(Contract).where(Contract.id == contract_id)
    )
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
