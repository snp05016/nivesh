"""
Piotroski F-Score calculator for NSE stocks.
9-point fundamental health check from yfinance balance sheet data.
No AI calls. Score 0-3=WEAK, 4-6=NEUTRAL, 7-9=STRONG.
"""
import yfinance as yf


def compute_piotroski(ticker: str) -> dict:
    checks = {}
    score = 0
    available = 0

    def get(df, row, col=0):
        try:
            return float(df.loc[row].iloc[col])
        except Exception:
            return None

    try:
        t = yf.Ticker(f"{ticker}.NS")
        cf = t.cashflow
        bs = t.balance_sheet
        fi = t.financials

        # ── PROFITABILITY ────────────────────────────────────────────────────

        net_income = get(fi, "Net Income")
        total_assets = get(bs, "Total Assets")
        if net_income is not None and total_assets and total_assets > 0:
            p = net_income / total_assets > 0
            checks["roa_positive"] = p; score += int(p); available += 1

        ocf = get(cf, "Operating Cash Flow") or get(cf, "Total Cash From Operating Activities")
        if ocf is not None:
            p = ocf > 0
            checks["ocf_positive"] = p; score += int(p); available += 1

        net_income_ly = get(fi, "Net Income", 1)
        total_assets_ly = get(bs, "Total Assets", 1)
        if all(v is not None for v in [net_income, total_assets, net_income_ly, total_assets_ly]):
            if total_assets > 0 and total_assets_ly > 0:
                p = (net_income / total_assets) > (net_income_ly / total_assets_ly)
                checks["roa_improving"] = p; score += int(p); available += 1

        if ocf is not None and total_assets and net_income is not None and total_assets > 0:
            p = (ocf / total_assets) > (net_income / total_assets)
            checks["accruals_low"] = p; score += int(p); available += 1

        # ── LEVERAGE & LIQUIDITY ─────────────────────────────────────────────

        ltd = get(bs, "Long Term Debt")
        ltd_ly = get(bs, "Long Term Debt", 1)
        ta_ly = get(bs, "Total Assets", 1)
        if all(v is not None for v in [ltd, total_assets, ltd_ly, ta_ly]):
            if total_assets > 0 and ta_ly > 0:
                p = (ltd / total_assets) < (ltd_ly / ta_ly)
                checks["leverage_decreasing"] = p; score += int(p); available += 1

        curr_a = get(bs, "Current Assets"); curr_l = get(bs, "Current Liabilities")
        curr_a_ly = get(bs, "Current Assets", 1); curr_l_ly = get(bs, "Current Liabilities", 1)
        if all(v is not None for v in [curr_a, curr_l, curr_a_ly, curr_l_ly]):
            if curr_l > 0 and curr_l_ly > 0:
                p = (curr_a / curr_l) > (curr_a_ly / curr_l_ly)
                checks["current_ratio_improving"] = p; score += int(p); available += 1

        shares = get(bs, "Ordinary Shares Number") or get(bs, "Share Issued")
        shares_ly = get(bs, "Ordinary Shares Number", 1) or get(bs, "Share Issued", 1)
        if shares is not None and shares_ly is not None:
            # Fix 2.49: relaxed from 1.01 to 1.05 to avoid ESOP plans
            # triggering false dilution flags on standard employee stock grants
            p = shares <= shares_ly * 1.05
            checks["no_dilution"] = p; score += int(p); available += 1

        # ── EFFICIENCY ───────────────────────────────────────────────────────

        gross = get(fi, "Gross Profit"); rev = get(fi, "Total Revenue")
        gross_ly = get(fi, "Gross Profit", 1); rev_ly = get(fi, "Total Revenue", 1)
        if all(v is not None for v in [gross, rev, gross_ly, rev_ly]):
            if rev > 0 and rev_ly > 0:
                p = (gross / rev) > (gross_ly / rev_ly)
                checks["gross_margin_improving"] = p; score += int(p); available += 1

        if all(v is not None for v in [rev, total_assets, rev_ly, ta_ly]):
            if total_assets > 0 and ta_ly > 0:
                p = (rev / total_assets) > (rev_ly / ta_ly)
                checks["asset_turnover_improving"] = p; score += int(p); available += 1

    except Exception as e:
        return {"f_score": None, "grade": "UNAVAILABLE", "checks": {}, "confidence": "LOW", "error": str(e)}

    # Fix 2.6: newly listed corporations often lack operating_cash_flow
    # and other financial history rows. Below 3 available checks, the
    # F-score is meaningless — flag as INSUFFICIENT_DATA instead of WEAK.
    if available < 3:
        return {
            "f_score": None,
            "max_possible": available,
            "grade": "INSUFFICIENT_DATA",
            "confidence": "LOW",
            "checks": {k: ("PASS" if v else "FAIL") for k, v in checks.items()},
            "reason": "Too few financial data points available for this listing",
        }

    confidence = "HIGH" if available >= 8 else ("MEDIUM" if available >= 5 else "LOW")
    grade = "STRONG" if score >= 7 else ("NEUTRAL" if score >= 4 else "WEAK")

    return {
        "f_score": score,
        "max_possible": available,
        "grade": grade,
        "confidence": confidence,
        "checks": {k: ("PASS" if v else "FAIL") for k, v in checks.items()},
    }
