"""App startup/shutdown, called by main._lifespan (moved out of main.py, REL-15)."""
import asyncio
import logging
import os
import threading

from database import init_db
from services.harvest_worker import start_scheduler, stop_scheduler

# Handle of the leader's price-alert poller task, cancelled on shutdown.
_price_alert_task = None


def _seed_catalogs():
    """Seed catalogs at startup, never from GET handlers (FAKE-06 / GH-696).

    Forum boards are structural categories and always seeded. The mutual-fund,
    IPO, loan-offer and FD-scheme catalogs hold illustrative figures, so they
    are seeded only when DEMO_MODE is set (dev/demo servers).
    """
    from config.settings import DEMO_MODE
    from services import fixed_deposit_service, forum_service, ipo_service
    from services import loan_marketplace_service, mutual_fund_service
    seeders = [forum_service.seed_mock_boards_if_empty]
    if DEMO_MODE:
        seeders += [
            mutual_fund_service.seed_mock_funds_if_empty,
            ipo_service.seed_mock_ipos_if_empty,
            loan_marketplace_service.seed_mock_loan_offers_if_empty,
            fixed_deposit_service.seed_mock_fd_schemes_if_empty,
        ]
    for seed in seeders:
        try:
            seed()
        except Exception as e:
            logging.warning("[startup] %s failed: %s", seed.__name__, e)


def _backfill_preferences():
    """Backfill UserPreferences for existing users without one."""
    try:
        from database import get_session, User
        from models.db_models import UserPreference
        with get_session() as s:
            existing = s.query(UserPreference.user_id).distinct().all()
            existing_ids = {r[0] for r in existing}
            users = s.query(User.id).filter(~User.id.in_(existing_ids)).all() if existing_ids else s.query(User.id).all()
            for (uid,) in users:
                s.add(UserPreference(user_id=uid))
            s.commit()
            if users:
                logging.info(f"Backfilled preferences for {len(users)} users")
    except Exception as e:
        logging.warning(f"Preference backfill skipped: {e}")


async def on_startup():
    """
    Execute application startup routines.

    Initializes structured logging in every worker. Only the leader (the worker
    holding the scheduler lock) runs the one-time tasks: database tables, the
    stale-job sweep, harvester/catalog seeding, the price-alert poller and the
    preference backfill (DB-13, ARCH-07). Even with `--workers N` there is one
    alert poller (no duplicate pushes), one job sweep and one backfill.
    """
    global _price_alert_task
    # Wire up structured JSON logging (fixes #83)
    from core.logging_config import configure_logging
    configure_logging()
    # Tests are always leader: the fcntl lock is machine-wide, and another local
    # process (dev server, a parallel pytest run) holding it must not skip seeding.
    is_leader = start_scheduler() or os.environ.get("NIVESH_TESTING") == "1"
    if not is_leader:
        logging.info("[startup] follower worker: skipping one-time tasks")
        return
    # Init DB on startup (fixes #87 — moved from module level)
    init_db()
    # v2 engine crash recovery: any analysis job left RUNNING/QUEUED by a previous
    # process (deploy/crash) has a dead worker → mark it FAILED so the app shows an
    # honest error and the user can re-run.
    try:
        import database
        swept = database.sweep_stale_jobs(90)
        if swept:
            logging.info("[startup] swept %d stale analysis jobs -> FAILED", swept)
    except Exception as e:
        logging.warning("[startup] analysis job sweep failed: %s", e)
    try:
        from services.harvester_db import init_harvester_db
        from services.harvest_worker import _seed_harvester_sources
        init_harvester_db()
        _seed_harvester_sources()
    except Exception as e:
        logging.warning("Harvester DB init failed: %s", e)
    _seed_catalogs()
    from services.alerts_service import price_alert_poller
    _price_alert_task = asyncio.create_task(price_alert_poller())

    # FinBERT loading is deferred to first request (lazy). Pre-warming at startup
    # causes memory spikes during model load, cascading worker death with uvicorn
    # --workers > 1. The 3-5s cost on first sentiment request is acceptable.

    threading.Thread(target=_backfill_preferences, daemon=True).start()

    # RAG ingestion is incremental and runs only in the leader scheduler
    # (harvest_worker job 'rag_ingest'), never per worker at startup.

    # ENABLE_SCHEDULER block removed (fixes #85): start_scheduler() from
    # harvest_worker (called above) already registers all cron jobs including
    # harvest_youtube_metadata, harvest_news, and snapshot_all_users.
    # The duplicate AsyncIOScheduler was causing double job execution.


async def on_shutdown():
    # Each step runs even if an earlier one fails, so worker processes are always reaped.
    if _price_alert_task is not None:
        _price_alert_task.cancel()
    try:
        stop_scheduler()
    except Exception:
        logging.exception("[shutdown] stop_scheduler failed")
    try:
        from services.job_manager import shutdown_all
        shutdown_all()
    except Exception:
        logging.exception("[shutdown] shutdown_all failed")
