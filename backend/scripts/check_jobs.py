"""Check analysis job status. Usage: python3 check_jobs.py [running|--all|--stuck|TICKER]"""

from __future__ import annotations
import logging

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.ai_engine_monitor import build_ai_engine_monitor


def _print_jobs(mode: str) -> int:
    monitor = build_ai_engine_monitor(mode=mode)
    jobs = monitor["jobs"]
    if not jobs:
        logging.info("No jobs found.")
        return 0

    logging.info(
        f"{'TICKER':<12} {'STATUS':<12} {'STAGE':<18} {'PROG':>4}  "
        f"{'AGE':>7}  {'TOOK':>9}  {'SCAN':<8}  {'JOB ID'}"
    )
    logging.info("-" * 108)
    for job in jobs:
        name = str(job.get("ticker") or "").ljust(12)
        status = str(job.get("status") or "").ljust(12)
        stage = str(job.get("stage") or "-").ljust(18)
        pct = f"{int(job.get('progress_pct') or 0)}%".rjust(4)
        age = str(job.get("age_label") or "-").rjust(7)
        took = str(job.get("took_label") or job.get("elapsed_label") or "-").rjust(9)
        scan = str(job.get("scan_type") or "standard").ljust(8)
        logging.info(f"{name} {status} {stage} {pct}  {age}  {took}  {scan}  {job.get('job_id')}")
        error = job.get("error")
        if error:
            logging.info(f"  Error: {str(error)[:200]}")
    return 0


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "running"
    raise SystemExit(_print_jobs(mode))
