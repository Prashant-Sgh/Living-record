from __future__ import annotations

import asyncio
import time
from typing import Callable

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.services.metadata_extraction.exceptions import (
    ConfigurationError,
    InvalidJSONError,
    ProviderAuthenticationError,
    ProviderConnectionError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ValidationError,
)
from app.services.metadata_extraction.openai_provider import OpenAIProvider
from app.services.metadata_extraction.ollama_provider import OllamaProvider
from app.services.metadata_extraction.provider import MetadataExtractionProvider
from app.services.metadata_extraction.schemas import MetadataExtractionResult

logger = get_logger("app.metadata_extraction.service")

ProviderFactory = Callable[[Settings], MetadataExtractionProvider]

PROVIDER_FACTORIES: dict[str, ProviderFactory] = {
    "openai": lambda settings: OpenAIProvider(
        openai_api_key=settings.openai_api_key or "",
        openai_model=settings.openai_model or "",
        openai_base_url=settings.openai_base_url,
        llm_timeout_seconds=settings.llm_timeout_seconds,
        llm_temperature=settings.llm_temperature,
    ),
    "ollama": lambda settings: OllamaProvider(
        ollama_base_url=settings.ollama_base_url or "",
        ollama_model=settings.ollama_model or "",
        llm_timeout_seconds=settings.llm_timeout_seconds,
        llm_temperature=settings.llm_temperature,
    ),
}


class MetadataExtractionService:
    """Provider-independent metadata extraction orchestration layer."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self.provider_key = (self._settings.metadata_extraction_llm_provider or "").strip().lower()
        if not self.provider_key:
            raise ConfigurationError("METADATA_EXTRACTION_LLM_PROVIDER is not configured")

        provider_factory = PROVIDER_FACTORIES.get(self.provider_key)
        if provider_factory is None:
            raise ConfigurationError(
                f"Unsupported METADATA_EXTRACTION_LLM_PROVIDER='{self.provider_key}'. "
                "Supported values: openai, ollama"
            )

        self._provider = provider_factory(self._settings)
        self.max_retries = self._settings.llm_max_retries

        logger.info(
            "Metadata extraction service initialized provider=%s model=%s base_url=%s",
            self.provider_key,
            self._provider.model,
            self._provider.base_url,
        )

    @property
    def provider(self) -> MetadataExtractionProvider:
        return self._provider

    async def extract_metadata(self, report_text: str) -> MetadataExtractionResult:
        start = time.time()
        retries = 0
        last_details: str | None = None

        logger.info(
            "Metadata extraction start provider=%s model=%s timeout=%s max_retries=%s",
            self.provider_key,
            self._provider.model,
            self._settings.llm_timeout_seconds,
            self.max_retries,
        )

        for attempt in range(self.max_retries + 1):
            try:
                data = await self._provider.extract_metadata(report_text)
                latency = time.time() - start
                logger.info(
                    "Metadata extraction success provider=%s model=%s latency=%.2f retries=%s validation=success",
                    self.provider_key,
                    self._provider.model,
                    latency,
                    retries,
                )
                return MetadataExtractionResult(
                    ok=True,
                    provider=self.provider_key,
                    model=self._provider.model,
                    base_url=self._provider.base_url,
                    latency_seconds=latency,
                    retries=retries,
                    data=data,
                )
            except ProviderAuthenticationError as exc:
                logger.error(
                    "Authentication failure provider=%s model=%s",
                    self.provider_key,
                    self._provider.model,
                )
                return MetadataExtractionResult.error_result(
                    "authentication_failure",
                    provider=self.provider_key,
                    model=self._provider.model,
                    base_url=self._provider.base_url,
                    details=str(exc),
                    status_code=401,
                    retries=retries,
                )
            except InvalidJSONError as exc:
                logger.error(
                    "Invalid JSON provider=%s model=%s validation=failure",
                    self.provider_key,
                    self._provider.model,
                )
                return MetadataExtractionResult.error_result(
                    "invalid_json",
                    provider=self.provider_key,
                    model=self._provider.model,
                    base_url=self._provider.base_url,
                    details=str(exc),
                    status_code=502,
                    retries=retries,
                )
            except ValidationError as exc:
                logger.error(
                    "Validation failure provider=%s model=%s validation=failure",
                    self.provider_key,
                    self._provider.model,
                )
                return MetadataExtractionResult.error_result(
                    "validation_failed",
                    provider=self.provider_key,
                    model=self._provider.model,
                    base_url=self._provider.base_url,
                    details=str(exc),
                    status_code=422,
                    retries=retries,
                )
            except (ProviderTimeoutError, ProviderRateLimitError, ProviderConnectionError) as exc:
                last_details = str(exc)
                logger.warning(
                    "Retryable metadata extraction error provider=%s attempt=%s/%s: %s",
                    self.provider_key,
                    attempt + 1,
                    self.max_retries + 1,
                    exc,
                )
                if attempt < self.max_retries:
                    retries += 1
                    await asyncio.sleep((2**attempt) * 0.5)
                    continue

                error_code = "timeout"
                status_code = 504
                if isinstance(exc, ProviderRateLimitError):
                    error_code = "rate_limit"
                    status_code = 429
                elif isinstance(exc, ProviderConnectionError):
                    error_code = "connection_failure"
                    status_code = 503

                return MetadataExtractionResult.error_result(
                    error_code,
                    provider=self.provider_key,
                    model=self._provider.model,
                    base_url=self._provider.base_url,
                    details=last_details,
                    status_code=status_code,
                    retries=retries,
                )
            except Exception as exc:
                logger.exception(
                    "Unexpected metadata extraction error provider=%s model=%s",
                    self.provider_key,
                    self._provider.model,
                )
                return MetadataExtractionResult.error_result(
                    "unexpected_error",
                    provider=self.provider_key,
                    model=self._provider.model,
                    base_url=self._provider.base_url,
                    details=str(exc),
                    status_code=500,
                    retries=retries,
                )

        return MetadataExtractionResult.error_result(
            "timeout",
            provider=self.provider_key,
            model=self._provider.model,
            base_url=self._provider.base_url,
            details=last_details,
            status_code=504,
            retries=retries,
        )


def create_metadata_extraction_service(settings: Settings | None = None) -> MetadataExtractionService:
    """Factory for constructing a metadata extraction service."""
    return MetadataExtractionService(settings=settings)


metadata_extraction_service = create_metadata_extraction_service()
