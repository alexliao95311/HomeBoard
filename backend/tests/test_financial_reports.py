from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes.auth import get_current_user
from app.database import Base, get_database_session
from app.main import app
from app.models.budget import Budget, BudgetLine
from app.models.organization import Organization, OrganizationMembership
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.auth import AuthenticatedUser


@pytest.fixture
def report_client():
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(test_engine)
    test_session = sessionmaker(bind=test_engine, expire_on_commit=False)

    def override_session():
        with test_session() as session:
            yield session

    def override_user() -> AuthenticatedUser:
        return AuthenticatedUser(
            uid="firebase-user-one",
            email="board@example.com",
            name="Board Member",
            email_verified=True,
        )

    app.dependency_overrides[get_database_session] = override_session
    app.dependency_overrides[get_current_user] = override_user

    yield TestClient(app), test_session

    app.dependency_overrides.clear()
    test_engine.dispose()


def _seed_organization(test_session):
    """Provision the same org the API would create for firebase-user-one, and return its id."""
    with test_session() as session:
        user = User(firebase_uid="firebase-user-one", email="board@example.com", name="Board Member")
        session.add(user)
        session.flush()
        organization = Organization(name="Board Member's HOA")
        session.add(organization)
        session.flush()
        session.add(OrganizationMembership(organization_id=organization.id, user_id=user.id, role="admin"))
        session.commit()
        return organization.id


def _add_transaction(
    test_session, organization_id, tx_date, description, amount, category,
    fund_type=None, transaction_type=None,
):
    with test_session() as session:
        session.add(Transaction(
            organization_id=organization_id,
            date=tx_date,
            description=description,
            amount=amount,
            transaction_type=transaction_type or ("income" if amount > 0 else "expense"),
            category=category,
            fund_type=fund_type,
        ))
        session.commit()


def _add_budget_with_landscaping_line(test_session, organization_id, monthly_budget):
    with test_session() as session:
        budget = Budget(organization_id=organization_id, fiscal_year=2026)
        session.add(budget)
        session.flush()
        session.add(BudgetLine(budget_id=budget.id, category="Landscaping", monthly_budget=monthly_budget))
        session.commit()
        return budget.id


def test_generate_report_income_expenses_and_budget_vs_actual(report_client) -> None:
    client, test_session = report_client
    organization_id = _seed_organization(test_session)

    _add_transaction(test_session, organization_id, date(2026, 1, 5), "Assessment income", 5000, "Assessments")
    _add_transaction(test_session, organization_id, date(2026, 1, 10), "Landscaping invoice", -2400, "Landscaping")
    _add_transaction(test_session, organization_id, date(2026, 1, 12), "Utility bill", -1500, "Utilities")
    _add_transaction(test_session, organization_id, date(2026, 1, 15), "Insurance premium", -1465, "Insurance")
    budget_id = _add_budget_with_landscaping_line(test_session, organization_id, monthly_budget=1200)

    response = client.post(
        "/api/v1/financials/reports/generate",
        json={"period_start": "2026-01-01", "period_end": "2026-01-31", "budget_id": str(budget_id)},
    )

    assert response.status_code == 201
    body = response.json()
    summary = body["report_json"]["executive_summary"]
    assert summary["total_income"] == 5000.0
    assert summary["total_expenses"] == 5365.0
    assert summary["net_income"] == -365.0

    landscaping = next(
        line for line in body["report_json"]["budget_vs_actual"] if line["category"] == "Landscaping"
    )
    assert landscaping["budget_amount"] == 1200.0
    assert landscaping["actual_amount"] == 2400.0
    assert landscaping["variance"] == -1200.0

    report_id = body["id"]

    list_response = client.get("/api/v1/financials/reports")
    assert list_response.status_code == 200
    listed = list_response.json()
    assert len(listed) == 1
    assert listed[0]["id"] == report_id
    assert listed[0]["executive_summary"]["net_income"] == -365.0

    detail_response = client.get(f"/api/v1/financials/reports/{report_id}")
    assert detail_response.status_code == 200
    assert detail_response.json()["report_json"]["executive_summary"]["total_income"] == 5000.0


