from pathlib import Path

from fastapi.testclient import TestClient
import fitz
import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes import documents as document_routes
from app.api.routes.auth import get_current_user
from app.database import Base, get_database_session
from app.main import app
from app.models.contract import Contract
from app.models.contract_review import ContractReview, ContractRubricScore, ContractRiskFlag
from app.schemas.auth import AuthenticatedUser


@pytest.fixture
def contract_client(tmp_path: Path):
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

    upload_root = tmp_path / "uploads"
    app.dependency_overrides[get_database_session] = override_session
    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[document_routes.get_upload_root] = lambda: upload_root

    yield TestClient(app), test_session, upload_root

    app.dependency_overrides.clear()
    test_engine.dispose()


def _upload_and_process_pdf(client: TestClient) -> str:
    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_text(
        (72, 72),
        "HOA landscaping contract. Vendor: ABC Landscaping. Term: 12 months. "
        "Monthly fee: $2,500. Termination notice: 90 days.",
    )
    pdf_bytes = pdf.tobytes()
    pdf.close()

    upload = client.post(
        "/documents/upload",
        data={"document_type": "contract"},
        files={"file": ("contract.pdf", pdf_bytes, "application/pdf")},
    )
    assert upload.status_code == 201
    document_id = upload.json()["id"]

    process = client.post(f"/documents/{document_id}/process")
    assert process.status_code == 200
    assert process.json()["status"] == "processed"

    return document_id


