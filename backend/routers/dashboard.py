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
    """Generate SSE events for dashboard and checkpoint progress updates."""
    ticker = request.query_params.get("ticker", "")
    last_check = time.time()
    sent_progress_count = 0

    while True:
        if await request.is_disconnected():
            break

        if ticker:
            # Serve analysis checkpoint progress for this ticker
            try:
                from services.orchestrator import get_analysis_progress
                events = get_analysis_progress(ticker)
                # Send only new events since last check
                for event in events[sent_progress_count:]:
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                sent_progress_count = len(events)
            except Exception:
                pass

        # Also send dashboard snapshot every 2s (for general monitoring)
        current_state = get_dashboard_snapshot()
        yield f"data: {json.dumps(current_state, ensure_ascii=False)}\n\n"

        await asyncio.sleep(1)  # Poll every 1s during analysis for faster updates

def get_dashboard_snapshot():
    """Get current dashboard state."""
    with _dash_lock:
        return {
            "type": "dashboard_snapshot",
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
    """SSE endpoint for live dashboard updates and checkpoint progress."""
    return StreamingResponse(
        event_generator(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )
