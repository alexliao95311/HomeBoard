import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    uploaded_by_id: uuid.UUID
    document_type: str
    status: str
    original_filename: str
    content_type: str
    size_bytes: int
    sha256: str
    created_at: datetime
