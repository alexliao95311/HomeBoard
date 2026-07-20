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
def budget_client():
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

    yield TestClient(app), test_session

    app.dependency_overrides.clear()
    test_engine.dispose()


def test_create_list_and_get_budget(budget_client) -> None:
    client, test_session = budget_client

    response = client.post(
        "/api/v1/financials/budgets",
        json={
            "fiscal_year": 2026,
            "lines": [
                {"category": "Landscaping", "monthly_budget": "1200.00"},
                {"category": "Utilities", "monthly_budget": "500.00", "fund_type": "operating"},
            ],
        },
    )
    assert response.status_code == 201
    body = response.json()
    budget_id = body["id"]
    assert len(body["lines"]) == 2
    assert {line["category"] for line in body["lines"]} == {"Landscaping", "Utilities"}

    list_response = client.get("/api/v1/financials/budgets")
    assert list_response.status_code == 200
    listed = list_response.json()
    assert len(listed) == 1
    assert listed[0]["id"] == budget_id
    assert listed[0]["line_count"] == 2

    detail_response = client.get(f"/api/v1/financials/budgets/{budget_id}")
    assert detail_response.status_code == 200
    assert detail_response.json()["fiscal_year"] == 2026


def test_get_budget_not_found(budget_client) -> None:
    client, test_session = budget_client

    response = client.get("/api/v1/financials/budgets/00000000-0000-0000-0000-000000000000")

    assert response.status_code == 404


def test_report_generation_uses_created_budget_for_budget_vs_actual(budget_client) -> None:
    client, test_session = budget_client

    budget_response = client.post(
        "/api/v1/financials/budgets",
        json={"fiscal_year": 2026, "lines": [{"category": "Landscaping", "monthly_budget": "1200.00"}]},
    )
    budget_id = budget_response.json()["id"]

    tx_response = client.post(
        "/api/v1/financials/transactions",
        json={
            "date": "2026-01-10",
            "description": "Landscaping invoice",
            "amount": "2400.00",
            "transaction_type": "expense",
            "category": "Landscaping",
        },
    )
    assert tx_response.status_code == 201

    report_response = client.post(
        "/api/v1/financials/reports/generate",
        json={"period_start": "2026-01-01", "period_end": "2026-01-31", "budget_id": budget_id},
    )
    assert report_response.status_code == 201
    budget_vs_actual = report_response.json()["report_json"]["budget_vs_actual"]
    landscaping = next(line for line in budget_vs_actual if line["category"] == "Landscaping")
    assert landscaping["budget_amount"] == 1200.0
    assert landscaping["actual_amount"] == 2400.0
    assert landscaping["variance"] == -1200.0
