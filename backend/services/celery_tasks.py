"""
Celery task definitions for background analysis.
To activate: pip install celery redis
Run worker: celery -A services.celery_tasks worker --loglevel=info
"""
import os

try:
    from celery import Celery
    CELERY_AVAILABLE = True

    celery_app = Celery(
        "nivesh",
        broker=os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0"),
        backend=os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1"),
    )

    celery_app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="Asia/Kolkata",
        enable_utc=True,
        task_track_started=True,
        task_soft_time_limit=600,
        task_time_limit=660,
    )

    @celery_app.task(bind=True, max_retries=3)
    def run_analysis_task(self, ticker: str, scan_type: str, user_id: int):
        """Celery task wrapper for stock analysis."""
        try:
            from services.orchestrator import analyze
            return analyze(ticker=ticker, scan_type=scan_type, user_id=user_id)
        except Exception as exc:
            raise self.retry(exc=exc, countdown=2 ** self.request.retries)

except ImportError:
    CELERY_AVAILABLE = False
    celery_app = None

    def run_analysis_task(*args, **kwargs):
        raise RuntimeError("Celery not installed. Run: pip install celery redis")
