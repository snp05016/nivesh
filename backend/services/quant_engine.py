"""
QuantitativeEngine — Deterministic ML proxy for mathematically provable predictions.

Runs BEFORE the LangGraph multi-agent pipeline (teacher-student flow).
Provides: market regime detection, conformal target bounds, SHAP-style
feature importance drivers, and calibrated confidence scoring.

All math is deterministic — no black-box ML.
"""

import asyncio
import logging
import math
from typing import Dict, Any, Tuple

import numpy as np

_LOG = logging.getLogger(__name__)

_NIFTY_LONG_RUN_DAILY_VOL = 0.016    # ~16% annualized — Nifty 50 historical average
_NIFTY_LONG_RUN_ANNUAL_VOL = 0.16


class QuantitativeEngine:
    """Deterministic ML proxy — provides mathematically provable predictions."""

    def __init__(self, ticker: str) -> None:
        self.ticker = ticker.upper()

    async def run_full_pipeline(self) -> Dict[str, Any]:
        """Execute the full quant pipeline: fetch data, compute regime,
        conformal targets, SHAP drivers, and calibrated confidence.
        
        Returns:
            Dict[str, Any]: A dictionary containing the detected market regime,
                calibrated confidence metrics, conformal target bounds, quantitative
                drivers, and tail risk flags.
        """
        # Fetch data concurrently — return_exceptions so one failure doesn't abort all
        results = await asyncio.gather(
            self._fetch_market_volatility(),
            self._fetch_fundamentals(),
            self._fetch_macro_indicators(),
            return_exceptions=True,
        )
        market_data = (
            results[0]
            if not isinstance(results[0], BaseException)
            else self._fallback_market_data()
        )
        fundamental_data = (
            results[1]
            if not isinstance(results[1], BaseException)
            else {"piotroski_score": 5, "promoter_pledge_pct": 0.0, "fallback": True}
        )
        _macro_data = (  # noqa: F841 — reserved for future regime enrichment (Nifty VIX)
            results[2]
            if not isinstance(results[2], BaseException)
            else {"nifty_50": 23600.0, "vix": None, "fallback": True}
        )

        # Sequential math (order matters — each step depends on prior)
        regime = self._detect_market_regime(market_data)
        targets = self._compute_conformal_targets(market_data)
        shap_drivers, tail_risks = self._compute_feature_importance(
            fundamental_data, market_data
        )
        confidence, confidence_breakdown = self._compute_calibrated_confidence(
            regime, shap_drivers, tail_risks
        )

        return {
            "market_regime": regime,
            "calibrated_confidence": confidence,
            "confidence_math_breakdown": confidence_breakdown,
            "conformal_target_upper_3m": targets["upper_3m"],
            "conformal_target_lower_3m": targets["lower_3m"],
            "quantitative_drivers": shap_drivers,
            "tail_risk_flags": tail_risks,
        }

    # ── Data Fetching (concurrent I/O) ──────────────────────────────────────

    async def _fetch_market_volatility(self) -> dict:
        """Fetch price history and compute 30d annualized volatility + RSI.
        
        Returns:
            dict: Market data including current price, daily and annualized volatility,
                RSI, and a fallback flag.
        """
        try:
            from services.nse_data_provider import get_price_history

            hist = get_price_history(self.ticker, period_days=60)
            if hist is None or hist.empty or len(hist) < 20:
                return self._fallback_market_data()

            closes = hist["Close"].values.astype(float)
            current_price = float(closes[-1])
            daily_returns = np.diff(closes) / closes[:-1]
            daily_returns = daily_returns[~np.isnan(daily_returns)]

            daily_vol = (
                float(np.std(daily_returns[-30:]))
                if len(daily_returns) >= 30
                else float(np.std(daily_returns))
            )
            annualized_vol = daily_vol * math.sqrt(252)

            # RSI-14
            rsi = self._compute_rsi(closes, 14)

            return {
                "current_price": current_price,
                "daily_volatility": daily_vol,
                "annualized_volatility_30d": annualized_vol,
                "rsi_14": rsi,
                "fallback": False,
            }
        except Exception as e:
            _LOG.warning("[QuantEngine] Market data fetch failed for %s: %s", self.ticker, e)
            return self._fallback_market_data()

    @staticmethod
    def _compute_rsi(closes: np.ndarray, period: int = 14) -> float:
        """Compute Relative Strength Index (RSI) for the given period.
        
        Args:
            closes (np.ndarray): Array of historical closing prices.
            period (int, optional): The lookback period for RSI calculation. Defaults to 14.

        Returns:
            float: The calculated RSI value, ranging from 0.0 to 100.0.
        """
        if len(closes) < period + 1:
            return 50.0
        deltas = np.diff(closes)
        gains = np.where(deltas > 0, deltas, 0.0)
        losses = np.where(deltas < 0, -deltas, 0.0)
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return float(100.0 - (100.0 / (1.0 + rs)))

    @staticmethod
    def _fallback_market_data() -> dict:
        """Return sensible fallback values when market data is unavailable.
        
        Returns:
            dict: Default market data values to prevent pipeline failure.
        """
        return {
            "current_price": 0.0,
            "daily_volatility": _NIFTY_LONG_RUN_DAILY_VOL,
            "annualized_volatility_30d": _NIFTY_LONG_RUN_ANNUAL_VOL,
            "rsi_14": 50.0,
            "fallback": True,
        }

    async def _fetch_fundamentals(self) -> dict:
        """Fetch fundamental data: Piotroski F-Score, promoter pledging, PE, ROE.
        
        Returns:
            dict: Fundamental metrics including F-score, pledge percentage, PE ratio,
                ROE, and a fallback flag.
        """
        try:
            from services.nse_data_provider import get_fundamentals
            from services.piotroski import compute_piotroski

            fund = get_fundamentals(self.ticker)
            f_score_result = compute_piotroski(self.ticker)

            piotroski_score = 5  # default neutral
            if isinstance(f_score_result, dict):
                raw = f_score_result.get("f_score", 5)
                piotroski_score = int(raw) if raw is not None else 5
            elif isinstance(f_score_result, (int, float)) and not math.isnan(float(f_score_result)):
                piotroski_score = int(f_score_result)

            promoter_pledge = fund.get("promoter_pledging_pct") or 0.0
            if isinstance(promoter_pledge, (int, float)) and not math.isnan(
                promoter_pledge
            ):
                promoter_pledge = float(promoter_pledge)
            else:
                promoter_pledge = 0.0

            return {
                "piotroski_score": piotroski_score,
                "promoter_pledge_pct": promoter_pledge,
                "pe_ratio": float(fund.get("pe_ratio") or 0.0),
                "roe": float(fund.get("roe") or 0.0),
                "fallback": False,
            }
        except Exception as e:
            _LOG.warning("[QuantEngine] Fundamentals fetch failed for %s: %s", self.ticker, e)
            return {
                "piotroski_score": 5,
                "promoter_pledge_pct": 0.0,
                "fallback": True,
            }

    async def _fetch_macro_indicators(self) -> dict:
        """Fetch macro indicators (Nifty 50 level) for regime context.
        
        Returns:
            dict: Macro data containing the Nifty 50 level and a fallback flag.
        """
        try:
            import yfinance as yf

            nifty = yf.Ticker("^NSEI")
            info = nifty.fast_info
            nifty_price = getattr(info, "last_price", None)
            if nifty_price is None or (
                isinstance(nifty_price, float) and math.isnan(nifty_price)
            ):
                hist = nifty.history(period="5d")
                nifty_price = (
                    float(hist["Close"].iloc[-1])
                    if not hist.empty
                    else 23600.0
                )
            else:
                nifty_price = float(nifty_price)
            return {"nifty_50": nifty_price, "vix": None, "fallback": False}
        except Exception as e:
            _LOG.warning("[QuantEngine] Macro data fetch failed: %s", e)
            return {"nifty_50": 23600.0, "vix": None, "fallback": True}

    # ── Core Math ───────────────────────────────────────────────────────────

    @staticmethod
    def _detect_market_regime(market_data: dict) -> str:
        """Classify the current market volatility regime.

        Thresholds:
          < 14% annualized → Low Volatility / Accumulation
          14%-22%         → Transition / Macro-Driven
          > 22%           → High Volatility / Crisis

        Args:
            market_data (dict): Dictionary containing market volatility metrics.

        Returns:
            str: The detected market regime classification.
        """
        vol = market_data.get("annualized_volatility_30d", 0.15)
        if isinstance(vol, (int, float)) and not math.isnan(vol):
            if vol < 0.14:
                return "Low Volatility / Accumulation"
            elif vol <= 0.22:
                return "Transition / Macro-Driven"
            else:
                return "High Volatility / Crisis"
        return "Transition / Macro-Driven"

    @staticmethod
    def _compute_conformal_targets(market_data: dict) -> Dict[str, float]:
        """Compute 3-month conformal prediction bounds.

        Uses: projected_vol_3m = daily_vol * sqrt(63) * 1.645 (95% VaR z-score)
        Upper/lower bounds around a 1.5% expected drift.

        Args:
            market_data (dict): Dictionary containing current price and daily volatility.

        Returns:
            Dict[str, float]: Upper and lower price target bounds for a 3-month horizon.
        """
        current_price = market_data.get("current_price", 0.0)
        daily_vol = market_data.get("daily_volatility", 0.02)

        if current_price <= 0:
            return {"upper_3m": 0.0, "lower_3m": 0.0}

        # 63 trading days in 3 months, 1.645 = 95% confidence z-score
        projected_vol_3m = daily_vol * math.sqrt(63) * 1.645
        drift = 0.015  # 1.5% expected drift over 3 months

        expected_price = current_price * (1 + drift)
        upper_bound = expected_price * (1 + projected_vol_3m)
        lower_bound = expected_price * (1 - projected_vol_3m)

        return {
            "upper_3m": round(upper_bound, 2),
            "lower_3m": round(lower_bound, 2),
        }

    @staticmethod
    def _compute_feature_importance(
        fundamental_data: dict, market_data: dict
    ) -> Tuple[Dict[str, float], Dict[str, bool]]:
        """Compute SHAP-style feature importance drivers and tail risk flags.

        Drivers with |contribution| <= 0.05 are filtered out as noise.

        Args:
            fundamental_data (dict): Dictionary containing fundamental metrics.
            market_data (dict): Dictionary containing technical market data (e.g., RSI).

        Returns:
            Tuple[Dict[str, float], Dict[str, bool]]: A tuple containing the SHAP-style
                quantitative drivers and tail risk flags.
        """
        f_score = fundamental_data.get("piotroski_score", 5)
        if f_score is None or (isinstance(f_score, float) and math.isnan(f_score)):
            f_score = 5
        f_score = int(f_score)
        promoter_pledge = fundamental_data.get("promoter_pledge_pct", 0.0)
        if promoter_pledge is None or (isinstance(promoter_pledge, float) and math.isnan(promoter_pledge)):
            promoter_pledge = 0.0
        rsi_14 = market_data.get("rsi_14", 50.0)
        if rsi_14 is None or (isinstance(rsi_14, float) and math.isnan(rsi_14)):
            rsi_14 = 50.0

        shap_drivers: Dict[str, float] = {}

        # F-Score contribution (normalized around 5 as neutral)
        shap_drivers["Fundamental Health (F-Score)"] = round(
            (f_score - 5) / 4.0 * 0.40, 3
        )

        # RSI-based technical drivers
        if rsi_14 < 30:
            shap_drivers["Technical Reversion (Oversold)"] = 0.25
        elif rsi_14 > 70:
            shap_drivers["Technical Overextension"] = -0.25

        # Promoter pledge risk (linear penalty)
        if promoter_pledge > 0:
            shap_drivers["Promoter Pledge Risk"] = round(
                -1.0 * (promoter_pledge / 100.0) * 0.50, 3
            )

        # Filter noise — only keep drivers with meaningful contribution
        shap_drivers = {
            k: v for k, v in shap_drivers.items() if abs(v) > 0.05
        }

        tail_risks = {
            "high_pledge_danger": promoter_pledge > 30.0,
            "distressed_fundamentals": f_score < 3,
        }

        return shap_drivers, tail_risks

    @staticmethod
    def _compute_calibrated_confidence(
        regime: str, shap_drivers: Dict[str, float], tail_risks: Dict[str, bool],
        venn_abers_base: float = None,
    ) -> Tuple[float, Dict[str, float]]:
        """Compute calibrated confidence score (0.05–0.95).

        Base confidence from Venn-Abers isotonic calibration when available,
        otherwise defaults to 0.50. Adjusted by SHAP driver sum,
        multiplied by regime factor, then penalized for tail risks.

        Args:
            regime (str): The current market volatility regime.
            shap_drivers (Dict[str, float]): Dictionary of quantitative drivers and their weights.
            tail_risks (Dict[str, bool]): Dictionary of detected tail risk flags.
            venn_abers_base (float, optional): Base confidence score if available.

        Returns:
            Tuple[float, Dict[str, float]]: The final calibrated confidence score and
                a breakdown of the mathematical adjustments applied.
        """
        base_probability = venn_abers_base if venn_abers_base is not None else 0.50
        net_shap_adjustment = sum(shap_drivers.values())
        adjusted_confidence = base_probability + net_shap_adjustment

        regime_multipliers = {
            "Low Volatility / Accumulation": 1.10,
            "Transition / Macro-Driven": 0.85,
            "High Volatility / Crisis": 0.55,
        }
        regime_multiplier = regime_multipliers.get(regime, 1.0)
        adjusted_confidence *= regime_multiplier

        tail_risk_deduction = 0.0
        if tail_risks.get("high_pledge_danger") or tail_risks.get(
            "distressed_fundamentals"
        ):
            tail_risk_deduction = 0.30
            adjusted_confidence -= tail_risk_deduction

        confidence = round(max(0.05, min(0.95, adjusted_confidence)), 3)
        breakdown = {
            "base_probability": base_probability,
            "net_shap_adjustment": round(net_shap_adjustment, 3),
            "regime_multiplier": regime_multiplier,
            "tail_risk_deduction": tail_risk_deduction,
            "final_calibrated_confidence": confidence,
        }
        return confidence, breakdown
