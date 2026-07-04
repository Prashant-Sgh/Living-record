import logging
import time
import asyncio
from pathlib import Path
from typing import Any, Dict, List

from app.core.logging import get_logger
from app.services.upload_service import UploadService
from app.services.metadata_extraction_service import MetadataExtractionService
from app.services.memory_service import MemoryService
from app.services.graph_history_service import GraphHistoryService

logger = get_logger("app.report_ingestion_service")

class ReportIngestionService:
    """
    Orchestrates the full ingestion pipeline for a single uploaded PDF report.

    Steps:
    1. Load stored PDF via UploadService.
    2. Extract raw text & metadata via MetadataExtractionService.
    3. Validate metadata.
    4. Determine deterministic dataset name (patient/{patient_id}).
    5. Generate deterministic NodeSet labels per specification.
    6. Initialise MemoryService (once) and activate dataset & NodeSet.
    7. Call remember() with the PDF path (Cognee ingests the file).
    8. Generate graph visualization (non‑blocking on failure).
    9. Return structured result.
    """

    def __init__(self, settings: Any = None, memory_service: MemoryService | None = None) -> None:
        # Settings are optional – services will fall back to get_settings()
        self.settings = settings
        self.upload_service = UploadService(settings=self.settings)
        self.metadata_service = MetadataExtractionService(settings=self.settings)
        # Allow injection of a shared MemoryService (used by verification script)
        self.memory_service = memory_service or MemoryService(settings=self.settings)
        self.graph_history_service = GraphHistoryService()

    async def _load_pdf_path(self, upload_id: str) -> Path:
        """Retrieve the stored PDF path from the UploadService."""
        upload_record = await self.upload_service.get(upload_id)
        storage_dir = Path(self.upload_service.storage_dir)  # type: ignore
        pdf_path = storage_dir / upload_record.stored_filename  # type: ignore
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found at {pdf_path}")
        return pdf_path

    def _metadata_to_labels(self, metadata: Any) -> List[str]:
        """
        Convert validated metadata into deterministic NodeSet labels.
        Supports raw dict, pydantic BaseModel, or MetadataExtractionResult.
        """
        # Extract underlying dict
        data = getattr(metadata, "data", None) or metadata
        if hasattr(data, "model_dump"):
            data = data.model_dump()
        elif hasattr(data, "dict"):
            data = data.dict()
        if not isinstance(data, dict):
            raise ValueError("Metadata is not a mapping")

        # Deterministic ordering
        labels: List[str] = []
        for key in sorted(data.keys()):
            # Simplify to string representation; complex types are stringified
            labels.append(f"{key}:{data[key]}")
        return labels

    async def process_report(self, upload_id: str) -> Dict[str, Any]:
        """
        Execute the full ingestion pipeline for a given upload_id.

        Returns a dictionary with:
            success (bool)
            patient_id (str | None)
            dataset (str | None)
            generated_nodesets (List[str])
            remember_completed (bool)
            graph_available (bool)
            graph_path (str | None)
            processing_time (float)
            metadata_summary (Dict[str, Any] | None)
            error (str | None)
        """
        start_time = time.time()
        result: Dict[str, Any] = {
            "success": False,
            "patient_id": None,
            "dataset": None,
            "generated_nodesets": [],
            "remember_completed": False,
            "graph_available": False,
            "graph_path": None,
            "processing_time": None,
            "metadata_summary": None,
            "error": None,
        }

        try:
            # 1. Load PDF path
            pdf_path = await self._load_pdf_path(upload_id)

            # 2. Extract metadata (read binary PDF and feed to extraction service)
            # Extract raw PDF bytes and attempt metadata extraction with retries
            with pdf_path.open("rb") as f:
                pdf_bytes = f.read()
            report_text = pdf_bytes.decode(errors="ignore")

            # Retry loop for metadata extraction (up to 4 attempts)
            max_attempts = 4
            metadata_res = None
            for attempt in range(1, max_attempts + 1):
                metadata_res = await self.metadata_service.extract_metadata(report_text)
                if getattr(metadata_res, "ok", False):
                    break
                logger.warning(
                    "[METADATA] Attempt %d/%d failed: %s",
                    attempt,
                    max_attempts,
                    getattr(metadata_res, "error", "unknown error"),
                )
                if attempt < max_attempts:
                    # exponential backoff
                    await asyncio.sleep(2 ** attempt)
            if not getattr(metadata_res, "ok", False):
                raise RuntimeError(f"Metadata extraction failed after {max_attempts} attempts: {metadata_res}")

            # Extract raw dict for further use
            meta_obj = metadata_res.data
            if hasattr(meta_obj, "model_dump"):
                meta_dict = meta_obj.model_dump()
            elif hasattr(meta_obj, "dict"):
                meta_dict = meta_obj.dict()
            else:
                meta_dict = meta_obj
            result["metadata_summary"] = meta_dict

            # 3. Validate required fields
            # Determine patient ID with deterministic fallback
            import hashlib

            patient_id = meta_dict.get("patient_id")
            if not patient_id:
                # Fallback: use deterministic hash of patient_name or full name
                fallback_name = (
                    meta_dict.get("patient_name")
                    or meta_dict.get("patient_full_name")
                    or "unknown"
                )
                # Generate a stable 8‑character hex ID from SHA‑256
                patient_id = hashlib.sha256(fallback_name.encode("utf-8")).hexdigest()[:8]
                logger.info(
                    "[PIPELINE] patient_id not found; generated deterministic ID %s from fallback name '%s'",
                    patient_id,
                    fallback_name,
                )

            result["patient_id"] = patient_id

            # 4. Determine deterministic dataset name
            dataset_name = f"patient/{patient_id}"
            result["dataset"] = dataset_name

            # 5. Generate deterministic NodeSet labels
            # According to spec: patient, timeline, month, visit, condition, specialty, document
            labels: List[str] = []
            # Patient NodeSet
            labels.append(f"patient/{patient_id}")
            # Timeline (year)
            report_date = meta_dict.get("report_date")
            if report_date:
                try:
                    year = report_date[:4]
                    month = report_date[:7]  # YYYY-MM
                    labels.append(f"year/{year}")
                    labels.append(f"month/{month}")
                except Exception:
                    pass
            # Visit type
            visit_type = meta_dict.get("visit_type")
            if visit_type:
                labels.append(f"visit/{visit_type}")
            # Conditions
            conditions = meta_dict.get("conditions") or []
            for cond in conditions:
                labels.append(f"condition/{cond}")
            # Specialties (derived from providers perhaps)
            providers = meta_dict.get("providers") or []
            for prov in providers:
                specialty = prov.get("specialty")
                if specialty:
                    labels.append(f"specialty/{specialty}")
            # Document type
            labels.append("document/medical_report")
            # Deduplicate while preserving order
            seen = set()
            deterministic_labels = [x for x in labels if not (x in seen or seen.add(x))]
            result["generated_nodesets"] = deterministic_labels

            # 6. Initialise MemoryService (once)
            if not self.memory_service._initialized:
                await self.memory_service.initialize()
            if not self.memory_service.connected:
                logger.warning("[MEMORY] MemoryService not connected – skipping ingestion.")

            # 7. Activate dataset & nodeset
            self.memory_service.create_dataset(dataset_name)
            self.memory_service.set_active_dataset(dataset_name)

            # Use first deterministic label as primary nodeset name
            primary_nodeset = deterministic_labels[0] if deterministic_labels else "default"
            self.memory_service.create_nodeset(primary_nodeset)
            self.memory_service.set_active_nodeset(primary_nodeset)

            # 8. Ingest PDF via remember()
            remember_res = await self.memory_service.remember([str(pdf_path)])
            if not remember_res.get("ok"):
                raise RuntimeError(f"MemoryService.remember failed: {remember_res}")
            result["remember_completed"] = True

            # 9. Generate graph visualization (non‑critical)
            graphs_dir = Path(__file__).resolve().parents[3] / "graphs"
            graphs_dir.mkdir(parents=True, exist_ok=True)
            graph_path = graphs_dir / f"{upload_id}_graph.html"
            vis_ok = await self.memory_service.visualize_graph(graph_path)
            if vis_ok:
                result["graph_available"] = True
                result["graph_path"] = str(graph_path)
            else:
                result["graph_path"] = None
                logger.warning("[GRAPH] Graph visualization failed for upload_id %s", upload_id)

            # Create checkpoint after graph handling
            try:
                checkpoint_info = self.graph_history_service.create_checkpoint(
                    patient_id=patient_id,
                    dataset=dataset_name,
                    source_report=pdf_path.name,
                    graph_path=result.get("graph_path"),
                    graph_available=result["graph_available"],
                    nodesets=deterministic_labels,
                    remember_completed=result["remember_completed"],
                )
                result["checkpoint_version"] = checkpoint_info["version"]
                result["checkpoint_dir"] = checkpoint_info["checkpoint_dir"]
                logger.info(
                    "[CHECKPOINT] Creating checkpoint version %s for patient %s",
                    checkpoint_info["version"],
                    patient_id,
                )
                logger.info(
                    "[CHECKPOINT] Checkpoint completed version %s directory=%s graph_available=%s",
                    checkpoint_info["version"],
                    checkpoint_info["checkpoint_dir"],
                    result["graph_available"],
                )
            except Exception as e:
                logger.exception("[CHECKPOINT] Failed to create checkpoint: %s", e)
                result["error"] = f"Checkpoint creation failed: {e}"
                result["success"] = False
                return result

            result["success"] = True

        except Exception as exc:
            logger.exception("[PIPELINE] Ingestion failed for upload_id %s: %s", upload_id, exc)
            result["error"] = str(exc)
        finally:
            result["processing_time"] = time.time() - start_time
        return result