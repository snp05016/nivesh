"""Serving policy for stored research reports (spec 2.3, 2.5, 5.6, 8.6, 9.1).

``serve_report`` turns a stored ``research_reports`` row into the served
ResearchReport. It is a pure function of its arguments: no database access, no
network and no LLM call (the template narrative is rendered locally). It sets
only the backend-owned blocks (``staleness``, ``narrative``,
``live_track_record``, ``compliance``, ``outlooks[].tier_text``,
``outlooks[].prediction_id``, ``model_card.horizons[].tier_text``) and applies
the served-tier policy:

1. an expired snapshot serves every outlook as ``unavailable`` (``snapshot_expired``);
2. a live ``under_review`` (kill-switch A1) serves ``no_reliable_edge`` (``live_under_review``);
3. an artefact ``validated_edge`` serves as ``weak_evidence`` unless the live gate
   G7 passed **and** an effective ``RESEARCH_SEBI_RA_REG_NO`` exists (D37), with
   ``live_shadow_collecting`` and/or ``policy_hidden``;
4. a cohort is served only under an effective ``cohort_frequency`` on a served
   ``validated_edge``; a stripped cohort appends ``policy_hidden`` (D9).

The remaining helpers are the read-only queries behind the router's model-card,
track-record and admin-status routes; none of them writes.
"""

from __future__ import annotations

import copy
import hashlib
import json
import logging
import threading
import time as _time
from collections.abc import Iterable, Mapping
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from models.db_models import (  # pyright: ignore[reportMissingImports]  (checker resolves `models` to ml-engine/models)
    ResearchReportRow,
    ResearchRun,
)
from repositories import research_repo as repo

from .config import ResearchConfig
from .jobs import IST, _ist_midnight, _last_success_market_date, _template_rate_7d
from .templates import AI_DISCLOSURE, DISCLAIMER_ID, DISCLAIMER_TEXT, TIER_TEXT
from .validator import LEXICON_VERSION

logger = logging.getLogger(__name__)

DUE_TIME = time(21, 30)          # IST: a market date's report is due from here (2.5)
STALE_AFTER_SESSIONS = 1
EXPIRED_AFTER_SESSIONS = 3
HORIZONS = (21, 63)
MIN_LIVE_PERIODS = 12
COMPLIANCE_MODE = "unregistered_educational"
MODEL_CARD_TTL_SECONDS = 3600.0
RECENT_RUNS = 20

# Artefact tiers the live policy can lower (out_of_universe and unavailable stay).
_RANKED_TIERS = frozenset({"validated_edge", "weak_evidence", "no_reliable_edge"})


# ---------------------------------------------------------------------------
# Staleness (spec 2.5, D25)
# ---------------------------------------------------------------------------

def _previous_weekday(d: date) -> date:
    d -= timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def _ist(now: datetime) -> datetime:
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return now.astimezone(IST)


def last_due_weekday(now: datetime) -> date:
    """Today (IST) on a weekday from 21:30 IST, otherwise the previous weekday."""
    local = _ist(now)
    today = local.date()
    if today.weekday() < 5 and local.time() >= DUE_TIME:
        return today
    return _previous_weekday(today)


def sessions_old(as_of: date, now: datetime, holiday_dates: Iterable[date]) -> int:
    """Weekdays d with ``as_of < d <= last_due_weekday(now)`` that are not
    recorded holidays. Duplicate or failed run rows never count (only the dates
    of ``skipped_holiday`` rows are subtracted)."""
    due = last_due_weekday(now)
    holidays = set(holiday_dates)
    n = 0
    d = as_of + timedelta(days=1)
    while d <= due:
        if d.weekday() < 5 and d not in holidays:
            n += 1
        d += timedelta(days=1)
    return n


def staleness(as_of: date, now: datetime, holiday_dates: Iterable[date]) -> dict[str, Any]:
    """Contract ``Staleness``: 0 fresh, 1-2 stale, 3 or more expired."""
    n = sessions_old(as_of, now, holiday_dates)
    state = "expired" if n >= EXPIRED_AFTER_SESSIONS else "stale" if n >= STALE_AFTER_SESSIONS else "fresh"
    return {"sessions_old": n, "state": state}


