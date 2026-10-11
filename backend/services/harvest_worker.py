"""Background harvest workers and scheduler.

Extracted from main.py during monolith refactor Phase 3.

Contains:
- Background harvest runners (YouTube, Advisor, News)
- APScheduler setup for nightly cron jobs
- Admin harvest trigger endpoints (FastAPI router)
"""

import asyncio
import functools
from datetime import datetime, timedelta, timezone
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


def _sync(coro_fn):
    """Wrap a coroutine function as a plain callable that runs it on a private loop.

    AsyncIOScheduler (and BackgroundTasks) run coroutine jobs ON the API event loop
    but send plain callables to a thread pool, so registering only sync callables
    keeps blocking yfinance/feedparser/yt-dlp/subprocess bodies off the loop (REL-03).
    """
    @functools.wraps(coro_fn)
    def run(*args, **kwargs):
        return asyncio.run(coro_fn(*args, **kwargs))
    return run


# ── Background runners ─────────────────────────────────────────────────────────

def _run_youtube_harvest_bg():
    _dash_update_harvest("youtube", "running")
    try:
        from services.youtube_harvester import harvest_youtube_metadata, harvest_portfolio_videos
        res1 = asyncio.run(harvest_youtube_metadata())
        res2 = asyncio.run(harvest_portfolio_videos())
        _dash_update_harvest("youtube", "idle", {"channels": res1, "portfolio": res2})
    except Exception as e:
        _dash_update_harvest("youtube", "error", {"error": str(e)})


def _run_advisor_harvest_bg():
    _dash_update_harvest("advisor", "running")
    try:
        from services.advisor_harvester import harvest_all_advisors
        res = asyncio.run(harvest_all_advisors())
        _dash_update_harvest("advisor", "idle", {"result": res})
    except Exception as e:
        _dash_update_harvest("advisor", "error", {"error": str(e)})


def _run_news_harvest_bg():
    _dash_update_harvest("news", "running")
    try:
        from services.news_harvester import harvest_news
        res = asyncio.run(harvest_news())
        _dash_update_harvest("news", "idle", {"added": res})
    except Exception as e:
        _dash_update_harvest("news", "error", {"error": str(e)})


# ── Admin trigger endpoints ────────────────────────────────────────────────────

@router.post("/harvest-youtube")
def admin_harvest_youtube(bg_tasks: BackgroundTasks, authorization: str = Header(None)):
    """Trigger both YouTube harvests on demand. Admin-only."""
    require_admin(authorization)
    with _dash_lock:
        if _harvest_status["youtube"]["status"] == "running":
            return {"status": "already running"}
    bg_tasks.add_task(_run_youtube_harvest_bg)
    return {"status": "started in background"}


@router.post("/harvest-advisors")
def admin_harvest_advisors(bg_tasks: BackgroundTasks, authorization: str = Header(None)):
    """Trigger advisor harvest on demand. Admin-only."""
    require_admin(authorization)
    with _dash_lock:
        if _harvest_status["advisor"]["status"] == "running":
            return {"status": "already running"}
    bg_tasks.add_task(_run_advisor_harvest_bg)
    return {"status": "started in background"}


@router.post("/harvest-news")
def admin_harvest_news(bg_tasks: BackgroundTasks, authorization: str = Header(None)):
    """Trigger news harvest on demand. Admin-only."""
    require_admin(authorization)
    with _dash_lock:
        if _harvest_status["news"]["status"] == "running":
            return {"status": "already running"}
    bg_tasks.add_task(_run_news_harvest_bg)
    return {"status": "started in background"}


# ── Scheduler ──────────────────────────────────────────────────────────────────

_scheduler_lock_file = None

