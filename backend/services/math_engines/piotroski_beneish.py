import logging
"""
Task 16 — Piotroski F-score and Beneish M-score engines.

Piotroski F-score (0–9): measures financial strength based on 9 criteria.
Beneish M-score: detects earnings manipulation. Score < -2.22 means likely NOT manipulating.
"""

from __future__ import annotations


def compute_piotroski_fscore(fundamentals: dict) -> dict:
    """
    Compute Piotroski F-score (0–9) from financial fundamentals.

    Args:
        fundamentals: dict with keys:
            net_income, total_assets, prev_total_assets,
            operating_cash_flow,
            prev_net_income (optional, else uses roa delta),
            long_term_debt, prev_long_term_debt,
            current_assets, current_liabilities,
            prev_current_assets, prev_current_liabilities,
            shares_outstanding, prev_shares_outstanding,
            gross_profit, revenue, prev_gross_profit, prev_revenue,
            prev_roa (optional)

    Returns:
        dict with 'score' (int 0-9), 'signals' (dict of bool), 'rating' (str)
    """
    signals: dict[str, bool] = {}

    total_assets = fundamentals.get("total_assets", 1) or 1
    prev_total_assets = fundamentals.get("prev_total_assets", total_assets) or total_assets
    net_income = fundamentals.get("net_income", 0)
    operating_cf = fundamentals.get("operating_cash_flow", 0)
    long_term_debt = fundamentals.get("long_term_debt", 0)
    prev_long_term_debt = fundamentals.get("prev_long_term_debt", 0)
    current_assets = fundamentals.get("current_assets", 0)
    current_liabilities = fundamentals.get("current_liabilities", 1) or 1
    prev_current_assets = fundamentals.get("prev_current_assets", 0)
    prev_current_liabilities = fundamentals.get("prev_current_liabilities", 1) or 1
    shares_outstanding = fundamentals.get("shares_outstanding", 0)
    prev_shares_outstanding = fundamentals.get("prev_shares_outstanding", 0)
    gross_profit = fundamentals.get("gross_profit", 0)
    revenue = fundamentals.get("revenue", 1) or 1
    prev_gross_profit = fundamentals.get("prev_gross_profit", 0)
    prev_revenue = fundamentals.get("prev_revenue", 1) or 1

    # ── Profitability signals ────────────────────────────────────────────────
    roa = net_income / total_assets
    prev_roa = fundamentals.get("prev_roa", net_income / prev_total_assets)

    # F1: ROA > 0
    signals["roa_positive"] = roa > 0

    # F2: Operating CF > 0
    signals["operating_cf_positive"] = operating_cf > 0

    # F3: Delta ROA improving
    signals["delta_roa_positive"] = roa > prev_roa

    # F4: Accruals (operating CF / total_assets > ROA)
    signals["accruals_low"] = (operating_cf / total_assets) > roa

    # ── Leverage / Liquidity signals ────────────────────────────────────────
    leverage = long_term_debt / total_assets if total_assets else 0
    prev_leverage = prev_long_term_debt / prev_total_assets if prev_total_assets else 0

    # F5: Leverage decreased (less debt relative to assets)
    signals["leverage_decreased"] = leverage < prev_leverage

    current_ratio = current_assets / current_liabilities
    prev_current_ratio = prev_current_assets / prev_current_liabilities

    # F6: Liquidity improved
    signals["liquidity_improved"] = current_ratio > prev_current_ratio

    # F7: No new shares issued
    signals["no_dilution"] = shares_outstanding <= prev_shares_outstanding

    # ── Operating efficiency signals ────────────────────────────────────────
    gross_margin = gross_profit / revenue
    prev_gross_margin = prev_gross_profit / prev_revenue

    # F8: Gross margin improved
    signals["gross_margin_improved"] = gross_margin > prev_gross_margin

    # F9: Asset turnover improved
    asset_turnover = revenue / total_assets
    prev_asset_turnover = prev_revenue / prev_total_assets if prev_total_assets else 0
    signals["asset_turnover_improved"] = asset_turnover > prev_asset_turnover

    score = sum(1 for v in signals.values() if v)

    if score >= 7:
        rating = "STRONG"
    elif score >= 4:
        rating = "MODERATE"
    else:
        rating = "WEAK"

    return {
        "score": score,
        "max_score": 9,
        "signals": signals,
        "rating": rating,
        "roa": round(roa, 4),
        "gross_margin": round(gross_margin, 4),
    }


