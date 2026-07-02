from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.memory_service import MemoryService

logger = get_logger("app.lifespan")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application startup and shutdown lifecycle hooks."""
    logger.info("Application starting")

    settings = get_settings()
    memory_service = MemoryService(settings=settings)
    try:
        initialized = await memory_service.initialize()
    except Exception as exc:  # pragma: no cover - defensive logging for startup
        logger.exception("Memory initialization failed: %s", exc)
        initialized = False

    app.state.memory_service = memory_service
    logger.info("Memory initialization %s", "succeeded" if initialized else "failed")

    yield

    await memory_service.shutdown()
    logger.info("Application shutting down")
