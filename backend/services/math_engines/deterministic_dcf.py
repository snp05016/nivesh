import logging
"""
Task 22 — Deterministic DCF Valuation with Indian G-Sec Rate.

Pure mathematical DCF using CAPM for discount rate (WACC).
No AI — fully reproducible given the same inputs.
"""

from __future__ import annotations
import math
from typing import Optional


# Default Indian 10-year G-Sec yield (fallback if not fetched)
_DEFAULT_RISK_FREE_RATE = 0.068  # 6.8% as of 2025 baseline


def _fetch_indian_gsec_yield() -> float:
    """
    Attempt to fetch live Indian 10Y G-Sec yield.
    Falls back to default if unavailable.
    """
    try:
        import urllib.request
        import json
        # RBI / FRED via a simple endpoint (non-interactive, read-only)
        url = "https://api.stlouisfed.org/fred/series/observations?series_id=INTGSTINM10N&api_key=DEMO&file_type=json&limit=1&sort_order=desc"
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read())
            obs = data.get("observations", [])
            if obs:
                val = float(obs[-1].get("value", 0))
                if 2.0 < val < 15.0:
                    return val / 100
    except Exception:
        pass
    return _DEFAULT_RISK_FREE_RATE


def compute_dcf_valuation(
    fcf: float,
    growth_rate: float,
    terminal_growth: float = 0.05,
    risk_free_rate: Optional[float] = None,
    equity_risk_premium: float = 0.055,
    beta: float = 1.0,
    years: int = 10,
    debt: float = 0.0,
    equity: float = 1.0,
    cost_of_debt: float = 0.08,
    tax_rate: float = 0.25,
    shares_outstanding: Optional[float] = None,
    current_price: Optional[float] = None,
) -> dict:
    """
    Pure mathematical DCF model using CAPM for discount rate.

    CAPM: re = risk_free + beta * equity_risk_premium
    WACC = (equity / (equity+debt)) * re + (debt / (equity+debt)) * cost_of_debt * (1 - tax_rate)
    DCF  = Σ FCF*(1+g)^t / (1+WACC)^t  +  terminal_value / (1+WACC)^years
    Terminal Value = FCF_year_n * (1 + terminal_growth) / (WACC - terminal_growth)

    Args:
        fcf: base Free Cash Flow (INR Crores or absolute).
        growth_rate: expected FCF growth rate (e.g. 0.15 = 15%).
        terminal_growth: long-term sustainable growth (default 0.05 = 5%).
        risk_free_rate: Indian 10Y G-Sec yield. Fetched if None.
        equity_risk_premium: market risk premium (default 5.5%).
        beta: equity beta (default 1.0 = market).
        years: projection horizon (default 10).
        debt: total debt in same units as fcf.
        equity: equity value in same units as fcf.
        cost_of_debt: pre-tax cost of debt (default 8%).
        tax_rate: corporate tax rate (default 25%).
        shares_outstanding: to compute per-share intrinsic value.
        current_price: current market price per share.

    Returns:
        dict with 'intrinsic_value', 'per_share_value', 'margin_of_safety',
        'wacc', 'terminal_value', 'pv_fcf_sum', 'fcf_projections', 'rating'
    """
    if risk_free_rate is None:
        risk_free_rate = _fetch_indian_gsec_yield()

    # CAPM cost of equity
    cost_of_equity = risk_free_rate + beta * equity_risk_premium

    # WACC
    total_capital = equity + debt
    we = equity / total_capital if total_capital else 1.0
    wd = debt / total_capital if total_capital else 0.0
    wacc = we * cost_of_equity + wd * cost_of_debt * (1 - tax_rate)

    # Safety check: growth must not exceed WACC forever
    if terminal_growth >= wacc:
        terminal_growth = wacc * 0.5  # cap terminal growth

    # Project FCFs
    fcf_projections = []
    pv_fcf_sum = 0.0
    current_fcf = fcf

    for t in range(1, years + 1):
        projected_fcf = current_fcf * (1 + growth_rate) ** t
        discount_factor = (1 + wacc) ** t
        pv_fcf = projected_fcf / discount_factor
        pv_fcf_sum += pv_fcf
        fcf_projections.append({
            "year": t,
            "fcf": round(projected_fcf, 2),
            "pv_fcf": round(pv_fcf, 2),
            "discount_factor": round(discount_factor, 4),
        })

    # Terminal value (Gordon Growth Model)
    fcf_terminal_year = fcf * (1 + growth_rate) ** years
    terminal_value = fcf_terminal_year * (1 + terminal_growth) / (wacc - terminal_growth)
    pv_terminal = terminal_value / (1 + wacc) ** years

    intrinsic_value = pv_fcf_sum + pv_terminal

    # Per-share value
    per_share = intrinsic_value / shares_outstanding if shares_outstanding else None

    # Margin of safety
    margin_of_safety = None
    if per_share and current_price and current_price > 0:
        margin_of_safety = round((per_share - current_price) / current_price * 100, 2)

    # Rating
    if margin_of_safety is not None:
        if margin_of_safety > 30:
            rating = "DEEPLY_UNDERVALUED"
        elif margin_of_safety > 10:
            rating = "UNDERVALUED"
        elif margin_of_safety > -10:
            rating = "FAIRLY_VALUED"
        elif margin_of_safety > -30:
            rating = "OVERVALUED"
        else:
            rating = "DEEPLY_OVERVALUED"
    else:
        rating = "UNKNOWN"

    return {
        "intrinsic_value": round(intrinsic_value, 2),
        "per_share_value": round(per_share, 2) if per_share else None,
        "current_price": current_price,
        "margin_of_safety_pct": margin_of_safety,
        "rating": rating,
        "wacc": round(wacc * 100, 4),  # as percentage
        "cost_of_equity": round(cost_of_equity * 100, 4),
        "risk_free_rate": round(risk_free_rate * 100, 4),
        "terminal_value": round(terminal_value, 2),
        "pv_terminal_value": round(pv_terminal, 2),
        "pv_fcf_sum": round(pv_fcf_sum, 2),
        "terminal_value_pct_of_total": round(pv_terminal / intrinsic_value * 100, 1) if intrinsic_value else 0,
        "fcf_projections": fcf_projections,
        "assumptions": {
            "fcf": fcf,
            "growth_rate_pct": round(growth_rate * 100, 2),
            "terminal_growth_pct": round(terminal_growth * 100, 2),
            "years": years,
            "beta": beta,
            "equity_risk_premium_pct": round(equity_risk_premium * 100, 2),
        },
    }


if __name__ == "__main__":
    # Tata Consultancy Services (TCS) style example
    result = compute_dcf_valuation(
        fcf=25_000,            # FCF in Crores
        growth_rate=0.12,      # 12% growth for 10 years
        terminal_growth=0.05,  # 5% terminal growth
        risk_free_rate=0.068,  # 6.8% Indian G-Sec
        equity_risk_premium=0.055,
        beta=0.9,
        years=10,
        debt=5_000,
        equity=95_000,
        shares_outstanding=366,  # crores of shares
        current_price=3500.0,   # INR per share
    )
    logging.info(f"Intrinsic Value: ₹{result['intrinsic_value']:,.0f} Cr")
    logging.info(f"Per Share: ₹{result['per_share_value']:,.2f}")
    logging.info(f"Margin of Safety: {result['margin_of_safety_pct']:.1f}%")
    logging.info(f"WACC: {result['wacc']:.2f}%")
    logging.info(f"Rating: {result['rating']}")
    assert result["intrinsic_value"] > 0
    assert result["wacc"] > 0
    logging.info("All deterministic_dcf tests passed.")
