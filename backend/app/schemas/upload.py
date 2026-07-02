from datetime import datetime
from pydantic import BaseModel, ConfigDict


class UploadMetadata(BaseModel):
    """Metadata stored for each uploaded document."""

    model_config = ConfigDict(extra="forbid")

    id: str
    original_filename: str
    stored_filename: str
    uploaded_at: datetime
    size_bytes: int
    content_type: str


class UploadResponse(UploadMetadata):
    """Response returned after an upload is accepted."""


class UploadListResponse(BaseModel):
    """Response containing all uploads."""

    model_config = ConfigDict(extra="forbid")

    items: list[UploadResponse]


class DeleteResponse(BaseModel):
    """Response returned after an upload is deleted."""

    model_config = ConfigDict(extra="forbid")

    message: str
    id: str
