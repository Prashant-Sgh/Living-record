from __future__ import annotations

from abc import ABC, abstractmethod

from app.services.metadata_extraction.schemas import MedicalMetadata


class MetadataExtractionProvider(ABC):
    """Abstract base class for metadata extraction providers."""

    @property
    @abstractmethod
    def model(self) -> str:
        """Configured model identifier."""

    @property
    @abstractmethod
    def base_url(self) -> str | None:
        """Provider base URL, if applicable."""

    @abstractmethod
    async def extract_metadata(self, report_text: str) -> MedicalMetadata:
        """Extract metadata from medical report text.

        Args:
            report_text: The text content of the medical report.

        Returns:
            Validated medical metadata extracted from the report.
        """
        raise NotImplementedError
