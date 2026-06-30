import logging
"""
Task 18 — Put/Call Ratio (PCR) and Gamma Exposure (GEX).

PCR: Total put OI / Total call OI. >1 = bearish sentiment; <1 = bullish.
GEX: Net dealer gamma exposure — tells how market makers will hedge and
     whether the market is self-stabilizing or self-amplifying.
"""

from __future__ import annotations
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

class PCRSignalResponse(BaseModel):
    pcr: float
    volume_pcr: Optional[float]
    sentiment: str
    description: str
    total_put_oi: int
    total_call_oi: int
    total_put_volume: int
    total_call_volume: int
    contrarian_signal: bool

class StrikeGex(BaseModel):
    strike: float
    gex: float

class GEXSignalResponse(BaseModel):
    gex: float
    regime: str
    description: str
    key_strikes: List[StrikeGex]
    gamma_flip_point: Optional[float]
    spot_price: float


def compute_pcr(option_chain: dict) -> float:
    """
    Compute Put/Call Ratio from option chain data.

    Args:
        option_chain: dict with keys:
            'calls': list of dict {'strike': float, 'oi': int, 'volume': int}
            'puts':  list of dict {'strike': float, 'oi': int, 'volume': int}

    Returns:
        PCR (float). >1 → bearish; <1 → bullish; ~1 → neutral.
    """
    calls = option_chain.get("calls", [])
    puts = option_chain.get("puts", [])

    total_put_oi = sum(c.get("oi", 0) for c in puts)
    total_call_oi = sum(c.get("oi", 0) for c in calls)

    if total_call_oi == 0:
        return float("inf")

    return round(total_put_oi / total_call_oi, 4)


def compute_pcr_with_signal(option_chain: dict) -> PCRSignalResponse:
    """
    PCR with market sentiment interpretation.

    Args:
        option_chain: same as compute_pcr.

    Returns:
        dict with 'pcr', 'sentiment', 'description', 'total_put_oi',
        'total_call_oi', 'volume_pcr'
    """
    calls = option_chain.get("calls", [])
    puts = option_chain.get("puts", [])

    total_put_oi = sum(c.get("oi", 0) for c in puts)
    total_call_oi = sum(c.get("oi", 0) for c in calls)
    total_put_vol = sum(c.get("volume", 0) for c in puts)
    total_call_vol = sum(c.get("volume", 0) for c in calls)

    pcr_oi = total_put_oi / total_call_oi if total_call_oi else float("inf")
    pcr_vol = total_put_vol / total_call_vol if total_call_vol else float("inf")

    if pcr_oi > 1.5:
        sentiment = "EXTREMELY_BEARISH"
        description = "High put OI — extreme fear in market, potential contrarian buy"
    elif pcr_oi > 1.1:
        sentiment = "BEARISH"
        description = "Put OI exceeds calls — bearish sentiment dominant"
    elif pcr_oi > 0.9:
        sentiment = "NEUTRAL"
        description = "Balanced put/call ratio — no directional bias"
    elif pcr_oi > 0.7:
        sentiment = "BULLISH"
        description = "Call OI exceeds puts — bullish sentiment dominant"
    else:
        sentiment = "EXTREMELY_BULLISH"
        description = "Very high call OI — excessive optimism, potential contrarian sell"

    return PCRSignalResponse(
        pcr=round(pcr_oi, 4),
        volume_pcr=round(pcr_vol, 4) if pcr_vol != float("inf") else None,
        sentiment=sentiment,
        description=description,
        total_put_oi=total_put_oi,
        total_call_oi=total_call_oi,
        total_put_volume=total_put_vol,
        total_call_volume=total_call_vol,
        contrarian_signal=sentiment in {"EXTREMELY_BEARISH", "EXTREMELY_BULLISH"},
    )


