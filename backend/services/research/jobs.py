"""Research Engine scheduler jobs (spec 2.2, 7.6, 8.2-8.5).

Plain ``def`` jobs (APScheduler runs them in its thread pool), registered by
``register_research_jobs`` only when the effective mode is not ``off``. Each
job takes optional ``now`` and ``client`` arguments for tests; the scheduler
calls them with none. Every stage reports to the admin dashboard under
``research_nightly`` and every failed or degraded stage goes to
``error_telemetry.log_diagnostic_error(subsystem="RESEARCH_ENGINE", ...)``,
which feeds the daily digest (SILENT-20).

Only symbols are sent to ml-engine (FINSEC-04); prose is generated only
between 19:30 and 00:25 IST within the daily LLM budget (D19, D26).
"""

from __future__ import annotations

import logging
from time import monotonic as _monotonic
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from core.dashboard_state import _dash_update_harvest
from database import get_session
from models.db_models import (  # pyright: ignore[reportMissingImports]  (checker resolves `models` to ml-engine/models)
    ResearchPrediction,
    ResearchReportRow,
    ResearchRun,
)
from repositories import research_repo as repo
from services import error_telemetry

from . import config
from .client import MLEngineClient, MLEngineError

logger = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))
DASH_KEY = "research_nightly"
SUBSYSTEM = "RESEARCH_ENGINE"

STALE_AFTER = timedelta(hours=3)
OUTCOME_BATCH = 2000
PROSE_WINDOW_START = time(19, 30)   # IST
PROSE_WINDOW_END = time(0, 25)      # IST, next day
BREAKER_MIN_GENERATIONS = 20
BREAKER_MIN_FIRST_PASS = 0.70
TEMPLATE_RATE_ALERT = 0.20

_DONE_FOR_DATE = frozenset({"ok", "degraded", "running", "skipped_holiday"})
_JOB_DEFAULTS: dict[str, Any] = {
    "max_instances": 1, "coalesce": True, "misfire_grace_time": 3600, "replace_existing": True, "timezone": "UTC",
}

_breaker_alerted_night: Optional[date] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _utc(now: Optional[datetime]) -> datetime:
    now = now or _now()
    return now.replace(tzinfo=timezone.utc) if now.tzinfo is None else now


def _previous_weekday(d: date) -> date:
    d -= timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def target_market_date(now: datetime) -> date:
    """Market date a kick handles: today (IST) for the evening kicks, the
    previous weekday for the 07:15 IST morning kick (and on weekends)."""
    local = _utc(now).astimezone(IST)
    d = local.date()
    if local.time() < time(12, 0) or d.weekday() >= 5:
        return _previous_weekday(d)
    return d


def in_prose_window(now: datetime) -> bool:
    t = _utc(now).astimezone(IST).time()
    return t >= PROSE_WINDOW_START or t < PROSE_WINDOW_END


def _night_start(now: datetime) -> datetime:
    """19:30 IST of the night ``now`` belongs to (as UTC)."""
    local = _utc(now).astimezone(IST)
    day = local.date() if local.time() >= PROSE_WINDOW_START else local.date() - timedelta(days=1)
    return datetime.combine(day, PROSE_WINDOW_START, tzinfo=IST).astimezone(timezone.utc)


def _ist_midnight(now: datetime) -> datetime:
    local = _utc(now).astimezone(IST)
    return datetime.combine(local.date(), time(0, 0), tzinfo=IST).astimezone(timezone.utc)


def _report_failure(stage: str, context: dict[str, Any], exc: Optional[BaseException] = None) -> None:
    """Telemetry for a failed or degraded stage; never raises."""
    try:
        error_telemetry.log_diagnostic_error(
            subsystem=SUBSYSTEM,
            classification=stage,
            context=context,
            exception={"type": type(exc).__name__, "message": str(exc)[:500]} if exc is not None else None,
        )
    except Exception:  # telemetry must never break a job
        logger.exception("research telemetry failed for %s", stage)


