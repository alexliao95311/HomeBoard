import hashlib
import logging
from pathlib import Path
import re
from typing import Annotated
import unicodedata
import uuid

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_database_session
from app.models.audit_log import AuditLog
from app.models.document import Document
from app.models.document_text_chunk import DocumentTextChunk
from app.schemas.document import (
    DocumentProcessResponse,
    DocumentResponse,
    DocumentTextChunkResponse,
    DocumentUpdateRequest,
)
from app.schemas.module import ModuleStatus
from app.services.organization_service import (
    OrganizationContext,
    get_current_organization,
)
from app.services.text_extraction_service import (
    DocumentExtractionError,
    chunk_extracted_text,
    extract_document_text,
)

router = APIRouter()
logger = logging.getLogger(__name__)

MAX_FILE_SIZE = 25 * 1024 * 1024
READ_CHUNK_SIZE = 1024 * 1024
ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "text/csv",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


def get_upload_root() -> Path:
    return Path(settings.document_storage_path)


def safe_filename(filename: str) -> str:
    basename = Path(filename.replace("\\", "/")).name
    normalized = (
        unicodedata.normalize("NFKD", basename)
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", normalized).strip("._")
    return (cleaned or "upload")[:255]


def _get_organization_document(
    session: Session,
    document_id: uuid.UUID,
    organization_id: uuid.UUID,
) -> Document:
    document = session.scalar(
        select(Document).where(
            Document.id == document_id,
            Document.organization_id == organization_id,
        )
    )
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    return document


@router.get("/status", response_model=ModuleStatus)
async def document_module_status() -> ModuleStatus:
    return ModuleStatus(
        module="Document management",
        status="active",
        message="Authenticated upload and metadata endpoints are available.",
    )


@router.post(
    "/upload",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    file: Annotated[UploadFile, File(...)],
    document_type: Annotated[str, Form(min_length=1, max_length=64)],
    organization: Annotated[
        OrganizationContext, Depends(get_current_organization)
    ],
    session: Annotated[Session, Depends(get_database_session)],
    upload_root: Annotated[Path, Depends(get_upload_root)],
) -> Document:
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unsupported file type",
        )

    normalized_document_type = document_type.strip()
    if not normalized_document_type:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="document_type cannot be blank",
        )

    document_id = uuid.uuid4()
    original_filename = file.filename or "upload"
    sanitized_filename = safe_filename(original_filename)
    organization_directory = upload_root / str(organization.organization_id)
    destination = organization_directory / f"{document_id}_{sanitized_filename}"
    temporary_destination = destination.with_name(f".{destination.name}.part")
    digest = hashlib.sha256()
    size_bytes = 0
    file_saved = False

    organization_directory.mkdir(parents=True, exist_ok=True)

    try:
        with temporary_destination.open("xb") as output:
            while chunk := await file.read(READ_CHUNK_SIZE):
                size_bytes += len(chunk)
                if size_bytes > MAX_FILE_SIZE:
                    raise HTTPException(
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                        detail="File exceeds the 25 MB limit",
                    )
                digest.update(chunk)
                output.write(chunk)

        temporary_destination.replace(destination)
        file_saved = True

        document = Document(
            id=document_id,
            organization_id=organization.organization_id,
            uploaded_by_id=organization.user_id,
            document_type=normalized_document_type,
            status="uploaded",
            original_filename=original_filename,
            safe_filename=sanitized_filename,
            content_type=file.content_type,
            size_bytes=size_bytes,
            sha256=digest.hexdigest(),
            storage_path=str(destination),
        )
        session.add(document)
        session.add(
            AuditLog(
                organization_id=organization.organization_id,
                actor_user_id=organization.user_id,
                action="document.uploaded",
                resource_type="document",
                resource_id=str(document_id),
                event_data={
                    "document_type": normalized_document_type,
                    "original_filename": original_filename,
                    "content_type": file.content_type,
                    "size_bytes": size_bytes,
                    "sha256": digest.hexdigest(),
                },
            )
        )
        session.commit()
        session.refresh(document)
        return document
    except Exception:
        session.rollback()
        if file_saved:
            destination.unlink(missing_ok=True)
        raise
    finally:
        temporary_destination.unlink(missing_ok=True)
        try:
            organization_directory.rmdir()
        except OSError:
            pass
        await file.close()


