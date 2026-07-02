from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.chat import router as chat_router
from app.api.dataset import router as dataset_router
from app.api.graph import router as graph_router
from app.api.health import router as health_router
from app.api.upload import router as upload_router
from app.core.config import get_settings
from app.core.lifespan import lifespan
from app.core.logging import get_logger

logger = get_logger("app.main")
settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload_router)
app.include_router(chat_router)
app.include_router(graph_router)
app.include_router(dataset_router)
app.include_router(health_router)


@app.get("/", include_in_schema=False)
async def root() -> dict[str, str]:
    """Simple root endpoint for service discovery."""
    return {"message": "Living Record API"}
