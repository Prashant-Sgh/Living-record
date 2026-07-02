from fastapi import APIRouter, Depends

from app.schemas import StatusResponse
from app.services.demo_service import DemoService

router = APIRouter(prefix="/chat", tags=["chat"])


def get_demo_service() -> DemoService:
    """Create a demo service instance for the router."""
    return DemoService()


@router.get("", response_model=StatusResponse)
async def chat_status(service: DemoService = Depends(get_demo_service)) -> StatusResponse:
    """Return a placeholder status response for chat routing."""
    return StatusResponse(status="not implemented")