@router.get("", response_model=list[DocumentResponse])
async def list_documents(
    organization: Annotated[
        OrganizationContext, Depends(get_current_organization)
    ],
    session: Annotated[Session, Depends(get_database_session)],
) -> list[Document]:
    return list(
        session.scalars(
            select(Document)
            .where(Document.organization_id == organization.organization_id)
            .order_by(Document.created_at.desc())
        )
    )


@router.post(
    "/{document_id}/process",
    response_model=DocumentProcessResponse,
)
def process_document(
    document_id: uuid.UUID,
    organization: Annotated[
        OrganizationContext, Depends(get_current_organization)
    ],
    session: Annotated[Session, Depends(get_database_session)],
) -> DocumentProcessResponse:
    document = _get_organization_document(
        session,
        document_id,
        organization.organization_id,
    )
    document.status = "processing"
    session.commit()

    try:
        storage_path = Path(document.storage_path)
        if not storage_path.is_file():
            raise DocumentExtractionError("The uploaded file is missing")

        extracted_chunks = chunk_extracted_text(
            extract_document_text(storage_path, document.content_type)
        )
        session.execute(
            delete(DocumentTextChunk).where(
                DocumentTextChunk.document_id == document.id
            )
        )
        for chunk in extracted_chunks:
            session.add(
                DocumentTextChunk(
                    document_id=document.id,
                    page_number=chunk.page_number,
                    chunk_index=chunk.chunk_index,
                    text=chunk.text,
                )
            )

        document.status = "processed"
        session.add(
            AuditLog(
                organization_id=organization.organization_id,
                actor_user_id=organization.user_id,
                action="document.processed",
                resource_type="document",
                resource_id=str(document.id),
                event_data={"chunk_count": len(extracted_chunks)},
            )
        )
        session.commit()
        return DocumentProcessResponse(
            document_id=document.id,
            status=document.status,
            chunk_count=len(extracted_chunks),
        )
    except Exception as error:
        session.rollback()
        failed_document = _get_organization_document(
            session,
            document_id,
            organization.organization_id,
        )
        session.execute(
            delete(DocumentTextChunk).where(
                DocumentTextChunk.document_id == failed_document.id
            )
        )
        failed_document.status = "failed"
        session.add(
            AuditLog(
                organization_id=organization.organization_id,
                actor_user_id=organization.user_id,
                action="document.processing_failed",
                resource_type="document",
                resource_id=str(failed_document.id),
                event_data={"error_type": type(error).__name__},
            )
        )
        session.commit()
        logger.exception("Document processing failed for %s", document_id)
        detail = (
            str(error)
            if isinstance(error, DocumentExtractionError)
            else "Document processing failed"
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=detail,
        ) from error


@router.get(
    "/{document_id}/text",
    response_model=list[DocumentTextChunkResponse],
)
def get_document_text(
    document_id: uuid.UUID,
    organization: Annotated[
        OrganizationContext, Depends(get_current_organization)
    ],
    session: Annotated[Session, Depends(get_database_session)],
) -> list[DocumentTextChunk]:
    document = _get_organization_document(
        session,
        document_id,
        organization.organization_id,
    )
    return list(
        session.scalars(
            select(DocumentTextChunk)
            .where(DocumentTextChunk.document_id == document.id)
            .order_by(DocumentTextChunk.chunk_index)
        )
    )


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: uuid.UUID,
    organization: Annotated[
        OrganizationContext, Depends(get_current_organization)
    ],
    session: Annotated[Session, Depends(get_database_session)],
) -> Document:
    return _get_organization_document(
        session,
        document_id,
        organization.organization_id,
    )


@router.patch("/{document_id}", response_model=DocumentResponse)
def update_document(
    document_id: uuid.UUID,
    body: DocumentUpdateRequest,
    organization: Annotated[
        OrganizationContext, Depends(get_current_organization)
    ],
    session: Annotated[Session, Depends(get_database_session)],
) -> Document:
    doc = _get_organization_document(session, document_id, organization.organization_id)
    doc.original_filename = body.original_filename.strip()
    session.commit()
    session.refresh(doc)
    return doc


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: uuid.UUID,
    organization: Annotated[
        OrganizationContext, Depends(get_current_organization)
    ],
    session: Annotated[Session, Depends(get_database_session)],
) -> None:
    doc = _get_organization_document(session, document_id, organization.organization_id)
    session.execute(
        delete(DocumentTextChunk).where(DocumentTextChunk.document_id == document_id)
    )
    session.delete(doc)
    session.commit()
