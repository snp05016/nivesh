"""
Currency-commodity spillover confidence modifier.

Deterministic modifier mirroring the monsoon modifier pattern:
  - USD/INR weakness → boost IT/pharma (export) confidence
  - USD/INR strength → penalise IT/pharma confidence
  - Crude oil spike  → penalise OMC/aviation/paint confidence
  - Crude oil drop   → boost OMC/aviation/logistics confidence

Uses yfinance for INR=X (USD/INR) and CL=F (crude) trend data.
Sector mapping is hardcoded (same approach as monsoon modifier).
"""
from __future__ import annotations
import logging
from typing import Any

from services.math_engines.protocol import InferenceEngine

logger = logging.getLogger(__name__)

# Sector sensitivity to USD/INR moves
# Positive = benefits from INR weakness (exporters)
# Negative = hurt by INR weakness (importers)
_USDINR_SENSITIVITY = {
    "IT": 0.08,
    "PHARMA": 0.06,
    "CHEMICALS": 0.04,
    "TEXTILES": 0.05,
    "AUTO": -0.03,
    "OIL & GAS": -0.06,
    "AVIATION": -0.07,
    "PAINT": -0.03,
    "FMCG": -0.02,
}

# Sector sensitivity to crude oil moves
# Positive = benefits from crude drop
# Negative = hurt by crude spike
_CRUDE_SENSITIVITY = {
    "OIL & GAS": -0.08,
    "OMC": -0.10,
    "AVIATION": -0.08,
    "PAINT": -0.05,
    "LOGISTICS": -0.04,
    "CHEMICALS": -0.04,
    "POWER": -0.03,
    "IT": 0.0,
    "PHARMA": 0.0,
}


class CurrencyCommodityEngine(InferenceEngine):

    @classmethod
    def name(cls) -> str:
        return "currency_commodity_spillover"

    @classmethod
    def tags(cls) -> set[str]:
        return {"confidence_modifier", "macro"}

    def compute(self, ticker: str, data: dict, session: Any = None) -> dict:
        """Compute currency/commodity spillover confidence modifier.

        data keys:
          - sector (str): stock's sector (e.g. "IT", "PHARMA", "OIL & GAS")
          - lookback_days (int, default 30): trend window
        """
        sector = (data.get("sector") or "").upper().strip()
        if not sector:
            return {
                "status": "ok",
                "output": {
                    "modifier": 0.0,
                    "reason": "No sector provided, no spillover adjustment.",
                },
            }

        lookback = data.get("lookback_days", 30)

        try:
            usdinr_trend = _fetch_trend("INR=X", lookback)
            crude_trend = _fetch_trend("CL=F", lookback)

            # USD/INR modifier: positive usdinr_trend means INR weakening
            usdinr_sens = _USDINR_SENSITIVITY.get(sector, 0.0)
            usdinr_mod = usdinr_trend * usdinr_sens if usdinr_trend is not None else 0.0

            # Crude modifier: positive crude_trend means crude rising
            crude_sens = _CRUDE_SENSITIVITY.get(sector, 0.0)
            crude_mod = crude_trend * crude_sens if crude_trend is not None else 0.0

            total_modifier = round(usdinr_mod + crude_mod, 4)
            # Cap at ±15% to prevent macro shocks from dominating
            total_modifier = max(-0.15, min(0.15, total_modifier))

            components = {}
            if usdinr_trend is not None:
                components["usdinr"] = {
                    "trend_pct": round(usdinr_trend, 2),
                    "sector_sensitivity": usdinr_sens,
                    "modifier": round(usdinr_mod, 4),
                }
            if crude_trend is not None:
                components["crude_oil"] = {
                    "trend_pct": round(crude_trend, 2),
                    "sector_sensitivity": crude_sens,
                    "modifier": round(crude_mod, 4),
                }

            return {
                "status": "ok",
                "output": {
                    "modifier": total_modifier,
                    "sector": sector,
                    "components": components,
                    "description": _describe(sector, total_modifier, usdinr_trend, crude_trend),
                },
            }

        except Exception as e:
            logger.warning("[currency_commodity] error: %s", e)
            return {
                "status": "ok",
                "output": {
                    "modifier": 0.0,
                    "reason": f"Could not fetch macro data: {e}",
                },
            }


def _fetch_trend(symbol: str, lookback_days: int) -> float | None:
    """Fetch percentage change over lookback_days for a yfinance symbol."""
    try:
        import yfinance as yf

        period = f"{lookback_days}d" if lookback_days <= 30 else f"{lookback_days // 30}mo"
        hist = yf.download(symbol, period=period, auto_adjust=True, progress=False)
        if hist is None or len(hist) < 2:
            return None
        start = float(hist["Close"].iloc[0])
        end = float(hist["Close"].iloc[-1])
        if start <= 0:
            return None
        return round(((end - start) / start) * 100, 2)
    except Exception:
        return None


def _describe(sector: str, modifier: float, usdinr: float | None, crude: float | None) -> str:
    parts = []
    if usdinr is not None:
        direction = "weakening" if usdinr > 0 else "strengthening"
        parts.append(f"INR {direction} ({usdinr:+.1f}%)")
    if crude is not None:
        direction = "rising" if crude > 0 else "falling"
        parts.append(f"crude {direction} ({crude:+.1f}%)")

    if not parts:
        return f"No macro data available for {sector}."

    effect = "positive" if modifier > 0 else ("negative" if modifier < 0 else "neutral")
    return f"Macro spillover for {sector}: {', '.join(parts)} → {effect} ({modifier:+.2%} modifier)."