def start_scheduler() -> bool:
    """Start APScheduler with all nightly cron jobs. Called from main.py startup.

    Returns True when this process holds the scheduler lock (it is the leader and
    runs the scheduler), False when another worker already does (ARCH-07), so
    main.py runs one-time startup tasks only on the leader.
    """
    global _scheduler, _scheduler_lock_file
    if _scheduler is not None and _scheduler.running:
        logging.getLogger(__name__).info("Scheduler already running, skipping re-init")
        return True

    try:
        import fcntl
        _scheduler_lock_file = open("/tmp/nivesh_scheduler.lock", "w")
        fcntl.lockf(_scheduler_lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except IOError:
        logging.getLogger(__name__).info("Another worker is running the scheduler. Skipping.")
        return False
        
    # misfire_grace_time: a job that comes due while the process is busy still runs
    # (APScheduler's default of 1 s silently skipped it).
    _scheduler = AsyncIOScheduler(timezone="UTC", job_defaults={
        "coalesce": True, "max_instances": 1, "misfire_grace_time": 3600,
    })

    from services.advisor_harvester import harvest_all_advisors, evaluate_analysis_outcomes
    from services.news_harvester import harvest_news
    from services.youtube_harvester import harvest_youtube_metadata, harvest_portfolio_videos
    from services.portfolio_snapshot import snapshot_all_users, pregen_morning_briefs_all_users
    from services.pkscreener_runner import run_nightly_screen
    from services.filings_extractor import harvest_filings
    from services.nse_data_provider import download_bhavcopy
    from services.piotroski import batch_refresh_piotroski
    from services.error_telemetry import generate_daily_digest

    # Every job below is a plain def: APScheduler runs those in a worker thread,
    # async harvesters get a private loop via asyncio.run (REL-03).
    def _run_harvest_all_advisors():
        _dash_update_harvest("advisor", "running")
        try:
            res = asyncio.run(harvest_all_advisors())
            _dash_update_harvest("advisor", "idle", {"result": res})
        except Exception as e:
            _dash_update_harvest("advisor", "error", {"error": str(e)})

    def _run_harvest_news():
        _dash_update_harvest("news", "running")
        try:
            res = asyncio.run(harvest_news())
            _dash_update_harvest("news", "idle", {"added": res})
        except Exception as e:
            _dash_update_harvest("news", "error", {"error": str(e)})

    def _run_harvest_youtube_metadata():
        _dash_update_harvest("youtube", "running")
        try:
            res = asyncio.run(harvest_youtube_metadata())
            _dash_update_harvest("youtube", "idle", {"metadata": res})
        except Exception as e:
            _dash_update_harvest("youtube", "error", {"error": str(e)})

    def _run_harvest_portfolio_videos():
        _dash_update_harvest("youtube", "running")
        try:
            res = asyncio.run(harvest_portfolio_videos())
            _dash_update_harvest("youtube", "idle", {"portfolio": res})
        except Exception as e:
            _dash_update_harvest("youtube", "error", {"error": str(e)})

    def _run_harvest_filings():
        _dash_update_harvest("filings", "running")
        try:
            res = harvest_filings()
            _dash_update_harvest("filings", "idle", {"result": res})
        except Exception as e:
            _dash_update_harvest("filings", "error", {"error": str(e)})

    def _run_evaluate_analysis_outcomes():
        with get_session() as db:
            evaluate_analysis_outcomes(db)

    # No cache-purge job: Redis TTLs and the in-process TTLCache fallback expire
    # entries on their own (ARCH-09).

    # ── NEW JOB 2: Bhavcopy download — 7:00 PM IST (13:30 UTC) ──────────────
    def _run_bhavcopy_download():
        _dash_update_harvest("bhavcopy", "running")
        try:
            result = download_bhavcopy()
            _dash_update_harvest("bhavcopy", "idle", result)
            logging.info(f"[bhavcopy] Downloaded {result.get('rows', 0)} EQ rows (source={result.get('source')})")
        except Exception as e:
            _dash_update_harvest("bhavcopy", "error", {"error": str(e)})
            logging.error(f"[bhavcopy] Download error: {e}")

    # ── NEW JOB 3: Morning brief pre-generation — 6:30 AM IST (1:00 UTC) ────
    def _run_pregen_morning_briefs():
        _dash_update_harvest("morning_brief", "running")
        try:
            result = asyncio.run(pregen_morning_briefs_all_users())
            _dash_update_harvest("morning_brief", "idle", result)
            logging.info(f"[morning_brief] Pre-gen done: {result}")
        except Exception as e:
            _dash_update_harvest("morning_brief", "error", {"error": str(e)})
            logging.error(f"[morning_brief] Pre-gen error: {e}")

    # ── NEW JOB 4: Piotroski weekly refresh — Sunday 11:00 PM IST (17:30 UTC)
    def _run_piotroski_batch():
        _dash_update_harvest("piotroski_batch", "running")
        try:
            result = batch_refresh_piotroski()
            _dash_update_harvest("piotroski_batch", "idle", result)
            logging.info(f"[piotroski_batch] Weekly refresh done: {result}")
        except Exception as e:
            _dash_update_harvest("piotroski_batch", "error", {"error": str(e)})
            logging.error(f"[piotroski_batch] Error: {e}")

    # ── NEW JOB 5: Pre-market cache warm — 9:00 AM IST (3:30 UTC) ───────────
    def _run_premarket_cache_warm():
        """Invalidate yesterday's stale analyses so users get fresh data at open."""
        _dash_update_harvest("premarket_warm", "running")
        try:
            from services.disk_cache import invalidate as cache_invalidate, CACHE_ROOT
            from datetime import date as _date
            import time as _time
            warmed = 0
            # Evict yfinance entries older than 8h to force fresh fetch at market open
            ns_path = CACHE_ROOT / "yfinance"
            if ns_path.exists():
                for path in ns_path.glob("*.json.gz"):
                    try:
                        age = _time.time() - path.stat().st_mtime
                        if age > 8 * 3600:
                            path.unlink(missing_ok=True)
                            warmed += 1
                    except Exception as _e:
                        pass
            _dash_update_harvest("premarket_warm", "idle", {"evicted_entries": warmed})
            logging.info(f"[premarket_warm] Evicted {warmed} stale yfinance cache entries")
        except Exception as e:
            _dash_update_harvest("premarket_warm", "error", {"error": str(e)})
            logging.error(f"[premarket_warm] Error: {e}")

    # ── NEW JOB 6: Error telemetry digest — 7:00 AM IST (1:30 UTC) ──────────
    def _run_error_digest():
        _dash_update_harvest("error_digest", "running")
        try:
            digest = generate_daily_digest()
            _dash_update_harvest("error_digest", "idle", {"lines": digest.count("\n")})
            logging.info("[error_digest] Daily digest written")
        except Exception as e:
            _dash_update_harvest("error_digest", "error", {"error": str(e)})
            logging.error(f"[error_digest] Error: {e}")

    # ── NEW JOB 7: Market Anomaly Scanner ────────────────────────────────────
    def _run_anomaly_scan():
        _dash_update_harvest("anomaly_scan", "running")
        try:
            from services.anomaly_scanner import run_anomaly_scan
            run_anomaly_scan()
            _dash_update_harvest("anomaly_scan", "idle", {})
            logging.info("[anomaly_scan] Hourly scan complete.")
        except Exception as e:
            _dash_update_harvest("anomaly_scan", "error", {"error": str(e)})
            logging.error(f"[anomaly_scan] Error: {e}")

    # ── DB backup — 2:30 AM IST (21:00 UTC); see docs/codebase/BACKUP_RESTORE.md ─
    def _run_db_backup():
        _dash_update_harvest("db_backup", "running")
        try:
            from services.backup_service import run_backup
            written = run_backup()
            _dash_update_harvest("db_backup", "idle", {k: str(v) for k, v in written.items()})
            logging.info(f"[db_backup] Complete: {sorted(written)}")
        except Exception as e:
            _dash_update_harvest("db_backup", "error", {"error": str(e)})
            logging.error(f"[db_backup] Error: {e}")

    # ── Wire all jobs ─────────────────────────────────────────────────────────

    # The six 2-hourly jobs are staggered 20 min apart (+ jitter) instead of all
    # firing at the same instant.
    _t0 = datetime.now(timezone.utc)

    def _stagger(minutes: int) -> dict:
        return {"next_run_time": _t0 + timedelta(minutes=minutes), "jitter": 300}

    _snapshot_all_users_job = _sync(snapshot_all_users)
    _run_nightly_screen_job = _sync(run_nightly_screen)

    _scheduler.add_job(_run_harvest_all_advisors,     "cron", hour=1,  minute=30)  # 1:30 AM IST
    _scheduler.add_job(_run_harvest_news,             "interval", hours=2, **_stagger(5))
    _scheduler.add_job(_run_harvest_youtube_metadata, "interval", hours=2, **_stagger(25))
    _scheduler.add_job(_run_harvest_portfolio_videos, "interval", hours=2, **_stagger(45))
    _scheduler.add_job(_snapshot_all_users_job,       "cron", hour=11, minute=0)   # 4:30 PM IST (11:00 UTC)
    _scheduler.add_job(_run_nightly_screen_job,       "cron", hour=11, minute=15)  # 4:45 PM IST (11:15 UTC)
    _scheduler.add_job(_run_evaluate_analysis_outcomes,"cron", hour=20, minute=30)  # 2:00 AM IST (20:30 UTC)

    # ── Notification TTL sweeper (daily, 3:00 AM IST) ───────────────────────
    def _run_notification_cleanup():
        from services.notifications_inbox import cleanup_old
        deleted = cleanup_old()
        logger.info(f"Notification cleanup: {deleted} old notifs deleted")

    _scheduler.add_job(_run_notification_cleanup, "cron", hour=21, minute=30)  # 3:00 AM IST

    # ── Backfill UserPreferences for existing users ─────────────────────────
    def _run_backfill_preferences():
        from database import get_session, User
        from models.db_models import UserPreference
        with get_session() as s:
            existing = s.query(UserPreference.user_id).distinct().all()
            existing_ids = {r[0] for r in existing}
            users = s.query(User.id).filter(~User.id.in_(existing_ids)).all() if existing_ids else s.query(User.id).all()
            for (uid,) in users:
                s.add(UserPreference(user_id=uid))
            s.commit()
            logger.info(f"Backfilled preferences for {len(users)} users")

    _scheduler.add_job(_run_backfill_preferences, "cron", hour=21, minute=35)  # 3:05 AM IST

    # ── Right-to-erasure: execute deletion requests past their grace period (DB-06) ──
    def _run_process_deletion_requests():
        from services.compliance_service import process_due_deletion_requests
        done = process_due_deletion_requests()
        logging.info(f"[erasure] {done} deletion request(s) completed")

    _scheduler.add_job(_run_process_deletion_requests, "cron", hour=22, minute=0,
                       id="process_deletion_requests", replace_existing=True)  # 3:30 AM IST

    # ── NEW jobs ──────────────────────────────────────────────────────────────
    _scheduler.add_job(_run_bhavcopy_download,    "cron", hour=13, minute=30)             # 7:00 PM IST
    _scheduler.add_job(_run_pregen_morning_briefs,"cron", hour=1,  minute=0)              # 6:30 AM IST
    _scheduler.add_job(_run_piotroski_batch,      "cron", day_of_week="sun", hour=17, minute=30)  # Sun 11 PM IST
    _scheduler.add_job(_run_premarket_cache_warm, "cron", hour=3,  minute=30)             # 9:00 AM IST
    _scheduler.add_job(_run_error_digest,         "cron", hour=1,  minute=30)             # 7:00 AM IST
    _scheduler.add_job(_run_anomaly_scan,         "cron", minute="0")
    _scheduler.add_job(_run_db_backup,            "cron", hour=21, minute=0, id="db_backup", replace_existing=True)  # 2:30 AM IST

    # ── Harvester jobs (ScraperAPI-backed, rate-limited for free tier) ─────────
    _scheduler.add_job(_run_expert_harvest_bg, "interval", minutes=120, id="expert_harvest", replace_existing=True, **_stagger(65))
    _scheduler.add_job(_run_sebi_harvest_bg,   "interval", minutes=120, id="sebi_harvest",   replace_existing=True, **_stagger(85))
    _scheduler.add_job(_run_youtube_expert_bg, "interval", minutes=120, id="youtube_expert_harvest", replace_existing=True, **_stagger(105))

    # ── RAG ingestion — incremental, leader-only (this scheduler holds the fcntl lock).
    # Replaces the old per-worker full re-embed at startup. First run 5 min after boot.
    def _run_rag_ingest():
        _dash_update_harvest("rag_ingest", "running")
        try:
            from services.vector_store import init_store
            if not init_store():
                _dash_update_harvest("rag_ingest", "idle", {"skipped": "vector store unavailable"})
                return
            from services.rag_ingestion import ingest_new
            n = ingest_new()  # sync job: already in a worker thread, off the event loop
            _dash_update_harvest("rag_ingest", "idle", {"chunks": n})
        except Exception as e:
            logging.exception("[rag_ingest] failed")
            _dash_update_harvest("rag_ingest", "error", {"error": str(e)})

    _scheduler.add_job(
        _run_rag_ingest, "cron", hour=21, minute=45, id="rag_ingest",  # 3:15 AM IST
        max_instances=1, coalesce=True, replace_existing=True,
        next_run_time=datetime.now(timezone.utc) + timedelta(minutes=5),
    )

    # Crash recovery for analysis/stress-test jobs whose worker died (pid-aware).
    from repositories.job_repo import sweep_stale_jobs
    _scheduler.add_job(sweep_stale_jobs, "interval", minutes=2, id="job_sweep",
                       max_instances=1, coalesce=True, replace_existing=True)

    _scheduler.start()
    logging.info(
        "All schedulers started — existing: (advisor 1:30, news 12:30, yt-channel 1:00, "
        "yt-portfolio 1:15, snapshot 4:30 PM, pkscreener 4:45 PM, outcome-eval 2:00 AM) | "
        "new: (bhavcopy 7:00 PM, morning-brief-pregen 6:30 AM, "
        "piotroski-weekly Sun 11 PM, premarket-warm 9:00 AM, error-digest 7:00 AM, db-backup 2:30 AM) | "
        "harvesters: (expert 120min, sebi 120min, yt-expert 120min) [all IST]"
    )
    return True


def _run_expert_harvest_bg():
    try:
        from services.harvester_expert import scrape_all_expert_sources
        from services.harvester_db import get_session as h_get_session, upsert_card
        cards = scrape_all_expert_sources()
        count = 0
        for card in cards:
            with h_get_session() as s:
                if upsert_card(s, card):
                    count += 1
        logging.info("Expert harvest: %d new cards", count)
    except Exception as e:
        logging.exception("Expert harvest failed: %s", e)


def _run_sebi_harvest_bg():
    try:
        from services.harvester_sebi import harvest_sebi_filings
        n = harvest_sebi_filings()
        logging.info("SEBI harvest: %d new cards", n)
    except Exception as e:
        logging.exception("SEBI harvest failed: %s", e)


def _run_youtube_expert_bg():
    try:
        from services.expert_youtube_harvester import harvest_youtube_transcripts
        n = harvest_youtube_transcripts()
        logging.info("YouTube expert harvest: %d new cards", n)
    except Exception as e:
        logging.exception("YouTube expert harvest failed: %s", e)


def _seed_harvester_sources():
    from services.harvester_db import get_session as h_get_session, record_source_health
    SOURCE_ROSTER = [
        "NSE Corporate Announcements", "CRISIL Ratings", "ICRA Ratings",
        "CARE Ratings", "India Ratings & Research", "CNBC-TV18 Expert View",
        "Moneycontrol Expert Columns", "SEBI RIA Registry",
        "AMFI Mutual Fund Data", "YouTube Finance Channels",
    ]
    try:
        with h_get_session() as s:
            for name in SOURCE_ROSTER:
                record_source_health(s, name, success=True, items=0)
    except Exception as _e:
        pass


def stop_scheduler():
    """Shutdown APScheduler. Called from main.py shutdown event."""
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None

async def check_signal_outcomes():
    import yfinance as yf
    from datetime import datetime, timedelta
    import json
    import gzip
    from database import AnalysisHistory, get_session
    import logging

    try:
        with get_session() as db:
            cutoff = datetime.now(timezone.utc) - timedelta(days=30)
            pending = (
                db.query(AnalysisHistory)
                .filter(AnalysisHistory.was_correct == None)
                .filter(AnalysisHistory.created_at < cutoff)
                .limit(50)
                .all()
            )
            for row in pending:
                try:
                    info = yf.Ticker(row.ticker).info
                    current_price = info.get('currentPrice') or info.get('regularMarketPrice')
                    if not current_price:
                        continue
                    
                    raw = row.full_json
                    if isinstance(raw, (bytes, bytearray, memoryview)):
                        report = json.loads(gzip.decompress(bytes(raw)))
                    else:
                        report = json.loads(raw)
                    
                    price_at_signal_date = report.get("current_price") or report.get("price")
                    if not price_at_signal_date:
                        continue
                    
                    outcome_delta_pct = (current_price - price_at_signal_date) / price_at_signal_date * 100
                    row.outcome_delta_pct = outcome_delta_pct
                    row.outcome_checked_at = datetime.now(timezone.utc)
                    
                    signal = row.signal.upper() if row.signal else "HOLD"
                    if signal == "BUY" and outcome_delta_pct > 0:
                        row.was_correct = True
                    elif signal == "SELL" and outcome_delta_pct < 0:
                        row.was_correct = True
                    elif signal == "HOLD" and abs(outcome_delta_pct) < 5:
                        row.was_correct = True
                    else:
                        row.was_correct = False
                        
                except Exception as e:
                    logging.error(f"Error checking outcome for {row.ticker}: {e}")
                    
            db.commit()
    except Exception as e:
        logging.error(f"Error in check_signal_outcomes: {e}")
