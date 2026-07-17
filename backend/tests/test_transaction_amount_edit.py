import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes.auth import get_current_user
from app.database import Base, get_database_session
from app.main import app
from app.schemas.auth import AuthenticatedUser


@pytest.fixture
def tx_client():
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

    yield TestClient(app)

    app.dependency_overrides.clear()
    test_engine.dispose()


def test_amount_and_description_are_editable(tx_client) -> None:
    client = tx_client

    created = client.post(
        "/api/v1/financials/transactions",
        json={
            "date": "2026-05-04",
            "description": "DEPOSIT",
            "amount": "50000.00",
            "transaction_type": "income",
        },
    )
    assert created.status_code == 201
    tx_id = created.json()["id"]
    assert created.json()["amount"] == "50000.00"

    # reclassify as a credit against Legal expense: negative amount, new category/description
    updated = client.patch(
        f"/api/v1/financials/transactions/{tx_id}",
        json={
            "amount": "-50000.00",
            "description": "Insurance settlement — credit to Legal",
            "category": "Legal",
        },
    )
    assert updated.status_code == 200
    body = updated.json()
    assert body["amount"] == "-50000.00"
    assert body["description"] == "Insurance settlement — credit to Legal"
    assert body["category"] == "Legal"

    report = client.post(
        "/api/v1/financials/reports/generate",
        json={"period_start": "2026-05-01", "period_end": "2026-05-31"},
    )
    summary = report.json()["report_json"]["executive_summary"]
    # the transaction_type label is still "income" (untouched), but the report
    # keys off the amount's sign, so it now correctly counts as an expense/credit
    assert summary["total_income"] == 0.0
    assert summary["total_expenses"] == 50000.0
