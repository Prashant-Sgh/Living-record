import time
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import asyncio
from app.core.config import get_settings
from app.services.memory_service import MemoryService

async def main():
    settings = get_settings()
    ms = MemoryService(settings=settings)
    await ms.initialize()
    questions = [
        "What condition does John Doe have?",
        "Summarize John Doe's diabetes progression.",
        "What medications has John Doe received?",
    ]
    results = []
    for q in questions:
        t0 = time.time()
        r = await ms.recall(q)
        t1 = time.time()
        results.append({"question": q, "time_s": t1 - t0, "response": r})
    await ms.shutdown()
    for r in results:
        print(r)

if __name__ == '__main__':
    asyncio.run(main())
