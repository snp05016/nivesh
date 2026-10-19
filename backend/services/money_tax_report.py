"""Financial-year capital-gains working for listed shares (I29, spec 3.7).

Informational only: a working from the user's Nivesh transactions, not tax advice and not a
filing. Mutual funds are not covered in v1. Lots come from FIFO matching of the ledger
(money_tax_lots); the 31-Jan-2018 value for grandfathering comes from the research engine in one
batched call per report and only while its numbers may be shown. Nothing here calls an LLM.
"""
from __future__ import annotations

import csv
import io
from collections import defaultdict
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Optional

from core.timeutil import ist_today
from database import get_session
from models.db_models import Portfolio, Transaction
from services import ledger_service, money_market_series
from services.money_tax_lots import Match, Row, TaxLedgerError, fifo_match
from services.money_tax_rules import (
    GRANDFATHER_LAST_ACQ, LTCG, RULES_VERSION, STCG, fy_bounds, grandfathered_cost, is_long_term,
    ltcg_exemption, rate_period, section,
)

SCOPE_NOTE = "Listed shares only. Mutual funds are not covered yet."
DISCLAIMER = (
    "Informational working from your Nivesh transactions. Not tax advice. Set-off of losses, surcharge, cess and "
    "slab-rate income are not applied. Verify with a chartered accountant before filing."
)
_TWO = Decimal("0.01")
_PERIODS = ("pre_2024_07_23", "post_2024_07_23")


def _money(value: Decimal) -> float:
    return float(value.quantize(_TWO, rounding=ROUND_HALF_UP))


def _qty(value: Decimal) -> float:
    return float(round(value, 6))


def _load(user_id: int) -> tuple[dict[str, list[Row]], dict[str, dict[str, Any]]]:
    with get_session() as session:
        txs = (
            session.query(Transaction)
            .filter(Transaction.user_id == user_id, Transaction.asset_class == "EQ", Transaction.transaction_type != "DIVIDEND")
            .order_by(Transaction.date, Transaction.id)
            .all()
        )
        by_ticker: dict[str, list[Row]] = defaultdict(list)
        for t in txs:
            by_ticker[str(t.ticker)].append(Row(
                id=int(t.id), date=t.date or t.created_at, type=str(t.transaction_type), quantity=float(t.quantity or 0.0),
                price=float(t.price or 0.0), fees=float(t.fees or 0.0), notes=t.notes,
                import_batch_id=t.import_batch_id, ticker=str(t.ticker),
            ))
        holdings = {
            str(h.ticker): {"name": str(h.company_name or h.ticker), "purchase_date": h.purchase_date}
            for h in session.query(Portfolio).filter(Portfolio.user_id == user_id, Portfolio.group_name == "holdings").all()
        }
    return by_ticker, holdings


def _opening_date(holding: Optional[dict[str, Any]]) -> Optional[date]:
    if not holding:
        return None
    try:
        parsed = ledger_service.parse_trade_date(holding.get("purchase_date"))
    except ValueError:
        return None
    return parsed.date() if parsed else None


def _looks_like_etf(ticker: str, name: str) -> bool:
    # ponytail: name heuristic until instruments are typed
    return "ETF" in name.upper() or ticker.upper().endswith(("BEES", "IETF"))


def _fmv_highs(tickers: list[str]) -> dict[str, dict[str, Any]]:
    """The raw 31-Jan-2018 high per ticker; {} when the engine's numbers may not be shown."""
    if not tickers or not money_market_series.display_allowed():
        return {}
    items = [{"key": t, "symbol": t, "isin": None, "date": GRANDFATHER_LAST_ACQ.isoformat()} for t in tickers]
    return money_market_series.raw_highs(items) or {}


