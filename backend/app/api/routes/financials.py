import json
import re
import uuid
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import delete as sql_delete, or_, select
from sqlalchemy.orm import Session

from app.ai.providers.openrouter_provider import AIProviderError, OpenRouterProvider
from app.config import settings
from app.database import get_database_session
from app.models.bank_account import BankAccount
from app.models.document import Document
from app.models.transaction import Transaction
from app.schemas.financial import (
    AiCategorizeResponse,
    BulkDeleteRequest,
    BulkDeleteResponse,
    TransactionCreateRequest,
    TransactionPreview,
    TransactionResponse,
    TransactionUpdateRequest,
    TransactionUploadCsvRequest,
    TransactionUploadCsvResponse,
)
from app.schemas.module import ModuleStatus
from app.services.categorization_service import CATEGORIES, categorize, vendor_key
from app.services.organization_service import OrganizationContext, get_current_organization
from app.services.transaction_parser import (
    detect_columns_with_ai,
    get_csv_headers_and_samples,
    parse_transaction_csv,
)

router = APIRouter()

_PREVIEW_LIMIT = 10
_CSV_CONTENT_TYPES = {"text/csv", "text/plain"}


def _find_or_create_bank_account(
    session: Session,
    organization_id: uuid.UUID,
    account_name: str,
    fund_type: str | None,
) -> BankAccount:
    account = session.scalar(
        select(BankAccount).where(
            BankAccount.organization_id == organization_id,
            BankAccount.account_name == account_name,
        )
    )
    if account is None:
        account = BankAccount(
            organization_id=organization_id,
            account_name=account_name,
            fund_type=fund_type,
        )
        session.add(account)
        session.flush()
    return account


def _get_org_transaction(
    session: Session,
    transaction_id: uuid.UUID,
    organization_id: uuid.UUID,
) -> Transaction:
    tx = session.scalar(
        select(Transaction).where(
            Transaction.id == transaction_id,
            Transaction.organization_id == organization_id,
        )
    )
    if tx is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    return tx


@router.get("/status", response_model=ModuleStatus)
async def financial_module_status() -> ModuleStatus:
    return ModuleStatus(
        module="Financial oversight",
        status="active",
        message="CSV transaction ingestion is available.",
    )


@router.get("/categories", response_model=list[str])
def list_categories() -> list[str]:
    return CATEGORIES


