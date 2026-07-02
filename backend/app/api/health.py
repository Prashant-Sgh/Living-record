from fastapi import APIRouter, Depends, Request

from app.schemas import HealthResponse
from app.services.health_service import HealthService

router = APIRouter(prefix="/health", tags=["health"])


def get_health_service(request: Request) -> HealthService:
    """Create a health service instance for the router."""
    memory_service = getattr(request.app.state, "memory_service", None)
    return HealthService(memory_service=memory_service)


@router.get("", response_model=HealthResponse)
async def health_check(service: HealthService = Depends(get_health_service)) -> HealthResponse:
    """Return the current health status for the application."""
    return await service.get_status()
