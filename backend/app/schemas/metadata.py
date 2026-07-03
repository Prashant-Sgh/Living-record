import re
import unicodedata
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator, ValidationError


def _snake_normalize(value: str) -> str:
    text = str(value).strip()
    text = unicodedata.normalize("NFKD", text)
    text = text.lower()
    # Replace common roman numerals with digits for medical conditions.
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
    text = text.strip("_")
    return text


def _normalize_medication(value: str) -> str:
    text = _snake_normalize(value)
    # Remove numeric dosages and units from medications.
    text = re.sub(r"\b\d+(?:\.\d+)?\b", "", text)
    text = re.sub(r"\b(mg|mcg|g|ml|tablet|tablets|capsule|capsules|once|twice|daily|bid|tid|qid)\b", "", text)
    text = re.sub(r"_+", "_", text)
    return text.strip("_")


class MetadataExtractionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    patient_id: str
    patient_name: str
    report_date: str
    visit_type: str
    conditions: list[str]
    medications: list[str]
    laboratory_tests: list[str]
    laboratory_values: list[str]
    providers: list[str]
    procedures: list[str]
    symptoms: list[str]
    diagnoses: list[str]
    recommendations: list[str]

    @field_validator("patient_id", "patient_name", "report_date", "visit_type", mode="before")
    def validate_text_fields(cls, value: Any) -> str:
        if not isinstance(value, str):
            raise ValueError("must be a string")
        normalized = str(value).strip()
        if normalized == "":
            raise ValueError("must not be empty")
        return normalized

    @field_validator(
        "conditions",
        "medications",
        "laboratory_tests",
        "laboratory_values",
        "providers",
        "procedures",
        "symptoms",
        "diagnoses",
        "recommendations",
        mode="before",
    )
    def validate_list_fields(cls, value: Any, info: Any) -> list[str]:
        if not isinstance(value, list):
            raise ValueError("must be an array")
        normalized_items: list[str] = []
        for item in value:
            if not isinstance(item, str):
                raise ValueError("array items must be strings")
            item_text = item.strip()
            if item_text == "":
                continue
            if info.field_name == "medications":
                normalized = _normalize_medication(item_text)
            else:
                normalized = _snake_normalize(item_text)
            if normalized:
                normalized_items.append(normalized)
        return normalized_items


class MetadataExtractionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool
    provider: str | None = None
    model: str | None = None
    latency_seconds: float | None = None
    retries: int = 0
    usage_tokens: dict[str, int] | None = None
    data: MetadataExtractionResponse | None = None
    error: str | None = None
    details: str | None = None
    status_code: int | None = None

    @classmethod
    def error_result(
        cls,
        message: str,
        provider: str | None = None,
        model: str | None = None,
        details: str | None = None,
        status_code: int | None = None,
        retries: int = 0,
    ) -> "MetadataExtractionResult":
        return cls(
            ok=False,
            provider=provider,
            model=model,
            error=message,
            details=details,
            status_code=status_code,
            retries=retries,
        )
