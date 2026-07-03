from functools import lru_cache
from pathlib import Path
import os
import logging

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[1]
ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    """Application configuration loaded from the runtime `.env` file.

    Note: `.env.example` is a template and is never loaded at runtime.
    """

    model_config = SettingsConfigDict(
        env_file=None,  # we explicitly load .env via python-dotenv
        extra="ignore",
    )

    app_name: str = "Living Record API"
    app_version: str = "0.1.0"
    debug: bool = False

    upload_directory: str = str(BASE_DIR / "storage" / "uploads")
    graph_directory: str = str(BASE_DIR / "storage" / "graphs")
    ontology_directory: str = str(BASE_DIR / "storage" / "ontology")

    memory_mode: str = "local"  # local | cloud | placeholder
    # Cognee Cloud (cloud mode)
    cognee_api_key: str | None = None
    cognee_api_url: str | None = None
    # Backwards-compat alias for older env var name
    cognee_service_url: str | None = None

    # LLM metadata extraction
    metadata_extraction_llm_provider: str | None = Field(default=None, env=("METADATA_EXTRACTION_LLM_PROVIDER", "LLM_PROVIDER"))
    metadata_extraction_llm_model: str | None = Field(
        default=None,
        env=("METADATA_EXTRACTION_LLM_MODEL", "OLLAMA_LLM_MODEL", "OPENAI_LLM_MODEL", "LLM_MODEL"),
    )
    llm_provider: str | None = None
    llm_model: str | None = Field(default=None, env="LLM_MODEL")
    llm_timeout_seconds: int = 30
    llm_max_retries: int = 3
    llm_temperature: float = 0.0

    openai_api_key: str | None = Field(default=None, env=("OPENAI_API_KEY", "LLM_API_KEY"))
    openai_model: str | None = Field(default=None, env=("OPENAI_MODEL", "OPENAI_LLM_MODEL", "LLM_MODEL"))
    openai_base_url: str | None = None

    ollama_api_key: str | None = Field(default=None, env="OLLAMA_API_KEY")
    ollama_base_url: str | None = Field(default=None, env=("OLLAMA_BASE_URL", "LLM_ENDPOINT"))
    ollama_model: str | None = Field(default=None, env=("OLLAMA_MODEL", "OLLAMA_LLM_MODEL", "LLM_MODEL"))

    embedding_provider: str | None = None
    embedding_model: str | None = None
    ontology_path: str | None = None
    ontology_file_path: str | None = None

    host: str = "0.0.0.0"
    port: int = 8000


def _load_dotenv_if_present() -> bool:
    """Load the `.env` file into the process environment if present.

    Returns True if a `.env` file was found and loaded, False otherwise.
    """
    if ENV_FILE.exists():
        load_dotenv(dotenv_path=str(ENV_FILE), override=True)
        return True
    return False


def _validate_settings(settings: Settings) -> None:
    """Validate required configuration and log startup clues.

    Raises RuntimeError for fatal misconfigurations (e.g., cloud mode
    without Cognee credentials). For non-fatal issues, logs warnings.
    """
    logger = logging.getLogger("app.config")

    mode = (settings.memory_mode or "local").lower()
    logger.info("Active MEMORY_MODE=%s", mode)

    # Ontology presence
    ontology_found = False
    if settings.ontology_file_path:
        ontology_found = Path(settings.ontology_file_path).exists()
    if not ontology_found and settings.ontology_path:
        ontology_found = Path(settings.ontology_path).exists()
    logger.info("Ontology found=%s", bool(ontology_found))

    # Cognee credentials/logging
    cognee_endpoint = settings.cognee_api_url or settings.cognee_service_url
    has_credentials = bool(settings.cognee_api_key and cognee_endpoint)
    logger.info("Cognee endpoint configured=%s", bool(cognee_endpoint))
    if cognee_endpoint:
        logger.info("Cognee endpoint=%s", cognee_endpoint)
    logger.info("Cognee credentials configured=%s", has_credentials)

    # LLM metadata extraction logging
    provider = (settings.metadata_extraction_llm_provider or settings.llm_provider or "").lower()
    logger.info("Metadata extraction LLM provider=%s", provider or "unset")
    logger.info("Metadata extraction model=%s", settings.metadata_extraction_llm_model or settings.llm_model or settings.openai_model or settings.ollama_model or "unset")
    logger.info("OpenAI configured=%s", bool(settings.openai_api_key))
    logger.info("Ollama base URL configured=%s", bool(settings.ollama_base_url))

    # Fatal checks
    if mode == "cloud":
        if not settings.cognee_api_key or not cognee_endpoint:
            raise RuntimeError(
                "MEMORY_MODE=cloud requires COGNEE_API_KEY and COGNEE_API_URL/COGNEE_SERVICE_URL to be set in .env"
            )


@lru_cache
def get_settings() -> Settings:
    """Return a cached settings instance.

    This function ensures `.env` is loaded first and validates settings.
    """
    # Load `.env` explicitly and fail early if not present. The application
    # requires a runtime `.env` file (`.env.example` is only a template).
    if not _load_dotenv_if_present():
        raise RuntimeError(f"Runtime .env file not found at {ENV_FILE}. Please create it from .env.example and set required variables.")
    settings = Settings()
    try:
        _validate_settings(settings)
    except Exception:
        # re-raise to fail startup when misconfigured
        raise
    return settings