def test_review_requires_auth() -> None:
    response = TestClient(app).post(
        "/api/v1/contracts/review",
        json={"document_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert response.status_code == 401


def test_review_returns_full_contract_review(contract_client) -> None:
    client, test_session, _ = contract_client
    document_id = _upload_and_process_pdf(client)

    response = client.post(
        "/api/v1/contracts/review",
        json={
            "document_id": document_id,
            "vendor_name": "ABC Landscaping",
            "contract_type": "landscaping",
        },
    )

    assert response.status_code == 201
    body = response.json()

    contract = body["contract"]
    assert contract["vendor_name"] == "ABC Landscaping"
    assert contract["contract_type"] == "landscaping"
    assert contract["document_id"] == document_id
    assert contract["status"] == "reviewed"

    review = body["review"]
    assert review["total_score"] == "75.00"
    assert review["risk_level"] == "medium"
    assert "placeholder" in review["executive_summary"].lower()
    assert len(review["rubric_scores"]) == 5
    assert len(review["risk_flags"]) == 2

    categories = {s["category"] for s in review["rubric_scores"]}
    assert "Price / Value" in categories
    assert "Scope Clarity" in categories

    severities = {f["severity"] for f in review["risk_flags"]}
    assert "high" in severities
    assert "medium" in severities

    with test_session() as session:
        assert session.scalar(select(func.count()).select_from(Contract)) == 1
        assert session.scalar(select(func.count()).select_from(ContractReview)) == 1
        assert session.scalar(select(func.count()).select_from(ContractRubricScore)) == 5
        assert session.scalar(select(func.count()).select_from(ContractRiskFlag)) == 2


def test_review_rejects_unprocessed_document(contract_client) -> None:
    client, _, _ = contract_client

    upload = client.post(
        "/documents/upload",
        data={"document_type": "contract"},
        files={"file": ("contract.pdf", b"%PDF-1.7 raw", "application/pdf")},
    )
    document_id = upload.json()["id"]

    response = client.post(
        "/api/v1/contracts/review",
        json={"document_id": document_id},
    )

    assert response.status_code == 422
    assert "process" in response.json()["detail"].lower()


def test_review_rejects_missing_document(contract_client) -> None:
    client, _, _ = contract_client
    response = client.post(
        "/api/v1/contracts/review",
        json={"document_id": "00000000-0000-0000-0000-000000000001"},
    )
    assert response.status_code == 404


def test_list_contracts(contract_client) -> None:
    client, _, _ = contract_client
    document_id = _upload_and_process_pdf(client)
    client.post("/api/v1/contracts/review", json={"document_id": document_id})

    response = client.get("/api/v1/contracts")
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_get_contract_and_review(contract_client) -> None:
    client, _, _ = contract_client
    document_id = _upload_and_process_pdf(client)

    review_response = client.post(
        "/api/v1/contracts/review",
        json={"document_id": document_id, "vendor_name": "Test Vendor"},
    )
    contract_id = review_response.json()["contract"]["id"]

    get_contract = client.get(f"/api/v1/contracts/{contract_id}")
    assert get_contract.status_code == 200
    assert get_contract.json()["vendor_name"] == "Test Vendor"

    get_review = client.get(f"/api/v1/contracts/{contract_id}/review")
    assert get_review.status_code == 200
    body = get_review.json()
    assert body["total_score"] == "75.00"
    assert len(body["rubric_scores"]) == 5
    assert len(body["risk_flags"]) == 2


def test_update_contract_fields(contract_client) -> None:
    client, _, _ = contract_client
    document_id = _upload_and_process_pdf(client)
    result = client.post("/api/v1/contracts/review", json={"document_id": document_id})
    contract_id = result.json()["contract"]["id"]

    response = client.patch(
        f"/api/v1/contracts/{contract_id}",
        json={"vendor_name": "Updated Vendor", "contract_type": "pool"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["vendor_name"] == "Updated Vendor"
    assert body["contract_type"] == "pool"

    # partial update — only vendor_name changes, contract_type stays
    response2 = client.patch(
        f"/api/v1/contracts/{contract_id}",
        json={"vendor_name": "Renamed"},
    )
    assert response2.status_code == 200
    assert response2.json()["vendor_name"] == "Renamed"
    assert response2.json()["contract_type"] == "pool"


def test_update_review_fields(contract_client) -> None:
    client, _, _ = contract_client
    document_id = _upload_and_process_pdf(client)
    result = client.post("/api/v1/contracts/review", json={"document_id": document_id})
    contract_id = result.json()["contract"]["id"]

    response = client.patch(
        f"/api/v1/contracts/{contract_id}/review",
        json={
            "executive_summary": "Edited summary.",
            "recommendation": "Edited recommendation.",
            "risk_level": "high",
            "total_score": 60,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["executive_summary"] == "Edited summary."
    assert body["recommendation"] == "Edited recommendation."
    assert body["risk_level"] == "high"
    assert body["total_score"] == "60.00"
    assert len(body["rubric_scores"]) == 5


def test_delete_contract_permanently(contract_client) -> None:
    client, _, _ = contract_client
    document_id = _upload_and_process_pdf(client)
    result = client.post("/api/v1/contracts/review", json={"document_id": document_id})
    contract_id = result.json()["contract"]["id"]

    delete_response = client.delete(f"/api/v1/contracts/{contract_id}")
    assert delete_response.status_code == 204

    assert client.get(f"/api/v1/contracts/{contract_id}").status_code == 404
    assert client.get("/api/v1/contracts").json() == []


def test_delete_requires_organization_ownership(contract_client) -> None:
    client, _, _ = contract_client
    document_id = _upload_and_process_pdf(client)
    result = client.post("/api/v1/contracts/review", json={"document_id": document_id})
    contract_id = result.json()["contract"]["id"]

    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        uid="firebase-user-two",
        email="other@example.com",
        name="Other Board",
        email_verified=True,
    )
    assert client.delete(f"/api/v1/contracts/{contract_id}").status_code == 404


def test_contract_review_is_organization_scoped(contract_client) -> None:
    client, _, _ = contract_client
    document_id = _upload_and_process_pdf(client)
    review_response = client.post(
        "/api/v1/contracts/review", json={"document_id": document_id}
    )
    contract_id = review_response.json()["contract"]["id"]

    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        uid="firebase-user-two",
        email="other@example.com",
        name="Other Board",
        email_verified=True,
    )

    assert client.get("/api/v1/contracts").json() == []
    assert client.get(f"/api/v1/contracts/{contract_id}").status_code == 404
    assert client.get(f"/api/v1/contracts/{contract_id}/review").status_code == 404
