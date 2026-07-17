"""Verifies overlaps are caught even when related files are imported in
SEPARATE requests (e.g. weeks apart), not just when bundled in one batch —
the gap the single-batch reconciliation in test_financial_reconciled_import.py
doesn't cover.
"""
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


@pytest.fixture
def history_client(tmp_path: Path):
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


def _import_reconciled(client: TestClient, doc_ids: list[str]):
    response = client.post(
        "/api/v1/financials/transactions/import-reconciled",
        json={"document_ids": doc_ids},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_invoice_matched_against_bank_payment_imported_weeks_earlier(history_client) -> None:
    client, test_session = history_client

    # Week 1: operating activity (including the check payment) is imported alone.
    operating_csv = (
        b"Post Date,Customer Ref,Debit,Credit,BAI Description,Detail,Account Number\n"
        b"08/05/2025,REF555,800.00,,CHECK ABC LANDSCAPING,,8050388751\n"
    )
    operating_doc_id = _upload_csv(client, "operating_activity.csv", operating_csv)
    first_import = _import_reconciled(client, [operating_doc_id])
    assert first_import["imported_count"] == 1
    assert first_import["invoice_matched_skipped_count"] == 0

    # Week 4: the invoice export arrives separately — should match the ALREADY
    # committed bank payment instead of being inserted as a second expense.
    invoice_csv = (
        b"Vendor Name,Amount,Invoice Date,Due Date,Status,Invoice,Reference,AccountNumber\n"
        b"ABC Landscaping,800.00,08/01/2025,08/20/2025,Paid,INV-100,,1234\n"
    )
    invoice_doc_id = _upload_csv(client, "invoice_export.csv", invoice_csv)
    second_import = _import_reconciled(client, [invoice_doc_id])

    assert second_import["invoice_matched_skipped_count"] == 1
    assert second_import["imported_count"] == 0
    match_types = {m["match_type"] for m in second_import["matches"]}
    assert "invoice_payment_match" in match_types

    with test_session() as session:
        txs = list(session.scalars(select(Transaction)))
    assert len(txs) == 1
    assert txs[0].description == "CHECK ABC LANDSCAPING"
    assert float(txs[0].amount) == -800.0


def test_internal_transfer_matched_against_leg_imported_earlier(history_client) -> None:
    client, test_session = history_client

    operating_csv = (
        b"Post Date,Customer Ref,Debit,Credit,BAI Description,Detail,Account Number\n"
        b"08/10/2025,XFER1,5000.00,,TRANSFER TO RESERVE,,8050388751\n"
    )
    operating_doc_id = _upload_csv(client, "operating_activity.csv", operating_csv)
    _import_reconciled(client, [operating_doc_id])

    reserve_csv = (
        b"Post Date,Customer Ref,Debit,Credit,BAI Description,Detail,Account Number\n"
        b"08/10/2025,XFER1,,5000.00,TRANSFER FROM OPERATING,,8410320037\n"
    )
    reserve_doc_id = _upload_csv(client, "reserve_activity.csv", reserve_csv)
    second_import = _import_reconciled(client, [reserve_doc_id])

    assert second_import["internal_transfer_count"] == 1
    assert second_import["imported_count"] == 1  # the reserve leg is still inserted, just tagged "transfer"

    with test_session() as session:
        txs = list(session.scalars(select(Transaction)))
    assert len(txs) == 2
    assert {t.transaction_type for t in txs} == {"transfer"}

    report = client.post(
        "/api/v1/financials/reports/generate",
        json={"period_start": "2025-08-01", "period_end": "2025-08-31"},
    )
    summary = report.json()["report_json"]["executive_summary"]
    assert summary["total_income"] == 0.0
    assert summary["total_expenses"] == 0.0


def test_bank_payment_matched_against_invoice_imported_earlier(history_client) -> None:
    client, test_session = history_client

    # Week 1: the invoice arrives first, alone, before the bank has paid it yet.
    invoice_csv = (
        b"Vendor Name,Amount,Invoice Date,Due Date,Status,Invoice,Reference,AccountNumber\n"
        b"ABC Landscaping,800.00,08/01/2025,08/20/2025,Pending,INV-100,,1234\n"
    )
    invoice_doc_id = _upload_csv(client, "invoice_export.csv", invoice_csv)
    first_import = _import_reconciled(client, [invoice_doc_id])
    assert first_import["imported_count"] == 1

    # Week 2: the bank statement shows the actual payment — should match the
    # EXISTING invoice-derived transaction rather than being added as a second expense.
    operating_csv = (
        b"Post Date,Customer Ref,Debit,Credit,BAI Description,Detail,Account Number\n"
        b"08/05/2025,REF555,800.00,,CHECK ABC LANDSCAPING,,8050388751\n"
    )
    operating_doc_id = _upload_csv(client, "operating_activity.csv", operating_csv)
    second_import = _import_reconciled(client, [operating_doc_id])

    assert second_import["imported_count"] == 0
    assert second_import["invoice_matched_skipped_count"] == 1

    with test_session() as session:
        txs = list(session.scalars(select(Transaction)))
    assert len(txs) == 1
    assert txs[0].description == "ABC Landscaping"
    assert float(txs[0].amount) == -800.0


def test_reimporting_overlapping_bank_export_is_caught_as_exact_duplicate(history_client) -> None:
    client, test_session = history_client

    # August export, ending with a few late-month rows.
    august_csv = (
        b"Post Date,Customer Ref,Debit,Credit,BAI Description,Detail,Account Number\n"
        b"08/28/2025,REF900,,250.00,LOCKBOX DEPOSIT,,8050388751\n"
    )
    august_doc_id = _upload_csv(client, "operating_august.csv", august_csv)
    _import_reconciled(client, [august_doc_id])

    # September export from the SAME bank account overlaps the last few August days.
    september_csv = (
        b"Post Date,Customer Ref,Debit,Credit,BAI Description,Detail,Account Number\n"
        b"08/28/2025,REF900,,250.00,LOCKBOX DEPOSIT,,8050388751\n"
        b"09/03/2025,REF901,,300.00,LOCKBOX DEPOSIT,,8050388751\n"
    )
    september_doc_id = _upload_csv(client, "operating_september.csv", september_csv)
    second_import = _import_reconciled(client, [september_doc_id])

    assert second_import["exact_duplicate_skipped_count"] == 1
    assert second_import["imported_count"] == 1  # only the genuinely new Sept 3 row

    with test_session() as session:
        txs = list(session.scalars(select(Transaction)))
    assert len(txs) == 2
    dates = sorted(str(t.date) for t in txs)
    assert dates == ["2025-08-28", "2025-09-03"]
