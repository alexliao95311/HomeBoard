from decimal import Decimal
from typing import Annotated
import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import delete as sql_delete, select
from sqlalchemy.orm import Session

from app.ai.agents.contract_comparator import (
    ContractComparisonError,
    run_ai_comparison,
    run_fake_comparison,
)
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
from app.models.contract_comparison import ContractComparison
from app.models.contract_review import (
    ContractReview,
    ContractRiskFlag,
    ContractRubricScore,
)
from app.models.document import Document
from app.models.document_text_chunk import DocumentTextChunk
from app.schemas.contract import (
    AiPerContractNote,
    ContractCompareRequest,
    ContractCompareResponse,
    ContractComparisonListItem,
    ContractResponse,
    ContractReviewRequest,
    ContractReviewResponse,
    ContractReviewUpdateRequest,
    ContractRiskFlagResponse,
    ContractRubricScoreResponse,
    ContractUpdateRequest,
    ContractWithReviewResponse,
    RankedContract,
    ShareResponse,
    SideBySideRow,
)
from app.models.user import User
from app.services.organization_service import (
    OrganizationContext,
    get_current_organization,
)

router = APIRouter()


def _preferred_model(session: Session, user_id: uuid.UUID) -> str:
    user = session.scalar(select(User).where(User.id == user_id))
    if user and user.preferred_model:
        return user.preferred_model
    return settings.default_model


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
    raw = review.raw_output_json or {}
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
        board_questions=raw.get("board_questions", []),
        negotiation_points=raw.get("negotiation_points", []),
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
        chosen_model = _preferred_model(session, organization.user_id)
        try:
            result = run_ai_review(
                text_chunks=[c.text for c in chunks],
                vendor_name=request.vendor_name,
                contract_type=request.contract_type,
                provider=OpenRouterProvider(api_key=settings.openrouter_api_key),
                model=chosen_model,
            )
        except ContractReviewError as exc:
            session.rollback()
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"AI review failed: {exc}",
            ) from exc
        model_name = chosen_model
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


