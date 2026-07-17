from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes import documents as document_routes
from app.api.routes.auth import get_current_user
from app.database import Base, get_database_session
from app.main import app
from app.models.transaction import Transaction
from app.schemas.auth import AuthenticatedUser

_INVOICE_CSV = (
    b"Vendor Name,Amount,Invoice Date,Due Date,Status,Invoice,Reference,AccountNumber\n"
    b"ABC Landscaping,800.00,08/01/2025,08/20/2025,Paid,INV-100,,1234\n"
)
_OPERATING_CSV = (
    b"Post Date,Customer Ref,Debit,Credit,BAI Description,Detail,Account Number\n"
    b"08/05/2025,REF555,800.00,,CHECK ABC LANDSCAPING,,8050388751\n"
    b"08/10/2025,XFER1,5000.00,,TRANSFER TO RESERVE,,8050388751\n"
)
_RESERVE_CSV = (
    b"Post Date,Customer Ref,Debit,Credit,BAI Description,Detail,Account Number\n"
    b"08/10/2025,XFER1,,5000.00,TRANSFER FROM OPERATING,,8410320037\n"
)


@pytest.fixture
def reconciled_import_client(tmp_path: Path):
    test_engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(test_engine)
    test_session = sessionmaker(bind=test_engine, expire_on_commit=False)

    def override_session():
        with test_session() as session:
            yield session

    def override_user() -> AuthenticatedUser:
        return AuthenticatedUser(uid="u1", email="board@example.com", name="Board Member", email_verified=True)

    app.dependency_overrides[get_database_session] = override_session
    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[document_routes.get_upload_root] = lambda: tmp_path / "uploads"

    yield TestClient(app), test_session

    app.dependency_overrides.clear()
    test_engine.dispose()


def _upload_csv(client: TestClient, filename: str, content: bytes) -> str:
    response = client.post(
        "/documents/upload",
        data={"document_type": "financial"},
        files={"file": (filename, content, "text/csv")},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_import_reconciled_avoids_double_counting_overlaps(reconciled_import_client) -> None:
    client, test_session = reconciled_import_client

    doc_ids = [
        _upload_csv(client, "invoice_export.csv", _INVOICE_CSV),
        _upload_csv(client, "operating_activity.csv", _OPERATING_CSV),
        _upload_csv(client, "reserve_activity.csv", _RESERVE_CSV),
    ]

    response = client.post(
        "/api/v1/financials/transactions/import-reconciled",
        json={"document_ids": doc_ids},
    )

    assert response.status_code == 201
    body = response.json()

    # invoice is covered by the matching bank payment -> not inserted as its own transaction
    assert body["imported_count"] == 3
    assert body["invoice_matched_skipped_count"] == 1
    assert body["internal_transfer_count"] == 1
    assert body["exact_duplicate_skipped_count"] == 0

    match_types = {m["match_type"] for m in body["matches"]}
    assert match_types == {"invoice_payment_match", "internal_transfer"}

    with test_session() as session:
        txs = list(session.scalars(select(Transaction).order_by(Transaction.date)))

    assert len(txs) == 3
    by_description = {t.description: t for t in txs}

    # the $800 landscaping cost appears exactly once, as an expense from the bank record —
    # not a second time as "income" from the invoice file
    assert "ABC Landscaping" not in by_description
    landscaping_expense = by_description["CHECK ABC LANDSCAPING"]
    assert float(landscaping_expense.amount) == -800.0
    assert landscaping_expense.transaction_type == "expense"

    # the operating<->reserve transfer legs are marked "transfer", not income/expense
    transfer_out = by_description["TRANSFER TO RESERVE"]
    transfer_in = by_description["TRANSFER FROM OPERATING"]
    assert transfer_out.transaction_type == "transfer"
    assert transfer_in.transaction_type == "transfer"


def test_import_reconciled_report_excludes_transfers_and_matched_invoice(reconciled_import_client) -> None:
    client, test_session = reconciled_import_client

    doc_ids = [
        _upload_csv(client, "invoice_export.csv", _INVOICE_CSV),
        _upload_csv(client, "operating_activity.csv", _OPERATING_CSV),
        _upload_csv(client, "reserve_activity.csv", _RESERVE_CSV),
    ]
    client.post("/api/v1/financials/transactions/import-reconciled", json={"document_ids": doc_ids})

    report = client.post(
        "/api/v1/financials/reports/generate",
        json={"period_start": "2025-08-01", "period_end": "2025-08-31"},
    )

    assert report.status_code == 201
    summary = report.json()["report_json"]["executive_summary"]
    assert summary["total_income"] == 0.0
    assert summary["total_expenses"] == 800.0
    assert summary["net_income"] == -800.0


def test_import_reconciled_requires_owned_documents(reconciled_import_client) -> None:
    client, test_session = reconciled_import_client

    response = client.post(
        "/api/v1/financials/transactions/import-reconciled",
        json={"document_ids": ["00000000-0000-0000-0000-000000000000"]},
    )

    assert response.status_code == 404
