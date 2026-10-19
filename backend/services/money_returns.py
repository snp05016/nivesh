"""Dated cash flows and money-weighted returns: one flow builder for a holding and the portfolio (spec 3.3).

ticker_flows() turns one (user, ticker) ledger into dated flows (money in < 0):
1. The last effective ADJUST (no-op edits ignored) decides the start: a CAS
   balance -> unavailable imported_without_history; a close -> clean restart
   after it; a restatement -> restart at the edit date valued at that day's
   close (since_edit), or unavailable edited_position without a close.
2. Opening-balance / legacy-backfill BUYs are dated from the purchase date the
   user entered (user_entered_date), else unavailable start_date_unknown.
3. A holding with no ledger is one BUY of shares x buy_price under rule 2.
4. BUY -(q*p + fees), SELL +(q*p - fees), DIVIDEND +(q*p); SPLIT/BONUS none.

Returns are MATH-04's compute_benchmark (absolute under 365 days, XIRR from a
year on, Nifty 50 price index on the same flows).
"""
from __future__ import annotations

import logging
import math
from bisect import bisect_right
from collections import defaultdict
from datetime import date, datetime, timezone
from typing import Any, Optional, cast

import yfinance as yf
from sqlalchemy.orm import Session

from core.timeutil import ist_today
from database import get_session
from models.db_models import Portfolio, Transaction
from services import disk_cache, money_pricing
from services import yfinance_client as yfc
from services.ledger_service import adjust_kinds, is_opening_balance, parse_trade_date
from services.portfolio_service import compute_benchmark, compute_holding_pnl

logger = logging.getLogger(__name__)

BENCHMARK_LABEL = "Nifty 50 price index (excludes dividends)"
_NIFTY_TTL = 6 * 3600
MIN_COVERAGE_PCT = 50.0


class NoHoldings(LookupError):
    """Nothing to benchmark (router: 404)."""


class BenchmarkUnavailable(RuntimeError):
    """No holding could be priced, or the return is undefined (router: 503)."""


def fetch_nifty_closes(start: date) -> Optional[list[tuple[date, float]]]:
    """Date-sorted ^NSEI closes from the last session on or before `start`; None on failure.

    One series from 2000-01-01 is cached for 6 h and sliced per caller.
    """
    cached = disk_cache.get("money_nifty", "full")
    if not cached:
        try:
            if not yfc._yf_guard():
                return None
            hist: Any = yf.Ticker("^NSEI").history(start="2000-01-01")
            if hist is None or bool(hist.empty):
                return None
            cached = [
                [ts.date().isoformat(), float(c)] for ts, c in hist["Close"].items()
                if c is not None and math.isfinite(float(c)) and float(c) > 0
            ]
        except Exception as e:
            logger.warning("[money_returns] Nifty history unavailable: %s", type(e).__name__)
            return None
        if not cached:
            return None
        disk_cache.set("money_nifty", "full", cached, ttl=_NIFTY_TTL)
    series = [(date.fromisoformat(d), float(c)) for d, c in cached]
    i = max(bisect_right([d for d, _ in series], start) - 1, 0)
    return series[i:]


def _when(tx: Transaction) -> datetime:
    d = cast(Optional[datetime], tx.date)
    if d is None:
        return datetime.min.replace(tzinfo=timezone.utc)
    return d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d.astimezone(timezone.utc)


def _f(v) -> float:
    return float(v) if v is not None else 0.0


def _purchase_day(holding: Optional[Portfolio]) -> Optional[date]:
    if holding is None:
        return None
    try:
        parsed = parse_trade_date(cast(Optional[str], holding.purchase_date))
    except ValueError:
        return None
    return parsed.date() if parsed else None


def _unavailable(reason: str) -> dict:
    return {"flows": [], "approximate_start": False, "start_reason": None, "since": None,
            "unavailable_reason": reason}


