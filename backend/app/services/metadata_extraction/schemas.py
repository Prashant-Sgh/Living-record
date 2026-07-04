from __future__ import annotations

import re
import unicodedata
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator


def _snake_normalize(value: str) -> str:
    """Normalize a string to lowercase snake_case terminology."""
    text = str(value).strip()
    text = unicodedata.normalize("NFKD", text)
    text = text.lower()
    roman_map = {
        " ii ": " 2 ",
        " iii ": " 3 ",
        " iv ": " 4 ",
        " v ": " 5 ",
        " vi ": " 6 ",
        " vii ": " 7 ",
        " viii ": " 8 ",
        " ix ": " 9 ",
        " x ": " 10 ",
    }
    for roman, digit in roman_map.items():
        text = text.replace(roman, digit)
    text = re.sub(r"[&/\\]", " ", text)
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text)
    return text.strip("_")


def _normalize_medication(value: str) -> str:
    text = str(value).strip().lower()
    text = re.sub(r"\b\d+(?:\.\d+)?\b", "", text)
    text = re.sub(
        r"\b(mg|mcg|g|ml|tablet|tablets|capsule|capsules|once|twice|daily|bid|tid|qid)\b",
        "",
        text,
    )
    text = _snake_normalize(text)
    return text.strip("_")


class MedicalMetadata(BaseModel):
    """Validated structured metadata extracted from a medical report."""

    model_config = ConfigDict(extra="forbid")

    patient_id: str = ""
    patient_name: str = ""
    report_date: str = ""
    visit_type: str = ""
    conditions: list[str] = []
    medications: list[str] = []
    laboratory_tests: list[str] = []
    laboratory_values: list[str] = []
    providers: list[str] = []
    procedures: list[str] = []
    symptoms: list[str] = []
    diagnoses: list[str] = []
    recommendations: list[str] = []

    @field_validator(
        "patient_id",
        "patient_name",
        "report_date",
        "visit_type",
        mode="before",
    )
    @classmethod
    def _validate_text_fields(cls, value: Any) -> str:
        if value is None:
            return ""
        if not isinstance(value, str):
            raise ValueError("must be a string")
        return _snake_normalize(value)

    @field_validator(
        "conditions",
        "laboratory_tests",
        "laboratory_values",
        "providers",
        "procedures",
        "symptoms",
        "diagnoses",
        "recommendations",
        mode="before",
    )
    @classmethod
    def _validate_list_fields(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValueError("must be an array")
        return [_snake_normalize(item) for item in value if isinstance(item, str) and item.strip()]

    @field_validator("medications", mode="before")
    @classmethod
    def _validate_medications(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValueError("must be an array")
        return [_normalize_medication(item) for item in value if isinstance(item, str) and item.strip()]


class MetadataExtractionResult(BaseModel):
    """Structured service response for metadata extraction."""

    model_config = ConfigDict(extra="forbid")

    ok: bool
    provider: str | None = None
    model: str | None = None
    base_url: str | None = None
    latency_seconds: float | None = None
    retries: int = 0
    usage_tokens: dict[str, int] | None = None
    data: MedicalMetadata | None = None
    error: str | None = None
    details: str | None = None
    status_code: int | None = None

    @classmethod
    def error_result(
        cls,
        message: str,
        *,
        provider: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        details: str | None = None,
        status_code: int | None = None,
        retries: int = 0,
    ) -> MetadataExtractionResult:
        return cls(
            ok=False,
            provider=provider,
            model=model,
            base_url=base_url,
            error=message,
            details=details,
            status_code=status_code,
            retries=retries,
        )


# Backward-compatible aliases
MetadataExtractionResponse = MedicalMetadata