def capital_gains(user_id: int, fy: str) -> dict[str, Any]:
    """The FY report for `fy` ('2025-26'). ValueError for a bad FY label."""
    start, end = fy_bounds(fy)
    by_ticker, holdings = _load(user_id)

    in_year: list[tuple[str, str, Match, list[Row]]] = []   # (ticker, name, match, ticker rows)
    not_computed: list[dict[str, Any]] = []
    for ticker, rows in sorted(by_ticker.items()):
        name = (holdings.get(ticker) or {}).get("name") or ticker
        try:
            matches, _open = fifo_match(rows, opening_balance_date=_opening_date(holdings.get(ticker)))
        except TaxLedgerError:
            for r in rows:
                sold = ist_today(r.date)
                if r.type.upper() == "SELL" and start <= sold <= end:
                    not_computed.append({"symbol": ticker, "sold_on": sold.isoformat(), "quantity": r.quantity,
                                         "reason": "ledger_inconsistent"})
            continue
        for m in matches:
            if start <= m.sold_on <= end:
                in_year.append((ticker, name, m, rows))

    computable: list[tuple[str, str, Match, list[Row]]] = []
    for item in in_year:
        ticker, name, m, _rows = item
        reason = None
        if m.lot.uncertain or m.lot.acquired_on is None:
            reason = "acquisition_date_uncertain"
        elif _looks_like_etf(ticker, name):
            reason = "etf_category_unverified"
        if reason:
            not_computed.append({"symbol": ticker, "sold_on": m.sold_on.isoformat(), "quantity": _qty(m.quantity), "reason": reason})
        else:
            computable.append(item)

    grandfathered = sorted({t for t, _n, m, _r in computable if m.lot.acquired_on <= GRANDFATHER_LAST_ACQ})  # type: ignore[operator]
    highs = _fmv_highs(grandfathered)

    out_rows: list[dict[str, Any]] = []
    for ticker, name, m, rows in computable:
        acquired = m.lot.acquired_on
        assert acquired is not None
        actual = m.quantity * m.lot.unit_cost
        fmv_per_unit: Optional[Decimal] = None
        fmv_total: Optional[Decimal] = None
        cost_used = actual
        reasons: list[str] = list(m.lot.review)
        if acquired <= GRANDFATHER_LAST_ACQ:
            high = highs.get(ticker)
            if not high or high.get("status") != "ok" or not high.get("high"):
                not_computed.append({"symbol": ticker, "sold_on": m.sold_on.isoformat(), "quantity": _qty(m.quantity),
                                     "reason": "fmv_unavailable"})
                continue
            fmv_per_unit = Decimal(str(high["high"])) / m.lot.split_factor_after_2018
            fmv_total = fmv_per_unit * m.quantity
            cost_used = grandfathered_cost(actual, fmv_total, m.sale_value)
            reasons.append("fmv_nse_high")
        if m.lot.auto_split:
            reasons.append("corporate_action_review")
        if any(r.type.upper() == "BUY" and ist_today(r.date) == m.sold_on and not ledger_service.is_opening_balance(r) for r in rows):
            reasons.append("possible_intraday")
        term = LTCG if is_long_term(acquired, m.sold_on) else STCG
        gain = m.sale_value - cost_used - m.transfer_expenses
        unique = list(dict.fromkeys(reasons))
        out_rows.append({
            "term": term, "section": section(term, m.sold_on), "rate_period": rate_period(m.sold_on),
            "symbol": ticker, "name": name, "quantity": _qty(m.quantity),
            "acquired_on": acquired.isoformat(), "sold_on": m.sold_on.isoformat(),
            "sale_value_inr": _money(m.sale_value), "cost_of_acquisition_inr": _money(actual),
            "fmv_per_unit": None if fmv_per_unit is None else _money(fmv_per_unit),
            "fmv_total_inr": None if fmv_total is None else _money(fmv_total),
            "cost_used_inr": _money(cost_used), "transfer_expenses_inr": _money(m.transfer_expenses),
            "gain_inr": _money(gain), "needs_review": bool(unique), "review_reasons": unique,
            "_gain": gain,
        })

    out_rows.sort(key=lambda r: (r["sold_on"], r["symbol"], r["acquired_on"]))
    not_computed.sort(key=lambda r: (r["sold_on"], r["symbol"], r["reason"]))

    def total(term: str, period: str) -> float:
        return _money(sum((r["_gain"] for r in out_rows if r["term"] == term and r["rate_period"] == period), Decimal(0)))

    net_ltcg = sum((r["_gain"] for r in out_rows if r["term"] == LTCG), Decimal(0))
    exemption = ltcg_exemption(fy)
    summary = {
        "stcg": {p: total(STCG, p) for p in _PERIODS},
        "ltcg": {p: total(LTCG, p) for p in _PERIODS},
        "ltcg_exemption_limit_inr": _money(exemption),
        "ltcg_above_exemption_inr": _money(max(Decimal(0), net_ltcg - exemption)),
        "rows": len(out_rows), "not_computed": len(not_computed),
        "needs_review": sum(1 for r in out_rows if r["needs_review"]),
    }
    for r in out_rows:
        del r["_gain"]
    return {
        "fy": fy, "rules_version": RULES_VERSION, "as_of": ist_today().isoformat(),
        "summary": summary,
        "rows": out_rows, "not_computed": not_computed, "scope_note": SCOPE_NOTE, "disclaimer": DISCLAIMER,
    }


CSV_HEADER = [
    "fy", "term", "section", "rate_period", "symbol", "name", "quantity", "acquired_on", "sold_on", "sale_value_inr",
    "cost_of_acquisition_inr", "fmv_31jan2018_per_unit", "fmv_total_inr", "cost_used_inr", "transfer_expenses_inr",
    "gain_inr", "needs_review", "review_reasons",
]


def _num(value: Optional[float]) -> str:
    return "" if value is None else f"{value:.2f}"


def capital_gains_csv(report: dict[str, Any]) -> str:
    """The report as CSV: a comment line, a header, computed rows, then not-computed rows."""
    fy = report["fy"]
    buf = io.StringIO()
    buf.write(f"# Nivesh capital gains working FY {fy} (rules {RULES_VERSION}). Listed shares only. "
              "Informational only; verify with a chartered accountant.\n")
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(CSV_HEADER)
    for r in report["rows"]:
        writer.writerow([
            fy, r["term"], r["section"], r["rate_period"], r["symbol"], r["name"], r["quantity"], r["acquired_on"],
            r["sold_on"], _num(r["sale_value_inr"]), _num(r["cost_of_acquisition_inr"]), _num(r["fmv_per_unit"]),
            _num(r["fmv_total_inr"]), _num(r["cost_used_inr"]), _num(r["transfer_expenses_inr"]), _num(r["gain_inr"]),
            "true" if r["needs_review"] else "false", ";".join(r["review_reasons"]),
        ])
    for n in report["not_computed"]:
        writer.writerow([fy, "", "", "", n["symbol"], "", n["quantity"], "", n["sold_on"], "", "", "", "", "", "", "",
                         "true", n["reason"]])
    return buf.getvalue()