def ticker_flows(rows: list[Transaction], holding_row: Optional[Portfolio]) -> dict:
    """One ticker's dated flows: {flows, approximate_start, start_reason, since, unavailable_reason}.

    `rows` is the (user, ticker) ledger, `holding_row` the open holdings row (or None).
    """
    rows = sorted(rows, key=lambda t: (_when(t), cast(Optional[int], t.id) or 0))
    if not rows and holding_row is not None:
        # Rule 3: a holding written before the ledger is one opening BUY.
        rows = [Transaction(ticker=holding_row.ticker, transaction_type="BUY", quantity=holding_row.shares,
                            price=holding_row.buy_price, fees=0.0, notes="Opening balance (no ledger)")]
    kinds = adjust_kinds(rows)
    flows: list[tuple[date, float]] = []
    approximate = False
    start_reason: Optional[str] = None

    last = next(
        (i for i in range(len(rows) - 1, -1, -1)
         if str(rows[i].transaction_type).upper() == "ADJUST" and kinds.get(cast(int, rows[i].id)) != "noop"),
        None,
    )
    if last is not None:
        adj = rows[last]
        if adj.import_batch_id is not None:
            return _unavailable("imported_without_history")
        if kinds.get(cast(int, adj.id)) == "restate":
            edit_day = ist_today(_when(adj))
            close = money_pricing.close_on(str(adj.ticker), edit_day)
            if close is None:
                return _unavailable("edited_position")
            flows.append((edit_day, -_f(adj.quantity) * close))
            approximate, start_reason = True, "since_edit"
        rows = rows[last + 1:]

    for tx in rows:
        kind = str(tx.transaction_type).upper()
        qty, prc, fee = _f(tx.quantity), _f(tx.price), _f(tx.fees)
        day = ist_today(_when(tx))
        if kind == "BUY":
            if is_opening_balance(tx):
                bought = _purchase_day(holding_row)
                if bought is None:
                    return _unavailable("start_date_unknown")
                day, approximate = bought, True
                start_reason = start_reason or "user_entered_date"
            flows.append((day, -(qty * prc + fee)))
        elif kind == "SELL":
            flows.append((day, qty * prc - fee))
        elif kind == "DIVIDEND":
            flows.append((day, qty * prc))
        # SPLIT / BONUS move no cash; remaining ADJUSTs are no-ops.

    return {
        "flows": flows,
        "approximate_start": approximate,
        "start_reason": start_reason,
        "since": min((d for d, _ in flows), default=None),
        "unavailable_reason": None,
    }


def holding_return(tf: dict, terminal_value: Optional[float], as_of: date) -> dict:
    """The holding detail 'returns' block (spec 3.2) from ticker_flows() and the current value."""
    since = tf.get("since")
    block = {
        "basis": "unavailable", "value_pct": None, "nifty_same_flows_pct": None, "nifty_available": False,
        "since": since.isoformat() if since else None, "period_days": None,
        "approximate_start": bool(tf.get("approximate_start")), "start_reason": tf.get("start_reason"),
        "unavailable_reason": tf.get("unavailable_reason"), "benchmark_label": BENCHMARK_LABEL,
    }
    if block["unavailable_reason"]:
        return block
    if terminal_value is None:
        block["unavailable_reason"] = "price_unavailable"
        return block
    flows = tf["flows"]
    if not any(cf < 0 for _, cf in flows):
        return block
    try:
        r = compute_benchmark(flows, terminal_value, fetch_nifty_closes(min(d for d, _ in flows)), as_of)
    except ValueError as e:  # XIRR found no root
        logger.info("[money_returns] holding return undefined: %s", e)
        return block
    block.update(
        basis=r["return_basis"], value_pct=r["portfolio_cagr_pct"], nifty_same_flows_pct=r["nifty_cagr_pct"],
        nifty_available=r["nifty_cagr_pct"] is not None, period_days=r["period_days"],
    )
    return block