@router.post("/compare", response_model=ContractCompareResponse)
def compare_contracts(
    request: ContractCompareRequest,
    organization: Annotated[OrganizationContext, Depends(get_current_organization)],
    session: Annotated[Session, Depends(get_database_session)],
) -> ContractCompareResponse:
    RISK_ORDER = {"low": 0, "medium": 1, "high": 2}
    RISK_PENALTY = {"low": 1.0, "medium": 0.85, "high": 0.70}

    contracts = [
        _get_org_contract(session, cid, organization.organization_id)
        for cid in request.contract_ids
    ]

    reviews: dict[str, ContractReview] = {}
    rubric_map: dict[str, list[ContractRubricScore]] = {}
    for c in contracts:
        review = session.scalar(
            select(ContractReview)
            .where(ContractReview.contract_id == c.id)
            .order_by(ContractReview.created_at.desc())
        )
        if review is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Contract {c.id} ({c.vendor_name or 'unknown vendor'}) has no review yet.",
            )
        reviews[str(c.id)] = review
        rubric_map[str(c.id)] = list(
            session.scalars(
                select(ContractRubricScore).where(
                    ContractRubricScore.contract_review_id == review.id
                )
            )
        )

    # Load contract text chunks for the AI
    text_map: dict[str, str] = {}
    for c in contracts:
        chunks = list(
            session.scalars(
                select(DocumentTextChunk)
                .where(DocumentTextChunk.document_id == c.document_id)
                .order_by(DocumentTextChunk.chunk_index)
            )
        )
        text_map[str(c.id)] = "\n\n".join(ch.text for ch in chunks)

    # Build AI input
    contracts_info = [
        {
            "contract_id": str(c.id),
            "vendor_name": c.vendor_name,
            "contract_type": c.contract_type,
            "total_score": float(reviews[str(c.id)].total_score),
            "risk_level": reviews[str(c.id)].risk_level,
            "rubric_rows": [
                {"category": s.category, "score": float(s.score), "max_score": float(s.max_score)}
                for s in rubric_map[str(c.id)]
            ],
            "contract_text": text_map[str(c.id)],
        }
        for c in contracts
    ]

    if settings.use_fake_ai:
        ai_result = run_fake_comparison(contracts_info)
        ai_model = "placeholder"
    else:
        if not settings.openrouter_api_key:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="OPENROUTER_API_KEY is not configured. Set USE_FAKE_AI=true or add the key.",
            )
        chosen_model = _preferred_model(session, organization.user_id)
        try:
            ai_result = run_ai_comparison(
                contracts_info,
                provider=OpenRouterProvider(api_key=settings.openrouter_api_key),
                model=chosen_model,
            )
        except ContractComparisonError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"AI comparison failed: {exc}",
            ) from exc
        ai_model = chosen_model

    # Code-based ranking
    sorted_contracts = sorted(
        contracts,
        key=lambda c: (
            -float(reviews[str(c.id)].total_score),
            RISK_ORDER.get(reviews[str(c.id)].risk_level, 1),
        ),
    )

    ranked = [
        RankedContract(
            rank=i + 1,
            contract_id=c.id,
            vendor_name=c.vendor_name,
            contract_type=c.contract_type,
            total_score=reviews[str(c.id)].total_score,
            risk_level=reviews[str(c.id)].risk_level,
        )
        for i, c in enumerate(sorted_contracts)
    ]

    # Side-by-side rubric table
    seen_categories: dict[str, Decimal] = {}
    for cid in [str(c.id) for c in contracts]:
        for s in rubric_map[cid]:
            seen_categories.setdefault(s.category, s.max_score)

    side_by_side: list[SideBySideRow] = []
    for category, max_score in seen_categories.items():
        row_scores: dict[str, Decimal] = {}
        for c in contracts:
            cid = str(c.id)
            row_scores[cid] = next(
                (Decimal(str(s.score)) for s in rubric_map[cid] if s.category == category),
                Decimal("0"),
            )
        side_by_side.append(SideBySideRow(category=category, scores=row_scores, max_score=max_score))

    best_overall = sorted_contracts[0]
    lowest_risk_contract = min(
        contracts,
        key=lambda c: (
            RISK_ORDER.get(reviews[str(c.id)].risk_level, 1),
            -float(reviews[str(c.id)].total_score),
        ),
    )
    best_value_contract = max(
        contracts,
        key=lambda c: float(reviews[str(c.id)].total_score)
        * RISK_PENALTY.get(reviews[str(c.id)].risk_level, 0.85),
    )

    def _spread(row: SideBySideRow) -> float:
        vals = list(row.scores.values())
        return float(max(vals)) - float(min(vals))

    key_differences: list[str] = []
    for row in sorted(side_by_side, key=_spread, reverse=True):
        if len(key_differences) >= 3:
            break
        spread = _spread(row)
        if spread == 0:
            break
        best_cid = max(row.scores, key=lambda k: row.scores[k])
        best_vendor = next(
            (c.vendor_name or "Unknown" for c in contracts if str(c.id) == best_cid), "Unknown"
        )
        key_differences.append(
            f"{row.category}: {spread:.0f}-pt spread — {best_vendor} scores highest"
        )

    if not key_differences:
        key_differences = ["Contracts have similar rubric scores across all categories."]

    response = ContractCompareResponse(
        comparison_id=uuid.uuid4(),  # placeholder, replaced after DB insert
        ai_summary=ai_result.summary,
        ai_model=ai_model,
        ai_per_contract=[
            AiPerContractNote(
                contract_id=p.contract_id,
                strengths=p.strengths,
                weaknesses=p.weaknesses,
                verdict=p.verdict,
            )
            for p in ai_result.per_contract
        ],
        ai_critical_differences=ai_result.critical_differences,
        ranked_contracts=ranked,
        side_by_side_table=side_by_side,
        best_overall=str(best_overall.id),
        lowest_risk=str(lowest_risk_contract.id),
        best_value=str(best_value_contract.id),
        key_differences=key_differences,
    )

    comparison = ContractComparison(
        organization_id=organization.organization_id,
        contract_ids=[str(c.id) for c in contracts],
        vendor_names=[c.vendor_name or "Unknown" for c in contracts],
        ai_model=ai_model,
        best_overall_vendor=best_overall.vendor_name,
        result_json=response.model_dump(mode="json"),
    )
    session.add(comparison)
    session.commit()
    session.refresh(comparison)

    response.comparison_id = comparison.id
    # patch stored json with real id
    comparison.result_json["comparison_id"] = str(comparison.id)
    session.commit()

    return response


