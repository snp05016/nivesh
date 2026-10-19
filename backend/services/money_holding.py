"""Holding detail (C11, spec 3.2): position, return, ledger, dividends and journal for one holding.

Read-only and free: nothing here calls an LLM or starts an analysis.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional, cast

from core.timeutil import ist_today
from database import get_session
from models.db_models import Portfolio, TradeJournal, Transaction
from services import money_pricing
from services.ledger_service import adjust_kinds
from services.money_returns import holding_return, ticker_flows
from services.portfolio_service import compute_holding_pnl

MAX_TRANSACTIONS = 200
JOURNAL_ENTRIES = 5
_EXCERPT = 140


def _ist_date(dt: Optional[datetime]) -> Optional[str]:
    """Naive DB datetimes are UTC; the user's calendar day is IST."""
    return ist_today(dt).isoformat() if dt is not None else None


def _excerpt(text: Optional[str]) -> str:
    text = " ".join(str(text or "").split())
    return text if len(text) <= _EXCERPT else text[: _EXCERPT - 3].rstrip() + "..."


def _f(v) -> float:
    return float(v) if v is not None else 0.0


def get_holding_detail(user_id: int, ticker: str) -> Optional[dict]:
    """The holding detail payload, or None when the user holds no open position in `ticker`."""
    with get_session() as session:
        holding = (
            session.query(Portfolio).execution_options(include_mf=True)
            .filter(Portfolio.user_id == user_id, Portfolio.ticker == ticker,
                    Portfolio.group_name == "holdings", Portfolio.shares > 0)
            .first()
        )
        if holding is None:
            return None
        rows = (
            session.query(Transaction)
            .filter(Transaction.user_id == user_id, Transaction.ticker == ticker)
            .order_by(Transaction.date.asc(), Transaction.id.asc())
            .all()
        )
        journal = (
            session.query(TradeJournal)
            .filter(TradeJournal.user_id == user_id, TradeJournal.ticker == ticker)
            .order_by(TradeJournal.created_at.desc(), TradeJournal.id.desc())
            .limit(JOURNAL_ENTRIES)
            .all()
        )
        session.expunge_all()  # plain detached objects; prices are fetched after the session closes

    asset_class = str(holding.asset_class or "EQ")
    shares, avg_cost = _f(holding.shares), _f(holding.buy_price)
    quote = money_pricing.price_quotes([(ticker, asset_class)]).get(ticker, money_pricing.UNAVAILABLE)
    priced = bool(quote.price) and quote.status != "unavailable"
    pnl = compute_holding_pnl(shares, avg_cost, quote.price if priced else None, quote.prev_close,
                              quote.status if priced else None)

    kinds = adjust_kinds(rows)
    visible = [tx for tx in rows if kinds.get(cast(int, tx.id)) != "noop"]  # target/notes-only edits
    dividends = [tx for tx in rows if str(tx.transaction_type).upper() == "DIVIDEND"]

    tf = ticker_flows(rows, holding)
    returns = holding_return(tf, pnl["current_value_inr"] if priced else None, ist_today())

    return {
        "ticker": ticker,
        "name": holding.company_name or ticker,
        "asset_class": asset_class,
        "position": {
            "quantity": round(shares, 6),
            "avg_cost": round(avg_cost, 4),
            "invested_inr": pnl["invested_inr"],
            "price": round(cast(float, quote.price), 4) if priced else round(avg_cost, 4),
            "price_status": quote.status if priced else "unavailable",
            "price_as_of": quote.as_of if priced else None,
            "value_inr": pnl["current_value_inr"],
            "pnl_inr": pnl["pnl_inr"],
            "pnl_pct": pnl["pnl_pct"],
        },
        "returns": returns,
        "transactions": [
            {
                "id": tx.id,
                "type": str(tx.transaction_type).upper(),
                "quantity": _f(tx.quantity),
                "price": _f(tx.price),
                "fees": _f(tx.fees),
                "date": _ist_date(cast(Optional[datetime], tx.date)),
                "imported": tx.import_batch_id is not None,
                "notes": tx.notes or None,
            }
            for tx in reversed(visible[-MAX_TRANSACTIONS:])
        ],
        "dividends": {
            "total_inr": round(sum(_f(tx.quantity) * _f(tx.price) for tx in dividends), 2),
            "count": len(dividends),
        },
        "notes": holding.notes or "",
        "target_price": _f(holding.target_price) if holding.target_price is not None else None,
        "journal": [
            {
                "id": j.id,
                "action": str(j.action or "").upper(),
                "created_at": _ist_date(cast(Optional[datetime], j.created_at)),
                "reason_excerpt": _excerpt(cast(Optional[str], j.reason_text)),
            }
            for j in journal
        ],
        "stock_report_available": asset_class == "EQ",
    }

