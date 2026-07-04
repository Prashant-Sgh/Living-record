import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any

from app.core.logging import get_logger

logger = get_logger("app.graph_history_service")


class GraphHistoryService:
    """
    Service responsible for managing immutable memory checkpoints.
    Each checkpoint contains a graph snapshot (HTML) and a small metadata JSON.
    Checkpoints are stored under:
        storage/graph_history/patient_{patient_id}/checkpoint_{version}/
    The version is a sequential integer starting from 1.
    """

    def __init__(self, base_dir: Path | None = None) -> None:
        # Base directory for all checkpoint storage
        if base_dir is None:
            # Resolve to project root's storage/graph_history
            base_dir = Path(__file__).resolve().parents[3] / "storage" / "graph_history"
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _patient_dir(self, patient_id: str) -> Path:
        """Directory storing all checkpoints for a given patient."""
        patient_dir = self.base_dir / f"patient_{patient_id}"
        patient_dir.mkdir(parents=True, exist_ok=True)
        return patient_dir

    def _next_version(self, patient_dir: Path) -> int:
        """Determine the next sequential checkpoint version for a patient."""
        existing = [
            int(p.name.split("_")[-1])
            for p in patient_dir.iterdir()
            if p.is_dir() and p.name.startswith("checkpoint_")
        ]
        return max(existing, default=0) + 1

    def create_checkpoint(
        self,
        patient_id: str,
        dataset: str,
        source_report: str,
        graph_path: str | None,
        graph_available: bool,
        nodesets: List[str],
        remember_completed: bool,
    ) -> Dict[str, Any]:
        """
        Create an immutable checkpoint for a patient.

        Parameters
        ----------
        patient_id: str
            Deterministic patient identifier.
        dataset: str
            Dataset name used for the ingestion.
        source_report: str
            Filename of the source PDF report.
        graph_path: str | None
            Path to the generated graph HTML file (may be None if generation failed).
        graph_available: bool
            Whether graph generation succeeded for this ingestion.
        nodesets: List[str]
            List of node set labels generated for the ingestion.
        remember_completed: bool
            Whether the memory remember() call succeeded.

        Returns
        -------
        dict with version number and checkpoint directory path.
        """
        patient_dir = self._patient_dir(patient_id)
        version = self._next_version(patient_dir)
        checkpoint_dir = patient_dir / f"checkpoint_{str(version).zfill(3)}"
        checkpoint_dir.mkdir(parents=True, exist_ok=False)

        # Copy graph file only when graph generation succeeded.
        if graph_available and graph_path:
            try:
                src = Path(graph_path)
                if src.is_file():
                    dest = checkpoint_dir / "graph.html"
                    shutil.copyfile(src, dest)
            except Exception as e:
                logger.error("[CHECKPOINT] Failed to copy graph for patient %s version %s: %s", patient_id, version, e)

        metadata = {
            "version": version,
            "patient_id": patient_id,
            "dataset": dataset,
            "source_report": source_report,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "graph_file": "graph.html" if graph_available and graph_path else None,
            "remember_completed": remember_completed,
            "graph_available": graph_available,
            "nodesets": nodesets,
        }

        try:
            meta_path = checkpoint_dir / "metadata.json"
            meta_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
            logger.info(
                "[CHECKPOINT] Created checkpoint version %s for patient %s at %s",
                version,
                patient_id,
                checkpoint_dir,
            )
        except Exception as e:
            logger.error("[CHECKPOINT] Failed to write metadata for patient %s version %s: %s", patient_id, version, e)
            # Cleanup partial checkpoint to avoid corrupt state
            shutil.rmtree(checkpoint_dir, ignore_errors=True)
            raise

        return {"version": version, "checkpoint_dir": str(checkpoint_dir)}