from pathlib import Path
from typing import Any

from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger("app.memory_service")


class GlobalContext:
    """Simple placeholder for a global context index used by MemoryService.

    This is intentionally lightweight for the initial milestone. Future
    enhancements will populate, refresh, and expose longitudinal context.
    """

    def __init__(self) -> None:
        self._last_refreshed: float | None = None
        self._status: str = "stale"
        self._version: int = 0

    async def refresh(self) -> None:
        """Refresh the global context index (placeholder)."""
        import time

        # Lightweight refresh: update timestamp and bump version so callers
        # can detect that global context has changed.
        self._last_refreshed = time.time()
        self._status = "fresh"
        self._version += 1

    def status(self) -> dict[str, Any]:
        return {"status": self._status, "last_refreshed": self._last_refreshed, "version": self._version}



class MemoryService:
    """Abstract the application's memory backend behind a stable service interface."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.connected = False
        self.mode = self.settings.memory_mode
        self.ontology_loaded = False
        self._initialized = False
        self._cognee_client = None
        # Dataset / NodeSet state
        self._active_dataset: str | None = "living-record"
        self._active_nodeset: str | None = None

        # Global context placeholder
        self.global_context = GlobalContext()
        # Tracking for enrichment and snapshots
        self._reports_processed: int = 0
        self._graph_snapshots: list[str] = []
        self._memory_enriched: bool = False

    async def initialize(self) -> bool:
        """Initialize the memory backend or fall back to a placeholder state."""
        # Normalize mode and inspect configuration
        self.mode = (self.settings.memory_mode or "local").lower()
        self.connected = False
        # Pre-check whether an ontology file exists on disk
        self.ontology_loaded = self._resolve_ontology_path() is not None and self._resolve_ontology_path().exists()

        if self.mode == "local":
            # Local mode uses locally-provided LLM / embedding providers and does
            # not intentionally connect to remote Cognee Cloud.
            if not (self.settings.llm_provider and self.settings.llm_model and self.settings.embedding_provider and self.settings.embedding_model):
                logger.warning("Incomplete local model/embedding configuration; memory unavailable in local mode.")
                self.connected = False
            else:
                self.connected = await self._connect_cognee_local()
                if self.connected:
                    self.ontology_loaded = await self._load_ontology()

        elif self.mode == "cloud":
            # Cloud mode uses Cognee Cloud API URL + API key
            if not (self.settings.cognee_api_key and (self.settings.cognee_api_url or self.settings.cognee_service_url)):
                logger.warning("Cognee Cloud credentials missing; memory unavailable in cloud mode.")
                self.connected = False
            else:
                self.connected = await self._connect_cognee_cloud()
                if self.connected:
                    self.ontology_loaded = await self._load_ontology()

        else:
            logger.warning("Unknown MEMORY_MODE '%s' — treating as unavailable", self.mode)

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
            "dataset": self._active_dataset,
            "nodeset": self._active_nodeset,
        }

    def is_connected(self) -> bool:
        """Return whether the memory backend is currently considered connected."""
        return self.connected

    # Dataset management
    def create_dataset(self, name: str) -> bool:
        """Create a dataset (logical). Currently a thin wrapper that sets active dataset.

        Future: call Cognee APIs to create persistent datasets.
        """
        logger.info("Creating dataset '%s' (logical)", name)
        self._active_dataset = name
        return True

    def set_active_dataset(self, name: str) -> None:
        """Set the active dataset for subsequent operations."""
        logger.info("Setting active dataset to '%s'", name)
        self._active_dataset = name

    def get_active_dataset(self) -> str | None:
        return self._active_dataset

    # NodeSet management
    def create_nodeset(self, name: str) -> bool:
        """Create a NodeSet (logical)."""
        logger.info("Creating NodeSet '%s' (logical)", name)
        # no-op for now beyond tracking
        return True

    def set_active_nodeset(self, name: str) -> None:
        logger.info("Setting active NodeSet to '%s'", name)
        self._active_nodeset = name

    def get_active_nodeset(self) -> str | None:
        return self._active_nodeset

    # Remember / Recall
    async def remember(self, file_paths: list[str]) -> dict[str, Any]:
        """Ingest files (PDFs) into the active dataset and NodeSet using Cognee.

        - Accepts one or many file paths
        - Uses configured ontology implicitly
        - Respects active dataset and NodeSet
        - Disables self-improvement by default
        """
        if not self.connected:
            logger.warning("MemoryService.remember called while disconnected")
            return {"ok": False, "reason": "not_connected"}

        results = []
        try:
            import cognee

            for p in file_paths:
                path = Path(p)
                if not path.exists():
                    logger.warning("Remember skipped missing file: %s", p)
                    continue

                kwargs: dict[str, Any] = {"dataset_name": self._active_dataset, "run_in_background": False, "self_improvement": False}
                if self._active_nodeset:
                    kwargs["node_set"] = [self._active_nodeset]

                logger.info("Remembering file %s into dataset=%s nodeset=%s", p, self._active_dataset, self._active_nodeset)
                res = await cognee.add(str(path), **kwargs)
                results.append(res)

            # Track processed reports for statistics
            self._reports_processed += len(results)
            return {"ok": True, "count": len(results), "results": results}
        except Exception as exc:
            logger.exception("Error during remember: %s", exc)
            return {"ok": False, "reason": str(exc)}

    async def recall(self, query: str) -> dict[str, Any]:
        """Perform a recall query against Cognee using the active dataset.

        Returns a generic dict with potential fields: answer, supporting_nodes, citations.
        """
        if not self.connected:
            logger.warning("MemoryService.recall called while disconnected")
            return {"answer": None, "results": [], "error": "not_connected"}

        try:
            import cognee
            from cognee import SearchType

            query_type = SearchType.TEMPORAL if any(keyword in query.lower() for keyword in ["progressed", "how has", "over time", "changes", "trend"]) else SearchType.GRAPH_COMPLETION
            logger.info("Recalling query against dataset=%s using type=%s: %s", self._active_dataset, query_type, query)
            recall_results = await cognee.recall(
                query,
                query_type=query_type,
                datasets=[self._active_dataset] if self._active_dataset else None,
            )
            return {"answer": recall_results, "results": recall_results, "query_type": query_type.value}
        except Exception as exc:
            # Provide richer guidance for common remote errors
            msg = str(exc)
            if "Remote recall failed (401)" in msg or "Unauthorized" in msg:
                logger.error("Recall failed due to authentication error: %s", msg)
                return {"answer": None, "results": [], "error": "unauthorized", "detail": msg}
            if "Remote recall failed (409)" in msg:
                logger.error("Recall failed on server (409): %s", msg)
                return {"answer": None, "results": [], "error": "server_recall_error", "detail": msg}

            logger.exception("Error during recall: %s", exc)
            return {"answer": None, "results": [], "error": "internal_error", "detail": msg}

    async def visualize_graph(self, output_path: str | Path) -> bool:
        """Generate a visualization of the knowledge graph and save to `output_path`."""
        if not self.connected:
            logger.warning("visualize_graph called while disconnected")
            return False

        try:
            import cognee
            logger.info("Generating graph visualization to %s", output_path)
            # Try the SDK's newer signature first, then fall back to older ones.
            try:
                await cognee.visualize_graph(destination_file_path=str(output_path), dataset=self._active_dataset)
            except TypeError:
                try:
                    await cognee.visualize_graph(str(output_path))
                except TypeError:
                    await cognee.visualize_graph(output_path=str(output_path))
            return True
        except Exception as exc:
            # Detect common DB access error (local SDK filesystem DB) and provide guidance
            msg = str(exc)
            if "unable to open database file" in msg or "sqlite3.OperationalError" in msg:
                logger.error(
                    "Graph visualization failed due to local DB access: %s. "
                    "This often means the Cognee local runtime cannot access its DB files. "
                    "If you intended to use cloud mode, set MEMORY_MODE=cloud and configure COGNEE_API_KEY/COGNEE_SERVICE_URL.",
                    msg,
                )
                return False

            logger.exception("Graph visualization failed: %s", exc)
            return False

    async def _connect_cognee(self) -> bool:
        # Legacy compatibility: prefer the explicit cloud/local connectors below.
        logger.debug("_connect_cognee() is deprecated; use mode-specific connectors")
        return False

    async def _connect_cognee_cloud(self) -> bool:
        try:
            import cognee

            service_url = self.settings.cognee_api_url or self.settings.cognee_service_url
            self._cognee_client = await cognee.serve(url=service_url, api_key=self.settings.cognee_api_key)
            logger.info("Connected to Cognee Cloud at %s", service_url)
            return True
        except ImportError as exc:
            logger.exception("Cognee SDK is not installed: %s", exc)
            return False
        except Exception as exc:  # pragma: no cover - backend init should not crash the app
            logger.exception("Failed to connect to Cognee Cloud: %s", exc)
            return False

    async def _connect_cognee_local(self) -> bool:
        try:
            import cognee

            # Local mode should not fall back to remote cloud.
            # Require an explicit local service URL for direct local connections.
            local_url = self.settings.cognee_api_url or self.settings.cognee_service_url
            if not local_url:
                logger.warning(
                    "Local Cognee mode requested but no local URL configured. "
                    "Set COGNEE_API_URL or COGNEE_SERVICE_URL to a local endpoint."
                )
                return False

            self._cognee_client = await cognee.serve(url=local_url)
            logger.info("Initialized local Cognee runtime at %s", local_url)
            return True
        except ImportError as exc:
            logger.exception("Cognee SDK is not installed: %s", exc)
            return False
        except Exception as exc:  # pragma: no cover - backend init should not crash the app
            logger.exception("Failed to initialize local Cognee runtime: %s", exc)
            return False

    async def _load_ontology(self) -> bool:
        ontology_file = self._resolve_ontology_path()
        if ontology_file is None or not ontology_file.exists():
                logger.warning(
                    "Ontology file not found. Tried paths: ontology_file_path=%s ontology_path=%s",
                    self.settings.ontology_file_path,
                    self.settings.ontology_path,
                )
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
        candidates: list[Path] = []
        if self.settings.ontology_file_path:
            candidates.append(Path(self.settings.ontology_file_path))
        if self.settings.ontology_path:
            candidates.append(Path(self.settings.ontology_path))

        application_root = Path(__file__).resolve().parents[2]
        for candidate in candidates:
            if candidate.is_absolute() and candidate.exists():
                return candidate

            resolved = application_root / candidate
            if resolved.exists():
                return resolved

            resolved_storage = application_root / "storage" / candidate
            if resolved_storage.exists():
                return resolved_storage

        # If no candidates were provided by configuration, do not fallback
        # to the repository file — an explicit empty string should disable
        # ontology loading in tests and runtime configurations.
        if not candidates:
            return None

        # Map common container paths into the local repository when running outside Docker.
        for candidate in candidates:
            if str(candidate).startswith("/app/"):
                mapped = application_root / candidate.relative_to("/app")
                if mapped.exists():
                    return mapped

        # Fallback to a known ontology file in the repository if configured paths failed.
        fallback = application_root / "app" / "storage" / "ontology" / "ontology.owl"
        if fallback.exists():
            return fallback

        return None

    def _is_configured_for_backend(self) -> bool:
        """Determine whether the current configuration can use a real backend."""
        if self.mode.lower() == "placeholder":
            return False
        if self.mode.lower() == "cognee":
            return bool(self.settings.cognee_api_key and self.settings.cognee_service_url)
        return False

    # --- Memory enrichment & evolution ---
    async def enrich_memory(self) -> dict[str, Any]:
        """Run Cognee's enrichment/improvement pipeline on the active dataset.

        If the installed Cognee SDK exposes an `improve`/`memify` API this will
        call it; otherwise this method logs a placeholder and returns a
        structured result so the public API is stable.
        """
        if not self.connected:
            logger.warning("enrich_memory called while disconnected")
            return {"ok": False, "reason": "not_connected"}

        try:
            import cognee

            # Detect the most likely enrichment API and call it.
            if hasattr(cognee, "improve"):
                logger.info("Starting Cognee.improve on dataset=%s", self._active_dataset)
                await cognee.improve(dataset=self._active_dataset, run_in_background=False)
                self._memory_enriched = True
                logger.info("Cognee.improve completed")
                return {"ok": True, "method": "improve"}

            if hasattr(cognee, "memify"):
                logger.info("Starting Cognee.memify on dataset=%s", self._active_dataset)
                await cognee.memify(dataset=self._active_dataset, run_in_background=False)
                self._memory_enriched = True
                logger.info("Cognee.memify completed")
                return {"ok": True, "method": "memify"}

            # Fallback: SDK doesn't support enrichment yet
            logger.info("Enrichment API not available in installed Cognee SDK; skipping enrichment")
            return {"ok": False, "reason": "unsupported"}
        except Exception as exc:
            logger.exception("Error during memory enrichment: %s", exc)
            return {"ok": False, "reason": str(exc)}

    async def save_graph_snapshot(self, label: str) -> str | None:
        """Generate and save a graph visualization labelled by `label`.

        The generated file is saved under the configured `graph_directory`.
        Returns the path string on success or None on failure.
        """
        graph_dir = Path(self.settings.graph_directory)
        graph_dir.mkdir(parents=True, exist_ok=True)
        safe_label = label.replace(" ", "_").lower()
        out_path = graph_dir / f"graph_{safe_label}.html"

        ok = await self.visualize_graph(out_path)
        if ok:
            self._graph_snapshots.append(str(out_path))
            logger.info("Graph snapshot saved: %s", out_path)
            return str(out_path)
        logger.warning("Graph snapshot failed for label=%s", label)
        return None

    async def process_memory(self, files: list[str]) -> dict[str, Any]:
        """Full memory lifecycle for a set of files.

        Pipeline: remember -> save_graph_snapshot('before') -> enrich_memory -> save_graph_snapshot('after') -> refresh global context
        Returns a structured summary of the process.
        """
        summary: dict[str, Any] = {"dataset": self._active_dataset, "nodeset": self._active_nodeset}

        remember_res = await self.remember(files)
        summary["remember"] = remember_res

        before = await self.save_graph_snapshot("before_enrichment")
        summary["graph_before"] = before

        enrich_res = await self.enrich_memory()
        summary["enrich"] = enrich_res

        after = await self.save_graph_snapshot("after_enrichment")
        summary["graph_after"] = after

        # Refresh global context
        await self.global_context.refresh()
        summary["global_context"] = self.global_context.status()

        return summary

    async def memory_statistics(self) -> dict[str, Any]:
        """Return lightweight memory statistics and placeholders for missing info."""
        return {
            "dataset": self._active_dataset,
            "nodeset": self._active_nodeset,
            "reports_processed": self._reports_processed,
            "memory_enriched": self._memory_enriched,
            "graph_snapshots": list(self._graph_snapshots),
        }