def _dash(status: str, result: Optional[dict[str, Any]] = None) -> None:
    try:
        _dash_update_harvest(DASH_KEY, status, result)
    except Exception:
        logger.exception("research dashboard update failed")


def _client(client: Optional[MLEngineClient]) -> MLEngineClient:
    return client if client is not None else MLEngineClient()


def _claim_run_uid(session: Session, run_id: int, run_uid: str) -> None:
    """Store an ml-engine run_id on ``run_id``. ml-engine hands back the same
    run_id for a run that already finished (or a 409 for the active one), and
    an older failed row may still hold it; run_uid is UNIQUE, so it moves."""
    for other in session.query(ResearchRun).filter(ResearchRun.run_uid == run_uid, ResearchRun.id != run_id).all():
        repo.update_run(session, other.id, run_uid=None)
    repo.update_run(session, run_id, run_uid=run_uid)


def _last_success_market_date(session: Session) -> Optional[date]:
    return (
        session.query(func.max(ResearchRun.market_date))
        .filter(ResearchRun.kind == "nightly", ResearchRun.status.in_(("ok", "degraded")))
        .scalar()
    )


# ---------------------------------------------------------------------------
# Kick
# ---------------------------------------------------------------------------

def _sweep_stale(session: Session, client: MLEngineClient, now: datetime) -> int:
    """Mark failed (stale_run) nightly rows running for more than 3 h, or
    whose ml-engine run is gone (404) or failed, and report them (SILENT-20)."""
    swept: list[dict[str, Any]] = []

    def _fail(row: ResearchRun, cause: str) -> None:
        repo.mark_run_failed(session, row.id, "stale_run")
        swept.append({"run_id": row.id, "market_date": str(row.market_date), "cause": cause})

    for row in repo.stale_running_runs(session, now - STALE_AFTER):
        _fail(row, "older_than_3h")
    running = (
        session.query(ResearchRun)
        .filter(ResearchRun.kind == "nightly", ResearchRun.status == "running", ResearchRun.run_uid.isnot(None))
        .all()
    )
    for row in running:
        try:
            status = client.run_status(str(row.run_uid))
        except MLEngineError:
            continue  # engine down: the 3 h rule catches it later
        if status is None:
            _fail(row, "engine_404")
        elif status.get("status") == "failed":
            _fail(row, "engine_failed")
    if swept:
        _report_failure("stale_sweep", {"stage": "kick", "swept": swept})
    return len(swept)


def research_nightly_kick(now: Optional[datetime] = None, client: Optional[MLEngineClient] = None) -> dict[str, Any]:
    """Start the nightly ml-engine run for the target market date (spec 2.2)."""
    if not config.CONFIG.enabled:
        return {"skipped": "research_off"}
    now = _utc(now)
    engine = _client(client)
    market_date = target_market_date(now)
    _dash("running")
    result: dict[str, Any] = {"stage": "kick", "market_date": market_date.isoformat()}
    run_id: Optional[int] = None
    try:
        with get_session() as session:
            result["swept"] = _sweep_stale(session, engine, now)
            existing = repo.get_run_by_market_date(session, market_date)
            if existing is not None and existing.status in _DONE_FOR_DATE:
                result["outcome"] = f"already_{existing.status}"
                _dash("idle", result)
                return result

            run_id = repo.create_run(session, kind="nightly", market_date=market_date, stage="kick").id
            extra = repo.extra_symbols(session)  # symbols only (FINSEC-04)
            resp = engine.start_run(market_date, extra)
            body = resp.body
            engine_run_id = str(body.get("run_id") or "")
            if resp.status_code == 409:
                if str(body.get("market_date")) == market_date.isoformat() and engine_run_id:
                    _claim_run_uid(session, run_id, engine_run_id)
                    repo.update_run(session, run_id, stage="engine_running")
                    result["outcome"] = "attached_active_run"
                else:
                    repo.mark_run_failed(session, run_id, "engine_busy")
                    result["outcome"] = "engine_busy"
                    _report_failure("kick", {**result, "active_market_date": body.get("market_date")})
            elif body.get("status") == "skipped_holiday":
                if engine_run_id:
                    _claim_run_uid(session, run_id, engine_run_id)
                repo.update_run(session, run_id, status="skipped_holiday", stage="kick")
                result["outcome"] = "skipped_holiday"
            elif engine_run_id:
                _claim_run_uid(session, run_id, engine_run_id)
                repo.update_run(session, run_id, stage="engine_running")
                result["outcome"] = "started"
            else:
                repo.mark_run_failed(session, run_id, "engine_bad_response")
                result["outcome"] = "engine_bad_response"
                _report_failure("kick", result)
            result["extra_symbols"] = len(extra)
    except Exception as exc:
        logger.exception("research kick failed for %s", market_date)
        if run_id is not None:
            try:
                with get_session() as session:
                    repo.mark_run_failed(session, run_id, "engine_unavailable" if isinstance(exc, MLEngineError) else "kick_failed")
            except Exception:
                logger.exception("research kick could not mark run %s failed", run_id)
        result["error"] = type(exc).__name__
        _report_failure("kick", result, exc)
        _dash("error", result)
        return result
    _dash("error" if result.get("outcome") in ("engine_busy", "engine_bad_response") else "idle", result)
    return result


