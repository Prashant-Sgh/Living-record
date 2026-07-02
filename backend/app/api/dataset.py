from fastapi import APIRouter, Depends

from app.schemas import StatusResponse
from app.services.dataset_service import DatasetService

router = APIRouter(prefix="/dataset", tags=["dataset"])


def get_dataset_service() -> DatasetService:
    """Create a dataset service instance for the router."""
    return DatasetService()


@router.get("", response_model=StatusResponse)
async def dataset_status(service: DatasetService = Depends(get_dataset_service)) -> StatusResponse:
    """Return a placeholder status response for dataset routing."""
    return StatusResponse(status="not implemented")
