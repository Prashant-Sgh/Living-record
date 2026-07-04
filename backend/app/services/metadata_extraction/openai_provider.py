from __future__ import annotations

import json

from openai import (
    APIConnectionError as OpenAIAPIConnectionError,
    APITimeoutError,
    AsyncOpenAI,
    AuthenticationError as OpenAIAuthenticationError,
    BadRequestError,
    PermissionDeniedError,
    RateLimitError as OpenAIRateLimitError,
)
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

logger = get_logger("app.metadata_extraction.openai")

_DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"
_STRUCTURED_OUTPUT_MODEL_HINTS = (
    "gpt-4o",
    "gpt-4.1",
    "gpt-4-turbo",
    "o1",
    "o3",
    "o4-mini",
    "gpt-5",
)


class OpenAIProvider(MetadataExtractionProvider):
    """Metadata extraction provider backed by the OpenAI API."""

    def __init__(
        self,
        *,
        openai_api_key: str,
        openai_model: str,
        openai_base_url: str | None = None,
        llm_timeout_seconds: float = 60,
        llm_temperature: float = 0.0,
    ) -> None:
        if not openai_api_key or not openai_api_key.strip():
            raise ConfigurationError("OPENAI_API_KEY is not configured")
        if not openai_model or not openai_model.strip():
            raise ConfigurationError("OPENAI_MODEL is not configured")

        self._model = openai_model.strip()
        self._base_url = openai_base_url.strip() if openai_base_url else _DEFAULT_OPENAI_BASE_URL
        self._timeout = llm_timeout_seconds
        self._temperature = llm_temperature

        client_kwargs: dict[str, object] = {
            "api_key": openai_api_key.strip(),
            "timeout": self._timeout,
        }
        if openai_base_url and openai_base_url.strip():
            client_kwargs["base_url"] = openai_base_url.strip()
        self._client = AsyncOpenAI(**client_kwargs)

    @property
    def model(self) -> str:
        return self._model

    @property
    def base_url(self) -> str | None:
        return self._base_url

    def _supports_structured_outputs(self) -> bool:
        if self._base_url.rstrip("/") != _DEFAULT_OPENAI_BASE_URL.rstrip("/"):
            return False

        normalized_model = self._model.lower().removeprefix("openai/")
        return any(hint in normalized_model for hint in _STRUCTURED_OUTPUT_MODEL_HINTS)

    async def extract_metadata(self, report_text: str) -> MedicalMetadata:
        logger.info("OpenAI metadata extraction start model=%s", self._model)

        messages = [{"role": "user", "content": METADATA_EXTRACTION_PROMPT + report_text}]

        try:
            if self._supports_structured_outputs():
                try:
                    return await self._extract_structured(messages)
                except BadRequestError:
                    logger.info(
                        "Structured outputs unavailable for model=%s; falling back to JSON mode",
                        self._model,
                    )
                    return await self._extract_json_mode(messages)
            return await self._extract_json_mode(messages)
        except OpenAIAuthenticationError as exc:
            raise ProviderAuthenticationError(str(exc)) from exc
        except PermissionDeniedError as exc:
            raise ProviderAuthenticationError(str(exc)) from exc
        except APITimeoutError as exc:
            raise ProviderTimeoutError("OpenAI request timed out") from exc
        except OpenAIRateLimitError as exc:
            raise ProviderRateLimitError(str(exc)) from exc
        except OpenAIAPIConnectionError as exc:
            raise ProviderConnectionError(str(exc)) from exc

    async def _extract_structured(
        self,
        messages: list[dict[str, str]],
    ) -> MedicalMetadata:
        completion = await self._client.chat.completions.parse(
            model=self._model,
            messages=messages,
            temperature=self._temperature,
            response_format=MedicalMetadata,
        )

        message = completion.choices[0].message if completion.choices else None
        if message is None or message.parsed is None:
            raise InvalidJSONError("OpenAI returned empty structured response")

        return message.parsed

    async def _extract_json_mode(
        self,
        messages: list[dict[str, str]],
    ) -> MedicalMetadata:
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=self._temperature,
            response_format={"type": "json_object"},
        )

        content = ""
        if response.choices:
            content = response.choices[0].message.content or ""

        return self._parse_response(content)

    def _parse_response(self, raw_content: str) -> MedicalMetadata:
        if not raw_content.strip():
            raise InvalidJSONError("OpenAI returned empty response")

        try:
            payload = json.loads(raw_content)
        except json.JSONDecodeError as exc:
            raise InvalidJSONError(str(exc)) from exc

        if not isinstance(payload, dict):
            raise InvalidJSONError("OpenAI response JSON must be an object")

        try:
            return MedicalMetadata.model_validate(payload)
        except PydanticValidationError as exc:
            raise ValidationError(str(exc)) from exc
