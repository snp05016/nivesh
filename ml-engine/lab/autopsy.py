"""Trade autopsy, counterfactuals and behaviour patterns for a Time Machine session.

Separates three kinds of statement and labels each:
* `knowable` — computed only from data dated on or before the entry decision (PITView).
* `hindsight` — what happened afterwards; never used to judge the decision itself.
* `counterfactual` — the same session replayed with one action changed.
Process quality is scored without looking at the outcome, so a good decision that lost
money and a bad one that made money are told apart.
"""
from __future__ import annotations

import math
from datetime import date

from .data import MarketData, PITView
from .metrics import performance
from .sim import ActionError, Order, Sim, SimConfig, Trade, replay

RISK_BUDGET = 0.02  # max equity at risk per trade, a common rule of thumb (assumption, configurable)
MAX_WEIGHT = 0.25


# ---------------------------------------------------------------- knowable at entry

def _has_thesis(order) -> bool:
    """A one-word placeholder ("test", "x") is not a reason; ask for at least two words."""
    return len(order.thesis.split()) >= 2

def entry_context(data: MarketData, symbol: str, asof: date, benchmark: str | None) -> dict:
    """Facts a trader could have seen at the close of `asof`."""
    v = PITView(data, asof)
    h = v.history(symbol)
    closes = [b.close for b in h]
    out: dict = {"asof": asof.isoformat(), "bars_available": len(h)}
    if len(closes) < 2:
        return out
    rets = [math.log(b / a) for a, b in zip(closes, closes[1:]) if a > 0 and b > 0]
    for n in (5, 20, 60):
        if len(closes) > n:
            out[f"ret_{n}d"] = round(closes[-1] / closes[-1 - n] - 1, 4)
    if len(rets) >= 20:
        sig = _sd(rets[-20:])
        out["vol_20d_daily"] = round(sig, 5)
        out["vol_20d_ann"] = round(sig * math.sqrt(252), 4)
        if "ret_5d" in out:
            out["ret_5d_z"] = round(math.log(1 + out["ret_5d"]) / (sig * math.sqrt(5)), 2) if sig else None
    hi = max(closes[-252:])
    out["dist_from_52w_high"] = round(closes[-1] / hi - 1, 4)
    vols = [b.volume for b in h[-21:-1] if b.volume > 0]
    if vols:
        out["volume_vs_20d_avg"] = round(h[-1].volume / (sum(vols) / len(vols)), 2)
    if benchmark:
        bh = v.history(benchmark)
        if len(bh) > 20:
            out["benchmark_ret_20d"] = round(bh[-1].close / bh[-21].close - 1, 4)
    out["news_visible"] = [{"date": n.published.isoformat(), "title": n.title, "source": n.source} for n in v.news(symbol, limit=5)]
    return out


def base_rate(data: MarketData, symbol: str, asof: date, horizon: int, benchmark: str | None, lookback: int = 756) -> dict | None:
    """How often, before `asof`, this stock beat the benchmark over `horizon` sessions. Uses only prior data."""
    h = PITView(data, asof).history(symbol)[-lookback:]
    if len(h) < horizon + 60 or not benchmark:
        return None
    bmap = {b.d: b.close for b in PITView(data, asof).history(benchmark)}
    wins = n = 0
    for a, b in zip(h, h[horizon:]):
        ba, bb = bmap.get(a.d), bmap.get(b.d)
        if ba and bb:
            n += 1
            wins += (b.close / a.close) > (bb / ba)
    return {"horizon": horizon, "windows": n, "beat_benchmark_share": round(wins / n, 3)} if n else None


