from fastapi import APIRouter, Depends

from app.schemas import StatusResponse
from app.services.graph_service import GraphService

router = APIRouter(prefix="/graph", tags=["graph"])


def get_graph_service() -> GraphService:
    """Create a graph service instance for the router."""
    return GraphService()


@router.get("", response_model=StatusResponse)
async def graph_status(service: GraphService = Depends(get_graph_service)) -> StatusResponse:
    """Return a placeholder status response for graph routing."""
    return StatusResponse(status="not implemented")