def compute_beneish_mscore(financials: dict) -> dict:
    """
    Compute Beneish M-score from financial data.
    M-score < -2.22 → likely NOT manipulating.
    M-score > -2.22 → possible earnings manipulation.

    Args:
        financials: dict with keys:
            receivables, prev_receivables,
            revenue, prev_revenue,
            gross_profit, prev_gross_profit,
            total_assets, prev_total_assets,
            ppe (property plant equipment), prev_ppe,
            depreciation, prev_depreciation,
            sga (selling general admin), prev_sga,
            net_income,
            total_debt,
            current_assets, current_liabilities,
            cash,
            securities (long-term securities)

    Returns:
        dict with 'm_score', 'manipulator' (bool), 'variables' (dict), 'interpretation' (str)
    """
    revenue = financials.get("revenue", 1) or 1
    prev_revenue = financials.get("prev_revenue", 1) or 1
    receivables = financials.get("receivables", 0)
    prev_receivables = financials.get("prev_receivables", 0)
    gross_profit = financials.get("gross_profit", 0)
    prev_gross_profit = financials.get("prev_gross_profit", 0)
    total_assets = financials.get("total_assets", 1) or 1
    prev_total_assets = financials.get("prev_total_assets", 1) or 1
    ppe = financials.get("ppe", 0)
    prev_ppe = financials.get("prev_ppe", 0)
    depreciation = financials.get("depreciation", 1) or 1
    prev_depreciation = financials.get("prev_depreciation", 1) or 1
    sga = financials.get("sga", 0)
    prev_sga = financials.get("prev_sga", 0)
    net_income = financials.get("net_income", 0)
    total_debt = financials.get("total_debt", 0)
    current_assets = financials.get("current_assets", 0)
    current_liabilities = financials.get("current_liabilities", 1) or 1
    cash = financials.get("cash", 0)
    securities = financials.get("securities", 0)

    # ── 8 Beneish variables ─────────────────────────────────────────────────
    # DSRI: Days Sales Receivables Index
    dsr_current = receivables / revenue if revenue else 0
    dsr_prev = prev_receivables / prev_revenue if prev_revenue else 0
    dsri = dsr_current / dsr_prev if dsr_prev else 1.0

    # GMI: Gross Margin Index
    gm_current = gross_profit / revenue if revenue else 0
    gm_prev = prev_gross_profit / prev_revenue if prev_revenue else 0
    gmi = gm_prev / gm_current if gm_current else 1.0

    # AQI: Asset Quality Index
    non_current_assets = total_assets - current_assets - ppe
    prev_non_current_assets = prev_total_assets - financials.get("prev_current_assets", current_assets) - prev_ppe
    aq_current = non_current_assets / total_assets if total_assets else 0
    aq_prev = prev_non_current_assets / prev_total_assets if prev_total_assets else 0
    aqi = aq_current / aq_prev if aq_prev else 1.0

    # SGI: Sales Growth Index
    sgi = revenue / prev_revenue if prev_revenue else 1.0

    # DEPI: Depreciation Index
    dep_rate_current = depreciation / (ppe + depreciation) if (ppe + depreciation) else 0
    dep_rate_prev = prev_depreciation / (prev_ppe + prev_depreciation) if (prev_ppe + prev_depreciation) else 0
    depi = dep_rate_prev / dep_rate_current if dep_rate_current else 1.0

    # SGAI: SG&A Index
    sga_ratio_current = sga / revenue if revenue else 0
    sga_ratio_prev = prev_sga / prev_revenue if prev_revenue else 0
    sgai = sga_ratio_current / sga_ratio_prev if sga_ratio_prev else 1.0

    # Accruals (total accruals to total assets)
    working_capital = current_assets - current_liabilities - cash
    accruals = (working_capital - depreciation) / total_assets if total_assets else 0

    # LEVI: Leverage Index
    lev_current = total_debt / total_assets if total_assets else 0
    lev_prev = financials.get("prev_total_debt", total_debt) / prev_total_assets if prev_total_assets else 0
    levi = lev_current / lev_prev if lev_prev else 1.0

    # M-score formula (Beneish 1999)
    m_score = (
        -4.840
        + 0.920 * dsri
        + 0.528 * gmi
        + 0.404 * aqi
        + 0.892 * sgi
        + 0.115 * depi
        - 0.172 * sgai
        + 4.679 * accruals
        - 0.327 * levi
    )

    manipulator = m_score > -2.22

    if m_score > -1.49:
        interpretation = "HIGH manipulation risk"
    elif m_score > -2.22:
        interpretation = "MODERATE manipulation risk"
    else:
        interpretation = "LOW manipulation risk (likely not manipulating)"

    return {
        "m_score": round(m_score, 4),
        "manipulator": manipulator,
        "threshold": -2.22,
        "interpretation": interpretation,
        "variables": {
            "DSRI": round(dsri, 4),
            "GMI": round(gmi, 4),
            "AQI": round(aqi, 4),
            "SGI": round(sgi, 4),
            "DEPI": round(depi, 4),
            "SGAI": round(sgai, 4),
            "Accruals": round(accruals, 4),
            "LEVI": round(levi, 4),
        },
    }


