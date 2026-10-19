from datetime import date

import pytest

from lab.costs import charges
from lab.data import Bar, CorporateAction, LookaheadError, PITView
from lab.sim import ActionError, Sim, SimConfig, replay
from tests.lab.synth import make_data, weekdays


def cfg(data, **kw):
    cal = data.calendar()
    return SimConfig(start=cal[0], end=cal[-1], universe=["AAA", "BBB"], capital=kw.pop("capital", 1_000_000.0), **kw)


def equity_identity(sim: Sim) -> None:
    assert sim.equity[-1].equity == pytest.approx(sim.cash + sim.holdings_value(), abs=0.05)
    assert sim.cash >= 0
    assert all(l.qty > 0 for lots in sim.lots.values() for l in lots)


def test_market_buy_fills_next_open_with_costs():
    data = make_data()
    sim = Sim(cfg(data), data)
    d0 = sim.clock
    sim.apply({"type": "order", "symbol": "AAA", "side": "BUY", "qty": 100})
    assert not sim.fills, "an order must never fill on the bar it was placed after"
    sim.advance()
    f = sim.fills[0]
    nxt = data.bar("AAA", sim.clock)
    assert f.d > d0 and f.d == sim.clock
    assert nxt.open < f.price <= nxt.high  # paid the open plus slippage, inside the range
    assert sim.cash == pytest.approx(1_000_000 - 100 * f.price - f.charges["total"], abs=0.01)
    equity_identity(sim)


def test_pit_view_refuses_future():
    data = make_data()
    sim = Sim(cfg(data), data)
    v = sim.view()
    assert v.history("AAA")[-1].d == sim.clock
    with pytest.raises(LookaheadError):
        v.history("AAA", upto=data.calendar()[5])
    state = sim.state()
    assert all(p["d"] <= state["clock"] for p in state["equity_curve"])


def test_limit_needs_trade_through():
    data = make_data()
    sim = Sim(cfg(data), data)
    sim.apply({"type": "order", "symbol": "BBB", "side": "BUY", "qty": 10, "order_type": "LIMIT", "limit": 97})
    sim.advance()  # low == 97 exactly: touched, not traded through
    assert not sim.fills and sim.orders[0].status == "EXPIRED"
    sim.apply({"type": "order", "symbol": "BBB", "side": "BUY", "qty": 10, "order_type": "LIMIT", "limit": 98, "tif": "GTC"})
    sim.advance()
    assert sim.fills[0].price == 98.0  # filled at the limit, never better than the open allows


def test_stop_gap_fills_at_open_not_stop():
    days = weekdays(date(2021, 1, 4), 10)
    gap = [Bar(d, 100, 101, 99, 100, 1_000_000) for d in days[:3]] + [Bar(d, 80, 82, 78, 80, 1_000_000) for d in days[3:]]
    data = make_data(n=10, CCC=gap)
    sim = Sim(SimConfig(days[0], days[-1], ["CCC"]), data)
    sim.apply({"type": "order", "symbol": "CCC", "side": "BUY", "qty": 100})
    sim.advance()
    sim.apply({"type": "order", "symbol": "CCC", "side": "SELL", "qty": 100, "order_type": "STOP", "stop": 95, "tif": "GTC"})
    sim.advance(2)
    sell = [f for f in sim.fills if f.side == "SELL"][0]
    assert sell.ref_price == 80 and sell.price <= 80  # gap through the stop: filled near the open, a loss far worse than planned
    assert sim.trades[0].pnl < -1900


def test_participation_cap_partial_and_market_rest_cancelled():
    data = make_data()
    sim = Sim(cfg(data, capital=1e9), data)
    sim.apply({"type": "order", "symbol": "BBB", "side": "BUY", "qty": 80_000})  # cap = 10% of 500k = 50k
    sim.advance()
    o = sim.orders[0]
    assert o.filled_qty == 50_000 and o.status == "CANCELLED" and "liquidity" in o.reason


