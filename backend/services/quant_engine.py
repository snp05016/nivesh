"""
QuantitativeEngine — rule-based heuristic scores.

Runs BEFORE the LangGraph multi-agent pipeline (teacher-student flow).
Provides: a volatility-regime label, an approximate 3-month volatility range,
fixed-rule factor scores and a heuristic confidence number.

These are hand-set rules, not a trained model: the factor scores are not SHAP
values, the range is not a conformal interval and the confidence is not
calibrated against outcomes. Payload key names (``conformal_target_*``,
``calibrated_confidence``) are kept only for the API contract.
"""

import asyncio
import logging
import math
from typing import Dict, Any, Optional, Tuple

import numpy as np

_LOG = logging.getLogger(__name__)

_NIFTY_LONG_RUN_DAILY_VOL = 0.016    # ~16% annualized — Nifty 50 historical average
_NIFTY_LONG_RUN_ANNUAL_VOL = 0.16


class QuantitativeEngine:
    """Rule-based heuristic scores; not a trained model, not SHAP, not conformal, not calibrated."""

    def __init__(self, ticker: str) -> None:
        self.ticker = ticker.upper()

    async def run_full_pipeline(self) -> Dict[str, Any]:
        """Fetch inputs and compute the regime label, volatility range,
        rule-based factor scores and heuristic confidence.

        When any input is unavailable the heuristic confidence is None (never a
        number built from partial inputs) and ``data_quality`` names the gap.

        Returns:
            Dict[str, Any]: Regime, heuristic confidence and its breakdown,
                volatility range, rule-based factors, tail risk flags,
                ``method`` and ``data_quality``.
        """
        # Fetch data concurrently — return_exceptions so one failure doesn't abort all
        results = await asyncio.gather(
            self._fetch_market_volatility(),
            self._fetch_fundamentals(),
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
            else {"piotroski_score": None, "promoter_pledge_pct": None, "fallback": True}
        )

        # Sequential math (order matters — each step depends on prior)
        regime = self._detect_market_regime(market_data)
        targets = self._compute_conformal_targets(market_data)
        shap_drivers, tail_risks = self._compute_feature_importance(
            fundamental_data, market_data
        )
        data_quality = {
            "fundamentals": "unavailable" if fundamental_data.get("fallback") else "ok",
            "market": "unavailable" if market_data.get("fallback") else "ok",
        }
        if data_quality["market"] != "ok":
            # The fallback volatility is a long-run constant, not this stock's regime.
            regime = "Data Unavailable"
        confidence: Optional[float] = None
        confidence_breakdown: Dict[str, float] = {}
        if all(v == "ok" for v in data_quality.values()):
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
            "method": "rule_based_heuristic",
            # Unknown inputs are reported, never imputed with neutral constants.
            "data_quality": data_quality,
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
            "rsi_14": None,
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

            piotroski_score = None  # unknown unless computed
            if isinstance(f_score_result, dict):
                raw = f_score_result.get("f_score")
                piotroski_score = int(raw) if raw is not None else None
            elif isinstance(f_score_result, (int, float)) and not math.isnan(float(f_score_result)):
                piotroski_score = int(f_score_result)

            promoter_pledge = fund.get("promoter_pledging_pct")
            if isinstance(promoter_pledge, (int, float)) and not math.isnan(
                promoter_pledge
            ):
                promoter_pledge = float(promoter_pledge)
            else:
                promoter_pledge = None  # missing pledge data is unknown, not 0%

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
                "piotroski_score": None,
                "promoter_pledge_pct": None,
                "fallback": True,
            }

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
    def _compute_conformal_targets(market_data: dict) -> Dict[str, Optional[float]]:
        """Compute an approximate 3-month volatility range.

        Bounds are current_price * (1 +/- daily_vol * sqrt(63) * 1.645): a
        ~90% two-sided range under a normal-returns assumption, centred on the
        current price with no assumed drift. This is NOT a conformal interval
        (no calibration set or nonconformity scores); the ``*_3m`` key names are
        kept only for the API contract.

        Args:
            market_data (dict): Dictionary containing current price and daily volatility.

        Returns:
            Dict[str, Optional[float]]: Upper and lower 3-month range bounds, None
                when there is no current price.
        """
        current_price = market_data.get("current_price", 0.0)
        daily_vol = market_data.get("daily_volatility", 0.02)

        if current_price <= 0:
            return {"upper_3m": None, "lower_3m": None}

        # 63 trading days in 3 months; 1.645 = two-sided 90% normal z-score
        projected_vol_3m = daily_vol * math.sqrt(63) * 1.645

        upper_bound = current_price * (1 + projected_vol_3m)
        lower_bound = current_price * (1 - projected_vol_3m)

        return {
            "upper_3m": round(upper_bound, 2),
            "lower_3m": round(lower_bound, 2),
        }

    @staticmethod
    def _compute_feature_importance(
        fundamental_data: dict, market_data: dict
    ) -> Tuple[Dict[str, float], Dict[str, bool]]:
        """Compute fixed-rule factor scores and tail risk flags.

        The scores are hand-set constants and linear rules (not SHAP values).

        Drivers with |contribution| <= 0.05 are filtered out as noise.

        Args:
            fundamental_data (dict): Dictionary containing fundamental metrics.
            market_data (dict): Dictionary containing technical market data (e.g., RSI).

        Returns:
            Tuple[Dict[str, float], Dict[str, bool]]: A tuple containing the rule-based
                factor scores and tail risk flags.
        """
        def _known(v):
            return None if v is None or (isinstance(v, float) and math.isnan(v)) else v

        # Unknown inputs (None/NaN) contribute no driver and no tail-risk key.
        f_score = _known(fundamental_data.get("piotroski_score"))
        promoter_pledge = _known(fundamental_data.get("promoter_pledge_pct"))
        rsi_14 = _known(market_data.get("rsi_14"))

        shap_drivers: Dict[str, float] = {}

        # F-Score contribution (normalized around 5 as neutral)
        if f_score is not None:
            f_score = int(f_score)
            shap_drivers["Fundamental Health (F-Score)"] = round(
                (f_score - 5) / 4.0 * 0.40, 3
            )

        # RSI-based technical drivers
        if rsi_14 is not None and rsi_14 < 30:
            shap_drivers["Technical Reversion (Oversold)"] = 0.25
        elif rsi_14 is not None and rsi_14 > 70:
            shap_drivers["Technical Overextension"] = -0.25

        # Promoter pledge risk (linear penalty)
        if promoter_pledge is not None and promoter_pledge > 0:
            shap_drivers["Promoter Pledge Risk"] = round(
                -1.0 * (promoter_pledge / 100.0) * 0.50, 3
            )

        # Filter noise — only keep drivers with meaningful contribution
        shap_drivers = {
            k: v for k, v in shap_drivers.items() if abs(v) > 0.05
        }

        tail_risks: Dict[str, bool] = {}
        if promoter_pledge is not None:
            tail_risks["high_pledge_danger"] = promoter_pledge > 30.0
        if f_score is not None:
            tail_risks["distressed_fundamentals"] = f_score < 3

        return shap_drivers, tail_risks

    @staticmethod
    def _compute_calibrated_confidence(
        regime: str, shap_drivers: Dict[str, float], tail_risks: Dict[str, bool],
        venn_abers_base: float = None,
    ) -> Tuple[float, Dict[str, float]]:
        """Compute a heuristic confidence score (0.05–0.95).

        Not calibrated: 0.50 (or a supplied base) plus the sum of the rule-based
        factor scores, multiplied by a fixed regime factor, minus a fixed
        tail-risk penalty. Key names keep the legacy "calibrated"/"shap" wording
        only for the API contract.

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
