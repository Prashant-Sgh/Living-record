import asyncio
import io
import json
from pathlib import Path

import pytest
from fastapi import HTTPException, UploadFile

from app.services.upload_service import UploadService


def test_upload_persists_pdf(tmp_path: Path) -> None:
    service = UploadService(storage_dir=tmp_path)
    upload_file = UploadFile(
        filename="report.pdf",
        file=io.BytesIO(b"%PDF-1.4\n%test pdf content"),
        headers={"content-type": "application/pdf"},
    )

    response = asyncio.run(service.upload(upload_file))

    assert response.original_filename == "report.pdf"
    assert response.content_type == "application/pdf"
    assert response.stored_filename.endswith(".pdf")
    assert (tmp_path / response.stored_filename).exists()

    metadata = json.loads((tmp_path / "index.json").read_text(encoding="utf-8"))
    assert len(metadata) == 1
    assert metadata[0]["id"] == response.id


def test_upload_rejects_non_pdf(tmp_path: Path) -> None:
    service = UploadService(storage_dir=tmp_path)
    upload_file = UploadFile(
        filename="notes.txt",
        file=io.BytesIO(b"not a pdf"),
        headers={"content-type": "text/plain"},
    )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(service.upload(upload_file))

    assert exc_info.value.status_code == 415
