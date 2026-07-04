from __future__ import annotations

# Async-safe custom exceptions for metadata extraction

# New exceptions (Task 1 specification)
class ConfigurationError(Exception):
    """Configuration error for metadata extraction provider."""


class ProviderAuthenticationError(Exception):
    """Authentication failed for metadata extraction provider."""


class ProviderConnectionError(Exception):
    """Connection failed for metadata extraction provider."""


class ProviderTimeoutError(Exception):
    """Request timed out for metadata extraction provider."""


class ProviderRateLimitError(Exception):
    """Rate limit exceeded for metadata extraction provider."""


class InvalidJSONError(Exception):
    """Invalid JSON response from metadata extraction provider."""


class ValidationError(Exception):
    """Validation error for metadata extraction result."""


# Backward-compatible exceptions (existing service)
class MetadataExtractionError(Exception):
    """Base error for metadata extraction."""


class AuthenticationError(MetadataExtractionError):
    pass


class ProviderNotConfiguredError(MetadataExtractionError):
    pass


class ValidationFailureError(MetadataExtractionError):
    def __init__(self, errors) -> None:
        super().__init__("Validation failed")
        self.errors = errors


class TimeoutError(MetadataExtractionError):
    pass


class RateLimitError(MetadataExtractionError):
    pass


class ConnectionError(MetadataExtractionError):
    pass