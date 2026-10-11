"""Research Engine ledger repository (spec §8).

Every function takes a SQLAlchemy ``Session`` (callers use
``database.get_session()``); write functions commit their own unit of work.

Write rules (DB-03, DB-17, LLM-14):
- predictions are created only by ``ingest_run_items`` (nightly ingest);
- prediction columns are never updated; the outcome columns change only through
  ``write_outcome_once`` (``WHERE outcome_status='pending'``);
- narratives are written only through ``set_narrative_once``
  (``WHERE narrative_json IS NULL``);
- report pruning nulls ``research_predictions.report_id`` through the FK's
  ``ON DELETE SET NULL``; nothing else touches a prediction row.

Datetime filter arguments may be naive (taken as UTC) or tz-aware (converted
to UTC); stored timestamps are UTC.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from models.db_models import (  # pyright: ignore[reportMissingImports]  (checker resolves `models` to ml-engine/models)
    Portfolio,
    ResearchLiveMetric,
    ResearchPrediction,
    ResearchReportRow,
    ResearchRun,
    StockUniverse,
    Watchlist,
)

FALLBACK_REASON = "prices_fallback_yfinance"
ON_DEMAND_RETENTION_DAYS = 30   # on-demand and non-universe reports
UNIVERSE_RETENTION_DAYS = 400   # nightly universe reports

_SYMBOL_RE = re.compile(r"^[A-Z0-9&-]{1,20}$")
_RUN_UPDATABLE = frozenset({"run_uid", "market_date", "status", "stage", "counts_json", "error", "finished_at"})
_TERMINAL_RUN_STATUSES = frozenset({"ok", "degraded", "failed", "skipped_holiday"})
_OUTCOME_FIELDS = (
    "void_reason", "realized_return_pct", "realized_excess_pp", "realized_top_half",
    "nifty50_return_pct", "stale_exit", "scorer_version",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_naive(dt: datetime) -> datetime:
    """Normalise a filter datetime to naive UTC (how SQLite stores DateTime)."""
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _as_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def normalize_symbol(ticker: Optional[str]) -> str:
    """'tcs.ns ' -> 'TCS'. Strips whitespace and a .NS/.BO suffix, upper-cases."""
    sym = (ticker or "").strip().upper()
    for suffix in (".NS", ".BO"):
        if sym.endswith(suffix):
            sym = sym[: -len(suffix)]
            break
    return sym


# ---------------------------------------------------------------------------
# Runs
# ---------------------------------------------------------------------------

def create_run(
    session: Session,
    *,
    kind: str,
    status: str = "running",
    market_date: Optional[date] = None,
    run_uid: Optional[str] = None,
    stage: Optional[str] = None,
    counts_json: Optional[dict] = None,
    error: Optional[str] = None,
) -> ResearchRun:
    """Insert a run row (kind: nightly|outcomes|live_metrics) and return it."""
    run = ResearchRun(
        kind=kind, status=status, market_date=market_date, run_uid=run_uid,
        stage=stage, counts_json=counts_json, error=error,
    )
    if status in _TERMINAL_RUN_STATUSES:
        run.finished_at = run.started_at = _now()
    session.add(run)
    session.commit()
    return run


def update_run(session: Session, run_id: int, **fields: Any) -> bool:
    """Update whitelisted run columns. A terminal status stamps finished_at
    unless one is given. Returns True if the row exists."""
    unknown = set(fields) - _RUN_UPDATABLE
    if unknown:
        raise ValueError(f"update_run: unsupported fields {sorted(unknown)}")
    values: dict[Any, Any] = dict(fields)
    if values.get("status") in _TERMINAL_RUN_STATUSES and "finished_at" not in values:
        values["finished_at"] = _now()
    n = session.query(ResearchRun).filter(ResearchRun.id == run_id).update(values, synchronize_session=False)
    session.commit()
    return n == 1


def mark_run_failed(session: Session, run_id: int, error: str) -> bool:
    """Mark a run failed with an error code (stale_run, engine_busy, ...)."""
    return update_run(session, run_id, status="failed", error=error)


def latest_run(session: Session, kind: str) -> Optional[ResearchRun]:
    """Most recently started run of a kind."""
    return (
        session.query(ResearchRun)
        .filter(ResearchRun.kind == kind)
        .order_by(ResearchRun.started_at.desc(), ResearchRun.id.desc())
        .first()
    )


def get_run_by_market_date(session: Session, market_date: date, kind: str = "nightly") -> Optional[ResearchRun]:
    """Latest run row for a market date (failed attempts may precede it)."""
    return (
        session.query(ResearchRun)
        .filter(ResearchRun.kind == kind, ResearchRun.market_date == market_date)
        .order_by(ResearchRun.id.desc())
        .first()
    )


def stale_running_runs(session: Session, older_than: datetime, kind: str = "nightly") -> list[ResearchRun]:
    """Runs still 'running' that started before ``older_than``."""
    return (
        session.query(ResearchRun)
        .filter(
            ResearchRun.kind == kind,
            ResearchRun.status == "running",
            ResearchRun.started_at < _utc_naive(older_than),
        )
        .order_by(ResearchRun.id)
        .all()
    )


def holiday_dates_after(session: Session, market_date: date) -> set[date]:
    """Market dates after ``market_date`` recorded as skipped_holiday (§2.5)."""
    rows = (
        session.query(ResearchRun.market_date)
        .filter(
            ResearchRun.kind == "nightly",
            ResearchRun.status == "skipped_holiday",
            ResearchRun.market_date > market_date,
        )
        .distinct()
        .all()
    )
    return {r[0] for r in rows if r[0] is not None}


# ---------------------------------------------------------------------------
# Ingest (§8.3)
# ---------------------------------------------------------------------------

def _report_row(report: Mapping[str, Any], *, origin: str, run_id: Optional[int],
                requested_by_user_id: Optional[int]) -> ResearchReportRow:
    return ResearchReportRow(
        report_uid=str(report["report_id"]),
        symbol=normalize_symbol(report["symbol"]),
        isin=report.get("isin"),
        as_of_date=_as_date(report["as_of"]["market_date"]),
        engine_version=report["engine_version"],
        procedure_id=(report.get("model_card") or {}).get("procedure_id"),
        run_id=run_id,
        origin=origin,
        status=report["status"],
        in_universe=bool(report["coverage"]["in_universe"]),
        requested_by_user_id=requested_by_user_id,
        report_json={**report, "origin": origin},
    )


def _existing_report(session: Session, row: ResearchReportRow) -> Optional[ResearchReportRow]:
    by_key = (
        session.query(ResearchReportRow)
        .filter(
            ResearchReportRow.symbol == row.symbol,
            ResearchReportRow.as_of_date == row.as_of_date,
            ResearchReportRow.engine_version == row.engine_version,
            ResearchReportRow.origin == row.origin,
        )
        .first()
    )
    if by_key is not None:
        return by_key
    return session.query(ResearchReportRow).filter(ResearchReportRow.report_uid == row.report_uid).first()


def ingest_run_items(session: Session, run_id: int, items: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    """Insert nightly RunItems ``{report, predictions}`` in one transaction.

    Reports and predictions that already exist (unique keys) are skipped, so a
    re-ingest is a no-op. Any other error rolls everything back and re-raises.
    Returns ``{reports_new, reports_existing, predictions_new}``.
    """
    counts = {"reports_new": 0, "reports_existing": 0, "predictions_new": 0}
    try:
        for item in items:
            report = item["report"]
            row = _report_row(report, origin="nightly", run_id=run_id, requested_by_user_id=None)
            existing = _existing_report(session, row)
            if existing is None:
                session.add(row)
                session.flush()
                counts["reports_new"] += 1
                parent = row
            else:
                counts["reports_existing"] += 1
                parent = existing

            for pred in item.get("predictions") or []:
                horizon = int(pred["horizon_days"])
                model_id = pred["model_id"]
                dup = (
                    session.query(ResearchPrediction.id)
                    .filter(
                        ((ResearchPrediction.report_id == parent.id) & (ResearchPrediction.horizon_days == horizon))
                        | (
                            (ResearchPrediction.symbol == parent.symbol)
                            & (ResearchPrediction.as_of_date == parent.as_of_date)
                            & (ResearchPrediction.horizon_days == horizon)
                            & (ResearchPrediction.model_id == model_id)
                        )
                    )
                    .first()
                )
                if dup is not None:
                    continue
                session.add(ResearchPrediction(
                    report_id=parent.id,
                    symbol=parent.symbol,
                    isin=parent.isin,
                    as_of_date=parent.as_of_date,
                    horizon_days=horizon,
                    procedure_id=pred["procedure_id"],
                    model_id=model_id,
                    manifest_sha256=pred["manifest_sha256"],
                    universe_id=pred["universe_id"],
                    evidence_tier=pred["evidence_tier"],
                    reason_codes=list(pred.get("reason_codes") or []),
                    score=float(pred["score"]),
                    rank_pct=float(pred["rank_pct"]),
                    bucket=pred.get("bucket"),
                    p_top_half=pred.get("p_top_half"),
                    entry_close=pred["entry_close"],
                    feature_hash=pred.get("feature_hash"),
                    expected_maturity_date=_as_date(pred["expected_maturity_date"]),
                ))
                session.flush()
                counts["predictions_new"] += 1
        session.commit()
    except Exception:
        session.rollback()
        raise
    return counts


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

def insert_on_demand_report(
    session: Session, report: Mapping[str, Any], requested_by_user_id: Optional[int],
) -> ResearchReportRow:
    """Persist an on-demand report (never creates predictions). Returns the
    existing row if one already exists for the same unique key."""
    row = _report_row(report, origin="on_demand", run_id=None, requested_by_user_id=requested_by_user_id)
    existing = _existing_report(session, row)
    if existing is not None:
        return existing
    session.add(row)
    session.commit()
    return row


def count_on_demand_since(session: Session, since: datetime, user_id: Optional[int] = None) -> int:
    """Persisted on-demand reports created at or after ``since`` (quota)."""
    q = session.query(func.count(ResearchReportRow.id)).filter(
        ResearchReportRow.origin == "on_demand",
        ResearchReportRow.created_at >= _utc_naive(since),
    )
    if user_id is not None:
        q = q.filter(ResearchReportRow.requested_by_user_id == user_id)
    return int(q.scalar() or 0)


def latest_report(session: Session, symbol: str) -> Optional[ResearchReportRow]:
    """Latest report by as_of_date; at equal dates nightly beats on-demand."""
    return (
        session.query(ResearchReportRow)
        .filter(ResearchReportRow.symbol == normalize_symbol(symbol))
        .order_by(
            ResearchReportRow.as_of_date.desc(),
            (ResearchReportRow.origin == "nightly").desc(),
            ResearchReportRow.id.desc(),
        )
        .first()
    )


def predictions_for_report(session: Session, report_id: int) -> list[ResearchPrediction]:
    return (
        session.query(ResearchPrediction)
        .filter(ResearchPrediction.report_id == report_id)
        .order_by(ResearchPrediction.horizon_days)
        .all()
    )


def reports_needing_prose(
    session: Session, *, run_id: Optional[int] = None, universe_only: bool = False, limit: Optional[int] = None,
) -> list[ResearchReportRow]:
    """Nightly reports without a narrative, universe names first."""
    q = session.query(ResearchReportRow).filter(
        ResearchReportRow.origin == "nightly",
        ResearchReportRow.narrative_json.is_(None),
    )
    if run_id is not None:
        q = q.filter(ResearchReportRow.run_id == run_id)
    if universe_only:
        q = q.filter(ResearchReportRow.in_universe.is_(True))
    q = q.order_by(ResearchReportRow.in_universe.desc(), ResearchReportRow.symbol, ResearchReportRow.id)
    if limit is not None:
        q = q.limit(limit)
    return q.all()


# ---------------------------------------------------------------------------
# Prose
# ---------------------------------------------------------------------------

def set_narrative_once(
    session: Session,
    report_id: int,
    *,
    narrative: dict,
    status: str,
    attempts: int,
    failures: Optional[list] = None,
    facts_hash: Optional[str] = None,
) -> bool:
    """Store a validated (or template) narrative once. Returns False if the
    report already has one (``WHERE narrative_json IS NULL`` guard)."""
    values: dict[Any, Any] = {
        "narrative_json": narrative,
        "narrative_status": status,
        "narrative_attempts": int(attempts),
        "narrative_failures_json": failures,
        "narrative_generated_at": _now(),
    }
    if facts_hash is not None:
        values["facts_hash"] = facts_hash
    n = (
        session.query(ResearchReportRow)
        .filter(ResearchReportRow.id == report_id, ResearchReportRow.narrative_json.is_(None))
        .update(values, synchronize_session=False)
    )
    session.commit()
    return n == 1


def llm_calls_since(session: Session, since: datetime) -> int:
    """SUM(narrative_attempts) of narratives generated at or after ``since``."""
    total = (
        session.query(func.coalesce(func.sum(ResearchReportRow.narrative_attempts), 0))
        .filter(ResearchReportRow.narrative_generated_at >= _utc_naive(since))
        .scalar()
    )
    return int(total or 0)


# ---------------------------------------------------------------------------
# Outcomes (§8.4)
# ---------------------------------------------------------------------------

def pending_matured_predictions(
    session: Session, last_session: date, batch_size: int = 2000, after_id: int = 0,
) -> list[ResearchPrediction]:
    """Pending predictions with expected_maturity_date <= last_session, by id.
    Page with ``after_id`` = the last id of the previous batch (rows that stay
    pending would otherwise be returned again)."""
    return (
        session.query(ResearchPrediction)
        .filter(
            ResearchPrediction.outcome_status == "pending",
            ResearchPrediction.expected_maturity_date <= last_session,
            ResearchPrediction.id > after_id,
        )
        .order_by(ResearchPrediction.id)
        .limit(batch_size)
        .all()
    )


def write_outcome_once(session: Session, prediction_id: int, result: Mapping[str, Any]) -> bool:
    """Write an OutcomeResult (matured|void) once. Returns False if the row is
    not pending any more or the result is still pending. This is the only
    update path on research_predictions."""
    status = result.get("outcome_status")
    if status not in ("matured", "void"):
        return False
    values: dict[Any, Any] = {name: result.get(name) for name in _OUTCOME_FIELDS}
    values["outcome_status"] = status
    values["scored_at"] = _now()
    n = (
        session.query(ResearchPrediction)
        .filter(ResearchPrediction.id == prediction_id, ResearchPrediction.outcome_status == "pending")
        .update(values, synchronize_session=False)
    )
    session.commit()
    return n == 1


def matured_rows(session: Session, procedure_id: str, horizon: int) -> list[dict[str, Any]]:
    """Scored (matured and void) rows for one (procedure, horizon) as
    LiveMetricsRequest rows, oldest first. Rows priced from the yfinance
    fallback are excluded. ml-engine computes metrics on matured rows only and
    counts the void ones."""
    rows = (
        session.query(ResearchPrediction)
        .filter(
            ResearchPrediction.procedure_id == procedure_id,
            ResearchPrediction.horizon_days == horizon,
            ResearchPrediction.outcome_status.in_(("matured", "void")),
        )
        .order_by(ResearchPrediction.as_of_date, ResearchPrediction.id)
        .all()
    )
    return [
        {
            "as_of": r.as_of_date.isoformat(),
            "symbol": r.symbol,
            "score": r.score,
            "rank_pct": r.rank_pct,
            "bucket": r.bucket,
            "p_top_half": r.p_top_half,
            "outcome_status": r.outcome_status,
            "realized_excess_pp": r.realized_excess_pp,
            "realized_top_half": r.realized_top_half,
            "stale_exit": r.stale_exit,
        }
        for r in rows
        if FALLBACK_REASON not in (r.reason_codes or [])
    ]


# ---------------------------------------------------------------------------
# Live metrics (§8.5)
# ---------------------------------------------------------------------------

def insert_live_metrics(
    session: Session, *, procedure_id: str, horizon_days: int, computed_on: date, response: Mapping[str, Any],
) -> bool:
    """Store one LiveMetricsResponse (kept whole in metrics_json). Returns
    False if a row already exists for (procedure, horizon, computed_on)."""
    exists = (
        session.query(ResearchLiveMetric.id)
        .filter(
            ResearchLiveMetric.procedure_id == procedure_id,
            ResearchLiveMetric.horizon_days == horizon_days,
            ResearchLiveMetric.computed_on == computed_on,
        )
        .first()
    )
    if exists is not None:
        return False
    session.add(ResearchLiveMetric(
        procedure_id=procedure_id,
        horizon_days=horizon_days,
        computed_on=computed_on,
        live_status=response["live_status"],
        live_gate_passed=bool(response["live_gate_passed"]),
        matured_n=int(response["matured_n"]),
        matured_dates=int(response["matured_dates"]),
        metrics_json=dict(response),
        alarms_json=list(response.get("alarms") or []),
    ))
    session.commit()
    return True


def latest_live_metrics(session: Session, procedure_id: Optional[str] = None) -> list[ResearchLiveMetric]:
    """Latest row per (procedure_id, horizon_days)."""
    q = session.query(ResearchLiveMetric)
    if procedure_id is not None:
        q = q.filter(ResearchLiveMetric.procedure_id == procedure_id)
    latest: dict[tuple[str, int], ResearchLiveMetric] = {}
    for row in q.order_by(ResearchLiveMetric.computed_on.desc(), ResearchLiveMetric.id.desc()).all():
        latest.setdefault((row.procedure_id, row.horizon_days), row)
    return sorted(latest.values(), key=lambda r: (r.procedure_id, r.horizon_days))


# ---------------------------------------------------------------------------
# Retention (§8.2)
# ---------------------------------------------------------------------------

def prune_reports(session: Session, today: date) -> int:
    """Delete on-demand / non-universe reports older than 30 days and universe
    reports older than 400 days. Predictions survive (FK ON DELETE SET NULL)."""
    short_cutoff = today - timedelta(days=ON_DEMAND_RETENTION_DAYS)
    long_cutoff = today - timedelta(days=UNIVERSE_RETENTION_DAYS)
    n = (
        session.query(ResearchReportRow)
        .filter(
            (
                ((ResearchReportRow.origin == "on_demand") | (ResearchReportRow.in_universe.is_(False)))
                & (ResearchReportRow.as_of_date < short_cutoff)
            )
            | (ResearchReportRow.as_of_date < long_cutoff)
        )
        .delete(synchronize_session=False)
    )
    session.commit()
    return n


# ---------------------------------------------------------------------------
# Symbols
# ---------------------------------------------------------------------------

def extra_symbols(session: Session, cap: int = 500) -> list[str]:
    """Distinct normalised portfolio and watchlist tickers, most holders first.
    Symbols only: no user ids leave this function (FINSEC-04)."""
    holders: dict[str, set[int]] = {}
    pairs = list(session.query(Portfolio.user_id, Portfolio.ticker).all())
    pairs += list(session.query(Watchlist.user_id, Watchlist.ticker).all())
    for user_id, ticker in pairs:
        sym = normalize_symbol(ticker)
        if _SYMBOL_RE.match(sym):
            holders.setdefault(sym, set()).add(user_id)
    ranked = sorted(holders, key=lambda s: (-len(holders[s]), s))
    return ranked[:cap]


def known_symbols_and_names(session: Session, exclude_symbol: str) -> tuple[set[str], list[str]]:
    """Normalised stock_universe tickers and company names for the grounding
    validator, excluding every row whose normalised ticker is ``exclude_symbol``."""
    own = normalize_symbol(exclude_symbol)
    symbols: set[str] = set()
    names: list[str] = []
    seen_names: set[str] = set()
    for ticker, name in session.query(StockUniverse.ticker, StockUniverse.company_name).all():
        sym = normalize_symbol(ticker)
        if not sym or sym == own:
            continue
        symbols.add(sym)
        if name and name not in seen_names:
            seen_names.add(name)
            names.append(name)
    return symbols, names


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

def _iso(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def health_summary(session: Session, now: Optional[datetime] = None) -> dict[str, Any]:
    """Ledger facts for /healthz and admin status (no flags, no ml-engine)."""
    now = now or _now()
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    last_nightly = latest_run(session, "nightly")
    last_success = (
        session.query(ResearchRun)
        .filter(ResearchRun.kind == "nightly", ResearchRun.status.in_(("ok", "degraded")))
        .order_by(ResearchRun.id.desc())
        .first()
    )
    last_outcomes = latest_run(session, "outcomes")

    hours_since: Optional[float] = None
    success_at = last_success.finished_at if last_success is not None else None
    if success_at is not None:
        if success_at.tzinfo is None:
            success_at = success_at.replace(tzinfo=timezone.utc)
        hours_since = round((now - success_at).total_seconds() / 3600.0, 2)

    return {
        "last_nightly_market_date": (
            last_nightly.market_date.isoformat()
            if last_nightly is not None and last_nightly.market_date is not None else None
        ),
        "last_nightly_status": last_nightly.status if last_nightly is not None else None,
        "last_success_market_date": (
            last_success.market_date.isoformat()
            if last_success is not None and last_success.market_date is not None else None
        ),
        "hours_since_last_success": hours_since,
        "last_outcome_run_at": _iso(last_outcomes.started_at) if last_outcomes is not None else None,
        "pending_predictions": int(
            session.query(func.count(ResearchPrediction.id))
            .filter(ResearchPrediction.outcome_status == "pending")
            .scalar() or 0
        ),
    }
