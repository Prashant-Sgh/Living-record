import asyncio
import time
from pathlib import Path
import io
import json

from fastapi import UploadFile

# Ensure project root is on PYTHONPATH
import sys
sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.services.upload_service import UploadService
from app.services.memory_service import MemoryService
from app.services.report_ingestion_service import ReportIngestionService

# -------------------------------------------------------------------------
# Verification script for sequential report ingestion.
# Ingests six John Doe PDF reports one after another.
# Uses a single shared MemoryService (ontology loaded once) and reuses the
# same patient dataset across reports.
# After each successful ingestion, runs a set of recall queries.
# -------------------------------------------------------------------------

REPORT_FILES = [
    "John_Doe_01.pdf",
    "John_Doe_02.pdf",
    # for testing we don't need to test with all the files, instead we can just test with the first two files. The rest can be uncommented if needed.
    # "John_Doe_03.pdf",
    # "John_Doe_04.pdf",
    # "John_Doe_05.pdf",
    # "John_Doe_06.pdf",
]

RECALL_QUERIES = [
    "Summarize John Doe's current health.",
    "How has John Doe's diabetes changed over time?",
    "What medications is John Doe currently taking?",
]


async def ingest_and_recall() -> dict:
    """
    Ingest reports sequentially and return ingestion statistics.
    Returns a dict with keys: successful, failed, total_processing_time.
    """
    # Initialise shared services
    memory_service = MemoryService()
    await memory_service.initialize()
    upload_service = UploadService()
    ingestion_service = ReportIngestionService(memory_service=memory_service)

    successful = 0
    failed = 0
    total_processing_time = 0.0

    for idx, pdf_name in enumerate(REPORT_FILES, start=1):
        print(f"\n========== Report {idx} ==========")
        pdf_path = Path("Living-record/reports") / pdf_name

        if not pdf_path.exists():
            print(f"[Error] Report file not found: {pdf_path}")
            failed += 1
            continue

        # Upload PDF
        with pdf_path.open("rb") as f:
            file_bytes = f.read()
        upload_file = UploadFile(filename=pdf_path.name, file=io.BytesIO(file_bytes))
        upload_resp = await upload_service.upload(upload_file)
        upload_id = getattr(upload_resp, "id", None)
        if not upload_id:
            print(f"[Error] Upload failed for {pdf_name}")
            failed += 1
            continue

        # Process ingestion
        start = time.time()
        try:
            result = await ingestion_service.process_report(upload_id)
            success = result.get("success", False)
        except Exception as exc:
            print(f"[Exception] Ingestion error for {pdf_name}: {exc}")
            success = False
        elapsed = time.time() - start
        total_processing_time += elapsed

        # Summary output
        print(f"Report: {pdf_name}")
        print(f"Success: {success}")
        print(f"Processing Time (s): {elapsed:.2f}")
        if success:
            print(f"Patient ID: {result.get('patient_id')}")
            print(f"Dataset: {result.get('dataset')}")
            print(f"Generated NodeSets: {result.get('generated_nodesets')}")
            print(f"Remember completed: {result.get('remember_completed')}")
            print(f"Graph available: {result.get('graph_available')}")
            print(f"Graph path: {result.get('graph_path')}")
            print(f"Checkpoint version: {result.get('checkpoint_version')}")
            print(f"Checkpoint dir: {result.get('checkpoint_dir')}")
        else:
            print(f"Error: {result.get('error')}")

        # Recall queries for successful ingestions
        if success:
            successful += 1
            for query in RECALL_QUERIES:
                recall_res = await memory_service.recall(query)
                answer = recall_res.get("answer") if isinstance(recall_res, dict) else recall_res
                print(f"--- Recall Query ---\n{query}\nAnswer: {answer}\n")
        else:
            failed += 1

    return {
        "successful": successful,
        "failed": failed,
        "total_processing_time": total_processing_time,
        "total_reports": len(REPORT_FILES),
    }

async def run_all():
    stats = await ingest_and_recall()
    # ----- Checkpoint verification -----
    total_reports = stats.get("total_reports", len(REPORT_FILES))
    successful = stats.get("successful", 0)
    failed = stats.get("failed", 0)
    total_processing_time = stats.get("total_processing_time", 0.0)

    storage_root = Path(__file__).resolve().parents[2] / "storage" / "graph_history"
    storage_root.mkdir(parents=True, exist_ok=True)

    total_checkpoints = 0
    latest_version = 0
    missing_graph = 0
    missing_metadata = 0

    for patient_dir in storage_root.iterdir():
        if not patient_dir.is_dir():
            continue
        for ckpt_dir in patient_dir.iterdir():
            if not ckpt_dir.is_dir() or not ckpt_dir.name.startswith("checkpoint_"):
                continue
            total_checkpoints += 1
            try:
                version = int(ckpt_dir.name.split("_")[-1])
                latest_version = max(latest_version, version)
            except Exception:
                pass
            meta_path = ckpt_dir / "metadata.json"
            if not meta_path.is_file():
                missing_metadata += 1
            else:
                try:
                    meta = json.loads(meta_path.read_text())
                    if not meta.get("graph_available", False):
                        missing_graph += 1
                    else:
                        graph_file = meta.get("graph_file")
                        if graph_file:
                            if not (ckpt_dir / graph_file).is_file():
                                missing_graph += 1
                        else:
                            missing_graph += 1
                except Exception:
                    missing_graph += 1

    print("\n----- Checkpoint Summary -----")
    print(f"Total Checkpoints: {total_checkpoints}")
    print(f"Latest Version: {latest_version}")
    print(f"Missing Graph Files: {missing_graph}")
    print(f"Missing Metadata Files: {missing_metadata}")

    print("\n===== Ingestion Summary =====")
    print(f"Total reports processed: {total_reports}")
    print(f"Successful ingestions: {successful}")
    print(f"Failed ingestions: {failed}")
    print(f"Total processing time (s): {total_processing_time:.2f}")
    print("=" * 30)
if __name__ == "__main__":
    asyncio.run(run_all())


