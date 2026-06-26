"""
Nivesh Microstructure Engine
----------------------------
Computes options microstructure metrics from NSE option chain data:
  - Volume PCR & OI PCR (retail sentiment indicators)
  - Gamma Exposure (GEX) estimate (dealer positioning)
  - Confidence modifier for breakout reliability

Pure Python math — zero LLM calls.
Cached for 15 minutes via disk_cache.
"""
import logging
import math
from datetime import datetime, date
from typing import Optional

from services.disk_cache import get as cache_get, set as cache_set
from services.options_scraper import fetch_option_chain

logger = logging.getLogger(__name__)

# ── Named Constants ──────────────────────────────────────────────────────

CACHE_NAMESPACE = "microstructure"
CACHE_TTL = 900

VOLUME_PCR_BEARISH_THRESHOLD = 1.2
VOLUME_PCR_BULLISH_THRESHOLD = 0.8
OI_PCR_EXTREME_UPPER = 1.5
OI_PCR_EXTREME_LOWER = 0.5

LONG_GAMMA_MODIFIER = -0.05
SHORT_GAMMA_MODIFIER = 0.05
OI_PCR_EXTREME_MODIFIER = 0.03

RISK_FREE_RATE = 0.07
IMPLIED_VOL_ESTIMATE = 0.30

TWO_PI = 2.0 * math.pi
MIN_TTE_DAYS = 1
DEFAULT_TTE_DAYS = 30
FETCH_TIMEOUT = 5


def _standard_normal_pdf(x: float) -> float:
    """
    Standard normal probability density function.
    
    Args:
        x (float): The z-score input value.
        
    Returns:
        float: The probability density at the given value.
    """
    # Calculate PDF using the standard normal distribution formula
    return math.exp(-x * x / 2.0) / math.sqrt(TWO_PI)


def _black_scholes_gamma(
    S: float, K: float, T: float, sigma: float, r: float = RISK_FREE_RATE
) -> float:
    """
    Approximate Black-Scholes gamma for a single option contract.

    Gamma = N'(d1) / (S * sigma * sqrt(T))

    Args:
        S: Current spot price.
        K: Strike price.
        T: Time to expiry in years.
        sigma: Implied volatility (decimal, e.g. 0.30 for 30%).
        r: Risk-free rate (decimal).

    Returns:
        Gamma per option contract. Returns 0.0 for invalid inputs.
    """
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        return 0.0
    vol_sqrt_t = sigma * math.sqrt(T)
    if vol_sqrt_t < 1e-12:
        return 0.0
    d1 = (math.log(S / K) + (r + sigma * sigma / 2.0) * T) / vol_sqrt_t
    return _standard_normal_pdf(d1) / (S * vol_sqrt_t)


def _parse_expiry_date(expiry_str: str) -> Optional[date]:
    """
    Parse NSE expiry date string to date object.
    
    Args:
        expiry_str (str): Expiry date as a string (e.g., '25-Jul-2024').
        
    Returns:
        Optional[date]: A standard python date object, or None if parsing fails.
    """
    try:
        # Convert the string to a date object using the standard NSE format
        return datetime.strptime(expiry_str, "%d-%b-%Y").date()
    except (ValueError, TypeError):
        # Gracefully handle malformed or invalid inputs
        return None


def _find_nearest_expiry(expiry_dates: list[str]) -> Optional[str]:
    """
    Find the nearest future expiry from a list of NSE date strings.
    
    Args:
        expiry_dates (list[str]): List of date strings from the option chain.
        
    Returns:
        Optional[str]: The string representing the nearest future expiry, or None.
    """
    today = date.today()
    nearest = None
    nearest_dt = None
    
    # Iterate through all available expiry strings to find the closest future date
    for expiry_str in expiry_dates:
        dt = _parse_expiry_date(expiry_str)
        # Ignore past dates or unparseable formats
        if dt is None or dt < today:
            continue
            
        # Update nearest if this is the first valid date or closer than current nearest
        if nearest_dt is None or dt < nearest_dt:
            nearest = expiry_str
            nearest_dt = dt
            
    return nearest


def _compute_time_to_expiry(expiry_str: str) -> float:
    """Compute time to expiry in years from an NSE date string."""
    dt = _parse_expiry_date(expiry_str)
    if dt is None:
        return DEFAULT_TTE_DAYS / 365.0
    seconds = (datetime.combine(dt, datetime.min.time()) - datetime.now()).total_seconds()
    days = max(seconds / 86400.0, MIN_TTE_DAYS)
    return days / 365.0


