"""
Nivesh Macro Modifiers
----------------------
Systematic confidence adjustments based on macroeconomic conditions.

GAP 10 — Monsoon Systematic Modifier: Sector-level confidence boost/penalty
    based on IMD monsoon status (DEFICIENT / NORMAL / ABOVE_NORMAL / EXCESS).

GAP 11 — Minskyan Risk as Computed Penalty: Scalar fragility score from
    FII-DII absorption ratio and Nifty P/E z-score, mapped to a confidence penalty.
"""
import logging
import threading
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────

MONSOON_SENSITIVE_SECTORS: dict[str, float] = {
    "FMCG": -0.08,
    "Auto Two-Wheeler": -0.07,
    "Tractors": -0.10,
    "Microfinance": -0.09,
    "Rural Banking": -0.06,
    "Agrochemicals": -0.05,
}

MONSOON_BENEFICIARY_SECTORS: dict[str, float] = {
    "FMCG": +0.06,
    "Auto Two-Wheeler": +0.05,
    "Tractors": +0.08,
    "Microfinance": +0.07,
}

MONSOON_CACHE_TTL_DAYS = 7

# Nifty 50 historical parameters (20-year mean/std)
NIFTY_HISTORICAL_MEAN_PE = 20.5
NIFTY_HISTORICAL_STD_PE = 4.2

# Score thresholds
MINSKYAN_THRESHOLD = 0.7
MINSKYAN_PENALTY_SLOPE = 25.0
MINSKYAN_SCORE_MAX = 1.0
MINSKYAN_SCORE_MIN = 0.0
PENALTY_LOWER_BOUND = -0.075
PENALTY_UPPER_BOUND = 0.0

# ── Module-level cache (thread-safe) ────────────────────────────────────────

_monsoon_cache: dict[str, tuple[dict, datetime]] = {}
_monsoon_cache_lock = threading.Lock()

# ── GAP 10: Monsoon Systematic Modifier ─────────────────────────────────────

