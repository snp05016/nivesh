"""Scheduled data-foundation jobs (Asia/Kolkata): EOD mirror, AMFI NAVs, equity master, results digest.

Registered from harvest_worker.start_scheduler. Each job runs its target with no arguments, logs
the returned dict and never raises, so one failing feed cannot disturb the others. The jobs
check their own flags (data_eod_prices, data_mf_universe, data_instruments, data_results_digest)
and return {'skipped': ...} while off. MATH-07's corporate-actions job keeps its own schedule.
"""
import importlib
import logging

logger = logging.getLogger(__name__)

IST_ZONE = "Asia/Kolkata"

# (job id, 'module:function', cron fields in IST)
JOBS: tuple[tuple[str, str, dict], ...] = (
    ("data_eod_mirror_evening", "services.eod_prices:mirror_recent",
     {"day_of_week": "mon-fri", "hour": 21, "minute": 40}),
    ("data_eod_mirror_morning", "services.eod_prices:mirror_recent",
     {"day_of_week": "tue-sat", "hour": 7, "minute": 40}),
    ("data_amfi_nav_night", "services.amfi:harvest", {"hour": 23, "minute": 30}),
    ("data_amfi_nav_morning", "services.amfi:harvest", {"hour": 8, "minute": 10}),
    ("data_equity_master", "services.instruments:refresh_equity_master",
     {"day_of_week": "sat", "hour": 8, "minute": 30}),
    ("data_results_feed", "services.results_digest:poll_feed_job", {"hour": "8-23", "minute": "5,35"}),
    ("data_results_numbers", "services.results_digest:fill_pending_numbers", {"hour": 22, "minute": 15}),
)


def run_job(job_id: str, target: str) -> None:
    """Import `module:function` lazily, call it, log the result. Errors are logged and recorded, never raised."""
    try:
        module_name, func_name = target.split(":", 1)
        result = getattr(importlib.import_module(module_name), func_name)()
        logger.info("[data-feeds] %s: %s", job_id, result)
    except Exception as exc:
        logger.exception("[data-feeds] %s failed", job_id)
        try:
            from services import error_telemetry

            error_telemetry.log_diagnostic_error(
                subsystem="DATA_FEEDS", classification=job_id, context={"error": type(exc).__name__},
            )
        except Exception:
            logger.exception("[data-feeds] could not record the failure of %s", job_id)


def register_data_jobs(scheduler) -> list[str]:
    """Add the seven IST cron jobs; returns their ids."""
    ids: list[str] = []
    for job_id, target, cron in JOBS:
        scheduler.add_job(
            run_job, "cron", args=[job_id, target], id=job_id, timezone=IST_ZONE, max_instances=1,
            coalesce=True, misfire_grace_time=3600, replace_existing=True, **cron,
        )
        ids.append(job_id)
    return ids
