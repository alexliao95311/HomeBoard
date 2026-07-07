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


class BulkDeleteRequest(BaseModel):
    ids: list[uuid.UUID]


class BulkDeleteResponse(BaseModel):
    deleted_count: int


class AiCategorizeResponse(BaseModel):
    updated_count: int
    skipped_count: int  # transactions where AI returned an invalid/unknown category