@router.post(
    "/transactions/upload-csv",
    response_model=TransactionUploadCsvResponse,
    status_code=status.HTTP_201_CREATED,
)
def upload_transaction_csv(
    request: TransactionUploadCsvRequest,
    organization: Annotated[OrganizationContext, Depends(get_current_organization)],
    session: Annotated[Session, Depends(get_database_session)],
) -> TransactionUploadCsvResponse:
    document = session.scalar(
        select(Document).where(
            Document.id == request.document_id,
            Document.organization_id == organization.organization_id,
        )
    )
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    if document.content_type not in _CSV_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Document must be a CSV file. Got content type '{document.content_type}'.",
        )

    storage_path = Path(document.storage_path)
    if not storage_path.exists():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Document file not found on disk.",
        )

    content = storage_path.read_bytes()

    # Pass 1: heuristic column detection
    parse_result = parse_transaction_csv(content)

    # Pass 2: AI fallback when heuristic cannot identify required columns
    used_ai = False
    if not parse_result.transactions and parse_result.warnings:
        ai_col_map = None
        if not settings.use_fake_ai and settings.openrouter_api_key:
            extracted = get_csv_headers_and_samples(content)
            if extracted is not None:
                headers, samples = extracted
                try:
                    ai_col_map = detect_columns_with_ai(
                        headers,
                        samples,
                        provider=OpenRouterProvider(api_key=settings.openrouter_api_key),
                        model=settings.default_model,
                    )
                except AIProviderError:
                    ai_col_map = None

        if ai_col_map is not None:
            parse_result = parse_transaction_csv(content, col_map=ai_col_map)
            used_ai = True

    if not parse_result.transactions and parse_result.warnings:
        if not (not settings.use_fake_ai and settings.openrouter_api_key):
            msg = "Could not detect column layout. AI fallback requires an OpenRouter API key."
        else:
            msg = "Could not parse any transactions."
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": msg, "warnings": parse_result.warnings},
        )

    # ── duplicate detection ───────────────────────────────────────────────────
    parsed_txs = parse_result.transactions
    duplicate_count = 0

    if request.skip_duplicates and parsed_txs:
        date_min = min(t.date for t in parsed_txs)
        date_max = max(t.date for t in parsed_txs)
        existing = list(session.scalars(
            select(Transaction).where(
                Transaction.organization_id == organization.organization_id,
                Transaction.date >= date_min,
                Transaction.date <= date_max,
            )
        ))
        existing_keys = {
            (tx.date, tx.amount, tx.description.lower().strip())
            for tx in existing
        }
        unique: list = []
        for parsed in parsed_txs:
            key = (parsed.date, parsed.amount, parsed.description.lower().strip())
            if key in existing_keys:
                duplicate_count += 1
            else:
                unique.append(parsed)
        parsed_txs = unique

    # ── force expense override (invoices) ─────────────────────────────────────
    if request.force_expense:
        for parsed in parsed_txs:
            parsed.amount = -abs(parsed.amount)
            parsed.transaction_type = "expense"

    # ── insert ────────────────────────────────────────────────────────────────
    bank_account_id: uuid.UUID | None = None
    if request.bank_account_name:
        account = _find_or_create_bank_account(
            session,
            organization.organization_id,
            request.bank_account_name,
            request.fund_type,
        )
        bank_account_id = account.id

    for parsed in parsed_txs:
        category, confidence = categorize(parsed.description)
        # Per-row fund_type (from CSV column) takes precedence over import-level default
        fund_type = parsed.fund_type or request.fund_type
        session.add(Transaction(
            organization_id=organization.organization_id,
            bank_account_id=bank_account_id,
            source_document_id=document.id,
            date=parsed.date,
            description=parsed.description,
            amount=parsed.amount,
            transaction_type=parsed.transaction_type,
            vendor_name=parsed.vendor_name,
            category=category,
            confidence_score=Decimal(str(confidence)),
            fund_type=fund_type,
        ))

    session.commit()

    preview = [
        TransactionPreview(
            date=t.date,
            description=t.description,
            amount=t.amount,
            transaction_type=t.transaction_type,
            category=categorize(t.description)[0],
        )
        for t in parsed_txs[:_PREVIEW_LIMIT]
    ]

    warnings = parse_result.warnings
    if used_ai:
        warnings = [f"[AI column detection used: {parse_result.detected_columns}]"] + warnings

    return TransactionUploadCsvResponse(
        imported_count=len(parsed_txs),
        skipped_count=parse_result.skipped_rows,
        duplicate_count=duplicate_count,
        warnings=warnings,
        detected_columns=parse_result.detected_columns,
        preview=preview,
    )


