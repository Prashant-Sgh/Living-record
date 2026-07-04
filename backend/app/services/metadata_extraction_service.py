"""Backward-compatible re-export of the metadata extraction service."""

from app.services.metadata_extraction import (
    MetadataExtractionService,
    create_metadata_extraction_service,
    metadata_extraction_service,
)

__all__ = [
    "MetadataExtractionService",
    "create_metadata_extraction_service",
    "metadata_extraction_service",
]