# ---------------------------------------------------------------------------
# Live track record (spec 8.5, 8.6): states only, never rates or IC
# ---------------------------------------------------------------------------

def _live_for(live_rows: Iterable[Any], procedure_id: Optional[str]) -> dict[int, Any]:
    """Latest live row per horizon for one procedure (rows arrive latest first
    or one per key, as ``repo.latest_live_metrics`` returns them)."""
    out: dict[int, Any] = {}
    if procedure_id is None:
        return out
    for r in live_rows:
        if r.procedure_id == procedure_id:
            out.setdefault(int(r.horizon_days), r)
    return out


def _since(live_row: Any) -> Optional[str]:
    """Start of the live window ('YYYY-MM-DD ...' in metrics.window), if any."""
    metrics = (live_row.metrics_json or {}).get("metrics") or {}
    window = metrics.get("window")
    if not isinstance(window, str):
        return None
    try:
        return date.fromisoformat(window[:10]).isoformat()
    except ValueError:
        return None


def _live_horizon(h: int, live_row: Any) -> dict[str, Any]:
    if live_row is None:
        return {
            "horizon_days": h, "state": "collecting", "since": None, "matured_dates": 0,
            "independent_periods": 0, "min_periods_required": MIN_LIVE_PERIODS,
        }
    matured_dates = int(live_row.matured_dates or 0)
    periods = (live_row.metrics_json or {}).get("independent_periods")
    return {
        "horizon_days": h,
        "state": live_row.live_status,
        "since": _since(live_row),
        "matured_dates": matured_dates,
        "independent_periods": int(periods) if periods is not None else matured_dates // h,
        "min_periods_required": MIN_LIVE_PERIODS,
    }


# ---------------------------------------------------------------------------
# Tier policy (spec 5.6, D9, D37)
# ---------------------------------------------------------------------------

def _add(reasons: list[str], code: str) -> None:
    if code not in reasons:
        reasons.append(code)


def _serve_outlook(
    outlook: dict[str, Any], *, expired: bool, live_row: Any, flags: ResearchConfig, prediction_id: Optional[int],
) -> None:
    tier = outlook.get("evidence_tier")
    reasons = [str(r) for r in outlook.get("reason_codes") or []]
    registered = flags.sebi_ra_reg_no is not None

    if expired:
        tier = "unavailable"
        _add(reasons, "snapshot_expired")
    elif tier in _RANKED_TIERS and live_row is not None and live_row.live_status == "under_review":
        tier = "no_reliable_edge"
        _add(reasons, "live_under_review")
    elif tier == "validated_edge":
        gate = bool(live_row is not None and live_row.live_gate_passed)
        if not (gate and registered):
            tier = "weak_evidence"
            if not gate:
                _add(reasons, "live_shadow_collecting")
            if not registered:
                _add(reasons, "policy_hidden")

    show_cohort = flags.outlook_display == "cohort_frequency" and registered and tier == "validated_edge"
    if outlook.get("cohort") is not None and not show_cohort:
        outlook["cohort"] = None
        _add(reasons, "policy_hidden")

    outlook["evidence_tier"] = tier
    outlook["reason_codes"] = reasons
    outlook["tier_text"] = TIER_TEXT.get(str(tier))
    outlook["prediction_id"] = prediction_id


# ---------------------------------------------------------------------------
# Narrative and compliance
# ---------------------------------------------------------------------------

def _template_narrative(report: Mapping[str, Any]) -> Optional[dict[str, Any]]:
    """The ``tf-1`` template narrative rendered now. ``allow_llm=False``: no
    LLM call is possible. Returns None if the report cannot be templated."""
    try:
        from . import formatter  # lazy: keeps the LLM client out of router import

        narrative, _attempts, _failures = formatter.generate_narrative(
            report, known_symbols=(), company_names=(), allow_llm=False, calls_remaining=0,
        )
        return narrative
    except Exception:
        logger.exception("research template narrative failed for %s", report.get("symbol"))
        return None


def compliance_block(flags: ResearchConfig) -> dict[str, Any]:
    """Contract ``Compliance`` stamped with the effective flags."""
    return {
        "mode": COMPLIANCE_MODE,
        "disclaimer_id": DISCLAIMER_ID,
        "disclaimer_text": DISCLAIMER_TEXT,
        "ai_disclosure": AI_DISCLOSURE,
        "outlook_display": flags.outlook_display,
        "track_record_visible": flags.track_record_public,
        "lexicon_version": LEXICON_VERSION,
    }


# ---------------------------------------------------------------------------
# Serve pipeline (spec 9.1)
# ---------------------------------------------------------------------------

def serve_report(
    row: Any,
    predictions: Iterable[Any],
    live_rows: Iterable[Any],
    holiday_dates: Iterable[date],
    flags: ResearchConfig,
    now: datetime,
) -> dict[str, Any]:
    """The served ResearchReport for a ``ResearchReportRow`` (spec 9.1 steps 1-8;
    the ETag is ``etag(result)``).

    ``predictions``: the row's ledger rows (``horizon_days``, ``id``);
    ``live_rows``: latest ``ResearchLiveMetric`` rows; ``holiday_dates``: market
    dates after ``as_of`` with a ``skipped_holiday`` run; ``flags``: the
    effective research config.
    """
    served: dict[str, Any] = copy.deepcopy(dict(row.report_json))
    as_of = row.as_of_date
    if isinstance(as_of, datetime):
        as_of = as_of.date()

    served["staleness"] = staleness(as_of, now, holiday_dates)
    expired = served["staleness"]["state"] == "expired"

    pred_ids = {int(p.horizon_days): int(p.id) for p in predictions}
    live_rows = list(live_rows)
    tier_text: dict[int, Optional[str]] = {}
    for outlook in served.get("outlooks") or []:
        h = int(outlook["horizon_days"])
        live_row = _live_for(live_rows, outlook.get("procedure_id")).get(h)
        _serve_outlook(outlook, expired=expired, live_row=live_row, flags=flags, prediction_id=pred_ids.get(h))
        tier_text[h] = outlook["tier_text"]

    served["narrative"] = row.narrative_json if row.narrative_json else _template_narrative(row.report_json)

    served["compliance"] = compliance_block(flags)
    procedure_id = (served.get("model_card") or {}).get("procedure_id")
    live_by_h = _live_for(live_rows, procedure_id)
    served["live_track_record"] = {
        "visible": flags.track_record_public,
        "horizons": [_live_horizon(h, live_by_h.get(h)) for h in HORIZONS],
    }

    model_card = served.get("model_card")
    if isinstance(model_card, dict):
        for entry in model_card.get("horizons") or []:
            entry["tier_text"] = tier_text.get(int(entry["horizon_days"]))
    return served


def etag(served: Mapping[str, Any]) -> str:
    """First 32 hex characters of sha256 of the canonical served JSON (2.5)."""
    blob = json.dumps(served, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:32]


# ---------------------------------------------------------------------------
# Read-only queries for the router (no writes anywhere below)
# ---------------------------------------------------------------------------

def serve_row(session: Session, row: ResearchReportRow, flags: ResearchConfig, now: datetime) -> dict[str, Any]:
    """Load the ledger context of ``row`` and serve it."""
    return serve_report(
        row,
        repo.predictions_for_report(session, row.id),
        repo.latest_live_metrics(session),
        repo.holiday_dates_after(session, row.as_of_date),
        flags,
        now,
    )


def latest_market_date(session: Session, now: datetime) -> date:
    """Latest market date with an ok/degraded nightly run, else the last due weekday."""
    return _last_success_market_date(session) or last_due_weekday(now)


def ist_midnight(now: datetime) -> datetime:
    """Start of the current IST day (as UTC)."""
    return _ist_midnight(now)


def seconds_to_ist_midnight(now: datetime) -> int:
    """Seconds until the next IST midnight (quota Retry-After), at least 1."""
    nxt = _ist_midnight(now) + timedelta(days=1)
    return max(1, int((nxt - _ist(now)).total_seconds()))


def model_card_summary(session: Session, flags: ResearchConfig, now: datetime) -> Optional[dict[str, Any]]:
    """The served ``model_card`` of the latest in-universe nightly report: tier
    text per horizon, data period, universe, limitations. Never gates."""
    row = (
        session.query(ResearchReportRow)
        .filter(ResearchReportRow.origin == "nightly", ResearchReportRow.in_universe.is_(True))
        .order_by(ResearchReportRow.as_of_date.desc(), ResearchReportRow.id.desc())
        .first()
    )
    if row is None:
        return None
    card = serve_row(session, row, flags, now).get("model_card")
    return card if isinstance(card, dict) else None


_engine_card_lock = threading.Lock()
_engine_card: dict[str, Any] = {}  # {"at": monotonic seconds, "body": ml-engine /model-card}


def engine_model_card(fetch: Any) -> dict[str, Any]:
    """ml-engine ``/model-card`` (validation.json with gates; admin only),
    cached for an hour per process. ``fetch`` is a zero-argument callable;
    its errors propagate and are not cached."""
    with _engine_card_lock:
        cached = _engine_card.get("body")
        if cached is not None and _time.monotonic() - float(_engine_card["at"]) < MODEL_CARD_TTL_SECONDS:
            return cached
    body = fetch()
    with _engine_card_lock:
        _engine_card.update(at=_time.monotonic(), body=body)
    return body


def _iso(value: Any) -> Optional[str]:
    return value.isoformat() if value is not None else None


def track_record(session: Session) -> list[dict[str, Any]]:
    """Admin only (8.6): the latest live row per (procedure, horizon) with its
    full metrics (n, matured dates, independent periods, window, CIs, void and
    stale_exit counts) and alarms."""
    return [
        {
            "procedure_id": r.procedure_id,
            "horizon_days": r.horizon_days,
            "computed_on": _iso(r.computed_on),
            "live_status": r.live_status,
            "live_gate_passed": r.live_gate_passed,
            "matured_n": r.matured_n,
            "matured_dates": r.matured_dates,
            "metrics": r.metrics_json,
            "alarms": r.alarms_json,
        }
        for r in repo.latest_live_metrics(session)
    ]


def admin_status(session: Session, flags: ResearchConfig, now: datetime) -> dict[str, Any]:
    """Admin only: runs, counts (including ``ca_unverified``), template rate,
    LLM calls today, live states, warnings and config degraded reasons."""
    runs = session.query(ResearchRun).order_by(ResearchRun.id.desc()).limit(RECENT_RUNS).all()
    last_nightly = next((r for r in runs if r.kind == "nightly" and r.status in ("ok", "degraded")), None)
    narratives, templates = _template_rate_7d(session, now)
    live = repo.latest_live_metrics(session)
    warnings = sorted({
        f"{r.procedure_id}:{r.horizon_days}:{alarm.get('code')}"
        for r in live for alarm in (r.alarms_json or []) if isinstance(alarm, Mapping)
    })
    return {
        "config": {
            "mode": flags.mode,
            "outlook_display": flags.outlook_display,
            "track_record_public": flags.track_record_public,
            "registration_effective": flags.sebi_ra_reg_no is not None,
            "legacy_retired": flags.legacy_retired,
            "llm_prose": flags.llm_prose,
            "llm_max_calls_per_day": flags.llm_max_calls_per_day,
            "compute_daily_quota": flags.compute_daily_quota,
            "degraded_reasons": list(flags.degraded_reasons),
        },
        "ledger": repo.health_summary(session, now),
        "runs": [
            {
                "id": r.id, "run_uid": r.run_uid, "kind": r.kind, "market_date": _iso(r.market_date),
                "status": r.status, "stage": r.stage, "counts": r.counts_json, "error": r.error,
                "started_at": _iso(r.started_at), "finished_at": _iso(r.finished_at),
            }
            for r in runs
        ],
        "last_nightly_counts": last_nightly.counts_json if last_nightly is not None else None,
        "prose": {
            "llm_calls_today": repo.llm_calls_since(session, _ist_midnight(now)),
            "llm_max_calls_per_day": flags.llm_max_calls_per_day,
            "narratives_7d": narratives,
            "templates_7d": templates,
            "template_rate_7d": round(templates / narratives, 4) if narratives else None,
        },
        "live": [
            {
                "procedure_id": r.procedure_id, "horizon_days": r.horizon_days, "computed_on": _iso(r.computed_on),
                "live_status": r.live_status, "live_gate_passed": r.live_gate_passed,
            }
            for r in live
        ],
        "warnings": warnings,
    }
