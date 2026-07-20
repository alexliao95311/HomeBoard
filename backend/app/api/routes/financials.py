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
from app.models.budget import Budget, BudgetLine
from app.models.document import Document
from app.models.financial_report import FinancialReport
from app.models.transaction import Transaction
from app.schemas.financial import (
    AiCategorizeResponse,
    BudgetCreateRequest,
    BudgetListItem,
    BudgetLineOut,
    BudgetResponse,
    BulkDeleteRequest,
    BulkDeleteResponse,
    ExecutiveSummary,
    FinancialReportGenerateRequest,
    FinancialReportListItem,
    FinancialReportResponse,
    ReconciledImportRequest,
    ReconciledImportResponse,
    ReconciliationFlagOut,
    ReconciliationMatchOut,
    TransactionCreateRequest,
    TransactionPreview,
    TransactionResponse,
    TransactionUpdateRequest,
    TransactionUploadCsvRequest,
    TransactionUploadCsvResponse,
)
from app.schemas.module import ModuleStatus
from app.services.categorization_service import CATEGORIES, categorize, vendor_key
from app.services.financial_reconciliation import (
    existing_record_from_transaction,
    reconcile_against_history,
    reconcile_financial_files,
)
from app.services.financial_report_service import generate_report_json
from app.services.organization_service import OrganizationContext, get_current_organization
from app.services.transaction_parser import (
    detect_columns_with_ai,
    get_csv_headers_and_samples,
    parse_transaction_csv,
)