# ---------------------------------------------------------------- per trade
def trade_autopsy(sim: Sim, t: Trade) -> dict:
    data, bench = sim.data, sim.data.benchmark
    entry_order = _order(sim, t.entry_order_id)
    exit_order = _order(sim, t.exit_order_id)
    decided = entry_order.placed or t.entry_date
    know = entry_context(data, t.symbol, decided, bench)
    eq_at_entry = next((p.equity for p in sim.equity if p.d >= t.entry_date), sim.cfg.capital)
    weight = t.qty * t.entry_cost / eq_at_entry
    risk = None
    if entry_order.planned_stop and entry_order.planned_stop < t.entry_cost:
        risk = t.qty * (t.entry_cost - entry_order.planned_stop) / eq_at_entry

    # Process checks: each uses only knowable facts and the player's own plan.
    checks = [
        _check("thesis_written", _has_thesis(entry_order), "A written reason for the trade (two words or more) was recorded."),
        _check("exit_plan", entry_order.planned_stop is not None, "A planned stop level was set before entry."),
        _check("size_within_budget", (risk is not None and risk <= RISK_BUDGET) or (risk is None and weight <= MAX_WEIGHT / 2),
               f"Risk per trade at most {RISK_BUDGET:.0%} of equity (or, without a stop, position under {MAX_WEIGHT / 2:.1%})."),
        _check("not_chasing", (know.get("ret_5d_z") or 0) < 2.0, "Entry did not follow an unusually large 5-day run (z < 2)."),
    ]
    if exit_order.order_type == "STOP" or entry_order.planned_stop is None:
        followed = True
    else:
        followed = not _breached_without_exit(data, t, entry_order.planned_stop)
    checks.append(_check("followed_plan", followed, "The position was not held through its own planned stop."))
    process = round(100 * sum(c["passed"] for c in checks) / len(checks))

    # Hindsight: what happened, and how surprising it was given what was known.
    hold_bars = [b for b in data.history(t.symbol, t.exit_date) if t.entry_date <= b.d <= t.exit_date]
    mae = min((b.low for b in hold_bars), default=t.entry_cost) / t.entry_cost - 1
    mfe = max((b.high for b in hold_bars), default=t.entry_cost) / t.entry_cost - 1
    b0, b1 = (data.bar(bench, t.entry_date), data.bar(bench, t.exit_date)) if bench else (None, None)
    bench_ret = b1.close / b0.close - 1 if b0 and b1 else None
    sig = know.get("vol_20d_daily")
    n_sess = max(len(hold_bars) - 1, 1)
    surprise = round(math.log(1 + t.ret) / (sig * math.sqrt(n_sess)), 2) if sig else None
    good_process, good_outcome = process >= 60, t.pnl > 0
    quadrant = {(True, True): "earned", (True, False): "bad_break", (False, True): "lucky", (False, False): "predictable_loss"}[(good_process, good_outcome)]
    gross = (t.exit_net - t.entry_cost) * t.qty
    fees = sum(f.charges["total"] for f in sim.fills if f.order_id in (t.entry_order_id, t.exit_order_id))
    return {
        "symbol": t.symbol, "qty": t.qty, "entry_order_id": t.entry_order_id, "exit_order_id": t.exit_order_id,
        "thesis": entry_order.thesis, "planned_stop": entry_order.planned_stop, "planned_exit": entry_order.planned_exit,
        "conviction": entry_order.conviction,
        "knowable": {**know, "position_weight": round(weight, 4), "risk_per_trade": round(risk, 4) if risk is not None else None,
                     "base_rate": base_rate(data, t.symbol, decided, max(n_sess, 5), bench)},
        "process": {"score": process, "checks": checks},
        "hindsight": {
            "entry_date": t.entry_date.isoformat(), "exit_date": t.exit_date.isoformat(), "sessions_held": n_sess,
            "return_net": round(t.ret, 4), "pnl_net": round(t.pnl, 2), "benchmark_return": _r(bench_ret),
            "excess_return": _r(t.ret - bench_ret) if bench_ret is not None else None,
            "max_adverse_excursion": round(mae, 4), "max_favourable_excursion": round(mfe, 4),
            "fees_inr": round(fees, 2), "fees_share_of_gross": round(fees / abs(gross + fees), 3) if gross + fees else None,
            "move_in_sigmas": surprise,
        },
        "verdict": {"quadrant": quadrant, "text": _verdict_text(quadrant, process, surprise)},
    }


def _verdict_text(q: str, score: int, z: float | None) -> str:
    zt = f" The move was {abs(z):.1f} standard deviations of the stock's recent daily volatility, scaled to the holding period." if z is not None else ""
    return {
        "earned": f"Process score {score}/100 and a gain: the plan and the outcome agree.{zt}",
        "bad_break": f"Process score {score}/100 but a loss. A sound process can still lose; judge the plan, not this one result.{zt}",
        "lucky": f"Process score {score}/100 yet a gain. The result came despite gaps in the process; repeating it is unlikely to pay reliably.{zt}",
        "predictable_loss": f"Process score {score}/100 and a loss: the gaps in the process were visible before entry.{zt}",
    }[q]


