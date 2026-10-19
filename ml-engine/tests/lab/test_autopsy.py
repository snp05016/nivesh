from datetime import date

import pytest

from lab.autopsy import behaviour, canonical, counterfactuals, entry_context, trade_autopsy
from lab.data import Bar, LookaheadError, PITView
from lab.metrics import performance
from lab.sim import SimConfig, replay
from tests.lab.synth import make_data, weekdays


def run(actions, data=None, capital=1_000_000.0):
    data = data or make_data(n=80)
    cal = data.calendar()
    cfg = SimConfig(cal[0], cal[-1], ["AAA", "BBB"], capital=capital)
    return cfg, data, replay(cfg, data, actions)


def test_knowable_block_uses_only_past_data(monkeypatch):
    cfg, data, sim = run([{"type": "advance", "days": 30}, {"type": "order", "symbol": "AAA", "side": "BUY", "qty": 100, "thesis": "steady uptrend", "planned_stop": 90},
                          {"type": "advance", "days": 10}, {"type": "order", "symbol": "AAA", "side": "SELL", "qty": 100}, {"type": "advance", "days": 2}])
    decided = sim.orders[0].placed
    seen: list[date] = []
    orig = PITView.history

    def spy(self, symbol, upto=None):
        rows = orig(self, symbol, upto)
        seen.extend(b.d for b in rows)
        return rows

    monkeypatch.setattr(PITView, "history", spy)
    ctx = entry_context(data, "AAA", decided, data.benchmark)
    assert seen and max(seen) <= decided
    assert ctx["asof"] == decided.isoformat()
    with pytest.raises(LookaheadError):
        PITView(data, decided).history("AAA", upto=sim.clock)


def test_autopsy_separates_process_from_outcome():
    cfg, data, sim = run([{"type": "advance", "days": 30},
                          {"type": "order", "symbol": "AAA", "side": "BUY", "qty": 100, "thesis": "trend", "planned_stop": 100},
                          {"type": "advance", "days": 10}, {"type": "order", "symbol": "AAA", "side": "SELL", "qty": 100}, {"type": "advance", "days": 2}])
    a = trade_autopsy(sim, sim.trades[0])
    assert a["hindsight"]["pnl_net"] > 0
    assert a["process"]["score"] >= 60 and a["verdict"]["quadrant"] == "earned"
    assert a["knowable"]["position_weight"] < 0.05
    # Same trade without a thesis or plan and with an oversized position: profitable but "lucky".
    cfg, data, sim2 = run([{"type": "advance", "days": 30}, {"type": "order", "symbol": "AAA", "side": "BUY", "qty": 7000},
                           {"type": "advance", "days": 10}, {"type": "order", "symbol": "AAA", "side": "SELL", "qty": 7000}, {"type": "advance", "days": 2}])
    b = trade_autopsy(sim2, sim2.trades[0])
    assert b["hindsight"]["pnl_net"] > 0 and b["verdict"]["quadrant"] == "lucky"


def test_counterfactual_hold_cash_undoes_the_trade():
    acts = [{"type": "advance", "days": 30}, {"type": "order", "symbol": "AAA", "side": "BUY", "qty": 100, "planned_stop": 120},
            {"type": "advance", "days": 10}]
    cfg, data, sim = run(acts)
    cf = {c["variant"]: c for c in counterfactuals(cfg, data, acts, "o1")}
    actual_gain = performance(sim)["final_equity"] - cfg.capital
    assert cf["hold_cash"]["delta_vs_actual"] == pytest.approx(-actual_gain, abs=0.01)
    assert cf["half_size"]["valid"] and cf["wait_2_sessions"]["valid"]
    assert "followed_stop_plan" in cf


def test_counterfactual_invalid_when_later_sell_depends_on_entry():
    acts = [{"type": "advance", "days": 30}, {"type": "order", "symbol": "AAA", "side": "BUY", "qty": 100},
            {"type": "advance", "days": 3}, {"type": "order", "symbol": "AAA", "side": "SELL", "qty": 100}, {"type": "advance", "days": 1}]
    cfg, data, _ = run(acts)
    cf = {c["variant"]: c for c in counterfactuals(cfg, data, acts, "o1")}
    assert cf["hold_cash"]["valid"] is False


def test_canonical_splits_advances():
    assert canonical([{"type": "advance", "days": 3}]) == [{"type": "advance", "days": 1}] * 3


def test_behaviour_flags_concentration_and_stop_breach():
    days = weekdays(date(2021, 1, 4), 60)
    falling = [Bar(d, 100 - i, 101 - i, 99 - i, 100 - i, 1_000_000) for i, d in enumerate(days)]
    data = make_data(n=60, AAA=falling)
    cfg, data, sim = run([{"type": "advance", "days": 25}, {"type": "order", "symbol": "AAA", "side": "BUY", "qty": 9000, "planned_stop": 70},
                          {"type": "advance", "days": 15}, {"type": "order", "symbol": "AAA", "side": "SELL", "qty": 9000}, {"type": "advance", "days": 2}], data=data)
    ids = {f["id"]: f for f in behaviour(sim)}
    assert "concentration" in ids and ids["concentration"]["evidence"]["max_position_weight"] > 0.5
    assert "stop_discipline" in ids
    a = trade_autopsy(sim, sim.trades[0])
    assert a["verdict"]["quadrant"] == "predictable_loss"
    assert not next(c for c in a["process"]["checks"] if c["id"] == "followed_plan")["passed"]