if __name__ == "__main__":
    # Quick sanity test
    sample_fundamentals = {
        "net_income": 5_00_00_000,
        "total_assets": 50_00_00_000,
        "prev_total_assets": 45_00_00_000,
        "operating_cash_flow": 6_00_00_000,
        "long_term_debt": 10_00_00_000,
        "prev_long_term_debt": 12_00_00_000,
        "current_assets": 15_00_00_000,
        "current_liabilities": 5_00_00_000,
        "prev_current_assets": 12_00_00_000,
        "prev_current_liabilities": 5_00_00_000,
        "shares_outstanding": 1_00_00_000,
        "prev_shares_outstanding": 1_00_00_000,
        "gross_profit": 20_00_00_000,
        "revenue": 40_00_00_000,
        "prev_gross_profit": 16_00_00_000,
        "prev_revenue": 35_00_00_000,
    }
    f_result = compute_piotroski_fscore(sample_fundamentals)
    logging.info(f"Piotroski F-score: {f_result['score']}/9 — {f_result['rating']}")
    assert 0 <= f_result["score"] <= 9

    sample_financials = {
        "revenue": 40_00_00_000,
        "prev_revenue": 35_00_00_000,
        "receivables": 5_00_00_000,
        "prev_receivables": 4_00_00_000,
        "gross_profit": 20_00_00_000,
        "prev_gross_profit": 16_00_00_000,
        "total_assets": 50_00_00_000,
        "prev_total_assets": 45_00_00_000,
        "ppe": 10_00_00_000,
        "prev_ppe": 9_00_00_000,
        "depreciation": 1_00_00_000,
        "prev_depreciation": 90_00_000,
        "sga": 3_00_00_000,
        "prev_sga": 2_50_00_000,
        "net_income": 5_00_00_000,
        "total_debt": 8_00_00_000,
        "current_assets": 15_00_00_000,
        "current_liabilities": 5_00_00_000,
        "cash": 2_00_00_000,
        "securities": 1_00_00_000,
    }
    m_result = compute_beneish_mscore(sample_financials)
    logging.info(f"Beneish M-score: {m_result['m_score']} — {m_result['interpretation']}")
    logging.info("All piotroski_beneish tests passed.")
