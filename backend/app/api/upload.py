from fastapi import APIRouter, Depends, File, UploadFile

from app.schemas import DeleteResponse, UploadListResponse, UploadResponse
from app.services.upload_service import UploadService

router = APIRouter(prefix="/upload", tags=["upload"])


def get_upload_service() -> UploadService:
    """Create an upload service instance for the router."""
    return UploadService()


@router.post("", response_model=UploadResponse, status_code=201)
async def upload_file(
    file: UploadFile = File(...),
    service: UploadService = Depends(get_upload_service),
) -> UploadResponse:
    """Accept and persist an uploaded PDF file."""
    return await service.upload(file)


@router.get("", response_model=UploadListResponse)
async def list_uploads(service: UploadService = Depends(get_upload_service)) -> UploadListResponse:
    """List all persisted uploads."""
    return UploadListResponse(items=await service.list())


@router.get("/{upload_id}", response_model=UploadResponse)
async def get_upload(upload_id: str, service: UploadService = Depends(get_upload_service)) -> UploadResponse:
    """Retrieve a single upload by its identifier."""
    return await service.get(upload_id)


@router.delete("/{upload_id}", response_model=DeleteResponse)
async def delete_upload(upload_id: str, service: UploadService = Depends(get_upload_service)) -> DeleteResponse:
    """Delete an uploaded file and remove its metadata entry."""
    return await service.delete(upload_id)
