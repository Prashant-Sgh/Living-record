import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx
import openai
from pydantic import ValidationError

from app.core.config import get_settings
from app.core.logging import get_logger
from app.schemas.metadata import MetadataExtractionResult, MetadataExtractionResponse

logger = get_logger("app.metadata_extraction")
settings = get_settings()


class AuthenticationConfigError(Exception):
    pass


class ProviderConfigError(Exception):
    pass


@dataclass
class ProviderConfig:
    name: str
    model: str
    timeout: int
    max_retries: int
    temperature: float


class MetadataExtractionService:
    """Provider-independent metadata extraction layer."""

    def __init__(self) -> None:
        self.settings = settings
        self.provider = (
            self.settings.metadata_extraction_llm_provider
            or self.settings.llm_provider
            or os.getenv("METADATA_EXTRACTION_LLM_PROVIDER")
            or os.getenv("LLM_PROVIDER")
            or ""
        ).strip().lower()
        self.model = self._resolve_model()
        self.timeout = self.settings.llm_timeout_seconds
        self.max_retries = self.settings.llm_max_retries
        self.temperature = self.settings.llm_temperature

    def _resolve_model(self) -> str:
        if self.provider == "openai":
            return (
                self.settings.metadata_extraction_llm_model
                or os.getenv("METADATA_EXTRACTION_LLM_MODEL")
                or self.settings.openai_model
                or os.getenv("OPENAI_LLM_MODEL")
                or self.settings.llm_model
                or os.getenv("LLM_MODEL")
                or "openai/gpt-4o-mini"
            )
        if self.provider == "ollama":
            return (
                self.settings.metadata_extraction_llm_model
                or os.getenv("METADATA_EXTRACTION_LLM_MODEL")
                or self.settings.ollama_model
                or os.getenv("OLLAMA_LLM_MODEL")
                or self.settings.llm_model
                or os.getenv("LLM_MODEL")
                or "llama3.2:1b"
            )
        return self.settings.metadata_extraction_llm_model or self.settings.llm_model or os.getenv("LLM_MODEL") or ""

    def _resolve_ollama_base_url(self) -> str | None:
        if self.settings.ollama_base_url:
            return self.settings.ollama_base_url.rstrip("/")

        candidate = (
            os.getenv("OLLAMA_BASE_URL")
            or os.getenv("LLM_ENDPOINT")
            or os.getenv("EMBEDDING_ENDPOINT")
        )
        if not candidate:
            return None

        parsed = urlparse(candidate)
        if parsed.scheme and parsed.netloc:
            if parsed.path and parsed.path not in {"", "/"}:
                return f"{parsed.scheme}://{parsed.netloc}"
            return candidate.rstrip("/")
        return candidate.rstrip("/")

    def _build_prompt(self, text: str) -> str:
        return (
            "You are extracting structured medical metadata from a clinical report. "
            "Return ONLY valid JSON with the following fields: patient_id, patient_name, report_date, visit_type, "
            "conditions, medications, laboratory_tests, laboratory_values, providers, procedures, symptoms, diagnoses, recommendations. "
            "Use empty arrays, not null. Do not invent information. "
            "Normalize values to snake_case strings. "
            "If a field is missing, return an empty string for patient_id/patient_name/report_date/visit_type and empty arrays for lists. "
            "Here is the report text:\n\n" + text
        )

    async def extract_metadata(self, text: str) -> MetadataExtractionResult:
        provider = self.provider
        model = self.model
        start = time.time()
        last_exception: str | None = None
        retries = 0

        logger.info("Metadata extraction start provider=%s model=%s timeout=%s retries=%s", provider, model, self.timeout, self.max_retries)

        if provider not in {"openai", "ollama"}:
            return MetadataExtractionResult.error_result(
                "invalid_provider",
                provider=provider,
                model=model,
                details=f"Unsupported provider: {provider}",
                status_code=400,
            )

        for attempt in range(self.max_retries + 1):
            try:
                if provider == "openai":
                    response = await self._call_openai(text)
                else:
                    response = await self._call_ollama(text)

                duration = time.time() - start
                logger.info("Metadata extraction completed provider=%s model=%s latency=%.2f retries=%s", provider, model, duration, retries)

                if response is None:
                    return MetadataExtractionResult.error_result(
                        "empty_response",
                        provider=provider,
                        model=model,
                        details="LLM returned no content",
                        status_code=502,
                        retries=retries,
                    )

                metadata = self._validate_response(response)
                return MetadataExtractionResult(
                    ok=True,
                    provider=provider,
                    model=model,
                    latency_seconds=duration,
                    retries=retries,
                    usage_tokens=response.get("usage_tokens") if isinstance(response, dict) else None,
                    data=metadata,
                )

            except httpx.TimeoutException as exc:
                last_exception = str(exc)
                logger.warning("Timeout on metadata extraction attempt=%s provider=%s: %s", attempt + 1, provider, exc)
                retries += 1
                if attempt < self.max_retries:
                    await self._sleep_backoff(attempt)
                continue
            except AuthenticationConfigError as exc:
                logger.error("Authentication/configuration failed for provider=%s: %s", provider, exc)
                return MetadataExtractionResult.error_result(
                    "authentication_failure",
                    provider=provider,
                    model=model,
                    details=str(exc),
                    status_code=401,
                    retries=retries,
                )
            except openai.AuthenticationError as exc:
                logger.error("Authentication failed for provider=%s: %s", provider, exc)
                return MetadataExtractionResult.error_result(
                    "authentication_failure",
                    provider=provider,
                    model=model,
                    details=str(exc),
                    status_code=401,
                    retries=retries,
                )
            except openai.RateLimitError as exc:
                last_exception = str(exc)
                logger.warning("Rate limited on metadata extraction attempt=%s provider=%s: %s", attempt + 1, provider, exc)
                retries += 1
                if attempt < self.max_retries:
                    await self._sleep_backoff(attempt)
                continue
            except json.JSONDecodeError as exc:
                logger.error("Invalid JSON from metadata extraction provider=%s: %s", provider, exc)
                return MetadataExtractionResult.error_result(
                    "invalid_json",
                    provider=provider,
                    model=model,
                    details=str(exc),
                    status_code=502,
                    retries=retries,
                )
            except ValidationError as exc:
                logger.error("Metadata validation failed provider=%s: %s", provider, exc)
                return MetadataExtractionResult.error_result(
                    "validation_failed",
                    provider=provider,
                    model=model,
                    details=str(exc),
                    status_code=422,
                    retries=retries,
                )
            except Exception as exc:
                last_exception = str(exc)
                logger.exception("Unexpected metadata extraction error provider=%s: %s", provider, exc)
                return MetadataExtractionResult.error_result(
                    "unexpected_error",
                    provider=provider,
                    model=model,
                    details=str(exc),
                    status_code=500,
                    retries=retries,
                )

        return MetadataExtractionResult.error_result(
            "timeout",
            provider=provider,
            model=model,
            details=last_exception,
            status_code=504,
            retries=retries,
        )

    async def _call_openai(self, text: str) -> dict[str, Any] | None:
        if not self.settings.openai_api_key:
            raise AuthenticationConfigError("OPENAI_API_KEY is not configured")
        openai.api_key = self.settings.openai_api_key
        if self.settings.openai_base_url:
            openai.api_base = self.settings.openai_base_url

        prompt = self._build_prompt(text)
        response = await openai.ChatCompletion.acreate(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=self.temperature,
            timeout=self.timeout,
        )
        usage = {}
        if response.usage is not None:
            usage = {
                "prompt_tokens": int(response.usage.prompt_tokens or 0),
                "completion_tokens": int(response.usage.completion_tokens or 0),
                "total_tokens": int(response.usage.total_tokens or 0),
            }
        content = response.choices[0].message.content if response.choices else ""
        return {"text": content, "usage_tokens": usage}

    async def _call_ollama(self, text: str) -> dict[str, Any] | None:
        base_url = self._resolve_ollama_base_url()
        if not base_url:
            raise AuthenticationConfigError("OLLAMA_BASE_URL or EMBEDDING_ENDPOINT is not configured for Ollama")
        prompt = self._build_prompt(text)
        headers = {}
        if self.settings.ollama_api_key:
            headers["Authorization"] = f"Bearer {self.settings.ollama_api_key}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            res = await client.post(
                f"{base_url}/api/v1/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "temperature": self.temperature,
                    "max_output_tokens": 1024,
                },
                headers=headers,
            )
        if res.status_code == 401:
            raise openai.AuthenticationError("Ollama authentication failed")
        if res.status_code == 429:
            raise openai.RateLimitError("Ollama rate limit exceeded")
        res.raise_for_status()
        payload = res.json()
        output = payload.get("output")
        if isinstance(output, list) and output:
            text_value = output[0].get("content", "")
        else:
            text_value = payload.get("text", "")
        usage = payload.get("usage", {}) if isinstance(payload, dict) else {}
        return {"text": text_value, "usage_tokens": usage}

    def _validate_response(self, response: dict[str, Any]) -> MetadataExtractionResponse:
        raw = response.get("text")
        if raw is None or not isinstance(raw, str) or raw.strip() == "":
            raise ValidationError([{"loc": ("text",), "msg": "Response text is empty", "type": "value_error"}], MetadataExtractionResponse)

        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValidationError([{"loc": ("response",), "msg": "Response JSON must be an object", "type": "type_error"}], MetadataExtractionResponse)

        normalized = {
            "patient_id": data.get("patient_id", "") or "",
            "patient_name": data.get("patient_name", "") or "",
            "report_date": data.get("report_date", "") or "",
            "visit_type": data.get("visit_type", "") or "",
            "conditions": data.get("conditions", []),
            "medications": data.get("medications", []),
            "laboratory_tests": data.get("laboratory_tests", []),
            "laboratory_values": data.get("laboratory_values", []),
            "providers": data.get("providers", []),
            "procedures": data.get("procedures", []),
            "symptoms": data.get("symptoms", []),
            "diagnoses": data.get("diagnoses", []),
            "recommendations": data.get("recommendations", []),
        }
        return MetadataExtractionResponse(**normalized)

    async def _sleep_backoff(self, attempt: int) -> None:
        await asyncio.sleep((2 ** attempt) * 0.5)


metadata_extraction_service = MetadataExtractionService()
