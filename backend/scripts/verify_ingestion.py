import asyncio
import time
from pathlib import Path
import io

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
    "John_Doe_03.pdf",
    # for testing we don't need to test with all the files, instead we can just test with the first three files. The rest can be uncommented if needed.
    # "John_Doe_04.pdf",
    # "John_Doe_05.pdf",
    # "John_Doe_06.pdf",
]

RECALL_QUERIES = [
    "Summarize John Doe's current health.",
    "How has John Doe's diabetes changed over time?",
    "What medications is John Doe currently taking?",
]


async def ingest_and_recall():
    # Initialise shared services
    memory_service = MemoryService()
    await memory_service.initialize()
    upload_service = UploadService()
    # Pass shared memory_service to ingestion service
    ingestion_service = ReportIngestionService(memory_service=memory_service)

    total_reports = len(REPORT_FILES)
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

        # Upload PDF and obtain upload_id
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

        # Concise summary
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
        else:
            print(f"Error: {result.get('error')}")

        # Recall queries (only on success)
        if success:
            successful += 1
            for query in RECALL_QUERIES:
                recall_res = await memory_service.recall(query)
                answer = recall_res.get("answer") if isinstance(recall_res, dict) else recall_res
                print(f"--- Recall Query ---\n{query}\nAnswer: {answer}\n")
        else:
            failed += 1

        print("=" * 30)

    # Final aggregated statistics
    print("\n===== Ingestion Summary =====")
    print(f"Total reports processed: {total_reports}")
    print(f"Successful ingestions: {successful}")
    print(f"Failed ingestions: {failed}")
    print(f"Total processing time (s): {total_processing_time:.2f}")
    print("=" * 30)


def main():
    asyncio.run(ingest_and_recall())


if __name__ == "__main__":
    main()