"""The ``research`` block of ``/healthz`` (spec 2.7, REL-12).

Effective mode, ledger heartbeat and ``degraded_reasons``:

- ``config_invalid:*`` from ``config.CONFIG.degraded_reasons``;
- ``no_run_for_last_weekday`` when research is enabled and, from 07:30 IST,
  the previous weekday has no nightly row that is ok, degraded, running or
  ``skipped_holiday`` (the last kick for a market date is 07:15 IST next day);
- ml-engine ``/ready`` reasons (2 s timeout), fetched only when a key is set.

The block is informational: callers must never let it change the overall
``/healthz`` status.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Optional

from database import get_session
from repositories import research_repo as repo

from . import config
from .client import MLEngineClient
from .jobs import _DONE_FOR_DATE, IST, _previous_weekday

NO_RUN_DEADLINE = time(7, 30)  # IST


def expected_market_date(now: datetime) -> date:
    """Latest weekday whose nightly run must exist by ``now``."""
    local = (now.replace(tzinfo=timezone.utc) if now.tzinfo is None else now).astimezone(IST)
    day = local.date() if local.time() >= NO_RUN_DEADLINE else local.date() - timedelta(days=1)
    return _previous_weekday(day)


def research_health(now: Optional[datetime] = None, client: Optional[MLEngineClient] = None) -> dict[str, Any]:
    """Build the block. Raises only on unexpected errors (the router guards it)."""
    now = now or datetime.now(timezone.utc)
    cfg = config.CONFIG
    reasons = list(cfg.degraded_reasons)
    with get_session() as session:
        ledger = repo.health_summary(session, now)
        if cfg.enabled:
            run = repo.get_run_by_market_date(session, expected_market_date(now))
            if run is None or run.status not in _DONE_FOR_DATE:
                reasons.append("no_run_for_last_weekday")
    if cfg.ml_engine_api_key:
        ready = (client or MLEngineClient()).ready()
        if not ready["ready"]:
            reasons.extend(str(r) for r in ready["reasons"] or ["ml_engine_not_ready"])
    return {"mode": cfg.mode, **ledger, "degraded": bool(reasons), "degraded_reasons": reasons}
