"""Background harvest workers and scheduler.

Extracted from main.py during monolith refactor Phase 3.

Contains:
- Background harvest runners (YouTube, Advisor, News)
- APScheduler setup for nightly cron jobs
- Admin harvest trigger endpoints (FastAPI router)
"""

import logging
from fastapi import APIRouter, BackgroundTasks, Header
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Dashboard state — canonical source in helpers.py
from helpers import (
    _dash_update_harvest, _dash_lock, _harvest_status,
)
# Auth
from core.security import require_admin
# DB
from database import get_session

router = APIRouter(prefix="/api/v1/admin", tags=["admin-harvest"])
_scheduler: AsyncIOScheduler | None = None


# ── Background runners ─────────────────────────────────────────────────────────

async def _run_youtube_harvest_bg():
    _dash_update_harvest("youtube", "running")
    try:
        from services.youtube_harvester import harvest_youtube_metadata, harvest_portfolio_videos
        res1 = await harvest_youtube_metadata()
        res2 = await harvest_portfolio_videos()
        _dash_update_harvest("youtube", "idle", {"channels": res1, "portfolio": res2})
    except Exception as e:
        _dash_update_harvest("youtube", "error", {"error": str(e)})


async def _run_advisor_harvest_bg():
    _dash_update_harvest("advisor", "running")
    try:
        from services.advisor_harvester import harvest_all_advisors
        res = await harvest_all_advisors()
        _dash_update_harvest("advisor", "idle", {"result": res})
    except Exception as e:
        _dash_update_harvest("advisor", "error", {"error": str(e)})


async def _run_news_harvest_bg():
    _dash_update_harvest("news", "running")
    try:
        from services.news_harvester import harvest_news
        res = await harvest_news()
        _dash_update_harvest("news", "idle", {"added": res})
    except Exception as e:
        _dash_update_harvest("news", "error", {"error": str(e)})


# ── Admin trigger endpoints ────────────────────────────────────────────────────

@router.post("/harvest-youtube")
async def admin_harvest_youtube(bg_tasks: BackgroundTasks, authorization: str = Header(None)):
    """Trigger both YouTube harvests on demand. Admin-only."""
    require_admin(authorization)
    with _dash_lock:
        if _harvest_status["youtube"]["status"] == "running":
            return {"status": "already running"}
    bg_tasks.add_task(_run_youtube_harvest_bg)
    return {"status": "started in background"}


@router.post("/harvest-advisors")
async def admin_harvest_advisors(bg_tasks: BackgroundTasks, authorization: str = Header(None)):
    """Trigger advisor harvest on demand. Admin-only."""
    require_admin(authorization)
    with _dash_lock:
        if _harvest_status["advisor"]["status"] == "running":
            return {"status": "already running"}
    bg_tasks.add_task(_run_advisor_harvest_bg)
    return {"status": "started in background"}


@router.post("/harvest-news")
async def admin_harvest_news(bg_tasks: BackgroundTasks, authorization: str = Header(None)):
    """Trigger news harvest on demand. Admin-only."""
    require_admin(authorization)
    with _dash_lock:
        if _harvest_status["news"]["status"] == "running":
            return {"status": "already running"}
    bg_tasks.add_task(_run_news_harvest_bg)
    return {"status": "started in background"}


# ── Scheduler ──────────────────────────────────────────────────────────────────

def start_scheduler():
    """Start APScheduler with all nightly cron jobs. Called from main.py startup."""
    global _scheduler
    _scheduler = AsyncIOScheduler(timezone="Asia/Kolkata")

    from services.advisor_harvester import harvest_all_advisors, evaluate_analysis_outcomes
    from services.news_harvester import harvest_news
    from services.youtube_harvester import harvest_youtube_metadata, harvest_portfolio_videos
    from services.portfolio_snapshot import snapshot_all_users
    from services.pkscreener_runner import run_nightly_screen
    from services.filings_extractor import harvest_filings
    from database import promote_initial_admins

    async def _run_harvest_all_advisors():
        _dash_update_harvest("advisor", "running")
        try:
            res = await harvest_all_advisors()
            _dash_update_harvest("advisor", "idle", {"result": res})
        except Exception as e:
            _dash_update_harvest("advisor", "error", {"error": str(e)})

    async def _run_harvest_news():
        _dash_update_harvest("news", "running")
        try:
            res = await harvest_news()
            _dash_update_harvest("news", "idle", {"added": res})
        except Exception as e:
            _dash_update_harvest("news", "error", {"error": str(e)})

    async def _run_harvest_youtube_metadata():
        _dash_update_harvest("youtube", "running")
        try:
            res = await harvest_youtube_metadata()
            _dash_update_harvest("youtube", "idle", {"metadata": res})
        except Exception as e:
            _dash_update_harvest("youtube", "error", {"error": str(e)})

    async def _run_harvest_portfolio_videos():
        _dash_update_harvest("youtube", "running")
        try:
            res = await harvest_portfolio_videos()
            _dash_update_harvest("youtube", "idle", {"portfolio": res})
        except Exception as e:
            _dash_update_harvest("youtube", "error", {"error": str(e)})

    async def _run_harvest_filings():
        _dash_update_harvest("filings", "running")
        try:
            res = harvest_filings()
            _dash_update_harvest("filings", "idle", {"result": res})
        except Exception as e:
            _dash_update_harvest("filings", "error", {"error": str(e)})

    def _run_evaluate_analysis_outcomes():
        with get_session() as db:
            evaluate_analysis_outcomes(db)

    _scheduler.add_job(_run_harvest_all_advisors, "cron", hour=1, minute=30)
    _scheduler.add_job(_run_harvest_news, "cron", hour=0, minute=30)           # 12:30 AM IST
    _scheduler.add_job(_run_harvest_youtube_metadata, "cron", hour=1, minute=0) # 1:00 AM IST — channel sweep
    _scheduler.add_job(_run_harvest_portfolio_videos, "cron", hour=1, minute=15) # 1:15 AM IST — ticker search
    _scheduler.add_job(snapshot_all_users, "cron", hour=11, minute=0)      # 4:30 PM IST (11:00 UTC)
    _scheduler.add_job(run_nightly_screen, "cron", hour=11, minute=15)     # 4:45 PM IST (11:15 UTC)
    _scheduler.add_job(_run_evaluate_analysis_outcomes, "cron", hour=2, minute=0)  # 2:00 AM IST
    _scheduler.add_job(_run_harvest_filings, "interval", minutes=15)            # corporate filings every 15 min
    _scheduler.start()
    promote_initial_admins()
    logging.info("All schedulers started (advisor 1:30, news 12:30, youtube-channel 1:00, youtube-portfolio 1:15, snapshot 4:30, pkscreener 4:45, outcome-eval 2:00 AM IST, filings 15min)")


def stop_scheduler():
    """Shutdown APScheduler. Called from main.py shutdown event."""
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