def test_generate_report_without_budget_has_empty_budget_vs_actual(report_client) -> None:
    client, test_session = report_client
    organization_id = _seed_organization(test_session)
    _add_transaction(test_session, organization_id, date(2026, 2, 1), "Assessment income", 1000, "Assessments")

    response = client.post(
        "/api/v1/financials/reports/generate",
        json={"period_start": "2026-02-01", "period_end": "2026-02-28"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["report_json"]["budget_vs_actual"] == []
    assert body["report_json"]["executive_summary"]["total_income"] == 1000.0


def test_generate_report_rejects_inverted_period(report_client) -> None:
    client, test_session = report_client
    _seed_organization(test_session)

    response = client.post(
        "/api/v1/financials/reports/generate",
        json={"period_start": "2026-02-01", "period_end": "2026-01-01"},
    )

    assert response.status_code == 422


def test_get_report_not_found(report_client) -> None:
    client, test_session = report_client
    _seed_organization(test_session)

    response = client.get("/api/v1/financials/reports/00000000-0000-0000-0000-000000000000")

    assert response.status_code == 404


def test_report_includes_fiscal_year_ytd_and_fund_split(report_client) -> None:
    client, test_session = report_client
    organization_id = _seed_organization(test_session)

    # earlier in the fiscal year (FY2026 runs 10/1/2025 - 9/30/2026) — counts toward YTD only
    _add_transaction(
        test_session, organization_id, date(2025, 11, 10), "Fall landscaping", -1000,
        "Landscaping", fund_type="operating",
    )
    # the report month itself — counts toward both month and YTD
    _add_transaction(
        test_session, organization_id, date(2026, 5, 10), "May landscaping", -2400,
        "Landscaping", fund_type="operating",
    )
    _add_transaction(
        test_session, organization_id, date(2026, 5, 12), "May assessments", 5000,
        "Assessments", fund_type="operating",
    )
    _add_transaction(
        test_session, organization_id, date(2026, 5, 15), "Roof repair", -800,
        "Roof Repairs", fund_type="reserve",
    )
    _add_transaction(
        test_session, organization_id, date(2026, 5, 20), "Monthly reserve contribution", -500,
        "Reserve Contribution", fund_type="operating", transaction_type="transfer",
    )
    budget_id = _add_budget_with_landscaping_line(test_session, organization_id, monthly_budget=1200)

    response = client.post(
        "/api/v1/financials/reports/generate",
        json={"period_start": "2026-05-01", "period_end": "2026-05-31", "budget_id": str(budget_id)},
    )

    assert response.status_code == 201
    report = response.json()["report_json"]

    assert report["organization_name"] == "Board Member's HOA"
    assert report["fiscal_year"] == 2026
    assert report["ytd_start"] == "2025-10-01"

    # the transfer-tagged $500 is excluded from both month and combined totals
    assert report["executive_summary"]["total_income"] == 5000.0
    assert report["executive_summary"]["total_expenses"] == 3200.0  # 2400 landscaping + 800 roof

    assert report["operating"]["executive_summary"]["total_income"] == 5000.0
    assert report["operating"]["executive_summary"]["total_expenses"] == 2400.0
    assert report["reserve"]["executive_summary"]["total_income"] == 0.0
    assert report["reserve"]["executive_summary"]["total_expenses"] == 800.0

    landscaping = next(line for line in report["budget_vs_actual"] if line["category"] == "Landscaping")
    assert landscaping["actual_amount"] == 2400.0
    # YTD = Oct 2025 through May 2026 = 8 months elapsed
    assert landscaping["ytd_budget_amount"] == 9600.0
    assert landscaping["ytd_actual_amount"] == 3400.0  # 1000 (Nov) + 2400 (May)
    assert landscaping["annual_budget_amount"] == 14400.0

    assert any("transfer" in note or "correction" in note for note in report["notes"])