@router.post(
    "/transactions",
    response_model=TransactionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_transaction(
    request: TransactionCreateRequest,
    organization: Annotated[OrganizationContext, Depends(get_current_organization)],
    session: Annotated[Session, Depends(get_database_session)],
) -> Transaction:
    description = request.description.strip()
    if not description:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Description is required",
        )

    amount = request.amount
    if request.transaction_type == "expense":
        amount = -abs(amount)
    elif request.transaction_type == "income":
        amount = abs(amount)

    if request.skip_duplicates:
        candidates = session.scalars(
            select(Transaction).where(
                Transaction.organization_id == organization.organization_id,
                Transaction.date == request.date,
                Transaction.amount == amount,
            )
        )
        is_duplicate = any(c.description.lower().strip() == description.lower() for c in candidates)
        if is_duplicate:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "message": "A transaction with the same date, amount, and description already exists.",
                    "duplicate": True,
                },
            )

    bank_account_id: uuid.UUID | None = None
    if request.bank_account_name:
        account = _find_or_create_bank_account(
            session,
            organization.organization_id,
            request.bank_account_name,
            request.fund_type,
        )
        bank_account_id = account.id

    category = request.category
    confidence_score = Decimal("1.0")
    if not category:
        category, confidence = categorize(description)
        confidence_score = Decimal(str(confidence))

    tx = Transaction(
        organization_id=organization.organization_id,
        bank_account_id=bank_account_id,
        source_document_id=None,
        date=request.date,
        description=description,
        amount=amount,
        transaction_type=request.transaction_type,
        vendor_name=request.vendor_name,
        category=category,
        confidence_score=confidence_score,
        fund_type=request.fund_type,
    )
    session.add(tx)
    session.commit()
    session.refresh(tx)
    return tx


_AI_CATEGORIZE_SYSTEM = (
    "You are a financial transaction categorizer for HOA (homeowners association) accounting. "
    "Respond with ONLY valid JSON — no explanation, no markdown fences."
)

_AI_CATEGORIZE_BATCH = """\
Assign each transaction to exactly one category from this list:
{categories}

Return a JSON array with one object per transaction:
[{{"id": "<id>", "category": "<category>"}}, ...]

Transactions (format: id|description):
{lines}
"""

_BATCH_SIZE = 50


@router.post("/transactions/ai-categorize", response_model=AiCategorizeResponse)
def ai_categorize_transactions(
    organization: Annotated[OrganizationContext, Depends(get_current_organization)],
    session: Annotated[Session, Depends(get_database_session)],
) -> AiCategorizeResponse:
    uncategorized = list(session.scalars(
        select(Transaction).where(
            Transaction.organization_id == organization.organization_id,
            or_(
                Transaction.category == "Uncategorized",
                Transaction.category.is_(None),
            ),
        )
    ))

    if not uncategorized:
        return AiCategorizeResponse(updated_count=0, skipped_count=0)

    updated = 0

    # ── sweep 1: reuse the category already assigned to the same vendor ────────
    # e.g. every prior "PG&E" transaction was categorized as Utilities, so any
    # new PG&E transaction gets Utilities immediately, no AI call needed.
    known = session.scalars(
        select(Transaction).where(
            Transaction.organization_id == organization.organization_id,
            Transaction.category.is_not(None),
            Transaction.category != "Uncategorized",
        )
    )
    vendor_to_category: dict[str, str] = {}
    for tx in known:
        key = vendor_key(tx.description, tx.vendor_name)
        if key and key not in vendor_to_category:
            vendor_to_category[key] = tx.category

    remaining: list[Transaction] = []
    for tx in uncategorized:
        known_category = vendor_to_category.get(vendor_key(tx.description, tx.vendor_name))
        if known_category:
            tx.category = known_category
            tx.confidence_score = Decimal("0.85")
            updated += 1
        else:
            remaining.append(tx)

    if not remaining:
        session.commit()
        return AiCategorizeResponse(updated_count=updated, skipped_count=0)

    if settings.use_fake_ai or not settings.openrouter_api_key:
        session.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI categorization requires an OpenRouter API key.",
        )

    # ── sweep 2: dedupe remaining transactions by vendor before calling the AI ──
    # Multiple uncategorized rows from the same new vendor only need one AI
    # lookup; the result is then broadcast to the whole group.
    groups: dict[str, list[Transaction]] = {}
    for tx in remaining:
        key = vendor_key(tx.description, tx.vendor_name) or str(tx.id)
        groups.setdefault(key, []).append(tx)
    representative_groups = list(groups.values())

    provider = OpenRouterProvider(api_key=settings.openrouter_api_key)
    category_set = set(CATEGORIES)
    skipped = 0

    # Process in batches to stay within token limits
    for batch_start in range(0, len(representative_groups), _BATCH_SIZE):
        batch = representative_groups[batch_start : batch_start + _BATCH_SIZE]
        id_to_group = {str(group[0].id): group for group in batch}
        batch_size = sum(len(group) for group in batch)
        lines = "\n".join(f"{group[0].id}|{group[0].description}" for group in batch)
        prompt = _AI_CATEGORIZE_BATCH.format(
            categories=", ".join(CATEGORIES),
            lines=lines,
        )
        try:
            raw = provider.complete(
                messages=[
                    {"role": "system", "content": _AI_CATEGORIZE_SYSTEM},
                    {"role": "user", "content": prompt},
                ],
                model=settings.default_model,
            )
        except AIProviderError:
            skipped += batch_size
            continue

        raw = re.sub(r"```(?:json)?\s*", "", raw).strip().strip("`").strip()
        try:
            results: list[dict] = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            skipped += batch_size
            continue

        matched_ids: set[str] = set()
        for item in results:
            tx_id = str(item.get("id", ""))
            category = item.get("category", "")
            if tx_id not in id_to_group or category not in category_set:
                skipped += 1
                continue
            for tx in id_to_group[tx_id]:
                tx.category = category
                tx.confidence_score = Decimal("0.75")
                updated += 1
            matched_ids.add(tx_id)

        for tx_id, group in id_to_group.items():
            if tx_id not in matched_ids:
                skipped += len(group)

    session.commit()
    return AiCategorizeResponse(updated_count=updated, skipped_count=skipped)


