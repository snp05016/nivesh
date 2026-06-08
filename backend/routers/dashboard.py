from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
import asyncio
import json
import time
from helpers import (
    _dash_lock, _active_analyses, _completed_analyses,
    _harvest_status, _token_stats, _request_log
)

router = APIRouter(tags=["Dashboard"])

async def event_generator(request: Request):
    """Generate SSE events for dashboard updates."""
    last_check = time.time()
    while True:
        if await request.is_disconnected():
            break
        
        # Check for new events
        current_state = get_dashboard_snapshot()
        
        # Send update if state changed
        # Fix 2.39: ensure_ascii=False for Indian news headings with
        # localized characters (Devanagari, Tamil, etc.)
        yield f"data: {json.dumps(current_state, ensure_ascii=False)}\n\n"
        
        await asyncio.sleep(2)  # Update every 2 seconds

def get_dashboard_snapshot():
    """Get current dashboard state."""
    with _dash_lock:
        return {
            "active_analyses": dict(_active_analyses),
            "recent_analyses": list(_completed_analyses)[:10],
            "harvest_status": dict(_harvest_status),
            "token_stats": {
                "total_input": _token_stats["total_input"],
                "total_output": _token_stats["total_output"],
                "total_calls": _token_stats["total_calls"],
            },
            "timestamp": time.time()
        }

@router.get("/api/v1/dashboard/stream")
async def dashboard_stream(request: Request):
    """SSE endpoint for live dashboard updates."""
    return StreamingResponse(
        event_generator(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )