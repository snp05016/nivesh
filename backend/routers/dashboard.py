from fastapi import APIRouter, Request, Header, HTTPException
from fastapi.responses import StreamingResponse
import asyncio
import json
import time
from helpers import (
    _dash_lock, _active_analyses, _completed_analyses,
    _harvest_status, _token_stats, _request_log, require_auth
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
    """Get current dashboard state.

    The authoritative 'is an analysis running' signal is the DB AnalysisJob table
    (survives restarts / connection drops). The in-memory _active_analyses dict is
    merged in as a best-effort supplement.
    """
    # DB-backed active jobs — single source of truth for the v2 engine.
    db_jobs = {}
    try:
        import database
        for j in database.list_active_jobs():
            db_jobs[j["job_id"]] = {
                "job_id": j["job_id"], "ticker": j["ticker"],
                "scan_type": j["scan_type"], "status": j["status"],
                "stage": j["stage"], "progress_pct": j["progress_pct"],
                "tokens_used": j["tokens_used"],
                "checkpoints": j["checkpoints"][-3:],  # last few for a live ticker
            }
    except Exception as e:
        print(f"[dashboard] active job read failed: {e}")

    with _dash_lock:
        merged = {**dict(_active_analyses), **db_jobs}
        return {
            "type": "dashboard_snapshot",
            "active_analyses": merged,
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
async def dashboard_stream(request: Request, authorization: str = Header(None)):
    """SSE endpoint for live dashboard updates and checkpoint progress."""
    require_auth(authorization)
    return StreamingResponse(
        event_generator(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )
