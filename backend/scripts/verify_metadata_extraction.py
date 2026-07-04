"""Verify metadata extraction end-to-end using Report 1."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings
from app.services.metadata_extraction import MetadataExtractionService


REPORT_1_PATH = Path(__file__).resolve().parent / "fixtures" / "report_1.txt"


def _resolve_base_url(settings, provider: str) -> str | None:
    if provider == "openai":
        return settings.openai_base_url or "https://api.openai.com/v1"
    if provider == "ollama":
        return settings.ollama_base_url
    return None


def _resolve_model(settings, provider: str) -> str | None:
    if provider == "openai":
        return settings.openai_model
    if provider == "ollama":
        return settings.ollama_model
    return None


def _validate_result(result) -> tuple[bool, list[str]]:
    issues: list[str] = []
    if not result.ok:
        issues.append(f"extraction failed: {result.error} ({result.details})")
        return False, issues

    if result.data is None:
        issues.append("missing metadata payload")
        return False, issues

    metadata = result.data
    if "john" not in metadata.patient_name:
        issues.append(f"unexpected patient_name: {metadata.patient_name}")
    if metadata.patient_id != "12345":
        issues.append(f"unexpected patient_id: {metadata.patient_id}")
    if not metadata.conditions:
        issues.append("conditions should not be empty")
    if not metadata.medications:
        issues.append("medications should not be empty")
    if "metformin" not in metadata.medications:
        issues.append(f"expected metformin in medications: {metadata.medications}")

    return len(issues) == 0, issues


async def main() -> int:
    settings = get_settings()
    provider = (settings.metadata_extraction_llm_provider or "").strip().lower()
    model = _resolve_model(settings, provider)
    base_url = _resolve_base_url(settings, provider)

    print("=== Metadata Extraction Verification ===")
    print(f"Selected provider: {provider or 'unset'}")
    print(f"Selected model:    {model or 'unset'}")
    print(f"Base URL:          {base_url or 'unset'}")

    if not REPORT_1_PATH.exists():
        print(f"FAIL: Report 1 fixture not found at {REPORT_1_PATH}")
        return 1

    report_text = REPORT_1_PATH.read_text(encoding="utf-8").strip()
    if not report_text:
        print("FAIL: Report 1 fixture is empty")
        return 1

    service = MetadataExtractionService(settings=settings)
    result = await service.extract_metadata(report_text)

    passed, issues = _validate_result(result)

    print("\n=== Extracted Metadata ===")
    if result.data is not None:
        print(json.dumps(result.data.model_dump(), indent=2))
    else:
        print(json.dumps({"error": result.error, "details": result.details}, indent=2))

    print("\n=== Run Metrics ===")
    print(f"Latency (s): {result.latency_seconds:.2f}" if result.latency_seconds is not None else "Latency (s): n/a")
    print(f"Retry count: {result.retries}")
    print(f"Validation:  {'success' if passed else 'failure'}")
    if issues:
        for issue in issues:
            print(f"  - {issue}")

    print(f"\nResult: {'PASS' if passed else 'FAIL'}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