def test_no_short_selling():
    data = make_data()
    sim = Sim(cfg(data), data)
    with pytest.raises(ActionError, match="short selling"):
        sim.apply({"type": "order", "symbol": "AAA", "side": "SELL", "qty": 1})


def test_split_keeps_value_and_real_share_counts():
    days = weekdays(date(2021, 1, 4), 8)
    px = [Bar(d, 200, 202, 198, 200, 1_000_000) for d in days[:4]] + [Bar(d, 100, 101, 99, 100, 2_000_000) for d in days[4:]]
    data = make_data(n=8, SPL=px)
    data.actions = {"SPL": [CorporateAction("SPL", days[4], "split", factor=2.0, source="test")]}
    sim = Sim(SimConfig(days[0], days[-1], ["SPL"]), data)
    sim.apply({"type": "order", "symbol": "SPL", "side": "BUY", "qty": 101})
    sim.advance(2)
    before = sim.equity[-1].equity
    sim.advance(2)  # crosses the ex-date
    assert sim.qty("SPL") == 202
    assert sim.equity[-1].equity == pytest.approx(before, rel=1e-3)
    equity_identity(sim)


def test_dividend_credited_on_ex_date():
    data = make_data(n=10)
    days = data.calendar()
    data.actions = {"BBB": [CorporateAction("BBB", days[3], "dividend", cash_per_share=5.0, source="test")]}
    sim = Sim(cfg(data), data)
    sim.apply({"type": "order", "symbol": "BBB", "side": "BUY", "qty": 100})
    sim.advance()
    cash = sim.cash
    sim.advance(2)
    assert sim.cash == pytest.approx(cash + 500.0)


def test_locked_bar_no_fill():
    days = weekdays(date(2021, 1, 4), 5)
    locked = [Bar(days[0], 100, 101, 99, 100, 1000)] + [Bar(d, 110, 110, 110, 110, 5000) for d in days[1:]]
    data = make_data(n=5, LCK=locked)
    sim = Sim(SimConfig(days[0], days[-1], ["LCK"]), data)
    sim.apply({"type": "order", "symbol": "LCK", "side": "BUY", "qty": 10})
    sim.advance()
    assert not sim.fills and "circuit" in sim.orders[0].reason


def test_replay_is_deterministic_and_cash_never_negative():
    data = make_data()
    actions = [
        {"type": "order", "symbol": "AAA", "side": "BUY", "qty": 3000},
        {"type": "advance", "days": 3},
        {"type": "order", "symbol": "BBB", "side": "BUY", "qty": 9000, "order_type": "LIMIT", "limit": 99, "tif": "GTC"},
        {"type": "advance", "days": 2},
        {"type": "order", "symbol": "AAA", "side": "SELL", "qty": 1500},
        {"type": "advance", "days": 10},
    ]
    a, b = replay(cfg(data), data, actions).state(), replay(cfg(data), data, actions).state()
    assert a == b
    sim = replay(cfg(data), data, actions)
    equity_identity(sim)
    assert sim.trades and sim.trades[0].qty == 1500


def test_buy_reduced_to_affordable():
    data = make_data()
    sim = Sim(cfg(data, capital=10_000.0), data)
    sim.apply({"type": "order", "symbol": "BBB", "side": "BUY", "qty": 1000})
    sim.advance()
    assert 0 < sim.orders[0].filled_qty < 100
    assert sim.cash >= 0


def test_replay_reports_bad_action_index():
    data = make_data()
    with pytest.raises(ActionError, match="action 2"):
        replay(cfg(data), data, [{"type": "advance"}, {"type": "order", "symbol": "ZZZ", "side": "BUY", "qty": 1}])


def test_charges_pick_effective_row():
    old = charges("BUY", 1_00_000, date(2024, 9, 30))
    new = charges("BUY", 1_00_000, date(2024, 10, 1))
    assert old["exchange_txn"] == 3.22 and new["exchange_txn"] == 2.97
    assert old["stt"] == 100.0 and old["stamp_duty"] == 15.0
    assert charges("SELL", 1_00_000, date(2024, 10, 1))["stamp_duty"] == 0.0
