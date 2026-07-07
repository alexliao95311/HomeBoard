import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class TransactionUploadCsvRequest(BaseModel):
    document_id: uuid.UUID
    bank_account_name: str | None = None
    fund_type: str | None = None


class TransactionPreview(BaseModel):
    date: date
    description: str
    amount: Decimal
    transaction_type: str
    category: str | None


class TransactionUploadCsvResponse(BaseModel):
    imported_count: int
    skipped_count: int
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
