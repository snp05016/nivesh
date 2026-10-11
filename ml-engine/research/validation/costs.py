"""Cost model ``nse_delivery_2026_v1`` and the daily-path portfolio test (spec 5.5).

Construction:
- Signal on the last session of each month (scores and membership read on that
  session), execution at the close of the next session (t+1).
- Equal weight across the top quintile of in-universe names with a valid price
  at the execution close.
- h = 21: one book rebalanced every month. h = 63: three tranches of one third;
  tranche k rebalances at month-ends whose calendar month index is k (mod 3).
  Months before every tranche has traded once are dropped (ramp-up).
- Holdings drift daily on ``px_idx``; a holding without a price (delisted,
  suspended) sits as cash at its last valid price until the next rebalance.
- Turnover = sum |w_target - w_drifted| at each execution, in whole-portfolio
  weight. Costs are per side on |delta w| (buy and sell rates differ) plus
  one-way slippage by 63-day median ADV, scaled by ``slippage_mult``.
- Active = net - the equal-weight buy-and-hold of the same universe over the
  same dates (no costs). Taxes are excluded (disclosed in the report).

All returns in the output are fractions per rebalance month, not percent.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np
import numpy.typing as npt
import pandas as pd

from .. import config

_C = config.COSTS


@dataclass(frozen=True)
class CostModel:
    """Indian delivery equity costs; rates are fractions of traded value per side."""

    model_id: str
    stt_rate: float
    stamp_duty_buy_rate: float
    exchange_rate: float
    sebi_rate: float
    gst_rate: float
    dp_charge_inr_per_sell: float
    ticket_inr: float
    slippage_bp_by_adv_cr: tuple[tuple[float, float], ...]

    @property
    def regulatory_rate(self) -> float:
        """Exchange + SEBI charges plus GST on both."""
        base = self.exchange_rate + self.sebi_rate
        return base * (1.0 + self.gst_rate)

    @property
    def buy_rate(self) -> float:
        return self.stt_rate + self.stamp_duty_buy_rate + self.regulatory_rate

    @property
    def sell_rate(self) -> float:
        """Includes the DP charge spread over the reference ticket."""
        return self.stt_rate + self.regulatory_rate + self.dp_charge_inr_per_sell / self.ticket_inr

    def slippage_bp(self, adv_cr: float) -> float:
        """One-way slippage for a 63-day median ADV in INR crore (unknown ADV: the worst row)."""
        if adv_cr is not None and math.isfinite(adv_cr):
            for threshold, bp in self.slippage_bp_by_adv_cr:
                if adv_cr > threshold:
                    return bp
        return self.slippage_bp_by_adv_cr[-1][1]

    def round_trip_inr(self, notional_inr: float, slippage_bp: float = 0.0) -> float:
        """Buy then sell ``notional_inr`` as one order each (the DP charge is per sell order)."""
        slip = 2.0 * notional_inr * slippage_bp * 1e-4
        pct = notional_inr * (2.0 * self.stt_rate + self.stamp_duty_buy_rate + 2.0 * self.regulatory_rate)
        return pct + self.dp_charge_inr_per_sell + slip


nse_delivery_2026_v1 = CostModel(
    model_id=config.COST_MODEL_VERSION,
    stt_rate=_C["stt_rate"],
    stamp_duty_buy_rate=_C["stamp_duty_buy_rate"],
    exchange_rate=_C["exchange_rate"],
    sebi_rate=_C["sebi_rate"],
    gst_rate=_C["gst_rate"],
    dp_charge_inr_per_sell=_C["dp_charge_inr_per_sell"],
    ticket_inr=_C["ticket_inr"],
    slippage_bp_by_adv_cr=tuple(tuple(r) for r in _C["slippage_bp_by_adv_cr"]),
)


def _wide(x: pd.DataFrame | pd.Series) -> pd.DataFrame:
    """Accept a (date x entity) frame or a Series indexed by (date, entity_id)."""
    if isinstance(x, pd.Series):
        x = x.unstack(level=1)
    out = x.copy()
    out.index = pd.DatetimeIndex(out.index)
    return out.sort_index()


@dataclass
class _Trade:
    pos: int  # execution session index
    tranche: int
    target: npt.NDArray[np.float64]  # weights within the tranche (sum 1 or 0)
    bench: npt.NDArray[np.float64]  # equal weights over the eligible universe
    slip: npt.NDArray[np.float64]  # one-way slippage fraction per name


def portfolio_returns(
    scores: pd.DataFrame | pd.Series,
    px_idx_daily: pd.DataFrame | pd.Series,
    membership: pd.DataFrame | pd.Series,
    adv: pd.DataFrame | pd.Series,
    h: int,
    slippage_mult: float = 1.0,
    *,
    top_fraction: float = _C["top_fraction"],
    cost_model: CostModel = nse_delivery_2026_v1,
) -> pd.DataFrame:
    """Monthly ``[gross, net, turnover, active]`` indexed by execution date (spec 5.5).

    Inputs are (date x entity_id) frames or (date, entity_id) Series: ``scores``
    (higher = preferred), daily ``px_idx`` (NaN when not validly traded),
    ``membership`` (bool, in U_t), ``adv`` (63-day median value traded, INR crore).
    Row p covers execution p to execution p+1: gross is the market move of the
    book after trading; net also pays the trade at execution p; turnover is that
    trade's sum |delta w|. The incomplete last period is not returned.
    """
    if h not in config.HORIZONS:
        raise ValueError(f"h must be one of {config.HORIZONS}")
    n_tranches = 1 if h == 21 else int(_C["h63_tranches"])
    px = _wide(px_idx_daily)
    cols = px.columns
    sessions = pd.DatetimeIndex(px.index)
    n_sess, n_names = px.shape
    valid = px.notna().to_numpy()
    pxf = px.ffill().to_numpy(dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        growth = pxf[1:] / pxf[:-1]
    growth = np.where(np.isfinite(growth), growth, 1.0)  # no price -> held as cash

    sc = _wide(scores).reindex(index=sessions, columns=cols)
    mem = _wide(membership).reindex(index=sessions, columns=cols).fillna(False).astype(bool)
    advw = _wide(adv).reindex(index=sessions, columns=cols)

    cal = sessions.to_series().dt
    month = (cal.year * 12 + cal.month).to_numpy()
    trades: list[_Trade] = []
    for i in np.flatnonzero(month[:-1] != month[1:]):  # last session of each month with a t+1
        e = int(i) + 1
        s_row = sc.iloc[i].to_numpy(dtype=float)
        if not np.isfinite(s_row).any():
            continue
        universe = mem.iloc[i].to_numpy() & valid[e]
        elig = np.flatnonzero(universe & np.isfinite(s_row))
        target = np.zeros(n_names)
        if len(elig):
            n_top = max(1, int(round(top_fraction * len(elig))))
            picks = elig[np.argsort(-s_row[elig], kind="stable")[:n_top]]
            target[picks] = 1.0 / n_top
        bench = universe / universe.sum() if universe.any() else np.zeros(n_names)
        a_row = advw.iloc[i].to_numpy(dtype=float)
        slip = np.array([cost_model.slippage_bp(a) for a in a_row]) * 1e-4 * slippage_mult
        trades.append(_Trade(e, int(month[i] % n_tranches), target, bench, slip))

    cols_out = ["gross", "net", "turnover", "active"]
    if len(trades) < 2:
        return pd.DataFrame(columns=cols_out, index=pd.DatetimeIndex([], name="exec_date"), dtype=float)

    hold = np.zeros((n_tranches, n_names))
    cash = np.full(n_tranches, 1.0 / n_tranches)
    v_before, v_after, turnover = [], [], []
    t = trades[0].pos
    for tr in trades:
        while t < tr.pos:  # drift every holding through each session up to this execution
            hold *= growth[t]
            t += 1
        total = hold.sum() + cash.sum()
        k = tr.tranche
        v_k = hold[k].sum() + cash[k]
        delta = (tr.target * v_k - hold[k]) / total  # whole-portfolio weights
        buys, sells = np.clip(delta, 0, None), np.clip(-delta, 0, None)
        cost = float(buys @ (cost_model.buy_rate + tr.slip) + sells @ (cost_model.sell_rate + tr.slip))
        v_k_after = v_k - cost * total
        if tr.target.any():
            hold[k], cash[k] = tr.target * v_k_after, 0.0
        else:
            hold[k], cash[k] = 0.0, v_k_after
        v_before.append(total)
        v_after.append(total - cost * total)
        turnover.append(float(np.abs(delta).sum()))

    rows = []
    for p in range(len(trades) - 1):
        a, b = trades[p], trades[p + 1]
        with np.errstate(divide="ignore", invalid="ignore"):
            rel = np.where(a.bench > 0, pxf[b.pos] / pxf[a.pos], 0.0)
        bench_ret = float(a.bench @ np.nan_to_num(rel, nan=1.0)) - 1.0 if a.bench.any() else 0.0
        net = v_before[p + 1] / v_before[p] - 1.0
        rows.append((sessions[a.pos], v_before[p + 1] / v_after[p] - 1.0, net, turnover[p], net - bench_ret))
    out = pd.DataFrame(rows, columns=["exec_date", *cols_out]).set_index("exec_date")
    return out.iloc[n_tranches - 1 :]
