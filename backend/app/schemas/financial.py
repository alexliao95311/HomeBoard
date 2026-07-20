import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class TransactionCreateRequest(BaseModel):
    date: date
    description: str
    amount: Decimal = Field(gt=0)
    transaction_type: Literal["income", "expense", "transfer"]
    vendor_name: str | None = None
    category: str | None = None
    fund_type: str | None = None
    bank_account_name: str | None = None
    skip_duplicates: bool = True


class TransactionUploadCsvRequest(BaseModel):
    document_id: uuid.UUID
    bank_account_name: str | None = None
    fund_type: str | None = None
    skip_duplicates: bool = True
    force_expense: bool = False


class TransactionPreview(BaseModel):
    date: date
    description: str
    amount: Decimal
    transaction_type: str
    category: str | None


class TransactionUploadCsvResponse(BaseModel):
    imported_count: int
    skipped_count: int
    duplicate_count: int
    warnings: list[str]
    detected_columns: dict[str, str]
    preview: list[TransactionPreview]


class TransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    bank_account_id: uuid.UUID | None
    source_document_id: uuid.UUID | None
    date: date
    description: str
    amount: Decimal
    transaction_type: str
    vendor_name: str | None
    category: str | None
    fund_type: str | None
    confidence_score: Decimal | None
    created_at: datetime


class TransactionUpdateRequest(BaseModel):
    category: str | None = None
    vendor_name: str | None = None
    fund_type: str | None = None
    transaction_type: str | None = None
    amount: Decimal | None = None
    description: str | None = None


class BulkDeleteRequest(BaseModel):
    ids: list[uuid.UUID]


class BulkDeleteResponse(BaseModel):
    deleted_count: int


class AiCategorizeResponse(BaseModel):
    updated_count: int
    skipped_count: int  # transactions where AI returned an invalid/unknown category


class ExecutiveSummary(BaseModel):
    total_income: float
    total_expenses: float
    net_income: float


class CategoryAmount(BaseModel):
    category: str
    amount: float


class BudgetVsActualLine(BaseModel):
    category: str
    budget_amount: float | None
    actual_amount: float
    variance: float | None
    ytd_budget_amount: float | None
    ytd_actual_amount: float
    ytd_variance: float | None
    annual_budget_amount: float | None


class FundSection(BaseModel):
    executive_summary: ExecutiveSummary
    expenses_by_category: list[CategoryAmount]
    income_by_category: list[CategoryAmount]


class FinancialReportJson(BaseModel):
    organization_name: str | None
    period_start: date
    period_end: date
    fiscal_year: int
    ytd_start: date
    executive_summary: ExecutiveSummary
    ytd_summary: ExecutiveSummary
    operating: FundSection
    reserve: FundSection
    expenses_by_category: list[CategoryAmount]
    income_by_category: list[CategoryAmount]
    budget_vs_actual: list[BudgetVsActualLine]
    ending_cash_estimate: float
    notes: list[str]


class FinancialReportGenerateRequest(BaseModel):
    period_start: date
    period_end: date
    budget_id: uuid.UUID | None = None


class FinancialReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    period_start: date
    period_end: date
    report_json: FinancialReportJson
    created_at: datetime


class FinancialReportListItem(BaseModel):
    id: uuid.UUID
    period_start: date
    period_end: date
    created_at: datetime
    executive_summary: ExecutiveSummary


class ReconciledImportRequest(BaseModel):
    document_ids: list[uuid.UUID] = Field(min_length=1)


class ReconciliationMatchOut(BaseModel):
    match_type: Literal["invoice_payment_match", "internal_transfer", "same_account_reversal"]
    confidence: Literal["high", "medium", "low"]
    amount: float
    should_double_count: bool
    reason: str
    invoice_record_id: str | None = None
    bank_record_id: str | None = None
    from_record_id: str | None = None
    to_record_id: str | None = None
    net_effect: float | None = None
    should_count_as_income: bool | None = None
    should_count_as_expense: bool | None = None


class ReconciliationFlagOut(BaseModel):
    flag_type: str
    confidence: Literal["high", "medium", "low"]
    record_ids: list[str]
    amount: float | None
    reason: str
    should_double_count: bool


class ReconciledImportResponse(BaseModel):
    imported_count: int
    exact_duplicate_skipped_count: int
    invoice_matched_skipped_count: int
    internal_transfer_count: int
    matches: list[ReconciliationMatchOut]
    flags: list[ReconciliationFlagOut]
    warnings: list[str]


class BudgetLineInput(BaseModel):
    category: str
    monthly_budget: Decimal | None = None
    annual_budget: Decimal | None = None
    fund_type: str | None = None


class BudgetCreateRequest(BaseModel):
    fiscal_year: int
    lines: list[BudgetLineInput] = Field(min_length=1)


class BudgetLineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    category: str
    monthly_budget: Decimal | None
    annual_budget: Decimal | None
    fund_type: str | None


class BudgetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    fiscal_year: int
    created_at: datetime
    lines: list[BudgetLineOut]


class BudgetListItem(BaseModel):
    id: uuid.UUID
    fiscal_year: int
    created_at: datetime
    line_count: int
