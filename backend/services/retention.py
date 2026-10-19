"""Nightly retention for append-only tables and the token log (PERF-15).

Each step runs in its own session and failure is logged, so one bad step does
not block the others. Market anomaly retention lives with PERF-19.
"""
import logging
import os
from datetime import datetime, timedelta, timezone

from core import dashboard_state
from database import get_session
from models.db_models import AnalysisJob, NewsArticle, PriceTarget
from services import job_runs

logger = logging.getLogger(__name__)

NEWS_DAYS = 90
JOB_PAYLOAD_DAYS = 30
TRIGGERED_ALERT_DAYS = 90
JOB_RUNS_DAYS = 90
TOKEN_LOG_MAX_BYTES = 20 * 1024 * 1024
_TERMINAL = ("SUCCEEDED", "FAILED", "CANCELLED", "TIMEOUT")


def _rotate_token_log() -> int:
    """Move token_log.jsonl to .1 once it passes TOKEN_LOG_MAX_BYTES (one generation kept)."""
    path = dashboard_state.TOKEN_LOG_PATH
    with dashboard_state._token_log_lock:
        if os.path.exists(path) and os.path.getsize(path) > TOKEN_LOG_MAX_BYTES:
            os.replace(path, path + ".1")
            return 1
    return 0


def run_retention() -> dict:
    now = datetime.now(timezone.utc)
    counts: dict = {}

    try:
        with get_session() as s:
            counts["news_deleted"] = (
                s.query(NewsArticle)
                .filter(NewsArticle.published_at < now - timedelta(days=NEWS_DAYS))
                .delete(synchronize_session=False)
            )
            s.commit()
    except Exception:
        logger.exception("[retention] news prune failed")

    try:
        with get_session() as s:
            # Keep the job row (history, status); drop the large payloads.
            counts["job_payloads_cleared"] = (
                s.query(AnalysisJob)
                .filter(
                    AnalysisJob.status.in_(_TERMINAL),
                    AnalysisJob.finished_at < now - timedelta(days=JOB_PAYLOAD_DAYS),
                    AnalysisJob.result_json.isnot(None),
                )
                .update({"result_json": None, "checkpoints": "[]"}, synchronize_session=False)
            )
            s.commit()
    except Exception:
        logger.exception("[retention] job payload prune failed")

    try:
        with get_session() as s:
            counts["alerts_deleted"] = (
                s.query(PriceTarget)
                .filter(
                    PriceTarget.triggered.is_(True),
                    PriceTarget.created_at < now - timedelta(days=TRIGGERED_ALERT_DAYS),
                )
                .delete(synchronize_session=False)
            )
            s.commit()
    except Exception:
        logger.exception("[retention] triggered alert prune failed")

    try:
        counts["job_runs_deleted"] = job_runs.purge_older_than(JOB_RUNS_DAYS)
    except Exception:
        logger.exception("[retention] job_runs prune failed")

    try:
        counts["token_log_rotated"] = _rotate_token_log()
    except Exception:
        logger.exception("[retention] token log rotation failed")

    return counts
