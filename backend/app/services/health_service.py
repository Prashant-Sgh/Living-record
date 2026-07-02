from typing import Any

from app.core.config import Settings, get_settings
from app.services.memory_service import MemoryService


class HealthService:
    """Provide health and readiness information for the application."""

    def __init__(self, memory_service: MemoryService | None = None, settings: Settings | None = None) -> None:
        self.memory_service = memory_service
        self.settings = settings or get_settings()

    async def get_status(self) -> dict[str, Any]:
        """Return the health payload for the API."""
        memory_state = (
            await self.memory_service.health() if self.memory_service is not None else {"connected": False, "mode": "placeholder", "ontology_loaded": False}
        )
        return {
            "status": "healthy",
            "memory": memory_state,
            "version": self.settings.app_version,
        }
