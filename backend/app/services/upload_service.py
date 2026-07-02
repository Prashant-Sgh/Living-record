import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, UploadFile

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.schemas.upload import DeleteResponse, UploadResponse

logger = get_logger("app.upload_service")


class UploadService:
    """Manage PDF uploads, persistence, and metadata without touching the memory layer."""

    def __init__(self, storage_dir: Path | None = None, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.storage_dir = Path(storage_dir or self.settings.upload_directory)
        self.index_path = self.storage_dir / "index.json"
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_index()

    async def upload(self, file: UploadFile) -> UploadResponse:
        """Validate and persist an uploaded PDF file."""
        if file.filename is None:
            raise HTTPException(status_code=400, detail="Filename is required")

        contents = await file.read()
        if not contents:
            raise HTTPException(status_code=400, detail="File is empty")

        if len(contents) > 20 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="File exceeds 20 MB limit")

        if not self._looks_like_pdf(contents, file.filename, file.content_type):
            raise HTTPException(status_code=415, detail="Only PDF files are supported")

        stored_filename = f"{uuid4().hex}.pdf"
        destination = self.storage_dir / stored_filename
        with destination.open("wb") as handle:
            handle.write(contents)

        content_type = (file.content_type or "application/pdf").lower()
        metadata = {
            "id": str(uuid4()),
            "original_filename": file.filename,
            "stored_filename": stored_filename,
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
            "size_bytes": len(contents),
            "content_type": content_type,
        }

        records = self._load_index()
        records.append(metadata)
        self._write_index(records)

        logger.info("Uploaded file %s as %s", file.filename, stored_filename)
        return UploadResponse(**metadata)

    async def get(self, upload_id: str) -> UploadResponse:
        """Retrieve a single upload record by its identifier."""
        records = self._load_index()
        for record in records:
            if record["id"] == upload_id:
                return UploadResponse(**record)
        raise HTTPException(status_code=404, detail="Upload not found")

    async def list(self) -> list[UploadResponse]:
        """Return all upload records."""
        records = self._load_index()
        return [UploadResponse(**record) for record in records]

    async def delete(self, upload_id: str) -> DeleteResponse:
        """Delete an upload record and the stored file."""
        records = self._load_index()
        for index, record in enumerate(records):
            if record["id"] == upload_id:
                stored_path = self.storage_dir / record["stored_filename"]
                if stored_path.exists():
                    stored_path.unlink()
                records.pop(index)
                self._write_index(records)
                return DeleteResponse(message="Upload deleted", id=upload_id)
        raise HTTPException(status_code=404, detail="Upload not found")

    def _looks_like_pdf(self, contents: bytes, filename: str, content_type: str | None) -> bool:
        """Determine whether the uploaded payload is a PDF file."""
        if not filename.lower().endswith(".pdf"):
            return False

        normalized_content_type = (content_type or "").lower()
        if normalized_content_type in {"application/pdf", "application/x-pdf"}:
            return True
        if normalized_content_type in {"", "application/octet-stream", "binary/octet-stream", "application/x-download"}:
            return contents.startswith(b"%PDF")
        return False

    def _ensure_index(self) -> None:
        """Create the upload metadata index if it does not already exist."""
        if not self.index_path.exists():
            self.index_path.write_text("[]", encoding="utf-8")

    def _load_index(self) -> list[dict[str, Any]]:
        """Read upload metadata from the index file."""
        self._ensure_index()
        return json.loads(self.index_path.read_text(encoding="utf-8"))

    def _write_index(self, records: list[dict[str, Any]]) -> None:
        """Write upload metadata to the index file."""
        self.index_path.write_text(json.dumps(records, indent=2), encoding="utf-8")
