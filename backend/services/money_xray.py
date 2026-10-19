"""Portfolio X-ray (I28, spec 3.5): what the user holds across stocks and funds, in plain figures.

Read-only and factual: allocation by asset type, fund-house and plan mix, concentration and
fixed-template facts. No rating, score or suggestion. Unpriced holdings are valued at cost and
listed. Fund rows are read with include_mf (this module is on the allowlist); nothing here calls an LLM.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from core.feature_flags import is_enabled
from database import get_session
from models.db_models import Portfolio
from services import money_commission, money_mf_meta, money_pricing

TOP_HOLDINGS = 10

_BUCKET_LABELS = {
    "stocks": "Stocks",
    "equity_funds": "Equity funds",
    "debt_funds": "Debt funds",
    "hybrid_funds": "Hybrid funds",
    "other_funds": "Index funds & other funds",
    "unclassified_funds": "Funds (category unknown)",
}


def _bucket(asset_class: str, info: Optional[money_mf_meta.SchemeInfo]) -> str:
    if asset_class != "MF":
        return "stocks"
    category = (info.category if info else None) or ""
    head = category.strip().lower()
    if not head:
        return "unclassified_funds"
    if head.startswith("equity"):
        return "equity_funds"
    if head.startswith("debt"):
        return "debt_funds"
    if head.startswith("hybrid"):
        return "hybrid_funds"
    return "other_funds"  # Solution Oriented and Other


def _pct(part: float, whole: float) -> float:
    return round(part / whole * 100, 1) if whole > 0 else 0.0


def _load_holdings(user_id: int) -> list[dict[str, Any]]:
    with get_session() as session:
        rows = (
            session.query(Portfolio)
            .execution_options(include_mf=True)
            .filter(Portfolio.user_id == user_id, Portfolio.group_name == "holdings", Portfolio.is_virtual.is_(False))
            .all()
        )
        return [
            {
                "ticker": str(r.ticker), "name": str(r.company_name or r.ticker), "shares": float(r.shares or 0.0),
                "buy_price": float(r.buy_price or 0.0), "asset_class": str(r.asset_class or "EQ"),
            }
            for r in rows
            if float(r.shares or 0.0) > 0
        ]


def _commission_drag(funds: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
    """Filled only while money_commission_drag is on; otherwise null."""
    if not is_enabled("money_commission_drag"):
        return None
    return money_commission.commission_drag([
        {"isin": p["ticker"], "name": p["name"], "value_inr": p["value"],
         "is_direct": p["scheme"].is_direct if p["scheme"] else None}
        for p in funds
    ])


def build_xray(user_id: int) -> dict[str, Any]:
    holdings = _load_holdings(user_id)
    quotes = money_pricing.price_quotes([(h["ticker"], h["asset_class"]) for h in holdings]) if holdings else {}
    info = money_mf_meta.scheme_info([h["ticker"] for h in holdings if h["asset_class"] == "MF"]) if holdings else {}

    positions: list[dict[str, Any]] = []
    unpriced: list[dict[str, str]] = []
    for h in holdings:
        quote = quotes.get(h["ticker"], money_pricing.UNAVAILABLE)
        scheme = info.get(h["ticker"]) if h["asset_class"] == "MF" else None
        name = (scheme.name if scheme and scheme.name else None) or h["name"]
        if quote.price:
            value = h["shares"] * quote.price
        else:
            value = h["shares"] * h["buy_price"]  # unpriced: valued at cost, never at zero
            unpriced.append({"ticker": h["ticker"], "name": name})
        positions.append({**h, "name": name, "value": value, "scheme": scheme, "bucket": _bucket(h["asset_class"], scheme)})

    total = sum(p["value"] for p in positions)
    positions.sort(key=lambda p: (-p["value"], p["ticker"]))

    allocation = []
    for key, label in _BUCKET_LABELS.items():
        value = sum(p["value"] for p in positions if p["bucket"] == key)
        if value > 0:
            allocation.append({"key": key, "label": label, "value_inr": round(value, 2), "pct": _pct(value, total)})

    funds = [p for p in positions if p["asset_class"] == "MF"]
    fund_total = sum(p["value"] for p in funds)
    amc_values: dict[str, float] = {}
    for p in funds:
        amc = (p["scheme"].amc if p["scheme"] and p["scheme"].amc else None) or "AMC unknown"
        amc_values[amc] = amc_values.get(amc, 0.0) + p["value"]
    amcs = [
        {"name": name, "value_inr": round(value, 2), "pct": _pct(value, fund_total)}
        for name, value in sorted(amc_values.items(), key=lambda kv: (-kv[1], kv[0]))
    ]

    plans: Optional[dict[str, float]] = None
    if funds and fund_total > 0:
        direct = sum(p["value"] for p in funds if p["scheme"] and p["scheme"].is_direct is True)
        regular = sum(p["value"] for p in funds if p["scheme"] and p["scheme"].is_direct is False)
        plans = {"direct_pct": _pct(direct, fund_total), "regular_pct": _pct(regular, fund_total),
                 "unknown_pct": _pct(fund_total - direct - regular, fund_total)}

    top = [
        {"ticker": p["ticker"], "name": p["name"], "asset_class": p["asset_class"],
         "value_inr": round(p["value"], 2), "pct": _pct(p["value"], total)}
        for p in positions[:TOP_HOLDINGS]
    ]
    concentration = {
        "largest_ticker": positions[0]["ticker"] if positions else None,
        "largest_pct": _pct(positions[0]["value"], total) if positions else 0.0,
        "top5_pct": _pct(sum(p["value"] for p in positions[:5]), total),
    }

    facts: list[dict[str, str]] = []
    if positions:
        facts.append({"code": "largest_holding_share",
                      "text": f"Your largest holding, {positions[0]['name']}, is {concentration['largest_pct']:.0f}% of your portfolio."})
    if len(positions) >= 5:
        facts.append({"code": "top5_share", "text": f"Your five largest holdings are {concentration['top5_pct']:.0f}% of your portfolio."})
    if plans and plans["regular_pct"] > 0:
        facts.append({"code": "regular_plan_share", "text": f"{plans['regular_pct']:.0f}% of your fund value is in regular plans."})
    if unpriced:
        facts.append({"code": "unpriced_count",
                      "text": f"{len(unpriced)} holdings have no current price and are counted at cost."})

    return {
        "as_of": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "total_value_inr": round(total, 2),
        "unpriced": unpriced,
        "allocation": allocation,
        "amcs": amcs,
        "plans": plans,
        "top_holdings": top,
        "concentration": concentration,
        "facts": facts,
        "commission_drag": _commission_drag(funds),
    }