def compute_gex(option_chain: dict, spot_price: float) -> float:
    """
    Compute Gamma Exposure (GEX).

    GEX = Σ(gamma * OI * contract_size * spot^2 * 0.01) for calls
        - Σ(gamma * OI * contract_size * spot^2 * 0.01) for puts

    Positive GEX: market makers are long gamma (self-stabilizing).
    Negative GEX: market makers are short gamma (self-amplifying/volatile).

    Args:
        option_chain: dict with:
            'calls': list of dict {'strike': float, 'oi': int, 'gamma': float}
            'puts':  list of dict {'strike': float, 'oi': int, 'gamma': float}
        spot_price: current underlying price.

    Returns:
        GEX (float) in dollars (or INR) per 1% move.
    """
    calls = option_chain.get("calls", [])
    puts = option_chain.get("puts", [])
    contract_size = option_chain.get("contract_size", 50)  # NSE lot size default

    gex_calls = sum(
        c.get("gamma", 0) * c.get("oi", 0) * contract_size * spot_price**2 * 0.01
        for c in calls
    )
    gex_puts = sum(
        c.get("gamma", 0) * c.get("oi", 0) * contract_size * spot_price**2 * 0.01
        for c in puts
    )

    return round(gex_calls - gex_puts, 2)


def compute_gex_with_signal(option_chain: dict, spot_price: float) -> GEXSignalResponse:
    """
    GEX with directional interpretation.

    Args:
        option_chain: same as compute_gex.
        spot_price: current underlying price.

    Returns:
        dict with 'gex', 'regime', 'key_strikes', 'description'
    """
    calls = option_chain.get("calls", [])
    puts = option_chain.get("puts", [])
    contract_size = option_chain.get("contract_size", 50)

    gex_by_strike: dict[float, float] = {}

    for c in calls:
        strike = c.get("strike", 0)
        g = c.get("gamma", 0) * c.get("oi", 0) * contract_size * spot_price**2 * 0.01
        gex_by_strike[strike] = gex_by_strike.get(strike, 0) + g

    for p in puts:
        strike = p.get("strike", 0)
        g = p.get("gamma", 0) * p.get("oi", 0) * contract_size * spot_price**2 * 0.01
        gex_by_strike[strike] = gex_by_strike.get(strike, 0) - g

    net_gex = sum(gex_by_strike.values())

    # Find strikes with highest absolute GEX (gamma walls/flip points)
    sorted_strikes = sorted(gex_by_strike.items(), key=lambda x: abs(x[1]), reverse=True)
    key_strikes = [
        StrikeGex(strike=s, gex=round(g, 2)) for s, g in sorted_strikes[:5]
    ]

    if net_gex > 0:
        regime = "POSITIVE_GEX"
        description = "Market makers long gamma — expect mean-reversion, reduced volatility"
    else:
        regime = "NEGATIVE_GEX"
        description = "Market makers short gamma — expect trend-following, increased volatility"

    # Find gamma flip point (where GEX changes sign)
    flip_point = None
    sorted_all = sorted(gex_by_strike.items())
    for i in range(len(sorted_all) - 1):
        if sorted_all[i][1] * sorted_all[i + 1][1] < 0:
            flip_point = (sorted_all[i][0] + sorted_all[i + 1][0]) / 2
            break

    return GEXSignalResponse(
        gex=round(net_gex, 2),
        regime=regime,
        description=description,
        key_strikes=key_strikes,
        gamma_flip_point=round(flip_point, 2) if flip_point else None,
        spot_price=spot_price,
    )


if __name__ == "__main__":
    sample_chain = {
        "contract_size": 50,
        "calls": [
            {"strike": 19800, "oi": 50000, "gamma": 0.0012, "volume": 10000},
            {"strike": 19900, "oi": 80000, "gamma": 0.0018, "volume": 20000},
            {"strike": 20000, "oi": 1_20_000, "gamma": 0.0025, "volume": 30000},
        ],
        "puts": [
            {"strike": 19800, "oi": 60000, "gamma": 0.0012, "volume": 15000},
            {"strike": 19700, "oi": 90000, "gamma": 0.0008, "volume": 12000},
            {"strike": 19600, "oi": 40000, "gamma": 0.0005, "volume": 8000},
        ],
    }
    pcr = compute_pcr(sample_chain)
    logging.info(f"PCR: {pcr}")
    assert pcr > 0

    pcr_sig = compute_pcr_with_signal(sample_chain)
    logging.info(f"PCR signal: {pcr_sig.sentiment} — {pcr_sig.description}")

    gex = compute_gex(sample_chain, spot_price=19950.0)
    logging.info(f"GEX: {gex}")

    gex_sig = compute_gex_with_signal(sample_chain, spot_price=19950.0)
    logging.info(f"GEX regime: {gex_sig.regime} — {gex_sig.description}")
    logging.info("All pcr_gex tests passed.")