@router.patch("/transactions/{transaction_id}", response_model=TransactionResponse)
def update_transaction(
    transaction_id: uuid.UUID,
    request: TransactionUpdateRequest,
    organization: Annotated[OrganizationContext, Depends(get_current_organization)],
    session: Annotated[Session, Depends(get_database_session)],
) -> Transaction:
    tx = _get_org_transaction(session, transaction_id, organization.organization_id)

    for field in request.model_fields_set:
        value = getattr(request, field)
        setattr(tx, field, value)

    # Manual category edits are treated as human-confirmed
    if "category" in request.model_fields_set:
        tx.confidence_score = Decimal("1.0")

    session.commit()
    session.refresh(tx)
    return tx


@router.delete("/transactions/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transaction(
    transaction_id: uuid.UUID,
    organization: Annotated[OrganizationContext, Depends(get_current_organization)],
    session: Annotated[Session, Depends(get_database_session)],
) -> Response:
    _get_org_transaction(session, transaction_id, organization.organization_id)
    session.execute(
        sql_delete(Transaction).where(Transaction.id == transaction_id)
    )
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/transactions/bulk-delete", response_model=BulkDeleteResponse)
def bulk_delete_transactions(
    request: BulkDeleteRequest,
    organization: Annotated[OrganizationContext, Depends(get_current_organization)],
    session: Annotated[Session, Depends(get_database_session)],
) -> BulkDeleteResponse:
    result = session.execute(
        sql_delete(Transaction).where(
            Transaction.id.in_(request.ids),
            Transaction.organization_id == organization.organization_id,
        )
    )
    session.commit()
    return BulkDeleteResponse(deleted_count=result.rowcount)


@router.get("/transactions", response_model=list[TransactionResponse])
def list_transactions(
    organization: Annotated[OrganizationContext, Depends(get_current_organization)],
    session: Annotated[Session, Depends(get_database_session)],
    date_from: Annotated[date | None, Query()] = None,
    date_to: Annotated[date | None, Query()] = None,
) -> list[Transaction]:
    query = (
        select(Transaction)
        .where(Transaction.organization_id == organization.organization_id)
        .order_by(Transaction.date.desc(), Transaction.created_at.desc())
    )
    if date_from is not None:
        query = query.where(Transaction.date >= date_from)
    if date_to is not None:
        query = query.where(Transaction.date <= date_to)

    return list(session.scalars(query))
