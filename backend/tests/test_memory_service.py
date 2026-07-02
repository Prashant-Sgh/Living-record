import asyncio
import json
from pathlib import Path

from app.core.config import Settings
from app.services.memory_service import MemoryService


def test_placeholder_memory_service_initializes_without_cognee(tmp_path: Path) -> None:
    ontology_path = tmp_path / "ontology.json"
    ontology_path.write_text(json.dumps({"nodes": [], "edges": []}), encoding="utf-8")

    settings = Settings(
        memory_mode="placeholder",
        ontology_path=str(ontology_path),
    )
    service = MemoryService(settings=settings)

    initialized = asyncio.run(service.initialize())

    assert initialized is True
    assert service.mode == "placeholder"
    assert service.is_connected() is False
    assert service.ontology_loaded is True

    asyncio.run(service.shutdown())
    assert service.is_connected() is False


def test_cognee_memory_service_requires_configuration() -> None:
    settings = Settings(
        memory_mode="cognee",
        cognee_api_key=None,
        cognee_service_url=None,
        ontology_path="",
    )
    service = MemoryService(settings=settings)

    initialized = asyncio.run(service.initialize())

    assert initialized is True
    assert service.mode == "cognee"
    assert service.is_connected() is False
    assert service.ontology_loaded is False
