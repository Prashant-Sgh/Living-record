from __future__ import annotations

import json

import httpx
from ollama import AsyncClient, ResponseError
from pydantic import ValidationError as PydanticValidationError

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
from app.services.metadata_extraction.prompt import METADATA_EXTRACTION_PROMPT
from app.services.metadata_extraction.provider import MetadataExtractionProvider
from app.services.metadata_extraction.schemas import MedicalMetadata

logger = get_logger("app.metadata_extraction.ollama")


class OllamaProvider(MetadataExtractionProvider):
    """Metadata extraction provider backed by Ollama."""

    def __init__(
        self,
        *,
        ollama_base_url: str,
        ollama_model: str,
        llm_timeout_seconds: float = 60,
        llm_temperature: float = 0.0,
    ) -> None:
        if not ollama_base_url or not ollama_base_url.strip():
            raise ConfigurationError("OLLAMA_BASE_URL is not configured")
        if not ollama_model or not ollama_model.strip():
            raise ConfigurationError("OLLAMA_MODEL is not configured")

        self._base_url = ollama_base_url.strip()
        self._model = ollama_model.strip()
        self._timeout = llm_timeout_seconds
        self._temperature = llm_temperature
        self._client = AsyncClient(host=self._base_url, timeout=self._timeout)

    @property
    def model(self) -> str:
        return self._model

    @property
    def base_url(self) -> str | None:
        return self._base_url

    async def extract_metadata(self, report_text: str) -> MedicalMetadata:
        logger.info("Ollama metadata extraction start model=%s", self._model)

        prompt = METADATA_EXTRACTION_PROMPT + report_text
        try:
            response = await self._client.generate(
                model=self._model,
                prompt=prompt,
                format="json",
                options={"temperature": self._temperature},
            )
        except ConnectionError as exc:
            raise ProviderConnectionError(str(exc)) from exc
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError("Ollama request timed out") from exc
        except ResponseError as exc:
            self._raise_response_error(exc)

        return self._parse_response(response.response or "")

    def _raise_response_error(self, exc: ResponseError) -> None:
        message = str(exc)
        status = exc.status_code
        if status in (401, 403):
            raise ProviderAuthenticationError(message) from exc
        if status == 429:
            raise ProviderRateLimitError(message) from exc
        raise ProviderConnectionError(message) from exc

    def _parse_response(self, raw_content: str) -> MedicalMetadata:
        if not raw_content.strip():
            raise InvalidJSONError("Ollama returned empty response")

        try:
            payload = json.loads(raw_content)
        except json.JSONDecodeError as exc:
            raise InvalidJSONError(str(exc)) from exc

        if not isinstance(payload, dict):
            raise InvalidJSONError("Ollama response JSON must be an object")

        try:
            return MedicalMetadata.model_validate(payload)
        except PydanticValidationError as exc:
            raise ValidationError(str(exc)) from exc