_FUND_TYPE_BY_SOURCE = {
    "operating_activity": "operating",
    "reserve_activity": "reserve",
}

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
    "/transactions/import-reconciled",
    response_model=ReconciledImportResponse,
    status_code=status.HTTP_201_CREATED,
)
def import_reconciled_transactions(
    request: ReconciledImportRequest,
    organization: Annotated[OrganizationContext, Depends(get_current_organization)],
    session: Annotated[Session, Depends(get_database_session)],
) -> ReconciledImportResponse:
    """Import multiple financial CSVs (e.g. invoice_export + operating_activity +
    reserve_activity) together, reconciling overlaps before writing transactions.

    Unlike /transactions/upload-csv (one file at a time, no cross-file awareness),
    this normalizes every file first, then excludes exact duplicates and invoices
    already covered by a matched bank payment, and marks operating<->reserve
    transfer legs with transaction_type="transfer" so they don't inflate income
    or expenses in reports.
    """
    documents = list(session.scalars(
        select(Document).where(
            Document.id.in_(request.document_ids),
            Document.organization_id == organization.organization_id,
        )
    ))
    found_ids = {doc.id for doc in documents}
    missing = [str(doc_id) for doc_id in request.document_ids if doc_id not in found_ids]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document(s) not found: {', '.join(missing)}",
        )

    files: list[tuple[str, bytes]] = []
    document_id_by_filename: dict[str, uuid.UUID] = {}
    for document in documents:
        if document.content_type not in _CSV_CONTENT_TYPES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"'{document.original_filename}' is not a CSV file.",
            )
        storage_path = Path(document.storage_path)
        if not storage_path.exists():
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"File not found on disk for '{document.original_filename}'.",
            )
        files.append((document.original_filename, storage_path.read_bytes()))
        document_id_by_filename[document.original_filename] = document.id

    result = reconcile_financial_files(files)

    exact_duplicate_excluded_ids: set[str] = set()
    for flag in result.duplicate_flags:
        if flag.flag_type == "exact_duplicate":
            exact_duplicate_excluded_ids.update(flag.record_ids[1:])

    invoice_matched_excluded_ids = {
        m.invoice_record_id
        for m in result.reconciliation_matches
        if m.match_type == "invoice_payment_match"
    }

    transfer_leg_ids: set[str] = set()
    for m in result.reconciliation_matches:
        if m.match_type == "internal_transfer":
            transfer_leg_ids.add(m.from_record_id)
            transfer_leg_ids.add(m.to_record_id)

    # ── pass 2: reconcile against transactions already committed from earlier
    # imports, so overlaps are caught even when related files (e.g. an invoice
    # export and the bank export that pays it) are imported weeks apart.
    surviving_records = [
        r for r in result.normalized_records
        if r.id not in exact_duplicate_excluded_ids and r.id not in invoice_matched_excluded_ids
    ]
    existing_transactions = list(session.scalars(
        select(Transaction).where(Transaction.organization_id == organization.organization_id)
    ))
    existing_records = [
        existing_record_from_transaction(
            transaction_id=str(tx.id),
            date_value=tx.date,
            amount=Decimal(str(tx.amount)),
            description=tx.description,
            vendor_name=tx.vendor_name,
            source_type=tx.source_type,
            external_ref=tx.external_ref,
            external_account_number=tx.external_account_number,
        )
        for tx in existing_transactions
    ]
    history = reconcile_against_history(surviving_records, existing_records)

    all_excluded_ids = exact_duplicate_excluded_ids | invoice_matched_excluded_ids | history.exact_duplicate_new_ids | history.invoice_matched_new_ids
    all_transfer_ids = transfer_leg_ids | history.transfer_new_ids

    # a transfer leg committed by an EARLIER import (before its pair existed)
    # was inserted as plain income/expense — now that the other leg has
    # arrived, reclassify it so reports stop double-counting it going forward.
    if history.transfer_existing_ids_to_reclassify:
        reclassify_ids = {
            uuid.UUID(rid.removeprefix("tx:")) for rid in history.transfer_existing_ids_to_reclassify
        }
        for tx in existing_transactions:
            if tx.id in reclassify_ids:
                tx.transaction_type = "transfer"

    bank_account_cache: dict[str, uuid.UUID] = {}
    imported_count = 0

    for record in result.normalized_records:
        if record.id in all_excluded_ids:
            continue

        effective_date = record.effective_date()
        if effective_date is None or record.amount == 0:
            continue

        if record.id in all_transfer_ids:
            transaction_type = "transfer"
        elif record.amount > 0:
            transaction_type = "income"
        else:
            transaction_type = "expense"

        fund_type = _FUND_TYPE_BY_SOURCE.get(record.source_type)

        bank_account_id: uuid.UUID | None = None
        if fund_type is not None:
            account_name = fund_type.capitalize()
            if account_name not in bank_account_cache:
                account = _find_or_create_bank_account(
                    session, organization.organization_id, account_name, fund_type,
                )
                bank_account_cache[account_name] = account.id
            bank_account_id = bank_account_cache[account_name]

        description = record.description or record.vendor_name or "Imported transaction"
        category, confidence = categorize(description)

        session.add(Transaction(
            organization_id=organization.organization_id,
            bank_account_id=bank_account_id,
            source_document_id=document_id_by_filename.get(record.source_file),
            date=effective_date,
            description=description,
            amount=record.amount,
            transaction_type=transaction_type,
            vendor_name=record.vendor_name,
            category=category,
            confidence_score=Decimal(str(confidence)),
            fund_type=fund_type,
            source_type=record.source_type,
            external_ref=record.customer_ref,
            external_account_number=record.account_number,
        ))
        imported_count += 1

    session.commit()

    all_matches = result.reconciliation_matches + history.matches
    all_flags = result.duplicate_flags + history.flags

    return ReconciledImportResponse(
        imported_count=imported_count,
        exact_duplicate_skipped_count=len(exact_duplicate_excluded_ids) + len(history.exact_duplicate_new_ids),
        invoice_matched_skipped_count=len(invoice_matched_excluded_ids) + len(history.invoice_matched_new_ids),
        internal_transfer_count=sum(1 for m in all_matches if m.match_type == "internal_transfer"),
        matches=[ReconciliationMatchOut(**m.to_dict()) for m in all_matches],
        flags=[ReconciliationFlagOut(**f.to_dict()) for f in all_flags],
        warnings=result.warnings,
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


@router.post(
    "/reports/generate",
    response_model=FinancialReportResponse,
    status_code=status.HTTP_201_CREATED,
)
def generate_financial_report(
    request: FinancialReportGenerateRequest,
    organization: Annotated[OrganizationContext, Depends(get_current_organization)],
    session: Annotated[Session, Depends(get_database_session)],
) -> FinancialReport:
    if request.period_end < request.period_start:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="period_end must be on or after period_start",
        )

    report_json = generate_report_json(
        session,
        organization.organization_id,
        request.period_start,
        request.period_end,
        request.budget_id,
    )

    report = FinancialReport(
        organization_id=organization.organization_id,
        period_start=request.period_start,
        period_end=request.period_end,
        report_json=report_json,
    )
    session.add(report)
    session.commit()
    session.refresh(report)
    return report