# ---------------------------------------------------------------------------
# Poll and ingest
# ---------------------------------------------------------------------------

def _poll_one(session: Session, engine: MLEngineClient, row: ResearchRun) -> str:
    run_id, run_uid = row.id, str(row.run_uid)
    context = {"run_id": run_id, "market_date": row.market_date.isoformat() if row.market_date else None}
    status = engine.run_status(run_uid)
    if status is None:
        repo.mark_run_failed(session, run_id, "run_not_found")
        _report_failure("poll", {**context, "error": "run_not_found"})
        return "failed"
    state = status.get("status")
    if state == "running":
        if status.get("stage"):
            repo.update_run(session, run_id, stage=str(status["stage"])[:40])
        return "running"
    if state == "skipped_holiday":
        repo.update_run(session, run_id, status="skipped_holiday", stage="engine")
        return "skipped_holiday"
    if state not in ("ok", "degraded"):
        repo.mark_run_failed(session, run_id, str(status.get("error") or "engine_failed")[:200])
        _report_failure("engine_run", {**context, "error": status.get("error")})
        return "failed"

    items = engine.run_items(run_uid)
    try:
        counts = repo.ingest_run_items(session, run_id, items)  # one transaction, rolled back on error
    except Exception as exc:
        logger.exception("research ingest failed for run %s", run_id)
        repo.mark_run_failed(session, run_id, "ingest_failed")
        _report_failure("ingest", {**context, "items": len(items)}, exc)
        return "failed"
    engine_counts = status.get("counts") or {}
    repo.update_run(
        session, run_id, status=state, stage="ingested",
        counts_json={**engine_counts, **counts, "items": len(items)},
    )
    if state == "degraded":
        _report_failure("engine_run_degraded", {**context, "counts": engine_counts})
    return state


def _night_prose_stats(session: Session, since: datetime) -> tuple[int, int]:
    """(LLM generations, first-pass validations) stored since ``since``."""
    rows = (
        session.query(ResearchReportRow.narrative_status, ResearchReportRow.narrative_attempts)
        .filter(
            ResearchReportRow.narrative_generated_at >= since.replace(tzinfo=None),
            ResearchReportRow.narrative_attempts > 0,
        )
        .all()
    )
    return len(rows), sum(1 for status, attempts in rows if status == "llm_validated" and attempts == 1)


