"""Oriented factor profile for one stock (spec 4.8, contract 6.2 ``factor_profile``).

Metric pctl = universe percentile of ``DISPLAY_ORIENTATION[f] * raw``, so the
percentile follows the displayed number. Family pctl = universe percentile of
the mean of a stock's oriented member pctls. Model features are unchanged.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from datetime import date

import numpy as np
import pandas as pd

from .contract import FAMILY_LABELS, Fact, FactorFamily, FactorMetric, FactorProfile, ReasonCode, Unit
from .features import DISPLAY_ORIENTATION, FEATURE_VERSION, FEATURES, universe_pct
from .formatting import make_fact

__all__ = ["FAMILY_LABELS", "METRICS", "display_value", "factor_profile"]


def _simple_pct(x: float) -> float:
    return math.expm1(x) * 100.0


def _times_100(x: float) -> float:
    return x * 100.0


# feature_id -> (label, unit, decimals, signed, raw -> displayed value). The
# labels and formats are the ones the contract fixtures show (export_contract).
METRICS: dict[str, tuple[str, Unit, int, bool, Callable[[float], float]]] = {
    "mom_12_1": ("Price return from 12 months to 1 month ago", "pct", 1, True, _simple_pct),
    "mom_6_1": ("Price return from 6 months to 1 month ago", "pct", 1, True, _simple_pct),
    "mom_3_1": ("Price return from 3 months to 1 month ago", "pct", 1, True, _simple_pct),
    "mom_12_1_vs": ("12-to-1-month return per unit of volatility", "ratio", 2, True, float),
    "dist_52wh": ("Distance from the 52-week high", "pct", 1, True, _times_100),
    # rev_* are minus log returns; show the plain return (higher = rose more).
    "rev_5": ("Price return, last 5 trading days", "pct", 1, True, lambda x: _simple_pct(-x)),
    "rev_21": ("Price return, last 21 trading days", "pct", 1, True, lambda x: _simple_pct(-x)),
    "vol_21": ("Annualised volatility, last 21 trading days", "pct", 1, False, _times_100),
    "vol_63": ("Annualised volatility, last 63 trading days", "pct", 1, False, _times_100),
    "vol_252": ("Annualised volatility, last 252 trading days", "pct", 1, False, _times_100),
    "beta_252": ("Beta to the average of the 200 most-traded NSE stocks", "ratio", 2, False, float),
    "idio_vol_63": ("Stock-specific volatility, last 63 trading days", "pct", 1, False, _times_100),
    "max_ret_21": ("Largest one-day return, last 21 trading days", "pct", 1, True, _simple_pct),
    "downside_vol_63": ("Downside volatility, last 63 trading days", "pct", 1, False, _times_100),
    # log(INR) -> INR crore.
    "log_adv_63": ("Median daily value traded, last 63 trading days", "inr_cr", 1, False,
                   lambda x: math.exp(x) / 1e7),
    # exp(raw) = mean |R| per 1e9 INR (= per ₹100 crore) traded, as a fraction -> %.
    "amihud_63": ("Average price move per ₹100 crore traded", "pct", 2, False, lambda x: math.exp(x) * 100.0),
    "turnover_ratio_21_126": ("Recent value traded compared with the 6-month median", "pct", 1, True, _times_100),
    "ma50_ma200": ("50-day average price above or below the 200-day average", "pct", 1, True, _times_100),
    "rsi_14": ("Relative strength index, 14 days", "ratio", 0, False, float),
}


def display_value(feature_id: str, raw: float) -> float:
    """The number shown for a raw fv1 feature value (4.8 conversions)."""
    return METRICS[feature_id][4](raw)


def _pctl_fact(fid: str, label: str, value: float, as_of: date, reason: ReasonCode) -> Fact:
    return make_fact(fid, value, "pctl", source="computed", as_of=as_of, decimals=0, signed=False,
                     label=label, method=FEATURE_VERSION, reason=None if math.isfinite(value) else reason)


def factor_profile(raw: pd.DataFrame, membership: pd.DataFrame, entity_id: str, as_of: date) -> FactorProfile:
    """Contract factor profile of ``entity_id`` against U_{as_of}.

    ``raw`` is ``features.compute_raw`` output; ``entity_id`` is the panel key
    (resolve a symbol with ``marketdata.resolve_entity`` first; dev mode uses
    the symbol). An off-universe stock is placed against the universe
    distribution. Missing values give unavailable facts (``source_unavailable``
    when the stock or the universe has no row that day, else
    ``insufficient_history``); nothing is zero-filled.
    """
    day = pd.Timestamp(as_of)
    dates = raw.index.get_level_values("date")
    rows: pd.DataFrame = raw.loc[dates == day].droplevel("date")
    on_day = (pd.to_datetime(membership["date"]) == day) & membership["in_universe"].astype(bool)
    universe = rows.index.intersection(pd.Index(membership.loc[on_day, "entity_id"]).unique())
    has_row = entity_id in rows.index
    reason: ReasonCode = "insufficient_history" if has_row and len(universe) else "source_unavailable"

    oriented = rows[list(FEATURES)].astype(float).mul(pd.Series(DISPLAY_ORIENTATION), axis=1)
    stocks = universe.append(pd.Index([entity_id])).unique() if has_row else universe
    # Oriented pctl (0..100) of every universe member (and the stock) per feature.
    pctl = pd.DataFrame(
        {f: 100.0 * universe_pct(oriented.loc[stocks, f].to_numpy(), oriented.loc[universe, f].to_numpy())
         for f in FEATURES},
        index=stocks,
    )

    families = []
    for family, fam_label in FAMILY_LABELS.items():
        members = [f for f, fam in FEATURES.items() if fam == family]
        metrics = []
        for f in members:
            label, unit, decimals, signed, convert = METRICS[f]
            x = float(rows.at[entity_id, f]) if has_row else math.nan
            value = convert(x) if math.isfinite(x) else math.nan
            p = float(pctl.at[entity_id, f]) if has_row else math.nan
            metrics.append(FactorMetric(
                feature_id=f,
                label=label,
                value=make_fact(f"factor.{f}.value", value, unit, source="computed", as_of=as_of,
                                decimals=decimals, signed=signed, label=label, method=FEATURE_VERSION,
                                reason=None if math.isfinite(value) else reason),
                pctl=_pctl_fact(f"factor.{f}.pctl", f"{label}, percentile", p, as_of, reason),
            ))
        fam_means = pctl[members].mean(axis=1, skipna=True)  # NaN only when every member is NaN
        fam_p = math.nan
        if has_row and not math.isnan(fam_means.at[entity_id]):
            fam_p = 100.0 * float(universe_pct(np.array([fam_means.at[entity_id]]),
                                               fam_means.loc[universe].to_numpy())[0])
        families.append(FactorFamily(
            family=family,  # type: ignore[arg-type]
            label=fam_label,
            pctl=make_fact(f"factor.{family}.pctl", fam_p, source="computed", as_of=as_of,
                           method=FEATURE_VERSION, reason=None if math.isfinite(fam_p) else reason),
            metrics=metrics,
        ))
    return FactorProfile(universe_id="NSE_LIQ200", families=families)