# ---------------------------------------------------------------- counterfactuals
def canonical(actions: list[dict]) -> list[dict]:
    """Split multi-day advances into single days so actions can be shifted precisely."""
    out = []
    for a in actions:
        if a.get("type") == "advance":
            out += [{"type": "advance", "days": 1}] * int(a.get("days", 1))
        else:
            out.append(dict(a))
    return out


def counterfactuals(cfg: SimConfig, data: MarketData, actions: list[dict], order_id: str) -> list[dict]:
    """Replay the session with the entry order `order_id` changed in one way at a time."""
    acts = canonical(actions)
    idx = _order_action_index(acts, order_id)
    base = performance(replay(cfg, data, acts))["final_equity"]
    a = acts[idx]
    variants: dict[str, list[dict]] = {
        "hold_cash": acts[:idx] + acts[idx + 1:],
        "half_size": acts[:idx] + [{**a, "qty": max(a["qty"] // 2, 1)}] + acts[idx + 1:],
        "wait_2_sessions": _shift(acts, idx, 2),
    }
    if a.get("planned_stop"):
        stop = {"type": "order", "symbol": a["symbol"], "side": "SELL", "qty": a["qty"], "order_type": "STOP", "stop": a["planned_stop"], "tif": "GTC"}
        nxt = next((i for i in range(idx + 1, len(acts)) if acts[i]["type"] == "advance"), None)
        if nxt is not None:
            variants["followed_stop_plan"] = acts[: nxt + 1] + [stop] + acts[nxt + 1:]
    out = []
    for name, va in variants.items():
        try:
            fe = performance(replay(cfg, data, va, lenient=True))["final_equity"]
            out.append({"variant": name, "final_equity": fe, "delta_vs_actual": round(fe - base, 2), "valid": True})
        except ActionError as e:  # e.g. a later sell of shares this variant never bought
            out.append({"variant": name, "valid": False, "reason": str(e)})
    return out


def _shift(acts: list[dict], idx: int, sessions: int) -> list[dict]:
    rest = acts[:idx] + acts[idx + 1:]
    seen, pos = 0, len(rest)
    for i in range(idx, len(rest)):
        if rest[i]["type"] == "advance":
            seen += 1
            if seen == sessions:
                pos = i + 1
                break
    return rest[:pos] + [acts[idx]] + rest[pos:]


def _order_action_index(acts: list[dict], order_id: str) -> int:
    n = int(order_id.lstrip("o"))
    seen = 0
    for i, a in enumerate(acts):
        if a.get("type") == "order":
            seen += 1
            if seen == n:
                return i
    raise ActionError(f"order {order_id} not found")


# ---------------------------------------------------------------- behaviour
def behaviour(sim: Sim) -> list[dict]:
    """Recurring patterns, each with the measured evidence behind it. Not a psychological diagnosis."""
    flags: list[dict] = []
    perf = performance(sim)
    sessions = max(perf["sessions"], 1)
    buys = [o for o in sim.orders if o.side == "BUY" and o.filled_qty]
    if len(sim.fills) / sessions * 20 > 8 and perf["cost_drag"] > 0.005:
        flags.append(_flag("overtrading", "medium", {"fills_per_20_sessions": round(len(sim.fills) / sessions * 20, 1), "cost_drag": perf["cost_drag"]},
                           "Frequent trading added visible cost drag. Barber & Odean (2000) found the most active retail accounts earned less after costs."))
    gains = sum(t.pnl for t in sim.trades if t.pnl > 0)
    if (gains > 0 and perf["costs_inr"] > 0.25 * gains) or perf["cost_drag"] > 0.01:
        flags.append(_flag("ignored_costs", "medium", {"costs_inr": perf["costs_inr"]}, "Charges consumed more than a quarter of gross gains, or more than 1% of starting capital."))
    max_w = _max_weight(sim)
    if max_w > 0.30:
        flags.append(_flag("concentration", "high" if max_w > 0.5 else "medium", {"max_position_weight": round(max_w, 3)}, "One position exceeded 30% of equity at a close."))
    pgr, plr, n = _odean(sim)
    if n >= 5 and pgr > plr:
        flags.append(_flag("disposition_effect", "medium", {"pgr": round(pgr, 3), "plr": round(plr, 3), "sell_days": n},
                           "Gains were realised more readily than losses (PGR > PLR, Odean 1998)."))
    chased = [o for o in buys if (entry_context(sim.data, o.symbol, o.placed or sim.clock, None).get("ret_5d_z") or 0) >= 2]
    if buys and len(chased) / len(buys) > 0.5:
        flags.append(_flag("chasing_momentum", "low", {"share_after_2sigma_run": round(len(chased) / len(buys), 2)}, "Most buys followed an unusually large 5-day run."))
    if buys and sum(not _has_thesis(o) for o in buys) / len(buys) > 0.5:
        flags.append(_flag("no_thesis", "low", {"share_without_thesis": round(sum(not _has_thesis(o) for o in buys) / len(buys), 2)}, "Most entries had no written reason."))
    breaches = [t for t in sim.trades if (o := _order(sim, t.entry_order_id)).planned_stop and _breached_without_exit(sim.data, t, o.planned_stop)]
    if breaches:
        flags.append(_flag("stop_discipline", "medium", {"trades_held_through_own_stop": len(breaches)}, "Positions were held after price traded through the stop you planned."))
    rated = [(o.conviction, t.pnl > 0) for t in sim.trades if (o := _order(sim, t.entry_order_id)).conviction is not None]
    if len(rated) >= 8:
        brier = sum((c - y) ** 2 for c, y in rated) / len(rated)
        if brier > 0.25:
            flags.append(_flag("poor_calibration", "low", {"brier": round(brier, 3), "n": len(rated)}, "Stated conviction predicted outcomes worse than a coin flip (Brier > 0.25)."))
    return flags


def _odean(sim: Sim) -> tuple[float, float, int]:
    """Proportion of gains / losses realised on days with a sale (Odean 1998)."""
    rg = pg = rl = pl = 0
    days = sorted({f.d for f in sim.fills if f.side == "SELL"})
    for d in days:
        sold = {f.symbol for f in sim.fills if f.side == "SELL" and f.d == d}
        for t in (t for t in sim.trades if t.exit_date == d):
            rg, rl = rg + (t.pnl > 0), rl + (t.pnl <= 0)
        held_after = _held_on(sim, d) - sold
        for s in held_after:
            px = sim.data.bar(s, d)
            cost = _avg_cost_on(sim, s, d)
            if px and cost:
                pg, pl = pg + (px.close > cost), pl + (px.close <= cost)
    pgr = rg / (rg + pg) if rg + pg else 0.0
    plr = rl / (rl + pl) if rl + pl else 0.0
    return pgr, plr, len(days)


def _held_on(sim: Sim, d: date) -> set[str]:
    net: dict[str, int] = {}
    for f in sim.fills:
        if f.d <= d:
            net[f.symbol] = net.get(f.symbol, 0) + (f.qty if f.side == "BUY" else -f.qty)
    return {s for s, q in net.items() if q > 0}


def _avg_cost_on(sim: Sim, s: str, d: date) -> float | None:
    buys = [f for f in sim.fills if f.symbol == s and f.side == "BUY" and f.d <= d]
    q = sum(f.qty for f in buys)
    return sum(f.qty * f.price for f in buys) / q if q else None


def _max_weight(sim: Sim) -> float:
    w = 0.0
    for p in sim.equity:
        for s in _held_on(sim, p.d):
            b = sim.data.history(s, p.d)
            net = sum((f.qty if f.side == "BUY" else -f.qty) for f in sim.fills if f.symbol == s and f.d <= p.d)
            if b and p.equity > 0:
                w = max(w, net * b[-1].close / p.equity)
    return w


def _breached_without_exit(data: MarketData, t: Trade, stop: float) -> bool:
    """True if price traded below the planned stop on a day before the actual exit day."""
    return any(b.low < stop for b in data.history(t.symbol, t.exit_date) if t.entry_date < b.d < t.exit_date)


def _order(sim: Sim, oid: str) -> Order:
    return next(o for o in sim.orders if o.id == oid)


def _check(cid: str, passed: bool, text: str) -> dict:
    return {"id": cid, "passed": bool(passed), "text": text}


def _flag(fid: str, severity: str, evidence: dict, text: str) -> dict:
    return {"id": fid, "severity": severity, "evidence": evidence, "text": text}


def _sd(xs: list[float]) -> float:
    m = sum(xs) / len(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def _r(x: float | None) -> float | None:
    return round(x, 4) if x is not None else None


__all__ = ["base_rate", "behaviour", "canonical", "counterfactuals", "entry_context", "trade_autopsy"]
