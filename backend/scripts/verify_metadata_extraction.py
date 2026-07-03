import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.metadata_extraction_service import MetadataExtractionService, metadata_extraction_service
from app.core.config import get_settings

sample_text = """
John Doe, patient ID 12345, visited the clinic on 2026-06-14 for a follow-up. Visit type: outpatient.
He continues with Type II Diabetes and hypertension. Medications include Metformin 500 mg once daily and Lisinopril 10 mg.
Lab tests: CBC, HbA1c. HbA1c result: 7.2%.
Providers: Dr. Alice Smith, Dr. Bob Lee. Procedures: EKG.
Symptoms: fatigue, increased thirst. Diagnoses: type 2 diabetes, essential hypertension.
Recommendations: continue medication, follow diet, return in 3 months.
"""

async def run_case(description: str, text: str, service=None):
    print(f"\n=== {description} ===")
    if service is None:
        service = metadata_extraction_service
    result = await service.extract_metadata(text)
    print(result.model_dump_json(indent=2))

async def run_invalid_json_case(description: str):
    print(f"\n=== {description} ===")
    service = MetadataExtractionService()
    service.provider = metadata_extraction_service.provider
    service.model = metadata_extraction_service.model
    # Monkeypatch the provider call to return invalid JSON directly.
    async def fake_call(_text: str):
        return {"text": "{invalid_json: true}"}
    service._call_openai = fake_call  # type: ignore[assignment]
    result = await service.extract_metadata(sample_text)
    print(result.model_dump_json(indent=2))

async def run_invalid_provider_case(description: str):
    print(f"\n=== {description} ===")
    service = MetadataExtractionService()
    service.provider = "unsupported"
    result = await service.extract_metadata(sample_text)
    print(result.model_dump_json(indent=2))

async def main():
    settings = get_settings()
    print(
        'Loaded settings: provider=',
        settings.metadata_extraction_llm_provider,
        'model=',
        settings.metadata_extraction_llm_model or settings.llm_model or settings.openai_model or settings.ollama_model,
    )

    # Valid sample
    await run_case('Sample medical report', sample_text)

    # Invalid JSON response handling
    await run_invalid_json_case('Invalid JSON')

    # Unsupported provider handling
    await run_invalid_provider_case('Invalid provider')

    # Timeout case: only if Ollama is configured with a base URL but not reachable.
    if settings.llm_provider == 'ollama':
        print('Skipping explicit timeout case for Ollama without invalid endpoint')

if __name__ == '__main__':
    asyncio.run(main())