def generate_prose(session: Session, now: datetime) -> dict[str, Any]:
    """Prose for the latest ingested reports without one, universe first,
    within the window, the daily budget and the circuit breaker (spec 7.6).
    Shadow mode covers universe reports only."""
    global _breaker_alerted_night
    cfg = config.CONFIG
    if not (cfg.enabled and cfg.llm_prose and in_prose_window(now)):
        return {"prose": "skipped"}
    latest = (
        session.query(ResearchRun)
        .filter(ResearchRun.kind == "nightly", ResearchRun.status.in_(("ok", "degraded")))
        .order_by(ResearchRun.market_date.desc(), ResearchRun.id.desc())
        .first()
    )
    if latest is None:
        return {"prose": "no_reports"}

    from . import formatter  # lazy: loads the LLM client only when prose runs

    remaining = cfg.llm_max_calls_per_day - repo.llm_calls_since(session, _ist_midnight(now))
    night_start = _night_start(now)
    generations, first_pass = _night_prose_stats(session, night_start)
    # The loop must not run past 00:25 IST, whatever time the poll started.
    local = now.astimezone(IST)
    window_end = datetime.combine(
        local.date() + timedelta(days=1 if local.time() >= PROSE_WINDOW_START else 0), PROSE_WINDOW_END, tzinfo=IST,
    )
    deadline = _monotonic() + (window_end - local).total_seconds()
    stats: dict[str, Any] = {"prose_written": 0, "llm_calls": 0}
    for row in repo.reports_needing_prose(session, run_id=latest.id, universe_only=cfg.mode == "shadow"):
        if _monotonic() >= deadline:
            stats["prose"] = "window_closed"
            break
        if remaining <= 0:
            stats["prose"] = "budget_exhausted"
            break
        if generations >= BREAKER_MIN_GENERATIONS and first_pass / generations < BREAKER_MIN_FIRST_PASS:
            stats["prose"] = "breaker_open"
            night = night_start.astimezone(IST).date()
            if _breaker_alerted_night != night:
                _breaker_alerted_night = night
                _report_failure("prose_breaker", {"generations": generations, "first_pass": first_pass})
            break
        try:
            symbols, names = repo.known_symbols_and_names(session, exclude_symbol=row.symbol)
            narrative, attempts, failures = formatter.generate_narrative(
                row.report_json, known_symbols=symbols, company_names=names,
                allow_llm=True, calls_remaining=remaining,
            )
        except Exception as exc:
            logger.exception("research prose failed for report %s", row.id)
            _report_failure("prose", {"report_id": row.id, "symbol": row.symbol}, exc)
            continue
        if attempts <= 0:
            break  # no call was made (budget): nothing worth storing
        remaining -= attempts
        stats["llm_calls"] += attempts
        generations += 1
        first_pass += int(narrative.get("status") == "llm_validated" and attempts == 1)
        # Template narratives after failed attempts are stored too: they carry
        # the attempts (budget) and failure codes (template rate).
        if repo.set_narrative_once(
            session, row.id, narrative=narrative, status=str(narrative["status"]), attempts=attempts,
            failures=failures or None, facts_hash=narrative.get("facts_hash"),
        ):
            stats["prose_written"] += 1
    stats.setdefault("prose", "done")
    return stats


def research_poll_ingest(now: Optional[datetime] = None, client: Optional[MLEngineClient] = None) -> dict[str, Any]:
    """Poll running nightly runs, ingest finished ones, then write prose."""
    if not config.CONFIG.enabled:
        return {"skipped": "research_off"}
    now = _utc(now)
    engine = _client(client)
    result: dict[str, Any] = {"stage": "poll", "runs": {}}
    try:
        with get_session() as session:
            running = (
                session.query(ResearchRun)
                .filter(ResearchRun.kind == "nightly", ResearchRun.status == "running", ResearchRun.run_uid.isnot(None))
                .order_by(ResearchRun.id)
                .all()
            )
            for row in running:
                row_id = row.id
                try:
                    result["runs"][str(row_id)] = _poll_one(session, engine, row)
                except MLEngineError as exc:  # transient: retried next poll; the kick's 3 h sweep bounds it
                    result["runs"][str(row_id)] = "engine_unavailable"
                    _report_failure("poll", {"run_id": row_id}, exc)
            result.update(generate_prose(session, now))
    except Exception as exc:
        logger.exception("research poll failed")
        result["error"] = type(exc).__name__
        _report_failure("poll", result, exc)
        _dash("error", result)
        return result
    # Quiet polls (nothing running, no prose) leave the dashboard untouched.
    states = set(result["runs"].values())
    if states or result.get("prose_written"):
        if states & {"failed", "engine_unavailable"}:
            _dash("error", result)
        else:
            _dash("running" if "running" in states else "idle", result)
    return result