def portfolio_cash_flows(session: Session, user_id: int, quotes: dict):
    """(flows, terminal_value, excluded, approximate_start, coverage_pct, funds_excluded).

    Stocks only in v1: open EQ holdings plus EQ tickers with ledger rows (closed
    positions add their realised flows). An unpriced or undatable ticker adds
    neither flows nor value; coverage_pct = included value / value of all EQ
    holdings (unpriced at cost). `quotes` is {ticker: PriceQuote}.
    """
    holdings = (
        session.query(Portfolio).execution_options(include_mf=True)
        .filter(Portfolio.user_id == user_id, Portfolio.group_name == "holdings")
        .all()
    )
    real = [h for h in holdings if not cast(bool, h.is_virtual)]
    funds_excluded = any(str(h.asset_class) == "MF" for h in real)
    # ponytail: a closed paper position (no row left) can't be told apart from a real one;
    # its ledger joins the real flows. Mark ledger rows virtual if that matters.
    virtual = {str(h.ticker) for h in holdings if cast(bool, h.is_virtual)}
    eq_open = {str(h.ticker): h for h in real if str(h.asset_class) == "EQ" and _f(h.shares) > 0}
    ledger: dict[str, list[Transaction]] = defaultdict(list)
    for tx in session.query(Transaction).filter(
        Transaction.user_id == user_id, Transaction.asset_class == "EQ"
    ).all():
        if str(tx.ticker) not in virtual:
            ledger[str(tx.ticker)].append(tx)

    flows: list[tuple[date, float]] = []
    excluded: list[dict] = []
    terminal = eq_value = 0.0
    approximate = False
    for ticker in sorted(set(eq_open) | set(ledger)):
        h = eq_open.get(ticker)
        value = 0.0
        if h is not None:
            q = quotes.get(ticker)
            price = q.price if q is not None else None
            pnl = compute_holding_pnl(_f(h.shares), _f(h.buy_price), price, None)
            eq_value += pnl["current_value_inr"]
            if not price:
                excluded.append({"ticker": ticker, "reason": "price_unavailable"})
                continue
            value = pnl["current_value_inr"]
        tf = ticker_flows(ledger.get(ticker, []), h)
        if tf["unavailable_reason"]:
            excluded.append({"ticker": ticker, "reason": tf["unavailable_reason"]})
            continue
        if not tf["flows"]:
            continue
        flows.extend(tf["flows"])
        terminal += value
        approximate = approximate or tf["approximate_start"]
    if eq_value > 0:
        coverage = round(terminal / eq_value * 100, 1)
    else:
        coverage = 100.0 if flows else 0.0
    return flows, round(terminal, 2), excluded, approximate, coverage, funds_excluded


def portfolio_benchmark(user_id: int) -> dict:
    """GET /portfolio/benchmark body: MATH-04 keys plus coverage and exclusions (spec 3.3).

    Raises NoHoldings when there is nothing to benchmark and BenchmarkUnavailable
    when no holding is priced or the return is undefined.
    """
    with get_session() as session:
        tickers = [str(t) for (t,) in session.query(Portfolio.ticker).filter(
            Portfolio.user_id == user_id, Portfolio.group_name == "holdings",
            Portfolio.is_virtual == False,  # noqa: E712
            Portfolio.asset_class == "EQ", Portfolio.shares > 0,
        ).all()]
    quotes = money_pricing.price_quotes([(t, "EQ") for t in tickers])
    with get_session() as session:
        flows, terminal, excluded, approximate, coverage, funds = portfolio_cash_flows(session, user_id, quotes)

    if not tickers and not funds and not flows and not excluded:
        raise NoHoldings("No holdings to benchmark")
    if tickers and not any(quotes.get(t) is not None and quotes[t].price for t in tickers):
        raise BenchmarkUnavailable("no holding is priced")

    body: dict = {
        "portfolio_cagr_pct": None, "nifty_cagr_pct": None, "alpha_pct": None,
        "return_basis": "unavailable", "period_days": None,
        "portfolio_cagr": None, "benchmark_cagr": None, "alpha": None,
        "tracking_error": None, "information_ratio": None,
        "earliest_holding_date": None, "current_portfolio_value": terminal,
        "unpriced_tickers": [e["ticker"] for e in excluded if e["reason"] == "price_unavailable"],
        "excluded_tickers": excluded, "benchmark_label": BENCHMARK_LABEL,
        "approximate_start": approximate, "coverage_pct": coverage, "funds_excluded": funds,
        "unavailable_reason": None, "nifty_available": False,
    }
    if not flows:
        body["unavailable_reason"] = "no_dated_holdings"
        return body
    if coverage < MIN_COVERAGE_PCT:
        body["unavailable_reason"] = "insufficient_history"
        return body
    earliest = min(d for d, _ in flows)
    try:
        result = compute_benchmark(flows, terminal, fetch_nifty_closes(earliest), ist_today())
    except ValueError as e:  # no investment flow, or XIRR with no root
        raise BenchmarkUnavailable(str(e)) from e
    body.update(result)
    body["earliest_holding_date"] = earliest.isoformat()
    body["nifty_available"] = result["nifty_cagr_pct"] is not None
    return body
