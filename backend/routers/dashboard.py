import logging
from fastapi import APIRouter, Request, Header, HTTPException, Query
from fastapi.responses import StreamingResponse
import asyncio
import json
import time
from helpers import (
    _dash_lock, _active_analyses, _completed_analyses,
    _harvest_status, _token_stats, _request_log, require_admin
)
from services import job_runs
from services.ai_engine_monitor import build_ai_engine_monitor, get_ai_engine_job_detail

router = APIRouter(tags=["Dashboard"])

# Admin-only operator stream: poll gently and close after a bounded time so a
# forgotten tab cannot hold a connection (and a DB poll) forever.
_STREAM_POLL_SEC = 3
_STREAM_MAX_SEC = 600


async def event_generator(request: Request):
    """Generate SSE dashboard snapshots for the admin operator view."""
    started = time.monotonic()
    while True:
        if await request.is_disconnected():
            break

        # The snapshot does sync DB reads; keep them off the event loop.
        current_state = await asyncio.to_thread(get_dashboard_snapshot)
        yield f"data: {json.dumps(current_state, ensure_ascii=False)}\n\n"

        if time.monotonic() - started >= _STREAM_MAX_SEC:
            break
        await asyncio.sleep(_STREAM_POLL_SEC)

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
        logging.info(f"[dashboard] active job read failed: {e}")

    # Built outside _dash_lock: it runs its own DB query and must not stall
    # writers of the in-memory dashboard state.
    ai_engine = build_ai_engine_monitor(mode="running")
    # job_runs holds scheduler runs from any worker, so every worker shows them (also a DB read).
    with _dash_lock:
        in_memory_harvests = dict(_harvest_status)
    harvest_status = job_runs.merge_harvest_status(in_memory_harvests)

    with _dash_lock:
        merged = {**dict(_active_analyses), **db_jobs}
        return {
            "type": "dashboard_snapshot",
            "active_analyses": merged,
            "recent_analyses": list(_completed_analyses)[:10],
            "ai_engine": ai_engine,
            "harvest_status": harvest_status,
            "token_stats": {
                "total_input": _token_stats["total_input"],
                "total_output": _token_stats["total_output"],
                "total_calls": _token_stats["total_calls"],
            },
            "timestamp": time.time()
        }

@router.get("/api/v1/dashboard/ai-engine")
def ai_engine_dashboard(
    mode: str = "running",
    ticker: str | None = None,
    limit: int = Query(20, ge=1, le=100),
    authorization: str = Header(None),
):
    """
    Live AI engine monitor matching scripts/check_stock.sh modes.

    Args:
        mode (str): The mode.
        ticker (Any): The ticker.
        limit (int): The limit.
        authorization (str): The authorization.

    Returns:
        Any: The response.
    """
    require_admin(authorization)
    return build_ai_engine_monitor(mode=mode, ticker=ticker, limit=limit)


@router.get("/api/v1/dashboard/ai-engine/{job_id}")
def ai_engine_job_detail(job_id: str, authorization: str = Header(None)):
    """
    Detailed monitor record for one AI engine job.

    Args:
        job_id (str): The job_id.
        authorization (str): The authorization.

    Returns:
        Any: The response.
    """
    require_admin(authorization)
    detail = get_ai_engine_job_detail(job_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="AI engine job not found")
    return detail


@router.get("/api/v1/dashboard/stream")
async def dashboard_stream(request: Request, authorization: str = Header(None)):
    """
    Admin-only SSE endpoint for live dashboard snapshots.

    Args:
        request (Request): The request.
        authorization (str): The authorization.

    Returns:
        Any: The response.
    """
    require_admin(authorization)
    return StreamingResponse(
        event_generator(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )
