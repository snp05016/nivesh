"""Stock report API (Research Engine, spec 9.1): ``/api/v1/research``.

Thin routes over ``services.research.serve``. GET routes never compute, call
the LLM or write; the only write is the on-demand report persisted by
``POST /stocks/{symbol}/compute`` (never ledger rows). Access follows the
effective ``RESEARCH_ENGINE_MODE``: ``on`` needs a signed-in user, ``shadow``
an admin, and ``off`` (or invalid config) answers 404 ``RESEARCH_DISABLED``.
``/track-record`` and ``/admin/status`` are admin-only in every mode.
Error bodies are ``{"detail": {"code": ...}}``. Importing this module never
raises (D36).
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from fastapi.responses import JSONResponse

from core import rate_limiter
from core.security import require_admin, require_auth
from database import get_session
from repositories import research_repo as repo
from services.research import config, serve
from services.research.client import MLEngineClient, MLEngineError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/research", tags=["research"])

SUPPORTED_LANGS = ("en",)
CACHE_CONTROL = "private, max-age=300"
COMPUTE_RETRY_AFTER = "300"
RATE_LIMIT_ENDPOINT = "research_compute"
_SYMBOL_RE = re.compile(r"^[A-Z0-9&-]{1,20}$")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _error(status: int, code: str, *, headers: Optional[dict[str, str]] = None, **extra: Any) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, **extra}, headers=headers)


# ---------------------------------------------------------------------------
# Access
# ---------------------------------------------------------------------------

def research_user(authorization: str = Header(None)) -> int:
    """Mode on: any signed-in user; shadow: admins only; off: 404."""
    mode = config.CONFIG.mode
    if mode == "on":
        return require_auth(authorization)
    if mode == "shadow":
        return require_admin(authorization)
    raise _error(404, "RESEARCH_DISABLED")


def research_admin(authorization: str = Header(None)) -> int:
    """``/model-card?detail=full``: admins only, and only while research is enabled."""
    if not config.CONFIG.enabled:
        raise _error(404, "RESEARCH_DISABLED")
    return require_admin(authorization)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _symbol(raw: str) -> str:
    """Upper-cased, .NS/.BO stripped, ``^[A-Z0-9&-]{1,20}$`` or 422."""
    sym = repo.normalize_symbol(raw)
    if not _SYMBOL_RE.match(sym):
        raise _error(422, "INVALID_SYMBOL")
    return sym


def _check_lang(lang: str) -> None:
    if lang not in SUPPORTED_LANGS:
        raise _error(422, "UNSUPPORTED_LANG")


def _etag_matches(if_none_match: Optional[str], tag: str) -> bool:
    if not if_none_match:
        return False
    candidates = {c.strip().removeprefix("W/") for c in if_none_match.split(",")}
    return "*" in candidates or tag in candidates


def _respond(served: dict[str, Any], request: Request) -> Response:
    """200 with ETag and Cache-Control, or 304 when If-None-Match matches."""
    tag = f'"{serve.etag(served)}"'
    headers = {"ETag": tag, "Cache-Control": CACHE_CONTROL}
    if _etag_matches(request.headers.get("if-none-match"), tag):
        return Response(status_code=304, headers=headers)
    return JSONResponse(served, headers=headers)


# ---------------------------------------------------------------------------
# Stock reports
# ---------------------------------------------------------------------------

@router.get("/stocks/{symbol}")
def get_stock_report(
    symbol: str, request: Request, lang: str = "en", user_id: int = Depends(research_user),
) -> Response:
    """The latest stored report (latest as_of, nightly preferred), served."""
    _check_lang(lang)
    sym = _symbol(symbol)
    now = _now()
    with get_session() as session:
        row = repo.latest_report(session, sym)
        if row is None:
            raise _error(404, "NOT_COVERED", compute_available=True)
        served = serve.serve_row(session, row, config.CONFIG, now)
    return _respond(served, request)


@router.post("/stocks/{symbol}/compute")
def compute_stock_report(
    symbol: str, request: Request, lang: str = "en", user_id: int = Depends(research_user),
) -> Response:
    """On-demand report for a symbol without one for the latest market date.

    A report already stored for that date is served without counting. Otherwise
    the attempt counts against the per-user rate limit, the persisted on-demand
    reports against the daily quota, and ml-engine ``/compute`` (15 s) runs; the
    result is stored as ``origin=on_demand`` (no ledger rows) and served with
    template prose.
    """
    _check_lang(lang)
    sym = _symbol(symbol)
    now = _now()
    cfg = config.CONFIG
    with get_session() as session:
        row = repo.latest_report(session, sym)
        if row is not None and row.as_of_date >= serve.latest_market_date(session, now):
            return _respond(serve.serve_row(session, row, cfg, now), request)
        rate_limiter._check_rate_limit(f"user:{user_id}", RATE_LIMIT_ENDPOINT)
        if repo.count_on_demand_since(session, serve.ist_midnight(now), user_id=user_id) >= cfg.compute_daily_quota:
            raise _error(429, "QUOTA_EXCEEDED", headers={"Retry-After": str(serve.seconds_to_ist_midnight(now))})

    unavailable = _error(503, "COMPUTE_UNAVAILABLE", headers={"Retry-After": COMPUTE_RETRY_AFTER})
    try:
        resp = MLEngineClient().compute(sym)
    except MLEngineError:
        raise unavailable from None
    if resp.status_code == 404:
        raise _error(404, "UNKNOWN_SYMBOL")
    if resp.status_code == 422:
        raise _error(422, "INSUFFICIENT_HISTORY")
    report = resp.body.get("report")
    if not isinstance(report, dict):
        logger.warning("research compute for %s returned no report object", sym)
        raise unavailable

    with get_session() as session:
        try:
            row = repo.insert_on_demand_report(session, report, user_id)
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            session.rollback()
            logger.warning("research compute for %s returned a malformed report: %s", sym, type(exc).__name__)
            raise unavailable from None
        served = serve.serve_row(session, row, cfg, now)
    return _respond(served, request)


# ---------------------------------------------------------------------------
# Model card, track record, admin status
# ---------------------------------------------------------------------------

@router.get("/model-card")
def get_model_card(detail: str = "summary", authorization: str = Header(None)) -> dict[str, Any]:
    """summary (signed-in): tier text per horizon, data period, universe,
    limitations; never gates. full (admin): adds ml-engine ``/model-card``
    (validation with gates), cached for an hour."""
    if detail not in ("summary", "full"):
        raise _error(422, "UNSUPPORTED_DETAIL")
    if detail == "full":
        research_admin(authorization)
    else:
        research_user(authorization)
    with get_session() as session:
        summary = serve.model_card_summary(session, config.CONFIG, _now())
    if detail == "summary":
        if summary is None:
            raise _error(404, "MODEL_CARD_UNAVAILABLE")
        return summary
    try:
        engine = serve.engine_model_card(lambda: MLEngineClient().model_card())
    except MLEngineError:
        raise _error(503, "ENGINE_UNAVAILABLE", headers={"Retry-After": COMPUTE_RETRY_AFTER}) from None
    return {"summary": summary, "engine": engine}


@router.get("/track-record")
def get_track_record(admin_id: int = Depends(require_admin)) -> dict[str, Any]:
    """Admin only, in every mode: latest live rows per (procedure, horizon)."""
    with get_session() as session:
        return {"rows": serve.track_record(session)}


@router.get("/admin/status")
def get_admin_status(admin_id: int = Depends(require_admin)) -> dict[str, Any]:
    """Admin only, in every mode (not mode-gated, so the config degraded
    reasons stay readable while research is off or the config is invalid):
    runs, counts, template rate, LLM calls today, live states, warnings."""
    with get_session() as session:
        return serve.admin_status(session, config.CONFIG, _now())