@router.post("/comparisons/{comparison_id}/share", response_model=ShareResponse)
def share_comparison(
    comparison_id: uuid.UUID,
    organization: Annotated[OrganizationContext, Depends(get_current_organization)],
    session: Annotated[Session, Depends(get_database_session)],
) -> ShareResponse:
    row = session.scalar(
        select(ContractComparison).where(
            ContractComparison.id == comparison_id,
            ContractComparison.organization_id == organization.organization_id,
        )
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comparison not found")
    if row.share_token is None:
        row.share_token = uuid.uuid4()
        session.commit()
        session.refresh(row)
    return ShareResponse(token=str(row.share_token))


@router.get("/comparisons", response_model=list[ContractComparisonListItem])
def list_comparisons(
    organization: Annotated[OrganizationContext, Depends(get_current_organization)],
    session: Annotated[Session, Depends(get_database_session)],
) -> list[ContractComparisonListItem]:
    rows = list(
        session.scalars(
            select(ContractComparison)
            .where(ContractComparison.organization_id == organization.organization_id)
            .order_by(ContractComparison.created_at.desc())
        )
    )
    return [
        ContractComparisonListItem(
            id=row.id,
            vendor_names=row.vendor_names,
            ai_model=row.ai_model,
            best_overall_vendor=row.best_overall_vendor,
            created_at=row.created_at,
        )
        for row in rows
    ]


@router.get("/comparisons/{comparison_id}", response_model=ContractCompareResponse)
def get_comparison(
    comparison_id: uuid.UUID,
    organization: Annotated[OrganizationContext, Depends(get_current_organization)],
    session: Annotated[Session, Depends(get_database_session)],
) -> ContractCompareResponse:
    row = session.scalar(
        select(ContractComparison).where(
            ContractComparison.id == comparison_id,
            ContractComparison.organization_id == organization.organization_id,
        )
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comparison not found")
    data = row.result_json
    data["comparison_id"] = str(row.id)
    return ContractCompareResponse.model_validate(data)


@router.delete("/comparisons/{comparison_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_comparison(
    comparison_id: uuid.UUID,
    organization: Annotated[OrganizationContext, Depends(get_current_organization)],
    session: Annotated[Session, Depends(get_database_session)],
) -> Response:
    row = session.scalar(
        select(ContractComparison).where(
            ContractComparison.id == comparison_id,
            ContractComparison.organization_id == organization.organization_id,
        )
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comparison not found")
    session.execute(sql_delete(ContractComparison).where(ContractComparison.id == comparison_id))
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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


@router.post("/{contract_id}/review/share", response_model=ShareResponse)
def share_contract_review(
    contract_id: uuid.UUID,
    organization: Annotated[OrganizationContext, Depends(get_current_organization)],
    session: Annotated[Session, Depends(get_database_session)],
) -> ShareResponse:
    _get_org_contract(session, contract_id, organization.organization_id)
    review = session.scalar(
        select(ContractReview)
        .where(ContractReview.contract_id == contract_id)
        .order_by(ContractReview.created_at.desc())
    )
    if review is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No review found")
    if review.share_token is None:
        review.share_token = uuid.uuid4()
        session.commit()
        session.refresh(review)
    return ShareResponse(token=str(review.share_token))


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
