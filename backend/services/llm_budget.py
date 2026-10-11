"""Daily LLM spend guard (LLM-02).

Every paid LLM call appends an ``LlmUsage`` ledger row (``record_usage``, called from
core.dashboard_state._log_token_usage). Routes that reach an LLM depend on
``require_llm_budget(feature)`` or call ``guard()``: no token -> 401, the user's tier cap
for today spent -> 429, everyone's spend today at LLM_GLOBAL_DAILY_BUDGET_USD -> 503.
The LLM wrappers call ``assert_global_budget()`` as well, so background jobs and
anonymous routes stop at the same global cap. A budget day runs midnight to midnight IST.
"""
import logging
import os
import time
from contextvars import ContextVar
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException
from sqlalchemy import func
from starlette.concurrency import run_in_threadpool

from core.dashboard_state import estimate_cost_usd, usage_tokens
from core.security import require_auth
from database import get_session
from models.db_models import LlmUsage
from services.entitlement_service import get_effective_tier
from services.llm_utils import SONNET_MODEL

logger = logging.getLogger(__name__)

_ctx_user: ContextVar[int | None] = ContextVar("llm_user", default=None)
_ctx_feature: ContextVar[str | None] = ContextVar("llm_feature", default=None)

_IST = timezone(timedelta(hours=5, minutes=30))
_DEFAULT_USER_CAP_USD = {"free": 0.25, "pro": 1.0, "super_pro": 3.0}
_GLOBAL_TTL_SEC = 60.0
# ponytail: per-process 60 s memo, so N workers may overshoot the cap by up to a minute of spend.
# No lock on purpose: a lock held across the DB read would be inherited locked by a job process
# forked mid-refresh (job_manager uses fork) and deadlock it. Racing threads just refresh twice.
_global_cache: tuple[float, float] | None = None  # (time.monotonic() of the read, spend today)

_PAUSED_DETAIL = "AI features are temporarily paused. Please try again later."


class LlmBudgetExceeded(RuntimeError):
    """Today's total LLM spend reached LLM_GLOBAL_DAILY_BUDGET_USD."""


def bind(user_id: int | None, feature: str | None) -> None:
    """Attribute the LLM calls made from this context (request, thread copy or job process)."""
    _ctx_user.set(user_id)
    _ctx_feature.set(feature)


def current_feature() -> str | None:
    return _ctx_feature.get()


def cost_usd(model: str | None, usage) -> float:
    """USD cost of one call. Unknown models are priced as Sonnet so they never under-count."""
    inp, out, cache_read, cache_write = usage_tokens(usage)

    def price(input_tokens: int, output_tokens: int) -> float:
        cost = estimate_cost_usd(model, input_tokens, output_tokens)
        return cost if cost is not None else estimate_cost_usd(SONNET_MODEL, input_tokens, output_tokens) or 0.0

    # Anthropic bills cache reads at 0.1x and cache writes at 1.25x the input rate.
    return price(inp, out) + 0.1 * price(cache_read, 0) + 1.25 * price(cache_write, 0)


def record_usage(feature: str, model: str | None, usage) -> None:
    """Append one ledger row, attributed to the user bound in this context (None for system jobs)."""
    inp, out, cache_read, cache_write = usage_tokens(usage)
    with get_session() as session:
        session.add(LlmUsage(
            user_id=_ctx_user.get(),
            feature=feature[:64],
            model=(model or "unknown")[:80],
            input_tokens=inp,
            output_tokens=out,
            cache_read_tokens=cache_read,
            cache_write_tokens=cache_write,
            cost_usd=cost_usd(model, usage),
        ))
        session.commit()


def _env_usd(name: str, default: float) -> float:
    return float(os.getenv(name) or default)


def _spend_today(user_id: int | None = None) -> float:
    """USD spent since midnight IST by one user, or by everyone when user_id is None."""
    start = datetime.now(_IST).replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)
    with get_session() as session:
        query = session.query(func.coalesce(func.sum(LlmUsage.cost_usd), 0.0)).filter(LlmUsage.created_at >= start)
        if user_id is not None:
            query = query.filter(LlmUsage.user_id == user_id)
        return float(query.scalar() or 0.0)


def assert_global_budget() -> None:
    """Raise LlmBudgetExceeded once everyone's spend today reaches LLM_GLOBAL_DAILY_BUDGET_USD.

    An unreadable ledger is logged and lets the call through, so a DB hiccup does not
    switch off every AI feature.
    """
    global _global_cache
    cached = _global_cache
    now = time.monotonic()
    if cached is None or now - cached[0] > _GLOBAL_TTL_SEC:
        try:
            cached = (now, _spend_today())
        except Exception as e:
            logger.warning("LLM global budget check skipped, ledger unreadable: %s", e)
            return
        _global_cache = cached  # one atomic assignment
    spend = cached[1]
    cap = _env_usd("LLM_GLOBAL_DAILY_BUDGET_USD", 25.0)
    if spend >= cap:
        logger.warning("LLM global daily budget reached: $%.2f of $%.2f", spend, cap)
        raise LlmBudgetExceeded("Daily AI budget reached")


def check_global_budget() -> None:
    """HTTP form of assert_global_budget: 503 while the global daily cap is spent."""
    try:
        assert_global_budget()
    except LlmBudgetExceeded:
        raise HTTPException(status_code=503, detail=_PAUSED_DETAIL)


def check_user_budget(user_id: int) -> None:
    """429 once the user's spend today reaches LLM_USER_DAILY_BUDGET_USD_<TIER>."""
    tier = get_effective_tier(user_id)
    cap = _env_usd(f"LLM_USER_DAILY_BUDGET_USD_{tier.upper()}",
                   _DEFAULT_USER_CAP_USD.get(tier, _DEFAULT_USER_CAP_USD["free"]))
    # ponytail: check-then-spend, so concurrent requests from one user can all pass the
    # check and overshoot the cap by their combined cost; upgrade path: atomic reservation.
    if _spend_today(user_id) >= cap:
        raise HTTPException(status_code=429, detail={
            "error_code": "AI_QUOTA_EXCEEDED",
            "error_title": "Daily AI Limit Reached",
            "error_detail": "You have used today's AI allowance. It resets at midnight IST.",
        })


def guard(user_id: int, feature: str) -> None:
    """Attribute this context's LLM calls to user_id, then refuse if a daily budget is spent."""
    bind(user_id, feature)
    check_global_budget()
    check_user_budget(user_id)


def require_llm_budget(feature: str):
    """FastAPI dependency for paid routes: 401 without a valid token, 503/429 over budget.
    Returns the authenticated user_id."""
    async def _dependency(user_id: int = Depends(require_auth)) -> int:
        await run_in_threadpool(guard, user_id, feature)  # DB reads off the event loop
        bind(user_id, feature)  # guard bound a thread copy; bind the request context the endpoint runs in
        return user_id
    return _dependency
