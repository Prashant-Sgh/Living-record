from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    """Application configuration loaded from environment variables and .env files."""

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Living Record API"
    app_version: str = "0.1.0"
    debug: bool = False

    upload_directory: str = str(BASE_DIR / "storage" / "uploads")
    graph_directory: str = str(BASE_DIR / "storage" / "graphs")
    ontology_directory: str = str(BASE_DIR / "storage" / "ontology")

    memory_mode: str = "placeholder"
    cognee_api_key: str | None = None
    cognee_service_url: str | None = None
    llm_provider: str = "placeholder"
    llm_model: str = "placeholder"
    embedding_provider: str = "placeholder"
    embedding_model: str = "placeholder"
    ontology_path: str = str(BASE_DIR / "storage" / "ontology" / "ontology.json")

    host: str = "0.0.0.0"
    port: int = 8000


@lru_cache
def get_settings() -> Settings:
    """Return a cached settings instance."""
    return Settings()
