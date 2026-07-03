import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings
from app.services.memory_service import MemoryService

async def main():
    settings = get_settings()
    service = MemoryService(settings=settings)
    initialized = await service.initialize()
    print('Initialized:', initialized)
    print('Health:', await service.health())

    reports_dir = Path(__file__).resolve().parents[2] / 'reports'
    report_files = sorted([str(p) for p in reports_dir.glob('John_Doe_*.pdf') if p.exists()])
    print('Found reports:', report_files)

    if report_files:
        summary = await service.process_memory(report_files)
        print('Process summary:', summary)

    recall_q = "Summarize John Doe's diabetes progression."
    recall_res = await service.recall(recall_q)
    print('Recall:', recall_res)

    stats = await service.memory_statistics()
    print('Stats:', stats)

    await service.shutdown()
    print('Shutdown complete')

if __name__ == '__main__':
    asyncio.run(main())