# ---------------------------------------------------------------------------
# Outcomes
# ---------------------------------------------------------------------------

def research_score_outcomes(now: Optional[datetime] = None, client: Optional[MLEngineClient] = None) -> dict[str, Any]:
    """Score matured predictions in batches of 2,000; each outcome is written
    once. Inserts an ``outcomes`` run row (the heartbeat)."""
    if not config.CONFIG.enabled:
        return {"skipped": "research_off"}
    engine = _client(client)
    counts = {"sent": 0, "matured": 0, "void": 0, "pending": 0, "written": 0}
    result: dict[str, Any] = {"stage": "outcomes", "counts": counts}
    run_id: Optional[int] = None
    try:
        with get_session() as session:
            run_id = repo.create_run(session, kind="outcomes", stage="scoring").id
            last_session = _last_success_market_date(session)
            result["last_session"] = last_session.isoformat() if last_session else None
            after_id = 0
            while last_session is not None:
                batch = repo.pending_matured_predictions(session, last_session, OUTCOME_BATCH, after_id)
                if not batch:
                    break
                after_id = batch[-1].id
                items = [
                    {
                        "prediction_id": p.id, "isin": p.isin, "symbol": p.symbol, "as_of": p.as_of_date.isoformat(),
                        "horizon_days": int(p.horizon_days), "entry_close": float(p.entry_close),
                    }
                    for p in batch
                ]
                counts["sent"] += len(items)
                ids = {p.id for p in batch}
                for res in engine.outcomes(items).get("results") or []:
                    pid = res.get("prediction_id")
                    status = res.get("outcome_status")
                    if pid not in ids or status not in ("matured", "void", "pending"):
                        continue  # only rows we sent; anything else is ignored
                    counts[status] += 1
                    if status != "pending" and repo.write_outcome_once(session, int(pid), res):
                        counts["written"] += 1
            repo.update_run(session, run_id, status="ok", stage="scored", counts_json=dict(counts))
    except Exception as exc:
        logger.exception("research outcome scoring failed")
        result["error"] = type(exc).__name__
        if run_id is not None:
            try:
                with get_session() as session:
                    repo.update_run(session, run_id, status="failed", error=type(exc).__name__, counts_json=dict(counts))
            except Exception:
                logger.exception("research outcomes could not mark run %s failed", run_id)
        _report_failure("outcomes", result, exc)
        _dash("error", result)
        return result
    _dash("idle", result)
    return result


# ---------------------------------------------------------------------------
# Live metrics
# ---------------------------------------------------------------------------

def research_live_metrics(now: Optional[datetime] = None, client: Optional[MLEngineClient] = None) -> dict[str, Any]:
    """One live-metrics row per (procedure, horizon) from matured rows, with
    yfinance-fallback predictions excluded (``repo.matured_rows``)."""
    if not config.CONFIG.enabled:
        return {"skipped": "research_off"}
    now = _utc(now)
    engine = _client(client)
    computed_on = now.astimezone(IST).date()
    result: dict[str, Any] = {"stage": "live_metrics", "stored": 0, "states": {}}
    run_id: Optional[int] = None
    try:
        with get_session() as session:
            run_id = repo.create_run(session, kind="live_metrics", stage="computing").id
            pairs = (
                session.query(ResearchPrediction.procedure_id, ResearchPrediction.horizon_days)
                .distinct()
                .order_by(ResearchPrediction.procedure_id, ResearchPrediction.horizon_days)
                .all()
            )
            for procedure_id, horizon in pairs:
                rows = repo.matured_rows(session, procedure_id, int(horizon))
                if not rows:
                    continue
                resp = engine.live_metrics({"procedure_id": procedure_id, "horizon_days": int(horizon), "rows": rows})
                if repo.insert_live_metrics(
                    session, procedure_id=procedure_id, horizon_days=int(horizon), computed_on=computed_on, response=resp,
                ):
                    result["stored"] += 1
                state = resp.get("live_status")
                result["states"][f"{procedure_id}:{horizon}"] = state
                if state == "under_review" or resp.get("alarms"):
                    _report_failure("live_metrics_alarm", {
                        "procedure_id": procedure_id, "horizon_days": int(horizon),
                        "live_status": state, "alarms": resp.get("alarms"),
                    })
            repo.update_run(session, run_id, status="ok", stage="stored", counts_json={"stored": result["stored"]})
    except Exception as exc:
        logger.exception("research live metrics failed")
        result["error"] = type(exc).__name__
        if run_id is not None:
            try:
                with get_session() as session:
                    repo.update_run(session, run_id, status="failed", error=type(exc).__name__)
            except Exception:
                logger.exception("research live metrics could not mark run %s failed", run_id)
        _report_failure("live_metrics", result, exc)
        _dash("error", result)
        return result
    _dash("idle", result)
    return result


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

