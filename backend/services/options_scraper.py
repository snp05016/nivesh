from config.settings import get_user_agent
"""
Nivesh Options Scraper
-----------------------
Fetches NSE option chain data and computes institutional positioning metrics.
All math done in Python — zero LLM computation.

Metrics: PCR, Max Pain, OI Skew, Institutional Signal.
Cached for 15 minutes in NIVESH_CACHE_DIR/options/.
"""
import logging
import time
from typing import Optional

import requests

from services.disk_cache import get as cache_get, set as cache_set

logger = logging.getLogger(__name__)

_NSE_HEADERS = {
    "User-Agent": get_user_agent(),
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/option-chain",
    "X-Requested-With": "XMLHttpRequest",
}


def _get_nse_session() -> requests.Session:
    """Initialize and return a requests.Session with NSE-specific headers.
    
    Returns:
        requests.Session: The configured session object.
    """
    session = requests.Session()
    session.headers.update(_NSE_HEADERS)
    try:
        session.get("https://www.nseindia.com", timeout=10)
        time.sleep(0.5)
    except Exception as e:
        logger.warning(f"[options_scraper] NSE session init failed: {e}")
    return session


def fetch_option_chain(symbol: str, use_cache: bool = True) -> Optional[dict]:
    """
    Fetch raw option chain from NSE. Returns None if unreachable.
    Cached 15 minutes.
    """
    cache_key = f"{symbol.upper()}_chain"
    if use_cache:
        cached = cache_get("options", cache_key)
        if cached:
            return cached

    try:
        session = _get_nse_session()
        url = f"https://www.nseindia.com/api/option-chain-equities?symbol={symbol.upper()}"
        resp = session.get(url, timeout=15)
        if resp.status_code != 200:
            logger.warning(f"[options_scraper] {symbol}: NSE returned {resp.status_code}")
            return None
        data = resp.json()
        if "records" not in data:
            logger.warning(f"[options_scraper] {symbol}: Unexpected response structure")
            return None
        cache_set("options", cache_key, data)
        logger.info(f"[options_scraper] {symbol}: Option chain fetched OK")
        return data
    except Exception as e:
        logger.warning(f"[options_scraper] {symbol}: Fetch failed: {e}")
        return None


