"""Risk-adjusted performance for a simulation. Ranks reward process, not one lucky trade."""
from __future__ import annotations

import math

from .sim import Sim

TRADING_DAYS = 252


def _returns(xs: list[float]) -> list[float]:
    return [b / a - 1 for a, b in zip(xs, xs[1:]) if a > 0]


def _max_drawdown(xs: list[float]) -> float:
    peak, mdd = -math.inf, 0.0
    for x in xs:
        peak = max(peak, x)
        mdd = min(mdd, x / peak - 1)
    return -mdd


def performance(sim: Sim, rf_annual: float = 0.0) -> dict:
    eq = [p.equity for p in sim.equity]
    rets = _returns(eq)
    n = len(rets)
    start = sim.cfg.capital
    total = eq[-1] / start - 1
    years = max(n, 1) / TRADING_DAYS
    rf_d = (1 + rf_annual) ** (1 / TRADING_DAYS) - 1
    mean = sum(rets) / n if n else 0.0
    sd = math.sqrt(sum((r - mean) ** 2 for r in rets) / (n - 1)) if n > 1 else 0.0
    down = [min(r - rf_d, 0.0) for r in rets]
    dsd = math.sqrt(sum(d * d for d in down) / n) if n else 0.0
    sharpe = (mean - rf_d) / sd * math.sqrt(TRADING_DAYS) if sd > 0 else None
    sortino = (mean - rf_d) / dsd * math.sqrt(TRADING_DAYS) if dsd > 0 else None
    mdd = _max_drawdown(eq)

    bench = [p.benchmark for p in sim.equity]
    bench_ret = bench[-1] / bench[0] - 1 if bench and bench[0] and bench[-1] else None
    gross_traded = sum(f.qty * f.price for f in sim.fills)
    costs = sum(f.charges["total"] for f in sim.fills)
    wins = [t.pnl for t in sim.trades if t.pnl > 0]
    losses = [t.pnl for t in sim.trades if t.pnl <= 0]
    avg_equity = sum(eq) / len(eq)
    hold = [(t.exit_date - t.entry_date).days for t in sim.trades]
    excess = total - bench_ret if bench_ret is not None else None
    return {
        "start_capital": start, "final_equity": eq[-1], "total_return": round(total, 5),
        "cagr": round((1 + total) ** (1 / years) - 1, 5) if years >= 0.25 and total > -1 else None,
        "ann_vol": round(sd * math.sqrt(TRADING_DAYS), 5), "sharpe": _r(sharpe), "sortino": _r(sortino),
        "max_drawdown": round(mdd, 5), "benchmark_return": _r(bench_ret), "excess_return": _r(excess),
        "turnover_x": round(gross_traded / avg_equity, 3) if avg_equity else 0.0,
        "costs_inr": round(costs, 2), "cost_drag": round(costs / start, 5),
        "trades": len(sim.trades), "hit_rate": round(len(wins) / len(sim.trades), 3) if sim.trades else None,
        "profit_factor": round(sum(wins) / -sum(losses), 3) if losses and sum(losses) < 0 else None,
        "avg_hold_days": round(sum(hold) / len(hold), 1) if hold else None,
        "sessions": n, "score": skill_score(excess, mdd, len(sim.trades)),
    }


def skill_score(excess: float | None, mdd: float, n_trades: int, min_trades: int = 3) -> float | None:
    """Excess return per unit of drawdown (drawdown floored at 5%). None until enough trades to judge.

    Rewards beating the benchmark without large drawdowns; an all-in bet that wins once
    scores no better than a careful player with the same excess and lower drawdown.
    """
    if excess is None or n_trades < min_trades:
        return None
    return round(excess / max(mdd, 0.05), 3)


def _r(x: float | None, nd: int = 5) -> float | None:
    return round(x, nd) if x is not None else None