@router.get("/reports", response_model=list[FinancialReportListItem])
def list_financial_reports(
    organization: Annotated[OrganizationContext, Depends(get_current_organization)],
    session: Annotated[Session, Depends(get_database_session)],
) -> list[FinancialReportListItem]:
    reports = session.scalars(
        select(FinancialReport)
        .where(FinancialReport.organization_id == organization.organization_id)
        .order_by(FinancialReport.created_at.desc())
    )
    return [
        FinancialReportListItem(
            id=r.id,
            period_start=r.period_start,
            period_end=r.period_end,
            created_at=r.created_at,
            executive_summary=ExecutiveSummary(**r.report_json["executive_summary"]),
        )
        for r in reports
    ]


@router.get("/reports/{report_id}", response_model=FinancialReportResponse)
def get_financial_report(
    report_id: uuid.UUID,
    organization: Annotated[OrganizationContext, Depends(get_current_organization)],
    session: Annotated[Session, Depends(get_database_session)],
) -> FinancialReport:
    report = session.scalar(
        select(FinancialReport).where(
            FinancialReport.id == report_id,
            FinancialReport.organization_id == organization.organization_id,
        )
    )
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    return report


@router.post("/budgets", response_model=BudgetResponse, status_code=status.HTTP_201_CREATED)
def create_budget(
    request: BudgetCreateRequest,
    organization: Annotated[OrganizationContext, Depends(get_current_organization)],
    session: Annotated[Session, Depends(get_database_session)],
) -> BudgetResponse:
    budget = Budget(organization_id=organization.organization_id, fiscal_year=request.fiscal_year)
    session.add(budget)
    session.flush()

    lines = [
        BudgetLine(
            budget_id=budget.id,
            category=line.category,
            monthly_budget=line.monthly_budget,
            annual_budget=line.annual_budget,
            fund_type=line.fund_type,
        )
        for line in request.lines
    ]
    session.add_all(lines)
    session.commit()
    for line in lines:
        session.refresh(line)

    return BudgetResponse(
        id=budget.id,
        fiscal_year=budget.fiscal_year,
        created_at=budget.created_at,
        lines=[BudgetLineOut.model_validate(line) for line in lines],
    )


@router.get("/budgets", response_model=list[BudgetListItem])
def list_budgets(
    organization: Annotated[OrganizationContext, Depends(get_current_organization)],
    session: Annotated[Session, Depends(get_database_session)],
) -> list[BudgetListItem]:
    budgets = list(session.scalars(
        select(Budget)
        .where(Budget.organization_id == organization.organization_id)
        .order_by(Budget.created_at.desc())
    ))
    line_counts: dict[uuid.UUID, int] = {}
    if budgets:
        lines = session.scalars(
            select(BudgetLine).where(BudgetLine.budget_id.in_([b.id for b in budgets]))
        )
        for line in lines:
            line_counts[line.budget_id] = line_counts.get(line.budget_id, 0) + 1

    return [
        BudgetListItem(
            id=b.id,
            fiscal_year=b.fiscal_year,
            created_at=b.created_at,
            line_count=line_counts.get(b.id, 0),
        )
        for b in budgets
    ]


@router.get("/budgets/{budget_id}", response_model=BudgetResponse)
def get_budget(
    budget_id: uuid.UUID,
    organization: Annotated[OrganizationContext, Depends(get_current_organization)],
    session: Annotated[Session, Depends(get_database_session)],
) -> BudgetResponse:
    budget = session.scalar(
        select(Budget).where(
            Budget.id == budget_id,
            Budget.organization_id == organization.organization_id,
        )
    )
    if budget is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Budget not found")

    lines = list(session.scalars(select(BudgetLine).where(BudgetLine.budget_id == budget.id)))
    return BudgetResponse(
        id=budget.id,
        fiscal_year=budget.fiscal_year,
        created_at=budget.created_at,
        lines=[BudgetLineOut.model_validate(line) for line in lines],
    )
