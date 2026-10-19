"""Decision journal scored against the Nifty 50 (C16, spec 3.4).

BUY/SELL entries are compared with the Nifty 50 price index over 21 and 63 sessions from the
closing price on the day of the entry. Numbers come from the research engine's series route
(``money_market_series``) and are stored once per horizon in ``trade_journal.market_score``.
Shown only while the engine is fully on; nothing here calls an LLM.
"""
from __future__ import annotations

import math
import statistics
import threading
import time
from datetime import timedelta
from typing import Any, Iterable, Optional

from core.feature_flags import is_enabled
from core.timeutil import ist_today
from database import get_session
from models.db_models import TradeJournal
from services import money_market_series

HORIZONS = {21: "1 month", 63: "3 months"}
FINAL = {"ok", "unknown_symbol", "no_data"}
SCORED_ACTIONS = ("BUY", "SELL")
THROTTLE_SECONDS = 600
BENCHMARK_LABEL = money_market_series.BENCHMARK_LABEL

_lock = threading.Lock()
_last_run: dict[int, float] = {}
_last_result: dict[int, Optional[int]] = {}  # per user: rows written by the last run, None = engine unreachable


def engine_unreachable(user_id: int) -> bool:
    with _lock:
        return user_id in _last_result and _last_result[user_id] is None


def _entry_date(created_at):
    return ist_today(created_at)


def _is_final(market_score: Any, horizon: int) -> bool:
    entry = (market_score or {}).get(str(horizon)) if isinstance(market_score, dict) else None
    return isinstance(entry, dict) and entry.get("status") in FINAL


def _r2(value: Optional[float]) -> Optional[float]:
    return None if value is None else round(float(value), 2)


def _stored(action: str, result: dict[str, Any]) -> dict[str, Any]:
    status = result.get("status")
    stock, nifty = result.get("return_pct"), result.get("nifty_return_pct")
    if status == "ok" and (stock is None or nifty is None):
        status = "no_data"  # no index series: nothing to compare against
    if status != "ok":
        return {"status": status, "stock_pct": None, "nifty_pct": None, "excess_pp": None,
                "decision_excess_pp": None, "start_date": result.get("start_date"),
                "end_date": result.get("end_date"), "stale_exit": None}
    excess = round(float(stock) - float(nifty), 2)
    return {"status": "ok", "stock_pct": _r2(stock), "nifty_pct": _r2(nifty), "excess_pp": excess,
            "decision_excess_pp": excess if action == "BUY" else round(-excess, 2),
            "start_date": result.get("start_date"), "end_date": result.get("end_date"),
            "stale_exit": bool(result.get("stale_exit"))}


def score_pending(user_id: int, limit: int = 200) -> int:
    """Score this user's due BUY/SELL entries. Returns the number of final horizons written."""
    if not is_enabled("money_journal_scoring") or not money_market_series.display_allowed():
        return 0
    with _lock:
        now = time.monotonic()
        last = _last_run.get(user_id)
        if last is not None and now - last < THROTTLE_SECONDS:
            return 0
        _last_run[user_id] = now
    today = ist_today()
    with get_session() as session:
        rows = (
            session.query(TradeJournal)
            .filter(TradeJournal.user_id == user_id, TradeJournal.action.in_(SCORED_ACTIONS))
            .order_by(TradeJournal.id.desc())
            .all()
        )
        items: list[dict[str, Any]] = []
        for row in rows:
            if row.created_at is None:
                continue
            entry_date = _entry_date(row.created_at)
            for horizon in HORIZONS:
                if _is_final(row.market_score, horizon):
                    continue
                if entry_date + timedelta(days=math.ceil(horizon * 7 / 5)) > today:
                    continue
                items.append({"key": f"j{row.id}:{horizon}", "symbol": row.ticker,
                              "start": entry_date, "sessions": horizon})
                if len(items) >= limit:
                    break
            if len(items) >= limit:
                break
        if not items:
            with _lock:
                _last_result[user_id] = 0
            return 0
        results = money_market_series.window_returns(items)
        if results is None:
            with _lock:
                _last_result[user_id] = None
            return 0
        by_id = {int(r.id): r for r in rows}
        written = 0
        for item in items:
            result = results.get(item["key"])
            if not result or result.get("status") not in FINAL:
                continue
            row = by_id[int(item["key"][1:].split(":")[0])]
            if _is_final(row.market_score, item["sessions"]):
                continue
            merged = dict(row.market_score or {})
            merged[str(item["sessions"])] = _stored(row.action, result)
            row.market_score = merged
            written += 1
        session.commit()
    with _lock:
        _last_result[user_id] = written
    return written


