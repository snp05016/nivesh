"""
Nivesh Advisor Intelligence — Nightly Harvest Launcher
Run manually: python run_advisor_harvest.py
Scheduled:    crontab -e → add:
              0 20 * * * /path/to/python /Users/saumya/Desktop/nivesh/backend/run_advisor_harvest.py
              (8 PM UTC = 1:30 AM IST)
"""
import asyncio
import logging
from pathlib import Path

# Ensure logs dir exists
_LOGS_DIR = Path(__file__).parent / "logs"
_LOGS_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    filename=str(_LOGS_DIR / "advisor_harvest.log"),
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

if __name__ == "__main__":
    from services.advisor_harvester import harvest_all_advisors
    asyncio.run(harvest_all_advisors())
