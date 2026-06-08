import os
import logging
from services.harvest_worker import harvest_youtube_metadata, harvest_news
from services.portfolio_snapshot import snapshot_all_users

def setup_apscheduler():
    if os.getenv("ENABLE_SCHEDULER", "false").lower() == "true":
        try:
            from apscheduler.schedulers.asyncio import AsyncIOScheduler
            scheduler = AsyncIOScheduler()
            scheduler.add_job(harvest_youtube_metadata, "cron", hour=0, minute=30)
            scheduler.add_job(harvest_news, "cron", hour=1, minute=30)
            scheduler.add_job(snapshot_all_users, "cron", hour=16, minute=30)
            scheduler.start()
            logging.info("APScheduler started with core harvest jobs.")
        except ImportError:
            # needs pip install apscheduler
            logging.warning("apscheduler not installed, please run: pip install apscheduler. Skipping scheduler startup.")