def _median(values: list[float]) -> Optional[float]:
    return round(statistics.median(values), 2) if values else None


def _horizon_stats(rows: Iterable[Any], horizon: int) -> dict[str, Any]:
    scored = pending = 0
    decisions: list[float] = []
    by_action: dict[str, dict[str, Any]] = {a: {"scored": 0, "decisions": []} for a in SCORED_ACTIONS}
    for row in rows:
        if row.action not in SCORED_ACTIONS:
            continue
        entry = (row.market_score or {}).get(str(horizon)) if isinstance(row.market_score, dict) else None
        if not isinstance(entry, dict) or entry.get("status") not in FINAL:
            pending += 1
            continue
        decision = entry.get("decision_excess_pp")
        if entry.get("status") != "ok" or decision is None:
            continue
        scored += 1
        decisions.append(float(decision))
        by_action[row.action]["scored"] += 1
        by_action[row.action]["decisions"].append(float(decision))
    return {
        "sessions": horizon, "label": HORIZONS[horizon], "scored": scored, "pending": pending,
        "favourable": sum(1 for d in decisions if d > 0), "median_decision_excess_pp": _median(decisions),
        "by_action": {
            a: {"scored": v["scored"], "favourable": sum(1 for d in v["decisions"] if d > 0),
                "median_decision_excess_pp": _median(v["decisions"])}
            for a, v in by_action.items()
        },
    }


def market_block(rows: list[Any], available: bool, reason: Optional[str]) -> dict[str, Any]:
    """The ``market`` object of the stats response, built only from stored scores."""
    if not available:
        return {"available": False, "reason": reason, "benchmark_label": BENCHMARK_LABEL, "as_of": None,
                "horizons": [], "entries": {}}
    horizons = [_horizon_stats(rows, h) for h in HORIZONS]
    entries = {str(r.id): r.market_score for r in rows
               if r.action in SCORED_ACTIONS and isinstance(r.market_score, dict) and r.market_score}
    as_of = max(
        (e.get("end_date") for ms in entries.values() for e in ms.values()
         if isinstance(e, dict) and e.get("status") == "ok" and e.get("end_date")),
        default=None,
    )
    has_any = any(h["scored"] or h["pending"] for h in horizons)
    return {"available": has_any, "reason": None, "benchmark_label": BENCHMARK_LABEL, "as_of": as_of,
            "horizons": horizons if has_any else [], "entries": entries if has_any else {}}


def market_status(user_id: int, rows: list[Any]) -> tuple[bool, Optional[str]]:
    """(available, reason) before the numbers are looked at."""
    if not is_enabled("money_journal_scoring"):
        return False, "flag_off"
    if not money_market_series.display_allowed():
        return False, "engine_not_live"
    any_scored = any(
        isinstance(r.market_score, dict) and any(isinstance(e, dict) and e.get("status") == "ok" for e in r.market_score.values())
        for r in rows
    )
    if engine_unreachable(user_id) and not any_scored:
        return False, "engine_unreachable"
    return True, None


def has_pending(rows: list[Any]) -> bool:
    return any(
        r.action in SCORED_ACTIONS and any(not _is_final(r.market_score, h) for h in HORIZONS)
        for r in rows
    )


def should_score(rows: list[Any]) -> bool:
    """True when a background scoring pass could change what the user sees."""
    return is_enabled("money_journal_scoring") and money_market_series.display_allowed() and has_pending(rows)