def _template_rate_7d(session: Session, now: datetime) -> tuple[int, int]:
    """(stored narratives, template narratives) generated in the last 7 days."""
    rows = (
        session.query(ResearchReportRow.narrative_status)
        .filter(ResearchReportRow.narrative_generated_at >= (now - timedelta(days=7)).replace(tzinfo=None))
        .all()
    )
    return len(rows), sum(1 for (status,) in rows if status == "template")


def research_cleanup(now: Optional[datetime] = None) -> dict[str, Any]:
    """Daily retention (``prune_reports``) and the 7-day template-rate alert."""
    if not config.CONFIG.enabled:
        return {"skipped": "research_off"}
    now = _utc(now)
    result: dict[str, Any] = {"stage": "cleanup"}
    try:
        with get_session() as session:
            result["pruned"] = repo.prune_reports(session, now.astimezone(IST).date())
            total, templates = _template_rate_7d(session, now)
            if total and templates / total > TEMPLATE_RATE_ALERT:
                _report_failure("prose_template_rate", {"narratives_7d": total, "templates_7d": templates})
    except Exception as exc:
        logger.exception("research cleanup failed")
        result["error"] = type(exc).__name__
        _report_failure("cleanup", result, exc)
        _dash("error", result)
        return result
    _dash("idle", result)
    return result


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def register_research_jobs(scheduler: Any) -> int:
    """Add the 7 research jobs (UTC cron, spec 2.2). Adds none when the
    effective mode is off. Returns the number of jobs added."""
    if not config.CONFIG.enabled:
        logger.info("research engine off (degraded_reasons=%s); no jobs registered", list(config.CONFIG.degraded_reasons))
        return 0
    jobs: list[tuple[Any, str, dict[str, Any]]] = [
        (research_nightly_kick, "research_kick_evening", {"day_of_week": "mon-fri", "hour": 14, "minute": 15}),
        (research_nightly_kick, "research_kick_late", {"day_of_week": "mon-fri", "hour": 15, "minute": 30}),
        (research_nightly_kick, "research_kick_morning", {"day_of_week": "tue-sat", "hour": 1, "minute": 45}),
        (research_poll_ingest, "research_poll_ingest", {"day_of_week": "mon-sat", "hour": "1-3,14-18", "minute": "*/5"}),
        (research_score_outcomes, "research_score_outcomes", {"day_of_week": "mon-fri", "hour": 17, "minute": 0}),
        (research_live_metrics, "research_live_metrics", {"day_of_week": "sun", "hour": 4, "minute": 30}),
        (research_cleanup, "research_cleanup", {"hour": 21, "minute": 0}),
    ]
    for func_, job_id, cron in jobs:
        scheduler.add_job(func_, "cron", id=job_id, **cron, **_JOB_DEFAULTS)
    logger.info("research engine (%s): %d jobs registered", config.CONFIG.mode, len(jobs))
    return len(jobs)
