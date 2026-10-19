"""Money I30: one dated flow builder for holding and portfolio returns (spec 3.3).

Pure flow rules on transient ORM rows, then portfolio_cash_flows / portfolio_benchmark
on an in-memory SQLite database. Prices, past closes and Nifty are stubbed: no network.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models.db_models import Base, Portfolio, Transaction
from services import money_pricing, money_returns
from services.money_pricing import PriceQuote
from services.money_returns import holding_return, portfolio_cash_flows, ticker_flows
from services.portfolio_service import compute_benchmark

UID = 1
TODAY = money_returns.ist_today()


def _tx(id_, kind, q, p, when, fees=0.0, notes=None, batch=None, ticker="INFY"):
    return Transaction(
        id=id_, user_id=UID, ticker=ticker, transaction_type=kind, quantity=q, price=p, fees=fees,
        date=when, notes=notes, import_batch_id=batch, asset_class="EQ",
    )


def _holding(ticker="INFY", shares=10.0, buy=100.0, purchase_date=None, asset_class="EQ"):
    return Portfolio(
        user_id=UID, ticker=ticker, company_name=f"{ticker} Ltd", shares=shares, buy_price=buy,
        purchase_date=purchase_date, group_name="holdings", asset_class=asset_class, is_virtual=False,
    )


def _at(y, m, d):
    return datetime(y, m, d, 6, 0)  # naive UTC, 11:30 IST: same calendar day


@pytest.fixture()
def no_close(monkeypatch):
    calls = []
    monkeypatch.setattr(money_pricing, "close_on", lambda t, d: calls.append((t, d)))
    return calls


# ---------------------------------------------------------------------------
# ticker_flows rules
# ---------------------------------------------------------------------------

def test_flow_signs_include_fees_and_dividends(no_close):
    rows = [
        _tx(1, "BUY", 10, 100.0, _at(2024, 1, 1), fees=20.0),
        _tx(2, "SELL", 4, 150.0, _at(2024, 6, 1), fees=10.0),
        _tx(3, "DIVIDEND", 6, 5.0, _at(2024, 7, 1)),
        _tx(4, "SPLIT", 2, 0.0, _at(2024, 8, 1)),
        _tx(5, "BONUS", 1, 0.0, _at(2024, 9, 1)),
    ]
    tf = ticker_flows(rows, _holding(shares=13))

    assert tf["flows"] == [(date(2024, 1, 1), -1020.0), (date(2024, 6, 1), 590.0), (date(2024, 7, 1), 30.0)]
    assert tf["unavailable_reason"] is None
    assert tf["approximate_start"] is False and tf["start_reason"] is None
    assert tf["since"] == date(2024, 1, 1)


@pytest.mark.parametrize("notes", ["Opening balance (pre-ledger holding)", "Legacy migration backfill"])
def test_opening_balance_is_dated_from_purchase_date(notes, no_close):
    rows = [_tx(1, "BUY", 10, 100.0, _at(2026, 10, 1), notes=notes)]

    tf = ticker_flows(rows, _holding(purchase_date="2023-05-10"))

    assert tf["flows"] == [(date(2023, 5, 10), -1000.0)]
    assert tf["approximate_start"] is True
    assert tf["start_reason"] == "user_entered_date"


@pytest.mark.parametrize("notes", ["Opening balance (pre-ledger holding)", "legacy migration backfill"])
@pytest.mark.parametrize("purchase_date", [None, "", "not-a-date"])
def test_opening_balance_without_purchase_date_is_unavailable(notes, purchase_date, no_close):
    rows = [_tx(1, "BUY", 10, 100.0, _at(2026, 10, 1), notes=notes)]

    tf = ticker_flows(rows, _holding(purchase_date=purchase_date))

    assert tf["unavailable_reason"] == "start_date_unknown"
    assert tf["flows"] == []


def test_ledgerless_holding_is_one_dated_buy(no_close):
    tf = ticker_flows([], _holding(shares=4, buy=250.0, purchase_date="2024-03-05"))
    assert tf["flows"] == [(date(2024, 3, 5), -1000.0)]
    assert tf["start_reason"] == "user_entered_date"

    assert ticker_flows([], _holding())["unavailable_reason"] == "start_date_unknown"


def test_noop_adjust_is_ignored(no_close):
    """A target- or notes-only edit restates the same shares at the same average cost."""
    rows = [
        _tx(1, "BUY", 10, 100.0, _at(2024, 1, 1), fees=20.0),
        _tx(2, "ADJUST", 10, 102.0, _at(2025, 2, 1)),  # WAC incl. fees
    ]
    tf = ticker_flows(rows, _holding(buy=102.0))

    assert tf["flows"] == [(date(2024, 1, 1), -1020.0)]
    assert tf["start_reason"] is None
    assert no_close == []


def test_close_then_buy_counts_only_the_later_buy(no_close):
    rows = [
        _tx(1, "BUY", 10, 100.0, _at(2024, 1, 1)),
        _tx(2, "ADJUST", 0, 0.0, _at(2024, 6, 1)),
        _tx(3, "BUY", 5, 200.0, _at(2025, 1, 1)),
    ]
    tf = ticker_flows(rows, _holding(shares=5, buy=200.0))

    assert tf["flows"] == [(date(2025, 1, 1), -1000.0)]
    assert tf["approximate_start"] is False


def test_restate_restarts_at_edit_day_close(monkeypatch):
    calls = []
    monkeypatch.setattr(money_pricing, "close_on", lambda t, d: (calls.append((t, d)), 150.0)[1])
    rows = [
        _tx(1, "BUY", 10, 100.0, _at(2024, 1, 1)),
        _tx(2, "ADJUST", 12, 110.0, datetime(2025, 3, 2, 20, 0)),  # 3 Mar 01:30 IST
        _tx(3, "SELL", 2, 160.0, _at(2025, 4, 1)),
    ]
    tf = ticker_flows(rows, _holding(shares=10, buy=110.0))

    assert calls == [("INFY", date(2025, 3, 3))]  # the IST date of the edit
    assert tf["flows"] == [(date(2025, 3, 3), -(12 * 150.0)), (date(2025, 4, 1), 320.0)]
    assert tf["start_reason"] == "since_edit"
    assert tf["approximate_start"] is True
    assert tf["since"] == date(2025, 3, 3)


def test_restate_without_close_is_edited_position(no_close):
    rows = [_tx(1, "BUY", 10, 100.0, _at(2024, 1, 1)), _tx(2, "ADJUST", 12, 110.0, _at(2025, 3, 3))]

    tf = ticker_flows(rows, _holding(shares=12, buy=110.0))

    assert tf["unavailable_reason"] == "edited_position"
    assert tf["flows"] == []


def test_cas_balance_is_imported_without_history(no_close):
    rows = [_tx(1, "ADJUST", 123.456, 40.5, _at(2026, 10, 8), batch=17, ticker="INF179K01VC4")]

    tf = ticker_flows(rows, _holding(ticker="INF179K01VC4", shares=123.456, buy=40.5, asset_class="MF"))

    assert tf["unavailable_reason"] == "imported_without_history"
    assert no_close == []


# ---------------------------------------------------------------------------
# holding_return
# ---------------------------------------------------------------------------

def _tf(flows, **kw):
    base = {"flows": flows, "approximate_start": False, "start_reason": None,
            "since": min(d for d, _ in flows) if flows else None, "unavailable_reason": None}
    return {**base, **kw}


def test_under_a_year_is_absolute_and_missing_nifty_is_flagged(monkeypatch):
    monkeypatch.setattr(money_returns, "fetch_nifty_closes", lambda _start: None)
    start = TODAY - timedelta(days=100)

    r = holding_return(_tf([(start, -1000.0)]), 1100.0, TODAY)

    assert r["basis"] == "absolute"
    assert r["value_pct"] == 10.0
    assert r["period_days"] == 100
    assert r["nifty_available"] is False and r["nifty_same_flows_pct"] is None
    assert r["since"] == start.isoformat()
    assert r["benchmark_label"] == "Nifty 50 price index (excludes dividends)"


def test_holding_return_with_nifty(monkeypatch):
    start = TODAY - timedelta(days=100)
    monkeypatch.setattr(money_returns, "fetch_nifty_closes", lambda _s: [(start, 100.0), (TODAY, 105.0)])

    r = holding_return(_tf([(start, -1000.0)]), 1100.0, TODAY)

    assert r["nifty_available"] is True
    assert r["nifty_same_flows_pct"] == 5.0


def test_over_a_year_is_xirr(monkeypatch):
    monkeypatch.setattr(money_returns, "fetch_nifty_closes", lambda _s: None)
    start = TODAY - timedelta(days=730)

    r = holding_return(_tf([(start, -100.0)]), 121.0, TODAY)

    assert r["basis"] == "annualized_xirr"
    assert r["value_pct"] == pytest.approx(10.0, abs=0.1)


def test_unpriced_or_undatable_holding_has_no_return(monkeypatch):
    monkeypatch.setattr(money_returns, "fetch_nifty_closes", lambda _s: pytest.fail("no fetch"))

    r = holding_return(_tf([(TODAY, -100.0)]), None, TODAY)
    assert (r["basis"], r["unavailable_reason"], r["value_pct"]) == ("unavailable", "price_unavailable", None)

    r = holding_return(_tf([], unavailable_reason="edited_position"), 100.0, TODAY)
    assert (r["basis"], r["unavailable_reason"]) == ("unavailable", "edited_position")


# ---------------------------------------------------------------------------
# portfolio_cash_flows / portfolio_benchmark
# ---------------------------------------------------------------------------

@pytest.fixture()
def db(monkeypatch):
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    @contextmanager
    def _get_session():
        session = Session()
        try:
            yield session
        finally:
            session.close()

    monkeypatch.setattr(money_returns, "get_session", _get_session)
    session = Session()
    yield session
    session.close()
    engine.dispose()


def _seed_clean_and_edited(db):
    db.add_all([
        _holding("CLEAN", shares=10, buy=100.0),
        _holding("EDIT", shares=20, buy=60.0),
        _tx(None, "BUY", 10, 100.0, _at(2024, 1, 1), ticker="CLEAN"),
        _tx(None, "BUY", 10, 50.0, _at(2024, 1, 1), ticker="EDIT"),
        _tx(None, "ADJUST", 20, 60.0, _at(2025, 1, 1), ticker="EDIT"),
    ])
    db.commit()


QUOTES = {"CLEAN": PriceQuote(130.0, None, "live", None), "EDIT": PriceQuote(70.0, None, "live", None)}


def test_portfolio_excludes_an_edited_holding_from_flows_and_value(db, no_close):
    _seed_clean_and_edited(db)

    flows, terminal, excluded, approx, coverage, funds = portfolio_cash_flows(db, UID, QUOTES)

    assert flows == [(date(2024, 1, 1), -1000.0)]
    assert terminal == 1300.0  # EDIT's 1,400 is left out
    assert excluded == [{"ticker": "EDIT", "reason": "edited_position"}]
    assert coverage == round(1300 / 2700 * 100, 1)
    assert approx is False and funds is False
    clean_alone = compute_benchmark([(date(2024, 1, 1), -1000.0)], 1300.0, None, TODAY)
    assert compute_benchmark(flows, terminal, None, TODAY)["portfolio_cagr_pct"] == clean_alone["portfolio_cagr_pct"]


def test_portfolio_unpriced_holding_is_excluded(db, no_close):
    _seed_clean_and_edited(db)

    _, terminal, excluded, _, _, _ = portfolio_cash_flows(db, UID, {"EDIT": QUOTES["EDIT"]})

    assert {"ticker": "CLEAN", "reason": "price_unavailable"} in excluded
    assert terminal == 0.0


def test_portfolio_counts_closed_positions_and_flags_funds(db, no_close):
    db.add_all([
        _holding("CLEAN", shares=10, buy=100.0),
        _holding("INF179K01VC4", shares=50, buy=40.0, asset_class="MF"),
        _tx(None, "BUY", 10, 100.0, _at(2024, 1, 1), ticker="CLEAN"),
        _tx(None, "BUY", 5, 200.0, _at(2024, 2, 1), ticker="SOLD"),
        _tx(None, "SELL", 5, 260.0, _at(2024, 9, 1), ticker="SOLD"),
    ])
    db.commit()

    flows, terminal, excluded, _, coverage, funds = portfolio_cash_flows(db, UID, {"CLEAN": QUOTES["CLEAN"]})

    assert funds is True
    assert (date(2024, 9, 1), 1300.0) in flows  # realised SELL of a closed position
    assert terminal == 1300.0 and coverage == 100.0
    assert all(e["ticker"] != "INF179K01VC4" for e in excluded)


def test_benchmark_hides_return_below_half_coverage(db, no_close, monkeypatch):
    _seed_clean_and_edited(db)
    monkeypatch.setattr(money_pricing, "price_quotes", lambda rows: {t: QUOTES[t] for t, _ in rows})
    monkeypatch.setattr(money_returns, "fetch_nifty_closes", lambda _s: pytest.fail("no Nifty needed"))

    body = money_returns.portfolio_benchmark(UID)

    assert body["return_basis"] == "unavailable"
    assert body["unavailable_reason"] == "insufficient_history"
    assert body["coverage_pct"] < 50
    assert body["portfolio_cagr_pct"] is None
    assert body["excluded_tickers"] == [{"ticker": "EDIT", "reason": "edited_position"}]
    assert body["benchmark_label"] == money_returns.BENCHMARK_LABEL


def test_benchmark_without_nifty_is_200_shape(db, no_close, monkeypatch):
    db.add_all([_holding("CLEAN", shares=10, buy=100.0), _tx(None, "BUY", 10, 100.0, _at(2024, 1, 1), ticker="CLEAN")])
    db.commit()
    monkeypatch.setattr(money_pricing, "price_quotes", lambda rows: {t: QUOTES[t] for t, _ in rows})
    monkeypatch.setattr(money_returns, "fetch_nifty_closes", lambda _s: None)

    body = money_returns.portfolio_benchmark(UID)

    assert body["return_basis"] == "annualized_xirr"
    assert body["nifty_available"] is False and body["nifty_cagr_pct"] is None
    assert body["portfolio_cagr_pct"] is not None
    assert body["earliest_holding_date"] == "2024-01-01"
    assert body["unpriced_tickers"] == [] and body["funds_excluded"] is False


def test_benchmark_only_funds_is_no_dated_holdings(db, no_close, monkeypatch):
    db.add(_holding("INF179K01VC4", shares=50, buy=40.0, asset_class="MF"))
    db.commit()
    monkeypatch.setattr(money_pricing, "price_quotes", lambda rows: {})

    body = money_returns.portfolio_benchmark(UID)

    assert body["unavailable_reason"] == "no_dated_holdings"
    assert body["funds_excluded"] is True


def test_benchmark_errors(db, no_close, monkeypatch):
    monkeypatch.setattr(money_pricing, "price_quotes", lambda rows: {})
    with pytest.raises(money_returns.NoHoldings):
        money_returns.portfolio_benchmark(UID)

    db.add(_holding("CLEAN", shares=10, buy=100.0, purchase_date="2024-01-01"))
    db.commit()
    with pytest.raises(money_returns.BenchmarkUnavailable):  # nothing priced
        money_returns.portfolio_benchmark(UID)


def test_nav_status_windows():
    friday = date(2026, 10, 2)
    assert money_pricing.nav_status(friday, date(2026, 10, 8)) == "nav"  # Thu: 4 weekdays
    assert money_pricing.nav_status(friday, date(2026, 10, 9)) == "stale"  # Fri: 5 weekdays, 7 days
    assert money_pricing.nav_status(friday, date(2026, 10, 10)) == "unavailable"
    assert money_pricing.nav_status(None, date(2026, 10, 8)) == "unavailable"