def compute_derivatives_metrics(option_data: dict, current_price: float) -> dict:
    """
    Compute PCR, Max Pain, OI Skew, and Institutional Signal from raw chain data.
    Pure Python math — no LLM.
    """
    result = {
        "pcr": None,
        "max_pain": None,
        "max_pain_distance_pct": None,
        "top_call_oi_strike": None,
        "top_put_oi_strike": None,
        "total_call_oi": None,
        "total_put_oi": None,
        "institutional_signal": "NEUTRAL",
        "signal_rationale": "",
    }

    try:
        records = option_data.get("records", {}).get("data", [])
        if not records:
            return result

        total_call_oi = 0
        total_put_oi  = 0
        strike_data   = {}

        for record in records:
            strike = record.get("strikePrice", 0)
            ce_oi  = (record.get("CE") or {}).get("openInterest", 0) or 0
            pe_oi  = (record.get("PE") or {}).get("openInterest", 0) or 0
            total_call_oi += ce_oi
            total_put_oi  += pe_oi
            if strike not in strike_data:
                strike_data[strike] = {"call_oi": 0, "put_oi": 0}
            strike_data[strike]["call_oi"] += ce_oi
            strike_data[strike]["put_oi"]  += pe_oi

        result["total_call_oi"] = total_call_oi
        result["total_put_oi"]  = total_put_oi

        if total_call_oi > 0:
            result["pcr"] = round(total_put_oi / total_call_oi, 3)
        else:
            result["pcr"] = 0.0  # illiquid chain — no call OI, PCR undefined

        # Max Pain: strike minimizing total buyer payout
        # Fix 2.5: filter out deep OTM strikes (>50% from current price) to
        # prevent operator-manipulated anomalous OI from skewing Max Pain
        if strike_data and current_price and current_price > 0:
            _filtered_strikes = {
                s: oi for s, oi in strike_data.items()
                if abs(s - current_price) / current_price <= 0.50
            }
            if _filtered_strikes:
                strike_data = _filtered_strikes

        if strike_data:
            pain = {}
            for target in strike_data:
                total_pain = 0
                for s, oi in strike_data.items():
                    total_pain += max(0, s - target) * oi["call_oi"]
                    total_pain += max(0, target - s) * oi["put_oi"]
                pain[target] = total_pain
            result["max_pain"] = min(pain, key=pain.get)
            if current_price > 0:
                result["max_pain_distance_pct"] = round(
                    ((result["max_pain"] - current_price) / current_price) * 100, 2
                )

        if strike_data:
            top_call = max(strike_data.items(), key=lambda x: x[1]["call_oi"])
            top_put  = max(strike_data.items(), key=lambda x: x[1]["put_oi"])
            result["top_call_oi_strike"] = top_call[0]
            result["top_put_oi_strike"]  = top_put[0]

        pcr     = result["pcr"]
        mp_dist = result["max_pain_distance_pct"] or 0
        if pcr is not None:
            if pcr > 1.5 and mp_dist > 3:
                result["institutional_signal"] = "BEARISH_TRAP"
                result["signal_rationale"] = (
                    f"PCR {pcr:.2f} — extreme bearish positioning. "
                    f"Max Pain ₹{result['max_pain']} is {abs(mp_dist):.1f}% above CMP. "
                    "Institutions positioned for short squeeze."
                )
            elif pcr < 0.7 and mp_dist < -3:
                result["institutional_signal"] = "BULLISH_TRAP"
                result["signal_rationale"] = (
                    f"PCR {pcr:.2f} — retail piling into calls while institutions write them. "
                    f"Max Pain ₹{result['max_pain']} suggests {abs(mp_dist):.1f}% downside to expiry gravity."
                )
            elif pcr > 1.2:
                result["institutional_signal"] = "CAUTIOUS_BULLISH"
                result["signal_rationale"] = (
                    f"PCR {pcr:.2f} — moderate put protection; institutional hedging, not panic."
                )
            elif pcr < 0.8:
                result["institutional_signal"] = "CAUTIOUS_BEARISH"
                result["signal_rationale"] = (
                    f"PCR {pcr:.2f} — call buying dominant; limited institutional conviction."
                )
            else:
                result["institutional_signal"] = "NEUTRAL"
                result["signal_rationale"] = f"PCR {pcr:.2f} — balanced positioning."

    except Exception as e:
        logger.error(f"[options_scraper] Metrics error: {e}", exc_info=True)

    return result


def format_derivatives_for_prompt(metrics: dict) -> str:
    """
    Format derivatives metrics for volatile HumanMessage injection (~80 tokens).
    Never inject into static system prompt.
    """
    if not metrics or metrics.get("pcr") is None:
        return ""

    return "\n".join([
        "=== F&O DERIVATIVES DATA (INSTITUTIONAL POSITIONING) ===",
        f"Put-Call Ratio (PCR):      {metrics.get('pcr', 'N/A')}",
        f"Max Pain Strike:           ₹{metrics.get('max_pain', 'N/A')} ({metrics.get('max_pain_distance_pct', 'N/A')}% from CMP)",
        f"Strongest Call Resistance: ₹{metrics.get('top_call_oi_strike', 'N/A')} (highest call OI)",
        f"Strongest Put Support:     ₹{metrics.get('top_put_oi_strike', 'N/A')} (highest put OI)",
        f"Institutional Signal:      {metrics.get('institutional_signal', 'NEUTRAL')}",
        f"Signal Rationale:          {metrics.get('signal_rationale', 'N/A')}",
        "INSTRUCTION: F&O signals override pure price-action signals.",
        "BULLISH_TRAP overrides bullish price action. BEARISH_TRAP overrides bearish.",
        "=== END F&O DATA ===",
    ])
