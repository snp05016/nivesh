"""COVID-2020 replay of the user's current stocks (I35, spec 3.9).

How today's holdings actually moved from 19 Feb to 23 Mar 2020, from the research engine's stored
history. Not a forecast and not a score. Stocks that were not listed in the window are not included
(no proxy return is ever invented) and funds are out of scope. Nothing here calls an LLM.
"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import date
from typing import Any, Optional

from database import get_session
from models.db_models import Portfolio
from services import disk_cache, money_market_series, money_pricing

logger = logging.getLogger(__name__)

# 21 Feb and 10 Mar 2020 were NSE holidays, so 21 sessions from 19 Feb end on 23 Mar.
SCENARIOS = {
    "covid_2020": {"label": "COVID crash", "start": date(2020, 2, 19), "end": date(2020, 3, 23), "sessions": 21},
}
CACHE_NS = "money_replay"
CACHE_TTL = 24 * 3600
NOTES = [
    "This replays how today's holdings moved in that window. It is not a forecast.",
    "Holdings not listed on 19 Feb 2020, mutual funds and holdings without a price are not included.",
    "Only stocks that still trade today are in your portfolio, so the replay can look better than what investors lived through.",
]


class ReplayUnavailable(Exception):
    """The engine cannot answer now (not live, unreachable, or its calendar disagrees)."""


def _holdings(user_id: int) -> list[dict[str, Any]]:
    with get_session() as session:
        rows = (
            session.query(Portfolio)
            .execution_options(include_mf=True)
            .filter(Portfolio.user_id == user_id, Portfolio.group_name == "holdings", Portfolio.is_virtual.is_(False))
            .all()
        )
        return [
            {"ticker": str(r.ticker), "name": str(r.company_name or r.ticker), "shares": float(r.shares or 0.0),
             "asset_class": str(r.asset_class or "EQ")}
            for r in rows if float(r.shares or 0.0) > 0
        ]


def _cache_key(user_id: int, scenario_id: str, holdings: list[dict[str, Any]]) -> str:
    digest = hashlib.sha1(json.dumps(sorted((h["ticker"], round(h["shares"], 6)) for h in holdings)).encode()).hexdigest()
    return f"{user_id}:{scenario_id}:{digest}"


def replay(user_id: int, scenario_id: str) -> dict[str, Any]:
    scenario = SCENARIOS.get(scenario_id)
    if scenario is None:
        raise ValueError(f"unknown scenario {scenario_id!r}")
    if not money_market_series.display_allowed():
        raise ReplayUnavailable("engine_not_live")

    holdings = _holdings(user_id)
    key = _cache_key(user_id, scenario_id, holdings)
    cached = disk_cache.get(CACHE_NS, key)
    if isinstance(cached, dict):
        return cached

    quotes = money_pricing.price_quotes([(h["ticker"], h["asset_class"]) for h in holdings]) if holdings else {}
    included: list[dict[str, Any]] = []
    not_included: list[dict[str, Any]] = []
    stocks: list[dict[str, Any]] = []
    for h in holdings:
        price = quotes.get(h["ticker"], money_pricing.UNAVAILABLE).price
        value = round(h["shares"] * price, 2) if price else None
        entry = {"ticker": h["ticker"], "name": h["name"], "value_inr": value}
        if h["asset_class"] == "MF":
            not_included.append({**entry, "reason": "mutual_fund"})
        elif value is None:
            not_included.append({**entry, "reason": "unpriced"})
        else:
            stocks.append(entry)

    items = [{"key": s["ticker"], "symbol": s["ticker"], "start": scenario["start"], "sessions": scenario["sessions"]}
             for s in stocks]
    results = money_market_series.window_returns(items) if items else {}
    if results is None:
        raise ReplayUnavailable("engine_unreachable")

    nifty: Optional[float] = None
    for s in stocks:
        res = results.get(s["ticker"]) or {}
        status = res.get("status")
        if status == "ok":
            if res.get("end_date") != scenario["end"].isoformat():
                logger.warning("[money_crisis_replay] calendar_mismatch")
                raise ReplayUnavailable("calendar_mismatch")
            if nifty is None and res.get("nifty_return_pct") is not None:
                nifty = float(res["nifty_return_pct"])
            if res.get("stale_exit"):
                not_included.append({**s, "reason": "not_traded_at_window_end"})
            else:
                included.append({**s, "return_pct": float(res["return_pct"])})
        elif status in ("no_data", "unknown_symbol"):
            not_included.append({**s, "reason": "listed_after_window"})
        else:
            raise ReplayUnavailable("engine_incomplete")
    if nifty is None:
        raise ReplayUnavailable("no_index_return")

    covered = sum(h["value_inr"] for h in included)
    change = sum(h["value_inr"] * h["return_pct"] / 100 for h in included)
    payload = {
        "scenario": {"id": scenario_id, "label": scenario["label"], "start": scenario["start"].isoformat(),
                     "end": scenario["end"].isoformat()},
        "nifty_return_pct": round(nifty, 1),
        "portfolio_return_pct": round(change / covered * 100, 1) if covered > 0 else None,
        "portfolio_change_inr": round(change, 2) if covered > 0 else None,
        "covered_value_inr": round(covered, 2),
        "holdings": [{"ticker": h["ticker"], "name": h["name"], "value_inr": h["value_inr"],
                      "return_pct": round(h["return_pct"], 1)} for h in included],
        "not_included": not_included,
        "notes": list(NOTES),
    }
    disk_cache.set(CACHE_NS, key, payload, ttl=CACHE_TTL)
    return payload
