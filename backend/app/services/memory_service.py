from pathlib import Path
from typing import Any

from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger("app.memory_service")


class MemoryService:
    """Abstract the application's memory backend behind a stable service interface."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.connected = False
        self.mode = self.settings.memory_mode
        self.ontology_loaded = False
        self._initialized = False
        self._cognee_client = None

    async def initialize(self) -> bool:
        """Initialize the memory backend or fall back to a placeholder state."""
        self.mode = self.settings.memory_mode or "placeholder"
        self.connected = False
        self.ontology_loaded = self._resolve_ontology_path() is not None and self._resolve_ontology_path().exists()

        if self.mode.lower() == "cognee" and self._is_configured_for_backend():
            self.connected = await self._connect_cognee()
            self.ontology_loaded = await self._load_ontology()

        self._initialized = True
        return self._initialized

    async def shutdown(self) -> None:
        """Shut down the memory backend if it was initialized."""
        if self.connected:
            try:
                import cognee

                await cognee.disconnect(clear_saved=False)
            except ImportError:
                logger.warning("Cognee SDK is not installed at shutdown.")
            except Exception as exc:  # pragma: no cover - defensive shutdown
                logger.exception("Error while disconnecting Cognee: %s", exc)

        self.connected = False
        self._initialized = False
        self._cognee_client = None

    async def health(self) -> dict[str, Any]:
        """Return a lightweight status snapshot for the memory subsystem."""
        return {
            "connected": self.connected,
            "mode": self.mode,
            "ontology_loaded": self.ontology_loaded,
        }

    def is_connected(self) -> bool:
        """Return whether the memory backend is currently considered connected."""
        return self.connected

    async def _connect_cognee(self) -> bool:
        try:
            import cognee

            self._cognee_client = await cognee.serve(
                url=self.settings.cognee_service_url,
                api_key=self.settings.cognee_api_key,
            )
            logger.info("Connected to Cognee backend at %s", self.settings.cognee_service_url)
            return True
        except ImportError as exc:
            logger.exception("Cognee SDK is not installed: %s", exc)
            return False
        except Exception as exc:  # pragma: no cover - backend init should not crash the app
            logger.exception("Failed to connect to Cognee backend: %s", exc)
            return False

    async def _load_ontology(self) -> bool:
        ontology_file = self._resolve_ontology_path()
        if ontology_file is None or not ontology_file.exists():
            logger.warning("Ontology file not found at path: %s", self.settings.ontology_path)
            return False

        if not self.connected:
            logger.warning("Cognee backend is not connected, skipping ontology load.")
            return False

        try:
            import cognee

            logger.info("Loading ontology from %s into Cognee", ontology_file)
            await cognee.add(str(ontology_file), dataset_name="ontology", run_in_background=False)
            return True
        except Exception as exc:  # pragma: no cover - ontology load should not crash startup
            logger.exception("Failed to load ontology into Cognee: %s", exc)
            return False

    def _resolve_ontology_path(self) -> Path | None:
        if not self.settings.ontology_path:
            return None

        candidate = Path(self.settings.ontology_path)
        if candidate.is_absolute():
            return candidate

        application_root = Path(__file__).resolve().parents[2]
        resolved = application_root / candidate
        if resolved.exists():
            return resolved

        storage_candidate = application_root / "storage" / candidate
        return storage_candidate

    def _is_configured_for_backend(self) -> bool:
        """Determine whether the current configuration can use a real backend."""
        if self.mode.lower() == "placeholder":
            return False
        if self.mode.lower() == "cognee":
            return bool(self.settings.cognee_api_key and self.settings.cognee_service_url)
        return False
