import asyncio
import logging
import sys
from pathlib import Path

# Ensure the backend package root is importable when executing this script directly.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings
from app.services.memory_service import MemoryService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify_memory_service")


async def run_verification(report_paths: list[Path]) -> None:
    settings = get_settings()
    service = MemoryService(settings=settings)

    initialized = await service.initialize()
    logger.info("Initialized: %s", initialized)
    logger.info("Health: %s", await service.health())

    valid_reports = [p for p in report_paths if p.exists()]
    if not valid_reports:
        logger.warning("No valid report files found: %s", report_paths)
    else:
        logger.info("Starting memory pipeline for %d reports", len(valid_reports))
        # Process memory: remember -> snapshot before -> enrich -> snapshot after -> refresh
        summary = await service.process_memory([str(p) for p in valid_reports])
        logger.info("Memory pipeline summary: %s", summary)

    recall_q = "Summarize John Doe's diabetes progression."
    logger.info("Executing recall: %s", recall_q)
    recall_res = await service.recall(recall_q)
    logger.info("Recall result: %s", recall_res)

    stats = await service.memory_statistics()
    logger.info("Memory statistics: %s", stats)

    await service.shutdown()
    logger.info("Shutdown complete")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        report_paths = [Path(arg) for arg in sys.argv[1:]]
    else:
        report_folder = Path(__file__).resolve().parents[1].parents[1] / "reports"
        report_paths = sorted(report_folder.glob("John_Doe_*.pdf"))
    asyncio.run(run_verification(report_paths))
