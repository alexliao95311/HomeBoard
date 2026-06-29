import hashlib
from pathlib import Path
import uuid

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
from app.models.audit_log import AuditLog
from app.models.document import Document
from app.models.document_text_chunk import DocumentTextChunk
from app.schemas.auth import AuthenticatedUser


def test_document_list_requires_authentication() -> None:
    response = TestClient(app).get("/documents")

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required"}


@pytest.fixture
def document_client(tmp_path: Path):
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


def test_upload_list_and_get_document(document_client) -> None:
    client, test_session, upload_root = document_client
    contents = b"%PDF-1.7 sample contract"

    response = client.post(
        "/documents/upload",
        data={"document_type": "contract"},
        files={"file": ("../Vendor Contract.pdf", contents, "application/pdf")},
    )

    assert response.status_code == 201
    uploaded = response.json()
    assert uploaded["document_type"] == "contract"
    assert uploaded["status"] == "uploaded"
    assert uploaded["original_filename"] == "../Vendor Contract.pdf"
    assert uploaded["size_bytes"] == len(contents)
    assert uploaded["sha256"] == hashlib.sha256(contents).hexdigest()

    document_id = uuid.UUID(uploaded["id"])
    organization_id = uuid.UUID(uploaded["organization_id"])
    stored_files = list((upload_root / str(organization_id)).iterdir())
    assert len(stored_files) == 1
    assert stored_files[0].name == f"{document_id}_Vendor_Contract.pdf"
    assert stored_files[0].read_bytes() == contents

    list_response = client.get("/documents")
    assert list_response.status_code == 200
    assert [item["id"] for item in list_response.json()] == [str(document_id)]

    detail_response = client.get(f"/documents/{document_id}")
    assert detail_response.status_code == 200
    assert detail_response.json()["id"] == str(document_id)

    with test_session() as session:
        assert session.scalar(select(func.count()).select_from(Document)) == 1
        audit_log = session.scalar(select(AuditLog))
        assert audit_log is not None
        assert audit_log.action == "document.uploaded"
        assert audit_log.resource_id == str(document_id)


def test_documents_are_scoped_to_current_organization(document_client) -> None:
    client, _, _ = document_client
    upload_response = client.post(
        "/documents/upload",
        data={"document_type": "budget"},
        files={"file": ("budget.csv", b"category,amount", "text/csv")},
    )
    document_id = upload_response.json()["id"]

    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        uid="firebase-user-two",
        email="other@example.com",
        name="Other Board",
        email_verified=True,
    )

    assert client.get("/documents").json() == []
    assert client.get(f"/documents/{document_id}").status_code == 404


def test_upload_rejects_unsupported_content_type(document_client) -> None:
    client, test_session, upload_root = document_client

    response = client.post(
        "/documents/upload",
        data={"document_type": "invoice"},
        files={"file": ("invoice.txt", b"not allowed", "text/plain")},
    )

    assert response.status_code == 415
    assert not upload_root.exists()
    with test_session() as session:
        assert session.scalar(select(func.count()).select_from(Document)) == 0


def test_upload_rejects_file_above_size_limit(
    document_client, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, test_session, upload_root = document_client
    monkeypatch.setattr(document_routes, "MAX_FILE_SIZE", 5)

    response = client.post(
        "/documents/upload",
        data={"document_type": "bank_statement"},
        files={"file": ("statement.pdf", b"123456", "application/pdf")},
    )

    assert response.status_code == 413
    assert list(upload_root.rglob("*")) == []
    with test_session() as session:
        assert session.scalar(select(func.count()).select_from(Document)) == 0


def test_process_pdf_and_return_text_chunks(document_client) -> None:
    client, test_session, _ = document_client
    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_text(
        (72, 72),
        "HOA landscaping contract with monthly service and termination terms.",
    )
    pdf_bytes = pdf.tobytes()
    pdf.close()

    upload_response = client.post(
        "/documents/upload",
        data={"document_type": "contract"},
        files={"file": ("sample.pdf", pdf_bytes, "application/pdf")},
    )
    document_id = upload_response.json()["id"]

    process_response = client.post(f"/documents/{document_id}/process")
    assert process_response.status_code == 200
    assert process_response.json() == {
        "document_id": document_id,
        "status": "processed",
        "chunk_count": 1,
    }

    text_response = client.get(f"/documents/{document_id}/text")
    assert text_response.status_code == 200
    chunks = text_response.json()
    assert len(chunks) == 1
    assert chunks[0]["page_number"] == 1
    assert chunks[0]["chunk_index"] == 0
    assert "landscaping contract" in chunks[0]["text"]

    metadata_response = client.get(f"/documents/{document_id}")
    assert metadata_response.json()["status"] == "processed"

    with test_session() as session:
        assert (
            session.scalar(select(func.count()).select_from(DocumentTextChunk)) == 1
        )
        actions = list(session.scalars(select(AuditLog.action).order_by(AuditLog.action)))
        assert actions == ["document.processed", "document.uploaded"]


def test_processing_failure_sets_failed_status(document_client) -> None:
    client, _, _ = document_client
    upload_response = client.post(
        "/documents/upload",
        data={"document_type": "contract"},
        files={"file": ("broken.pdf", b"not a pdf", "application/pdf")},
    )
    document_id = upload_response.json()["id"]

    process_response = client.post(f"/documents/{document_id}/process")

    assert process_response.status_code == 422
    assert client.get(f"/documents/{document_id}").json()["status"] == "failed"
    assert client.get(f"/documents/{document_id}/text").json() == []


def test_document_text_is_organization_scoped(document_client) -> None:
    client, _, _ = document_client
    upload_response = client.post(
        "/documents/upload",
        data={"document_type": "budget"},
        files={"file": ("budget.csv", b"category,amount\nWater,100", "text/csv")},
    )
    document_id = upload_response.json()["id"]
    assert client.post(f"/documents/{document_id}/process").status_code == 200

    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        uid="firebase-user-two",
        email="other@example.com",
        name="Other Board",
        email_verified=True,
    )

    assert client.get(f"/documents/{document_id}/text").status_code == 404
    assert client.post(f"/documents/{document_id}/process").status_code == 404