def compute_pcr_gex(symbol: str, expiry: Optional[str] = None) -> dict:
    """
    Compute Put-Call Ratio and Gamma Exposure from NSE option chain data.

    Args:
        symbol: NSE stock symbol (e.g., "RELIANCE", "TCS").
        expiry: Specific expiry date string ("DD-Mon-YYYY").
                If None, uses the nearest future expiry.

    Returns:
        dict with keys:
            volume_pcr: float or None
            oi_pcr: float or None
            gex_estimate: float or None
            dealer_regime: "LONG_GAMMA" | "SHORT_GAMMA" | "NEUTRAL"
            pcr_signal: "BEARISH_RETAIL" | "BULLISH_RETAIL" | "NEUTRAL"
            microstructure_confidence_modifier: float (-0.10 to +0.08)
    """
    result_default = {
        "volume_pcr": None,
        "oi_pcr": None,
        "gex_estimate": None,
        "dealer_regime": "NEUTRAL",
        "pcr_signal": "NEUTRAL",
        "microstructure_confidence_modifier": 0.0,
    }

    cache_key = f"{symbol.upper()}_{expiry or 'NONE'}"
    try:
        cached = cache_get(CACHE_NAMESPACE, cache_key)
        if cached is not None:
            return cached
    except Exception as e:
        logger.warning(f"[microstructure] {symbol}: Cache read failed: {e}")

    try:
        option_data = fetch_option_chain(symbol)
        if option_data is None:
            logger.warning(f"[microstructure] {symbol}: No option chain data")
            return result_default
    except Exception as e:
        logger.error(f"[microstructure] {symbol}: Fetch failed: {e}", exc_info=True)
        return result_default

    try:
        records = option_data.get("records", {})
        raw_data = records.get("data", [])
        if not raw_data:
            logger.warning(f"[microstructure] {symbol}: Empty records data")
            return result_default

        underlying_value = records.get("underlyingValue")
        current_price = float(underlying_value) if underlying_value and float(underlying_value) > 0 else None

        expiry_dates = records.get("expiryDates", [])
        target_expiry = expiry or _find_nearest_expiry(expiry_dates)
        if not target_expiry:
            logger.warning(f"[microstructure] {symbol}: No valid expiry found")
            return result_default

        expiry_records = [r for r in raw_data if r.get("expiryDate") == target_expiry]
        if not expiry_records:
            logger.warning(f"[microstructure] {symbol}: No records for expiry {target_expiry}")
            return result_default

        total_call_volume = 0
        total_put_volume = 0
        total_call_oi = 0
        total_put_oi = 0
        total_gex = 0.0

        T = _compute_time_to_expiry(target_expiry)

        for record in expiry_records:
            strike = record.get("strikePrice", 0)
            if strike <= 0:
                continue

            ce = record.get("CE") or {}
            pe = record.get("PE") or {}

            ce_vol = ce.get("totalTradedVolume", 0) or 0
            pe_vol = pe.get("totalTradedVolume", 0) or 0
            ce_oi = ce.get("openInterest", 0) or 0
            pe_oi = pe.get("openInterest", 0) or 0
            ce_iv = ce.get("impliedVolatility")
            pe_iv = pe.get("impliedVolatility")

            total_call_volume += ce_vol
            total_put_volume += pe_vol
            total_call_oi += ce_oi
            total_put_oi += pe_oi

            if current_price is not None and current_price > 0:
                sigma_call = (float(ce_iv) / 100.0) if ce_iv and float(ce_iv) > 0 else IMPLIED_VOL_ESTIMATE
                gamma_call = _black_scholes_gamma(current_price, strike, T, sigma_call, RISK_FREE_RATE)
                total_gex -= gamma_call * ce_oi

                sigma_put = (float(pe_iv) / 100.0) if pe_iv and float(pe_iv) > 0 else IMPLIED_VOL_ESTIMATE
                gamma_put = _black_scholes_gamma(current_price, strike, T, sigma_put, RISK_FREE_RATE)
                total_gex += gamma_put * pe_oi

        total_gex = round(total_gex, 2)

        volume_pcr = round(total_put_volume / total_call_volume, 3) if total_call_volume > 0 else None
        oi_pcr = round(total_put_oi / total_call_oi, 3) if total_call_oi > 0 else None

        pcr_signal = "NEUTRAL"
        if volume_pcr is not None:
            if volume_pcr > VOLUME_PCR_BEARISH_THRESHOLD:
                pcr_signal = "BEARISH_RETAIL"
            elif volume_pcr < VOLUME_PCR_BULLISH_THRESHOLD:
                pcr_signal = "BULLISH_RETAIL"

        dealer_regime = "NEUTRAL"
        if abs(total_gex) < 1:
            dealer_regime = "NEUTRAL"
        elif total_gex > 0:
            dealer_regime = "LONG_GAMMA"
        else:
            dealer_regime = "SHORT_GAMMA"

        modifier = 0.0
        if dealer_regime == "LONG_GAMMA":
            modifier += LONG_GAMMA_MODIFIER
        elif dealer_regime == "SHORT_GAMMA":
            modifier += SHORT_GAMMA_MODIFIER

        if oi_pcr is not None:
            if oi_pcr > OI_PCR_EXTREME_UPPER:
                modifier -= OI_PCR_EXTREME_MODIFIER
            elif oi_pcr < OI_PCR_EXTREME_LOWER:
                modifier += OI_PCR_EXTREME_MODIFIER

        modifier = round(max(-0.10, min(0.08, modifier)), 3)

        result = {
            "volume_pcr": volume_pcr,
            "oi_pcr": oi_pcr,
            "gex_estimate": total_gex,
            "dealer_regime": dealer_regime,
            "pcr_signal": pcr_signal,
            "microstructure_confidence_modifier": modifier,
        }

        try:
            cache_set(CACHE_NAMESPACE, cache_key, result, CACHE_TTL)
        except Exception as e:
            logger.warning(f"[microstructure] {symbol}: Cache write failed: {e}")

        logger.info(
            f"[microstructure] {symbol} {target_expiry}: "
            f"vPCR={volume_pcr}, oiPCR={oi_pcr}, GEX={total_gex}, "
            f"regime={dealer_regime}, modifier={modifier}"
        )
        return result

    except Exception as e:
        logger.error(f"[microstructure] {symbol}: Computation error: {e}", exc_info=True)
        return result_default