def _fetch_imd_status() -> Optional[str]:
    """Attempt to fetch current monsoon status from IMD/Skymet.

    Returns one of "DEFICIENT", "NORMAL", "ABOVE_NORMAL", "EXCESS"
    or None if the API is unreachable.
    """
    try:
        import requests
        # Placeholder: IMD public API endpoint — replace with actual URL when available
        # Current implementation falls back to static lookup per AGENTS.md §6
        resp = requests.get(
            "https://mausam.imd.gov.in/api/monsoon-status",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            status = data.get("monsoon_status", "").upper()
            if status in ("DEFICIENT", "NORMAL", "ABOVE_NORMAL", "EXCESS"):
                return status
    except ImportError:
        logger.warning("[monsoon] requests not available, using static lookup")
    except Exception as e:
        logger.warning(f"[monsoon] IMD API failed: {e}")
    return None


def get_monsoon_modifier(
    ticker: str,
    sector: str,
    monsoon_status: str = "NORMAL",
) -> dict:
    """Return a confidence modifier based on monsoon conditions and sector.

    Args:
        ticker: Stock ticker symbol.
        sector: Sector classification string.
        monsoon_status: "DEFICIENT", "NORMAL", "ABOVE_NORMAL", or "EXCESS".

    Returns:
        dict with keys: modifier (float), reasoning (str), sector (str),
        monsoon_status (str).
    """
    try:
        status = monsoon_status.upper().strip()
        if status not in ("DEFICIENT", "NORMAL", "ABOVE_NORMAL", "EXCESS"):
            status = "NORMAL"

        # Attempt IMD API fetch; fall back to provided status on failure
        imd_status = _fetch_imd_status()
        effective_status = imd_status if imd_status is not None else status

        # Resolve modifier
        modifier = 0.0
        reasoning_parts = []

        if effective_status == "DEFICIENT":
            if sector in MONSOON_SENSITIVE_SECTORS:
                modifier = MONSOON_SENSITIVE_SECTORS[sector]
                reasoning_parts.append(
                    f"Deficit monsoon hits {sector} ({modifier:+.0%} confidence)"
                )
        elif effective_status in ("ABOVE_NORMAL", "EXCESS"):
            if sector in MONSOON_BENEFICIARY_SECTORS:
                modifier = MONSOON_BENEFICIARY_SECTORS[sector]
                reasoning_parts.append(
                    f"{effective_status.replace('_', ' ').title()} monsoon boosts {sector} ({modifier:+.0%} confidence)"
                )

        if not reasoning_parts:
            reasoning_parts.append(
                f"No monsoon modifier for {sector} under {effective_status} conditions"
            )

        result = {
            "modifier": modifier,
            "reasoning": " | ".join(reasoning_parts),
            "sector": sector,
            "monsoon_status": effective_status,
        }

        # Update cache (discard stale entries)
        now = datetime.utcnow()
        global _monsoon_cache
        with _monsoon_cache_lock:
            _monsoon_cache[ticker] = (result, now)

        return result

    except Exception as e:
        logger.error(f"[monsoon] Unexpected error for {ticker}: {e}")
        return {
            "modifier": 0.0,
            "reasoning": f"Monsoon modifier unavailable: {e}",
            "sector": sector,
            "monsoon_status": monsoon_status,
        }


def get_cached_monsoon_modifier(ticker: str) -> Optional[dict]:
    """Return cached monsoon modifier if still fresh (< 7 days)."""
    with _monsoon_cache_lock:
        entry = _monsoon_cache.get(ticker)
        if entry is None:
            return None
        result, cached_at = entry
        age = datetime.utcnow() - cached_at
        if age.days < MONSOON_CACHE_TTL_DAYS:
            return result
        del _monsoon_cache[ticker]
    return None


# ── GAP 11: Minskyan Risk as Computed Penalty ───────────────────────────────

def compute_minskyan_risk(
    dii_ytd: float = 0,
    fii_ytd: float = 0,
    nifty_pe: float = 21.5,
) -> dict:
    """Compute Minskyan fragility score and momentum confidence penalty.

    Formula:
        dii_fii_absorption_ratio = abs(dii_ytd) / max(1, abs(fii_ytd))
        cape_zscore = (nifty_pe - 20.5) / 4.2
        minskyan_score = 0.6 * min(dii_absorption / 2.0, 1.0)
                        + 0.4 * min(cape_zscore / 2.0, 1.0)
        if minskyan_score > 0.7:
            penalty = -(minskyan_score - 0.7) * 25

    Args:
        dii_ytd: DII net purchases YTD in crores.
        fii_ytd: FII net outflows YTD in crores (negative = selling).
        nifty_pe: Current Nifty 50 P/E ratio.

    Returns:
        dict with keys: minskyan_score (float 0-1),
        momentum_confidence_penalty (float -0.075 to 0),
        minskyan_flag (bool), reasoning (str).
    """
    try:
        abs_fii = abs(fii_ytd)
        denominator = max(1.0, abs_fii)
        absorption_ratio = abs(dii_ytd) / denominator

        cape_zscore = (nifty_pe - NIFTY_HISTORICAL_MEAN_PE) / NIFTY_HISTORICAL_STD_PE

        capped_absorption = min(absorption_ratio / 2.0, 1.0)
        capped_cape = min(cape_zscore / 2.0, 1.0)

        raw_score = 0.6 * capped_absorption + 0.4 * capped_cape
        minskyan_score = max(MINSKYAN_SCORE_MIN, min(MINSKYAN_SCORE_MAX, raw_score))

        if minskyan_score > MINSKYAN_THRESHOLD:
            penalty = -(minskyan_score - MINSKYAN_THRESHOLD) * MINSKYAN_PENALTY_SLOPE
            # Clamp to [-0.075, 0] as a percentage point modifier
            momentum_confidence_penalty = max(PENALTY_LOWER_BOUND, min(PENALTY_UPPER_BOUND, penalty))
        else:
            momentum_confidence_penalty = 0.0

        if momentum_confidence_penalty < 0:
            minskyan_flag = True
            reasoning = (
                f"Minskyan score {minskyan_score:.2f} exceeds {MINSKYAN_THRESHOLD:.0%} threshold — "
                f"applying {momentum_confidence_penalty:.1%} momentum confidence penalty. "
                f"DII absorption ratio {absorption_ratio:.2f}, Nifty P/E z-score {cape_zscore:.2f}"
            )
        else:
            minskyan_flag = False
            reasoning = (
                f"Minskyan score {minskyan_score:.2f} below threshold — no penalty. "
                f"DII absorption ratio {absorption_ratio:.2f}, Nifty P/E z-score {cape_zscore:.2f}"
            )

        return {
            "minskyan_score": round(minskyan_score, 4),
            "momentum_confidence_penalty": round(momentum_confidence_penalty, 6),
            "minskyan_flag": minskyan_flag,
            "reasoning": reasoning,
        }

    except Exception as e:
        logger.error(f"[minskyan] Computation failed: {e}")
        return {
            "minskyan_score": 0.0,
            "momentum_confidence_penalty": 0.0,
            "minskyan_flag": False,
            "reasoning": f"Minskyan risk unavailable: {e}",
        }


# ── FII/DII Data Fetch ──────────────────────────────────────────────────────

def fetch_fii_dii_ytd() -> dict:
    """Fetch FII/DII net purchase data YTD from NSE API.

    Returns:
        dict with keys:
            dii_net_purchases_ytd (float): DII net purchases YTD in crores.
            fii_net_outflows_ytd (float): FII net outflows YTD in crores.
        All values default to 0 on failure.
    """
    try:
        import requests
        # NSE FII/DII data endpoint
        # Placeholder — replace with actual NSDL/CDSL API when integrated
        resp = requests.get(
            "https://www.nseindia.com/api/fiidii",
            headers={
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
                "Referer": "https://www.nseindia.com",
            },
            timeout=15,
        )
        if resp.status_code == 200:
            data = resp.json()
            dii_net = float(data.get("dii_net_purchases", 0))
            fii_net = float(data.get("fii_net_outflows", 0))
            logger.info(f"[fiidii] FII={fii_net:.0f} Cr, DII={dii_net:.0f} Cr")
            return {
                "dii_net_purchases_ytd": dii_net,
                "fii_net_outflows_ytd": fii_net,
            }

        logger.warning(f"[fiidii] NSE returned HTTP {resp.status_code}")
    except ImportError:
        logger.warning("[fiidii] requests not available, returning zeros")
    except Exception as e:
        logger.warning(f"[fiidii] Fetch failed: {e}")

    return {
        "dii_net_purchases_ytd": 0.0,
        "fii_net_outflows_ytd": 0.0,
    }
