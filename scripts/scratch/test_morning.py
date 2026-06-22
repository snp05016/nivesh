import asyncio
from backend.services.cache_service import cache, _run_async_in_thread

async def main():
    # Set a dummy result
    result = {
        "summary": "This is a test summary",
        "movers": ["AAPL", "TSLA"],
        "mood": "positive",
        "generated_at": "12:00",
        "priority_items": []
    }
    await cache.set("morning_brief", "1", result)
    
    # Get it back
    cached = await cache.get("morning_brief", "1")
    print(type(cached))
    print(cached)

asyncio.run(main())
