"""
Stock Financials Endpoints
/api/v1/stocks/{symbol}/financials — income, balance sheet, cash flow, ratios
/api/v1/stocks/{symbol}/shareholding — shareholding pattern & trends
/api/v1/stocks/{symbol}/corporate-actions — dividends, splits, bonuses, buybacks
/api/v1/stocks/{symbol}/valuation — P/E bands, peer comparison, valuation snapshot
/api/v1/stocks/{symbol}/risk-signals — consolidated risk assessment
"""

import hashlib
import logging
import math
import random
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from helpers import require_auth
from schemas.ml_signal import MLSignalResponse
from schemas.stock_fundamentals import (
    CorporateAction,
    CorporateActionsResponse,
    FinancialLineItem,
    FinancialPeriod,
    FinancialStatementResponse,
    RiskSignal,
    RiskSignalsResponse,
    ShareholderCategory,
    ShareholdingQuarter,
    ShareholdingResponse,
    TopHolder,
    ValuationResponse,
    ValuationSnapshot,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Deterministic seed per symbol so mock data is stable across requests
# ---------------------------------------------------------------------------

BANK_TICKERS = {"HDFCBANK", "ICICIBANK", "SBIN", "KOTAKBANK", "AXISBANK"}
FINANCIAL_TICKERS = BANK_TICKERS | {
    "BAJFINANCE", "CHOLAFIN", "MUTHOOTFIN", "SBICARD", "JIOFIN",
    "RECLTD", "PFC", "LICI", "HUDCO", "BANDHANBNK", "FEDERALBNK",
}


def _symbol_seed(symbol: str) -> int:
    """Return a deterministic integer seed for a ticker symbol."""
    h = hashlib.md5(symbol.strip().upper().encode()).hexdigest()
    return int(h[:8], 16)


def _seeded_random(symbol: str) -> random.Random:
    """Return a `random.Random` instance seeded deterministically from the symbol."""
    return random.Random(_symbol_seed(symbol))


def _is_bank(symbol: str) -> bool:
    return symbol.strip().upper() in BANK_TICKERS


def _is_financial(symbol: str) -> bool:
    return symbol.strip().upper() in FINANCIAL_TICKERS


# ---------------------------------------------------------------------------
# Quarter generation helpers
# ---------------------------------------------------------------------------

def _generate_quarters(symbol: str, count: int = 8) -> List[FinancialPeriod]:
    """Generate the last `count` quarters as FinancialPeriod objects, newest first."""
    today = date.today()
    # Find the most recently completed quarter
    current_month = today.month
    if current_month <= 3:
        last_quarter_end_month = 12
        last_quarter_end_year = today.year - 1
    elif current_month <= 6:
        last_quarter_end_month = 3
        last_quarter_end_year = today.year
    elif current_month <= 9:
        last_quarter_end_month = 6
        last_quarter_end_year = today.year
    else:
        last_quarter_end_month = 9
        last_quarter_end_year = today.year

    quarters: List[FinancialPeriod] = []
    end_month = last_quarter_end_month
    end_year = last_quarter_end_year
    for i in range(count):
        q_num = ((end_month - 1) // 3) + 1
        fy_suffix = str(end_year)[-2:] if end_month <= 3 else str(end_year + 1)[-2:]
        label = f"Q{q_num} FY{fy_suffix}"
        # End date: last day of the quarter month
        import calendar
        last_day = calendar.monthrange(end_year, end_month)[1]
        end_date = date(end_year, end_month, last_day).isoformat()
        is_bank = _is_bank(symbol)
        quarters.append(FinancialPeriod(
            label=label,
            end_date=end_date,
            is_bank=is_bank,
        ))
        # Step back one quarter
        end_month -= 3
        if end_month <= 0:
            end_month += 12
            end_year -= 1
    return quarters


def _quarter_labels(quarters: List[FinancialPeriod]) -> List[str]:
    return [q.label for q in quarters]


# ---------------------------------------------------------------------------
# 1. Financial Statements — GET /api/v1/stocks/{symbol}/financials
# ---------------------------------------------------------------------------

# Base revenue ranges per sector (used to scale mock data)
_SECTOR_BASE = {
    "IT": (5000, 45000), "Banking": (8000, 120000), "Finance": (2000, 60000),
    "Oil & Gas": (10000, 200000), "FMCG": (2000, 15000), "Pharma": (1500, 8000),
    "Auto": (3000, 35000), "Steel": (5000, 60000), "Cement": (2000, 15000),
    "Power": (2000, 30000), "Telecom": (3000, 35000), "Metals": (3000, 45000),
    "Mining": (2000, 20000), "Consumer": (1000, 8000), "Retail": (1000, 10000),
    "Engineering": (2000, 25000), "Defence": (500, 8000), "Chemicals": (500, 5000),
    "Consumer Tech": (500, 6000), "Infrastructure": (1000, 12000),
    "Real Estate": (500, 8000), "Media": (400, 3000), "Hotels": (300, 2500),
    "Fertilizers": (800, 6000), "Paints": (1000, 6000), "Tyres": (1000, 7000),
    "Gas": (1000, 12000), "Healthcare": (800, 6000), "Renewable Energy": (500, 5000),
    "Logistics": (500, 4000), "Travel": (300, 3000), "Electricals": (1000, 8000),
    "Consumer Durables": (1000, 12000), "Diversified": (2000, 30000),
    "Tea": (200, 1500),
}


def _sector_for_symbol(symbol: str) -> str:
    """Look up sector from the NSE directory in main.py if accessible, else default."""
    # We try to import the in-memory directory; if unavailable, fall back.
    try:
        from main import _NSE_DIR_INDEX
        s = symbol.strip().upper()
        for entry in _NSE_DIR_INDEX:
            if entry["_t"] == s.lower():
                return entry["sector"]
    except Exception:
        pass
    return "Diversified"


def _build_income_line_items(
    symbol: str, labels: List[str], rng: random.Random, base: float
) -> List[FinancialLineItem]:
    is_bank = _is_bank(symbol)
    # Common items
    items: List[dict] = []

    if not is_bank:
        revenue = [base * (1.0 + rng.uniform(-0.15, 0.25)) * (1.0 + i * 0.04) for i in range(len(labels))]
        # Reverse so newest is first
        revenue = revenue[::-1]
        cogs_pct = rng.uniform(0.35, 0.65)
        ebitda_margin = rng.uniform(0.15, 0.35)

        items.append({"label": "Revenue", "values": revenue, "is_pct": False})

        cogs = [v * cogs_pct for v in revenue]
        items.append({"label": "Cost of Goods Sold", "values": cogs, "is_pct": False})

        gross = [revenue[i] - cogs[i] for i in range(len(revenue))]
        items.append({"label": "Gross Profit", "values": gross, "is_pct": False})

        ebitda = [revenue[i] * ebitda_margin for i in range(len(revenue))]
        items.append({"label": "EBITDA", "values": ebitda, "is_pct": False})

        depreciation = [ebitda[i] * rng.uniform(0.15, 0.40) for i in range(len(ebitda))]
        items.append({"label": "Depreciation & Amortisation", "values": depreciation, "is_pct": False})

        ebit = [ebitda[i] - depreciation[i] for i in range(len(ebitda))]
        items.append({"label": "EBIT", "values": ebit, "is_pct": False})

        interest = []
        for v in revenue:
            rate = rng.uniform(0.04, 0.12)
            interest.append(v * rate * rng.uniform(0.05, 0.25))
        items.append({"label": "Interest Expense", "values": interest, "is_pct": False})

        other_income = [revenue[i] * rng.uniform(0.005, 0.04) for i in range(len(revenue))]
        items.append({"label": "Other Income", "values": other_income, "is_pct": False})

        pbt = [ebit[i] - interest[i] + other_income[i] for i in range(len(revenue))]
        items.append({"label": "Profit Before Tax", "values": pbt, "is_pct": False})

        tax_rate = rng.uniform(0.22, 0.28)
        tax = [max(0, pbt[i] * tax_rate) for i in range(len(pbt))]
        items.append({"label": "Tax Expense", "values": tax, "is_pct": False})

        net_profit = [pbt[i] - tax[i] for i in range(len(pbt))]
        items.append({"label": "Net Profit", "values": net_profit, "is_pct": False})

        # Margins
        gross_margin = [(gross[i] / revenue[i]) * 100 if revenue[i] else 0 for i in range(len(revenue))]
        items.append({"label": "Gross Margin %", "values": gross_margin, "is_pct": True})

        ebitda_m = [(ebitda[i] / revenue[i]) * 100 if revenue[i] else 0 for i in range(len(revenue))]
        items.append({"label": "EBITDA Margin %", "values": ebitda_m, "is_pct": True})

        net_margin = [(net_profit[i] / revenue[i]) * 100 if revenue[i] else 0 for i in range(len(revenue))]
        items.append({"label": "Net Profit Margin %", "values": net_margin, "is_pct": True})

        eps_vals = [net_profit[i] / (base * 0.001 + rng.uniform(10, 500)) for i in range(len(net_profit))]
        items.append({"label": "EPS (₹)", "values": eps_vals, "is_pct": False})
    else:
        # Bank-specific income
        nii_base = base * rng.uniform(0.15, 0.30)
        nii = [nii_base * (1.0 + rng.uniform(-0.10, 0.20)) * (1.0 + i * 0.05) for i in range(len(labels))]
        nii = nii[::-1]

        items.append({"label": "Net Interest Income (NII)", "values": nii, "is_pct": False, "bank_specific": True})

        other_income_b = [nii[i] * rng.uniform(0.15, 0.40) for i in range(len(nii))]
        items.append({"label": "Other Income", "values": other_income_b, "is_pct": False})

        total_income_b = [nii[i] + other_income_b[i] for i in range(len(nii))]
        items.append({"label": "Total Income", "values": total_income_b, "is_pct": False})

        opex_b = [total_income_b[i] * rng.uniform(0.40, 0.55) for i in range(len(total_income_b))]
        items.append({"label": "Operating Expenses", "values": opex_b, "is_pct": False})

        ppp = [total_income_b[i] - opex_b[i] for i in range(len(total_income_b))]
        items.append({"label": "Pre-Provision Profit (PPP)", "values": ppp, "is_pct": False, "bank_specific": True})

        provisions = [ppp[i] * rng.uniform(0.10, 0.35) for i in range(len(ppp))]
        items.append({"label": "Provisions & Contingencies", "values": provisions, "is_pct": False})

        pbt_b = [ppp[i] - provisions[i] for i in range(len(ppp))]
        items.append({"label": "Profit Before Tax", "values": pbt_b, "is_pct": False})

        tax_b = [max(0, pbt_b[i] * rng.uniform(0.22, 0.28)) for i in range(len(pbt_b))]
        items.append({"label": "Tax Expense", "values": tax_b, "is_pct": False})

        net_profit_b = [pbt_b[i] - tax_b[i] for i in range(len(pbt_b))]
        items.append({"label": "Net Profit", "values": net_profit_b, "is_pct": False})

        # Bank margins
        nim = [rng.uniform(3.0, 4.5) for _ in range(len(nii))]
        items.append({"label": "Net Interest Margin (NIM) %", "values": nim, "is_pct": True, "bank_specific": True})

        cost_income = [(opex_b[i] / total_income_b[i]) * 100 if total_income_b[i] else 0 for i in range(len(nii))]
        items.append({"label": "Cost-to-Income %", "values": cost_income, "is_pct": True, "bank_specific": True})

        eps_b = [net_profit_b[i] / (rng.uniform(100, 2000)) for i in range(len(net_profit_b))]
        items.append({"label": "EPS (₹)", "values": eps_b, "is_pct": False})

    # Build FinancialLineItem objects
    result: List[FinancialLineItem] = []
    for item in items:
        values = {}
        qoq = {}
        yoy = {}
        vals = item["values"]
        for idx, lbl in enumerate(labels):
            values[lbl] = round(vals[idx], 2)
            if idx < len(vals) - 1:
                prev = vals[idx + 1]
                qoq[lbl] = round(((vals[idx] - prev) / abs(prev)) * 100, 2) if prev != 0 else None
            else:
                qoq[lbl] = None
            yoy_idx = idx + 4
            if yoy_idx < len(vals):
                prev_yr = vals[yoy_idx]
                yoy[lbl] = round(((vals[idx] - prev_yr) / abs(prev_yr)) * 100, 2) if prev_yr != 0 else None
            else:
                yoy[lbl] = None

        result.append(FinancialLineItem(
            label=item["label"],
            group="INCOME",
            values=values,
            qoq_change_pct=qoq,
            yoy_change_pct=yoy,
            is_percentage=item.get("is_pct", False),
            bank_specific=item.get("bank_specific", False),
        ))
    return result


def _build_balance_sheet_line_items(
    symbol: str, labels: List[str], rng: random.Random, base: float
) -> List[FinancialLineItem]:
    is_bank = _is_bank(symbol)
    items: List[FinancialLineItem] = []

    if not is_bank:
        # Non-bank balance sheet
        equity_base = base * rng.uniform(2.0, 8.0)
        equity = [equity_base * (1.0 + i * 0.06) for i in range(len(labels))]
        equity = equity[::-1]
        items.append(_make_bs_item("Shareholders' Equity", equity, labels))

        total_assets_mult = rng.uniform(2.5, 6.0)
        total_assets = [e * total_assets_mult for e in equity]
        items.append(_make_bs_item("Total Assets", total_assets, labels))

        fixed_assets = [a * rng.uniform(0.20, 0.50) for a in total_assets]
        items.append(_make_bs_item("Fixed Assets", fixed_assets, labels))

        current_assets = [a * rng.uniform(0.30, 0.55) for a in total_assets]
        items.append(_make_bs_item("Current Assets", current_assets, labels))

        borrowings = [total_assets[i] * rng.uniform(0.05, 0.35) for i in range(len(total_assets))]
        items.append(_make_bs_item("Total Borrowings", borrowings, labels))

        current_liab = [total_assets[i] * rng.uniform(0.20, 0.40) for i in range(len(total_assets))]
        items.append(_make_bs_item("Current Liabilities", current_liab, labels))

        # Debt-to-equity
        de = [(borrowings[i] / equity[i]) if equity[i] else 0 for i in range(len(equity))]
        items.append(_make_bs_item("Debt/Equity", de, labels, is_pct=True))
    else:
        # Bank balance sheet
        advances_base = base * rng.uniform(20.0, 60.0)
        advances = [advances_base * (1.0 + i * 0.06) for i in range(len(labels))]
        advances = advances[::-1]
        items.append(_make_bs_item("Advances (Loans)", advances, labels, bank_specific=True))

        deposits_base = advances_base * rng.uniform(1.1, 1.4)
        deposits = [deposits_base * (1.0 + i * 0.06) for i in range(len(labels))]
        deposits = deposits[::-1]
        items.append(_make_bs_item("Deposits", deposits, labels, bank_specific=True))

        total_assets_b = [deposits[i] * rng.uniform(1.05, 1.20) for i in range(len(deposits))]
        items.append(_make_bs_item("Total Assets", total_assets_b, labels))

        networth_b = [total_assets_b[i] * rng.uniform(0.06, 0.12) for i in range(len(total_assets_b))]
        items.append(_make_bs_item("Net Worth", networth_b, labels))

        borrowings_b = [total_assets_b[i] * rng.uniform(0.02, 0.10) for i in range(len(total_assets_b))]
        items.append(_make_bs_item("Borrowings", borrowings_b, labels))

        # Asset quality
        gnpa = [rng.uniform(0.80, 3.50) for _ in range(len(labels))]
        items.append(_make_bs_item("Gross NPA %", gnpa, labels, is_pct=True, bank_specific=True))

        nnpa = [rng.uniform(0.20, 1.20) for _ in range(len(labels))]
        items.append(_make_bs_item("Net NPA %", nnpa, labels, is_pct=True, bank_specific=True))

        prov_coverage = [rng.uniform(55.0, 85.0) for _ in range(len(labels))]
        items.append(_make_bs_item("Provision Coverage Ratio %", prov_coverage, labels, is_pct=True, bank_specific=True))

        car = [rng.uniform(14.0, 20.0) for _ in range(len(labels))]
        items.append(_make_bs_item("CRAR / CAR %", car, labels, is_pct=True, bank_specific=True))

        cd_ratio = [rng.uniform(65.0, 85.0) for _ in range(len(labels))]
        items.append(_make_bs_item("Credit-Deposit Ratio %", cd_ratio, labels, is_pct=True, bank_specific=True))

    return items


def _make_bs_item(
    label: str,
    values: List[float],
    labels: List[str],
    is_pct: bool = False,
    bank_specific: bool = False,
) -> FinancialLineItem:
    vals: Dict[str, Optional[float]] = {}
    qoq: Dict[str, Optional[float]] = {}
    yoy: Dict[str, Optional[float]] = {}
    for idx, lbl in enumerate(labels):
        vals[lbl] = round(values[idx], 2)
        if idx < len(values) - 1:
            prev = values[idx + 1]
            qoq[lbl] = round(((values[idx] - prev) / abs(prev)) * 100, 2) if prev != 0 else None
        else:
            qoq[lbl] = None
        yoy_idx = idx + 4
        if yoy_idx < len(values):
            prev_yr = values[yoy_idx]
            yoy[lbl] = round(((values[idx] - prev_yr) / abs(prev_yr)) * 100, 2) if prev_yr != 0 else None
        else:
            yoy[lbl] = None
    return FinancialLineItem(
        label=label,
        group="BALANCE_SHEET",
        values=vals,
        qoq_change_pct=qoq,
        yoy_change_pct=yoy,
        is_percentage=is_pct,
        bank_specific=bank_specific,
    )


def _build_cash_flow_line_items(
    symbol: str, labels: List[str], rng: random.Random, base: float
) -> List[FinancialLineItem]:
    items: List[FinancialLineItem] = []
    n = len(labels)

    ops = [base * rng.uniform(0.08, 0.25) * (1.0 + i * 0.05) for i in range(n)]
    ops = ops[::-1]
    items.append(_make_cf_item("Operating Cash Flow", ops, labels))

    capex = [ops[i] * rng.uniform(-0.80, -0.20) for i in range(n)]
    items.append(_make_cf_item("Capital Expenditure", capex, labels))

    fcf = [ops[i] + capex[i] for i in range(n)]
    items.append(_make_cf_item("Free Cash Flow", fcf, labels))

    fin = [fcf[i] * rng.uniform(-0.40, 0.10) for i in range(n)]
    items.append(_make_cf_item("Financing Cash Flow", fin, labels))

    inv = [fcf[i] * rng.uniform(-0.30, 0.05) for i in range(n)]
    items.append(_make_cf_item("Investing Cash Flow", inv, labels))

    net = [ops[i] + capex[i] + fin[i] + inv[i] for i in range(n)]
    items.append(_make_cf_item("Net Cash Flow", net, labels))

    return items


def _make_cf_item(label: str, values: List[float], labels: List[str]) -> FinancialLineItem:
    vals: Dict[str, Optional[float]] = {}
    qoq: Dict[str, Optional[float]] = {}
    yoy: Dict[str, Optional[float]] = {}
    for idx, lbl in enumerate(labels):
        vals[lbl] = round(values[idx], 2)
        if idx < len(values) - 1:
            prev = values[idx + 1]
            qoq[lbl] = round(((values[idx] - prev) / abs(prev)) * 100, 2) if prev != 0 else None
        else:
            qoq[lbl] = None
        yoy_idx = idx + 4
        if yoy_idx < len(values):
            prev_yr = values[yoy_idx]
            yoy[lbl] = round(((values[idx] - prev_yr) / abs(prev_yr)) * 100, 2) if prev_yr != 0 else None
        else:
            yoy[lbl] = None
    return FinancialLineItem(
        label=label,
        group="CASH_FLOW",
        values=vals,
        qoq_change_pct=qoq,
        yoy_change_pct=yoy,
        is_percentage=False,
        bank_specific=False,
    )


def _build_ratio_line_items(
    symbol: str, labels: List[str], rng: random.Random
) -> List[FinancialLineItem]:
    n = len(labels)
    items: List[FinancialLineItem] = []

    roe = [rng.uniform(8.0, 28.0) for _ in range(n)]
    items.append(_make_ratio_item("ROE %", roe, labels))

    roce = [rng.uniform(10.0, 30.0) for _ in range(n)]
    items.append(_make_ratio_item("ROCE %", roce, labels))

    debteq = [rng.uniform(0.0, 1.5) for _ in range(n)]
    items.append(_make_ratio_item("Debt/Equity", debteq, labels))

    current_ratio = [rng.uniform(1.0, 3.5) for _ in range(n)]
    items.append(_make_ratio_item("Current Ratio", current_ratio, labels))

    asset_turnover = [rng.uniform(0.3, 1.5) for _ in range(n)]
    items.append(_make_ratio_item("Asset Turnover", asset_turnover, labels))

    if not _is_bank(symbol):
        inventory_turnover = [rng.uniform(3.0, 12.0) for _ in range(n)]
        items.append(_make_ratio_item("Inventory Turnover", inventory_turnover, labels))

    return items


def _make_ratio_item(label: str, values: List[float], labels: List[str]) -> FinancialLineItem:
    vals: Dict[str, Optional[float]] = {}
    qoq: Dict[str, Optional[float]] = {}
    yoy: Dict[str, Optional[float]] = {}
    for idx, lbl in enumerate(labels):
        vals[lbl] = round(values[idx], 2)
        if idx < len(values) - 1:
            prev = values[idx + 1]
            qoq[lbl] = round(values[idx] - prev, 2)
        else:
            qoq[lbl] = None
        yoy_idx = idx + 4
        if yoy_idx < len(values):
            prev_yr = values[yoy_idx]
            yoy[lbl] = round(values[idx] - prev_yr, 2)
        else:
            yoy[lbl] = None
    return FinancialLineItem(
        label=label,
        group="RATIOS",
        values=vals,
        qoq_change_pct=qoq,
        yoy_change_pct=yoy,
        is_percentage=True,
        bank_specific=False,
    )


@router.get(
    "/api/v1/stocks/{symbol}/financials",
    response_model=FinancialStatementResponse,
    summary="Stock Financial Statements",
    description="Returns income statement, balance sheet, cash flow, and ratio line items "
    "across the requested number of periods. Supports bank-specific labels for Indian "
    "bank tickers (HDFCBANK, ICICIBANK, SBIN, KOTAKBANK, AXISBANK).",
)
def get_stock_financials(
    symbol: str,
    period_type: str = Query("QUARTERLY", description="QUARTERLY or ANNUAL"),
    consolidation: str = Query("STANDALONE", description="STANDALONE or CONSOLIDATED"),
    periods: Optional[int] = Query(8, description="Number of periods to return", ge=1, le=20),
    user_id: int = Depends(require_auth),
):
    """Return financial statements for a given ticker symbol."""
    try:
        symbol = symbol.strip().upper()
        rng = _seeded_random(symbol)
        sector = _sector_for_symbol(symbol)
        base_range = _SECTOR_BASE.get(sector, (500, 5000))
        base = rng.uniform(base_range[0], base_range[1])

        quarters = _generate_quarters(symbol, min(periods, 20))
        labels = _quarter_labels(quarters)

        line_items: List[FinancialLineItem] = []
        line_items.extend(_build_income_line_items(symbol, labels, rng, base))
        line_items.extend(_build_balance_sheet_line_items(symbol, labels, rng, base))
        line_items.extend(_build_cash_flow_line_items(symbol, labels, rng, base))
        line_items.extend(_build_ratio_line_items(symbol, labels, rng))

        # Also generate annual labels for available_periods
        today = date.today()
        current_fy_end = today.year if today.month > 3 else today.year - 1
        annual_labels = [f"FY{str(y)[-2:]}" for y in range(current_fy_end, current_fy_end - 5, -1)]
        available_periods = labels + annual_labels

        return FinancialStatementResponse(
            ticker=symbol,
            period_type=period_type,
            consolidation=consolidation,
            periods=quarters,
            line_items=line_items,
            available_periods=available_periods,
        )
    except Exception:
        logger.exception("Failed to build financials for %s", symbol)
        raise HTTPException(status_code=500, detail="Internal error building financial statements")


# ---------------------------------------------------------------------------
# 2. Shareholding Pattern — GET /api/v1/stocks/{symbol}/shareholding
# ---------------------------------------------------------------------------

_PROMOTER_ENTITIES = {
    "RELIANCE": ["Mukesh Ambani (Family)", "Reliance Group Holdings", "Petroleum Trust"],
    "TCS": ["Tata Sons Pvt Ltd", "Tata Investment Corporation", "Ratan Tata Trust"],
    "HDFCBANK": ["Housing Development Finance Corp", "HDFC Trustee Company"],
    "INFY": ["Sudha Gopalakrishnan", "Nandan Nilekani", "S. Gopalakrishnan Family Trust"],
    "ICICIBANK": ["ICICI Prudential Trust", "LIC of India"],
    "SBIN": ["Government of India", "LIC of India", "SBI Mutual Fund"],
    "HINDUNILVR": ["Unilever PLC", "Hindustan Unilever Trust"],
    "ITC": ["LIC of India", "Specified Undertaking of UTI", "General Insurance Corp"],
    "TITAN": ["Tata Sons Pvt Ltd", "TIDCO", "Rakesh Jhunjhunwala Family"],
    "MARUTI": ["Suzuki Motor Corporation", "LIC of India"],
    "BHARTIARTL": ["Bharti Telecom Ltd", "SingTel", "Pastel Ltd"],
    "KOTAKBANK": ["Uday Kotak Family", "Kotak Mahindra Trustee Co"],
    "AXISBANK": ["LIC of India", "Specified Undertaking of UTI", "Axis Mutual Fund Trustee"],
    "WIPRO": ["Azim Premji Trust", "Hasham Premji Family"],
    "NTPC": ["Government of India", "LIC of India"],
    "ONGC": ["Government of India", "LIC of India"],
    "COALINDIA": ["Government of India", "LIC of India"],
    "LT": ["LIC of India", "Specified Undertaking of UTI", "SBI Mutual Fund"],
    "SUNPHARMA": ["Dilip Shanghvi Family", "Shanghvi Finance"],
    "ADANIENT": ["Gautam Adani Family", "Adani Tradeline LLP", "Emerging Market Investment DMCC"],
    "TATAMOTORS": ["Tata Sons Pvt Ltd", "Tata Investment Corporation"],
    "HCLTECH": ["Shiv Nadar Trust", "HCL Corporation"],
    "BAJFINANCE": ["Bajaj Family Trusts", "Rahul Bajaj Family"],
    "DIVISLAB": ["Murali K. Divi Family Trust"],
}

_FII_NAMES = [
    "Government of Singapore", "Vanguard Emerging Markets", "BlackRock Global Funds",
    "Abu Dhabi Investment Authority", "Norges Bank (Govt Pension Fund)", "Capital Group",
    "Fidelity Investments", "EuroPacific Growth Fund", "JPMorgan Chase",
    "Goldman Sachs Asset Management", "Morgan Stanley Asia", "T. Rowe Price",
]

_DII_NAMES = [
    "LIC of India", "SBI Mutual Fund", "HDFC Mutual Fund", "ICICI Prudential Mutual Fund",
    "Nippon India Mutual Fund", "Kotak Mahindra Mutual Fund", "UTI Mutual Fund",
    "Axis Mutual Fund", "Mirae Asset Mutual Fund", "Aditya Birla Sun Life Mutual Fund",
]

_PUBLIC_NAMES = [
    "Ishares Core MSCI EM", "Rakesh Jhunjhunwala", "Radhakishan Damani",
    "Rekha Jhunjhunwala", "Ashish Dhawan", "Vanguard Total International",
]


def _trend_label(bps_change: float) -> Optional[str]:
    if bps_change < -200:
        return "selling"
    elif bps_change < -50:
        return "falling"
    elif bps_change > 200:
        return "accumulating"
    elif bps_change > 50:
        return "rising"
    return None


@router.get(
    "/api/v1/stocks/{symbol}/shareholding",
    response_model=ShareholdingResponse,
    summary="Shareholding Pattern",
    description="Returns current shareholding pattern broken down by investor category, "
    "top 10 holders, promoter pledge details, and multi-quarter holding trends.",
)
def get_shareholding(symbol: str, user_id: int = Depends(require_auth)):
    """Return shareholding pattern for a given ticker."""
    try:
        symbol = symbol.strip().upper()
        rng = _seeded_random(symbol)
        is_psu = symbol in {"NTPC", "ONGC", "COALINDIA", "SBIN", "PFC", "RECLTD", "NHPC", "SAIL", "NMDC", "HUDCO", "BHEL", "BEL"}

        # Generate 8 quarters of trend data
        quarter_labels = _quarter_labels(_generate_quarters(symbol, 8))
        latest_quarter = quarter_labels[0]
        available_quarters = quarter_labels

        # Base holdings with realistic ranges
        if is_psu:
            prom_base = rng.uniform(55.0, 75.0)
            fii_base = rng.uniform(3.0, 12.0)
            dii_base = rng.uniform(8.0, 20.0)
        elif symbol == "ADANIENT":
            prom_base = rng.uniform(65.0, 75.0)
            fii_base = rng.uniform(5.0, 12.0)
            dii_base = rng.uniform(3.0, 8.0)
        else:
            prom_base = rng.uniform(25.0, 55.0)
            fii_base = rng.uniform(10.0, 35.0)
            dii_base = rng.uniform(8.0, 20.0)

        # Generate trend series with small random walks
        trend: List[ShareholdingQuarter] = []
        prom = prom_base
        fii = fii_base
        dii = dii_base
        for q_label in quarter_labels:
            prom += rng.uniform(-1.2, 0.8)
            fii += rng.uniform(-1.5, 1.5)
            dii += rng.uniform(-1.0, 1.0)
            prom = max(5, min(95, prom))
            fii = max(0, min(60, fii))
            dii = max(0, min(40, dii))
            public_pct = round(100 - prom - fii - dii, 2)
            others_pct = round(rng.uniform(0, max(0.5, public_pct * 0.2)), 2)
            public_pct = round(public_pct - others_pct, 2)
            if public_pct < 0:
                public_pct = 0
            trend.append(ShareholdingQuarter(
                quarter=q_label,
                promoter_pct=round(prom, 2),
                fii_pct=round(fii, 2),
                dii_pct=round(dii, 2),
                public_pct=round(public_pct, 2),
                others_pct=round(others_pct, 2),
            ))

        latest = trend[0]
        prev = trend[1] if len(trend) > 1 else None
        prev_year = trend[4] if len(trend) > 4 else None

        # Category objects
        categories: List[ShareholderCategory] = []
        prom_qoq = round((latest.promoter_pct - prev.promoter_pct) * 100, 2) if prev else None
        prom_yoy = round((latest.promoter_pct - prev_year.promoter_pct) * 100, 2) if prev_year else None
        categories.append(ShareholderCategory(
            name="PROMOTER",
            current_pct=latest.promoter_pct,
            qoq_change_bps=prom_qoq,
            yoy_change_bps=prom_yoy,
            warning=_trend_label(prom_qoq or 0),
        ))
        fii_qoq = round((latest.fii_pct - prev.fii_pct) * 100, 2) if prev else None
        fii_yoy = round((latest.fii_pct - prev_year.fii_pct) * 100, 2) if prev_year else None
        categories.append(ShareholderCategory(
            name="FII",
            current_pct=latest.fii_pct,
            qoq_change_bps=fii_qoq,
            yoy_change_bps=fii_yoy,
            warning=_trend_label(fii_qoq or 0),
        ))
        dii_qoq = round((latest.dii_pct - prev.dii_pct) * 100, 2) if prev else None
        dii_yoy = round((latest.dii_pct - prev_year.dii_pct) * 100, 2) if prev_year else None
        categories.append(ShareholderCategory(
            name="DII",
            current_pct=latest.dii_pct,
            qoq_change_bps=dii_qoq,
            yoy_change_bps=dii_yoy,
            warning=_trend_label(dii_qoq or 0),
        ))
        pub_qoq = round((latest.public_pct - prev.public_pct) * 100, 2) if prev else None
        pub_yoy = round((latest.public_pct - prev_year.public_pct) * 100, 2) if prev_year else None
        categories.append(ShareholderCategory(
            name="PUBLIC",
            current_pct=latest.public_pct,
            qoq_change_bps=pub_qoq,
            yoy_change_bps=pub_yoy,
            warning=_trend_label(pub_qoq or 0),
        ))
        categories.append(ShareholderCategory(
            name="OTHERS",
            current_pct=latest.others_pct,
            qoq_change_bps=None,
            yoy_change_bps=None,
            warning=None,
        ))

        # Top holders
        total_shares_cr = rng.uniform(50, 5000)
        top_holders: List[TopHolder] = []
        prom_entities = _PROMOTER_ENTITIES.get(symbol, [f"{symbol} Promoter Holdings Pvt Ltd", f"{symbol} Family Trust"])
        for name in prom_entities:
            pct = latest.promoter_pct / len(prom_entities) * rng.uniform(0.6, 1.4)
            pct = min(pct, latest.promoter_pct - sum(h.holding_pct for h in top_holders if h.category == "PROMOTER"))
            if pct > 0.5:
                top_holders.append(TopHolder(
                    name=name,
                    category="PROMOTER",
                    shares_crores=round(pct / 100 * total_shares_cr, 4),
                    holding_pct=round(pct, 2),
                    qoq_change_bps=round(rng.uniform(-30, 30), 2),
                ))

        # FII holders
        fii_sampled = rng.sample(_FII_NAMES, min(3, len(_FII_NAMES)))
        remaining_fii = latest.fii_pct
        for name in fii_sampled:
            pct = remaining_fii / (len(fii_sampled) - fii_sampled.index(name)) * rng.uniform(0.4, 1.3)
            pct = min(pct, remaining_fii)
            if pct > 0.3:
                top_holders.append(TopHolder(
                    name=name,
                    category="FII",
                    shares_crores=round(pct / 100 * total_shares_cr, 4),
                    holding_pct=round(pct, 2),
                    qoq_change_bps=round(rng.uniform(-50, 80), 2),
                ))
                remaining_fii -= pct

        # DII holders
        dii_sampled = rng.sample(_DII_NAMES, min(2, len(_DII_NAMES)))
        remaining_dii = latest.dii_pct
        for name in dii_sampled:
            pct = remaining_dii / (len(dii_sampled) - dii_sampled.index(name)) * rng.uniform(0.5, 1.2)
            pct = min(pct, remaining_dii)
            if pct > 0.3:
                top_holders.append(TopHolder(
                    name=name,
                    category="DII",
                    shares_crores=round(pct / 100 * total_shares_cr, 4),
                    holding_pct=round(pct, 2),
                    qoq_change_bps=round(rng.uniform(-40, 60), 2),
                ))
                remaining_dii -= pct

        # Public holders
        pub_sampled = rng.sample(_PUBLIC_NAMES, min(2, len(_PUBLIC_NAMES)))
        for name in pub_sampled:
            pct = latest.public_pct / 5 * rng.uniform(0.3, 1.5)
            if pct > 0.2:
                top_holders.append(TopHolder(
                    name=name,
                    category="PUBLIC",
                    shares_crores=round(pct / 100 * total_shares_cr, 4),
                    holding_pct=round(pct, 2),
                    qoq_change_bps=round(rng.uniform(-20, 30), 2),
                ))

        # Pledge — higher for certain groups
        if is_psu:
            pledge_pct = 0.0
        elif symbol.startswith("ADANI"):
            pledge_pct = rng.uniform(5.0, 35.0)
        elif latest.promoter_pct > 50:
            pledge_pct = rng.uniform(0.0, 18.0)
        else:
            pledge_pct = rng.uniform(0.0, 8.0)

        pledge_qoq = round(rng.uniform(-3.0, 3.0), 2)

        return ShareholdingResponse(
            ticker=symbol,
            latest_quarter=latest_quarter,
            available_quarters=available_quarters,
            categories=categories,
            top_holders=top_holders[:10],
            promoter_pledge_pct=round(pledge_pct, 2),
            promoter_pledge_qoq_change=pledge_qoq,
            holding_trend=trend,
        )
    except Exception:
        logger.exception("Failed to build shareholding for %s", symbol)
        raise HTTPException(status_code=500, detail="Internal error building shareholding pattern")


# ---------------------------------------------------------------------------
# 3. Corporate Actions — GET /api/v1/stocks/{symbol}/corporate-actions
# ---------------------------------------------------------------------------

# Realistic dividend yields by sector
_SECTOR_DIV_YIELD = {
    "IT": (0.3, 2.5), "Banking": (0.5, 2.0), "FMCG": (1.0, 3.5),
    "Pharma": (0.5, 2.5), "Oil & Gas": (1.5, 5.0), "Power": (1.0, 4.0),
    "Telecom": (0.5, 3.0), "Steel": (0.5, 3.0), "Metals": (0.5, 3.0),
    "Cement": (0.5, 2.0), "Auto": (0.5, 2.5), "Mining": (2.0, 6.0),
    "Consumer": (0.5, 2.5), "Finance": (0.0, 2.0), "Chemicals": (0.3, 1.5),
    "Infrastructure": (0.3, 1.5), "Gas": (1.0, 3.5), "Paints": (0.5, 1.5),
    "Retail": (0.0, 1.0), "Healthcare": (0.3, 1.5), "Real Estate": (0.0, 1.0),
    "Diversified": (0.5, 2.5), "Renewable Energy": (0.0, 1.0),
    "Fertilizers": (0.5, 2.0), "Consumer Tech": (0.0, 0.5),
    "Consumer Durables": (0.3, 1.5), "Media": (0.5, 3.0),
    "Hotels": (0.0, 0.5), "Engineering": (0.5, 2.0), "Defence": (0.2, 1.5),
    "Electricals": (0.3, 1.5), "Logistics": (0.0, 1.0), "Travel": (0.0, 1.0),
    "Tyres": (0.5, 2.0), "Tea": (0.5, 2.0),
}


@router.get(
    "/api/v1/stocks/{symbol}/corporate-actions",
    response_model=CorporateActionsResponse,
    summary="Corporate Actions",
    description="Returns historical and upcoming corporate actions: dividends "
    "(interim + final), bonus issues, stock splits, rights issues, and buybacks.",
)
def get_corporate_actions(symbol: str, user_id: int = Depends(require_auth)):
    """Return corporate actions history for a given ticker."""
    try:
        symbol = symbol.strip().upper()
        rng = _seeded_random(symbol)
        sector = _sector_for_symbol(symbol)
        div_range = _SECTOR_DIV_YIELD.get(sector, (0.3, 2.0))
        today = date.today()

        actions: List[CorporateAction] = []
        # Generate 4 years of historical corporate actions
        for year_offset in range(4):
            yr = today.year - year_offset
            # Final dividend — issued after year-end
            final_div_amt = round(rng.uniform(2.0, 25.0), 2)
            final_ann = date(yr, rng.choice([3, 4, 5]), rng.randint(1, 28))
            final_ex = final_ann + timedelta(days=rng.randint(7, 21))
            final_rec = final_ex + timedelta(days=rng.randint(2, 5))
            actions.append(CorporateAction(
                type="DIVIDEND",
                announcement_date=final_ann.isoformat(),
                ex_date=final_ex.isoformat(),
                record_date=final_rec.isoformat(),
                details=f"Final Dividend of ₹{final_div_amt} per share for FY{str(yr - 1)[-2:]}",
                amount=final_div_amt,
                ratio=None,
            ))
            # Interim dividend (most years)
            if rng.random() > 0.15:
                interim_div_amt = round(rng.uniform(1.0, 15.0), 2)
                interim_ann = date(yr, rng.choice([10, 11]), rng.randint(1, 28))
                interim_ex = interim_ann + timedelta(days=rng.randint(7, 21))
                interim_rec = interim_ex + timedelta(days=rng.randint(2, 5))
                actions.append(CorporateAction(
                    type="DIVIDEND",
                    announcement_date=interim_ann.isoformat(),
                    ex_date=interim_ex.isoformat(),
                    record_date=interim_rec.isoformat(),
                    details=f"Interim Dividend of ₹{interim_div_amt} per share for FY{str(yr)[-2:]}",
                    amount=interim_div_amt,
                    ratio=None,
                ))

        # Past bonus issues (1-2 in history)
        bonus_years = [today.year - rng.randint(3, 8), today.year - rng.randint(9, 15)]
        bonus_ratios = ["1:1", "1:2", "2:1", "3:1", "1:3", "5:1"]
        for byr in bonus_years[:rng.randint(0, 3)]:
            ratio = rng.choice(bonus_ratios)
            ann_d = date(byr, rng.randint(1, 12), rng.randint(1, 28))
            actions.append(CorporateAction(
                type="BONUS",
                announcement_date=ann_d.isoformat(),
                ex_date=(ann_d + timedelta(days=21)).isoformat(),
                record_date=(ann_d + timedelta(days=24)).isoformat(),
                details=f"Bonus Issue in the ratio of {ratio}",
                amount=None,
                ratio=ratio,
            ))

        # Stock splits (0-2 in history)
        split_years = [today.year - rng.randint(5, 10)]
        split_ratios = ["2:1", "5:1", "10:1", "1:5"]
        for syr in split_years[:rng.randint(0, 2)]:
            ratio = rng.choice(split_ratios)
            ann_d = date(syr, rng.randint(1, 12), rng.randint(1, 28))
            actions.append(CorporateAction(
                type="SPLIT",
                announcement_date=ann_d.isoformat(),
                ex_date=(ann_d + timedelta(days=14)).isoformat(),
                record_date=(ann_d + timedelta(days=17)).isoformat(),
                details=f"Stock Split — face value changed, ratio {ratio}",
                amount=None,
                ratio=ratio,
            ))

        # Buyback (0-1)
        if rng.random() > 0.6:
            byr = today.year - rng.randint(1, 3)
            bb_price = round(rng.uniform(500, 5000), 2)
            ann_d = date(byr, rng.randint(1, 12), rng.randint(1, 28))
            actions.append(CorporateAction(
                type="BUYBACK",
                announcement_date=ann_d.isoformat(),
                ex_date=(ann_d + timedelta(days=30)).isoformat(),
                record_date=(ann_d + timedelta(days=33)).isoformat(),
                details=f"Share Buyback at ₹{bb_price} per share via tender offer",
                amount=bb_price,
                ratio=None,
            ))

        # Rights issue (0-1)
        if rng.random() > 0.7:
            ryr = today.year - rng.randint(2, 5)
            ratio = rng.choice(["1:5", "1:3", "1:4", "2:7"])
            rights_price = round(rng.uniform(50, 800), 2)
            ann_d = date(ryr, rng.randint(1, 12), rng.randint(1, 28))
            actions.append(CorporateAction(
                type="RIGHTS",
                announcement_date=ann_d.isoformat(),
                ex_date=(ann_d + timedelta(days=14)).isoformat(),
                record_date=(ann_d + timedelta(days=17)).isoformat(),
                details=f"Rights Issue in the ratio {ratio} at ₹{rights_price} per share",
                amount=rights_price,
                ratio=ratio,
            ))

        # Sort by announcement date, most recent first
        actions.sort(key=lambda a: a.announcement_date, reverse=True)

        # Upcoming — announced but ex-date in future (mock: sometimes none)
        upcoming: List[CorporateAction] = []
        if rng.random() > 0.5:
            upcoming_div = round(rng.uniform(1.5, 12.0), 2)
            future_ann = today - timedelta(days=rng.randint(1, 30))
            future_ex = today + timedelta(days=rng.randint(10, 45))
            upcoming.append(CorporateAction(
                type="DIVIDEND",
                announcement_date=future_ann.isoformat(),
                ex_date=future_ex.isoformat(),
                record_date=(future_ex + timedelta(days=2)).isoformat(),
                details=f"Interim Dividend of ₹{upcoming_div} per share",
                amount=upcoming_div,
                ratio=None,
            ))

        # TTM dividend yield & payout ratio
        div_yield_ttm = round(rng.uniform(div_range[0], div_range[1]), 2)
        payout_ratio = round(rng.uniform(10.0, 45.0), 2) if div_yield_ttm > 0.1 else None

        return CorporateActionsResponse(
            ticker=symbol,
            actions=actions,
            upcoming=upcoming,
            dividend_yield_ttm=div_yield_ttm,
            dividend_payout_ratio=payout_ratio,
        )
    except Exception:
        logger.exception("Failed to build corporate actions for %s", symbol)
        raise HTTPException(status_code=500, detail="Internal error building corporate actions")


# ---------------------------------------------------------------------------
# 4. Valuation — GET /api/v1/stocks/{symbol}/valuation
# ---------------------------------------------------------------------------

# Peer groups for common indices/sectors
_PEER_GROUPS: Dict[str, List[str]] = {
    "RELIANCE": ["ONGC", "IOC", "BPCL", "HPCL", "GAIL", "OIL"],
    "TCS": ["INFY", "WIPRO", "HCLTECH", "TECHM", "LTIM", "COFORGE"],
    "HDFCBANK": ["ICICIBANK", "SBIN", "KOTAKBANK", "AXISBANK", "BANDHANBNK"],
    "INFY": ["TCS", "WIPRO", "HCLTECH", "TECHM", "LTIM", "COFORGE"],
    "ICICIBANK": ["HDFCBANK", "SBIN", "KOTAKBANK", "AXISBANK", "FEDERALBNK"],
    "SBIN": ["HDFCBANK", "ICICIBANK", "KOTAKBANK", "AXISBANK", "PNB", "CANBK"],
    "ITC": ["HINDUNILVR", "NESTLEIND", "DABUR", "MARICO", "BRITANNIA", "TATACONSUM"],
    "TITAN": ["KALYANKJIL", "TRENT", "MANYAVAR", "METROBRAND"],
    "SUNPHARMA": ["DRREDDY", "CIPLA", "DIVISLAB", "LUPIN", "TORNTPHARM"],
    "MARUTI": ["TATAMOTORS", "M&M", "BAJAJ-AUTO", "EICHERMOT", "HEROMOTOCO"],
    "TATASTEEL": ["JSWSTEEL", "HINDALCO", "SAIL", "JINDALSTEL", "VEDL"],
    "ULTRACEMCO": ["SHREECEM", "ACC", "AMBUJACEM", "DALBHARAT", "RAMCOCEM"],
    "NTPC": ["POWERGRID", "TATAPOWER", "NHPC", "JSWENERGY"],
    "BHARTIARTL": ["IDEA", "JIOFIN"],
    "LT": ["BHEL", "SIEMENS", "ABB", "RVNL"],
    "PIDILITIND": ["ASIANPAINT", "BERGEPAINT", "AKZOINDIA", "INDIGOPNTS"],
    "NESTLEIND": ["HINDUNILVR", "BRITANNIA", "DABUR", "MARICO", "TATACONSUM", "ITC"],
    "DMART": ["TRENT", "VBL", "METROBRAND", "KALYANKJIL"],
    "ZOMATO": ["SWIGGY", "NYKAA", "POLICYBZR", "DELHIVERY"],
}

# Default peers per sector
_SECTOR_PEERS: Dict[str, List[str]] = {
    "IT": ["TCS", "INFY", "WIPRO", "HCLTECH", "TECHM", "LTIM", "COFORGE", "PERSISTENT"],
    "Banking": ["HDFCBANK", "ICICIBANK", "SBIN", "KOTAKBANK", "AXISBANK", "BANDHANBNK", "FEDERALBNK"],
    "Finance": ["BAJFINANCE", "CHOLAFIN", "MUTHOOTFIN", "SBICARD", "RECLTD", "PFC"],
    "Oil & Gas": ["RELIANCE", "ONGC", "IOC", "BPCL", "HPCL"],
    "FMCG": ["HINDUNILVR", "NESTLEIND", "ITC", "DABUR", "MARICO", "BRITANNIA", "TATACONSUM"],
    "Pharma": ["SUNPHARMA", "DRREDDY", "CIPLA", "DIVISLAB", "LUPIN", "TORNTPHARM", "AUROPHARMA"],
    "Auto": ["MARUTI", "TATAMOTORS", "M&M", "BAJAJ-AUTO", "HEROMOTOCO", "EICHERMOT"],
    "Steel": ["TATASTEEL", "JSWSTEEL", "SAIL", "HINDALCO", "JINDALSTEL"],
    "Cement": ["ULTRACEMCO", "SHREECEM", "ACC", "AMBUJACEM", "DALBHARAT"],
    "Power": ["NTPC", "POWERGRID", "TATAPOWER", "NHPC", "JSWENERGY", "TORNTPOWER"],
    "Telecom": ["BHARTIARTL", "IDEA", "TEJASNET"],
    "Consumer Tech": ["ZOMATO", "NYKAA", "POLICYBZR", "PAYTM", "IXIGO"],
}


@router.get(
    "/api/v1/stocks/{symbol}/valuation",
    response_model=ValuationResponse,
    summary="Valuation Snapshot",
    description="Returns current valuation metrics, 5-year P/E band data, and "
    "peer comparison across key valuation multiples.",
)
def get_valuation(symbol: str, user_id: int = Depends(require_auth)):
    """Return valuation overview for a given ticker."""
    try:
        symbol = symbol.strip().upper()
        rng = _seeded_random(symbol)
        sector = _sector_for_symbol(symbol)

        # Market cap in Crores
        if symbol in {"RELIANCE", "TCS", "HDFCBANK"}:
            market_cap = rng.uniform(5_00_000, 20_00_000)
        elif symbol in {"INFY", "ICICIBANK", "SBIN", "HINDUNILVR", "ITC", "BHARTIARTL"}:
            market_cap = rng.uniform(2_00_000, 8_00_000)
        elif symbol in {"LT", "KOTAKBANK", "AXISBANK", "SUNPHARMA", "MARUTI"}:
            market_cap = rng.uniform(1_00_000, 4_50_000)
        elif symbol in {"NTPC", "ONGC", "TITAN", "WIPRO", "HCLTECH", "ULTRACEMCO"}:
            market_cap = rng.uniform(80_000, 3_50_000)
        elif symbol in {"TATASTEEL", "JSWSTEEL", "ADANIENT", "M&M", "BAJFINANCE"}:
            market_cap = rng.uniform(60_000, 3_00_000)
        else:
            market_cap = rng.uniform(5_000, 1_50_000)

        # PE ratios
        pe_5yr_high = round(rng.uniform(20, 80), 2)
        pe_5yr_low = round(rng.uniform(5, 25), 2)
        pe_5yr_avg = round((pe_5yr_high + pe_5yr_low) / 2 + rng.uniform(-5, 5), 2)
        pe_current = round(pe_5yr_avg + rng.uniform(-10, 12), 2)
        pe_current = max(pe_5yr_low * 0.8, min(pe_5yr_high * 1.1, pe_current))
        pe_sector_avg = round(pe_5yr_avg + rng.uniform(-6, 8), 2)

        pb = round(rng.uniform(1.5, 8.0), 2)
        pb_5yr_avg = round(rng.uniform(1.5, 7.0), 2)
        ev_ebitda = round(rng.uniform(8.0, 35.0), 2)
        enterprise_value = round(market_cap * rng.uniform(1.0, 2.5), 2)

        div_yield = round(rng.uniform(0.1, 4.5), 2)
        earnings_yield = round(1.0 / pe_current * 100, 2) if pe_current > 0 else None

        # PEG
        growth = rng.uniform(5.0, 25.0)
        peg = round(pe_current / growth, 2) if growth > 0 else None

        snapshot = ValuationSnapshot(
            ticker=symbol,
            pe_current=round(pe_current, 2),
            pe_5yr_avg=pe_5yr_avg,
            pe_sector_avg=round(pe_sector_avg, 2),
            pe_5yr_high=pe_5yr_high,
            pe_5yr_low=pe_5yr_low,
            pb_current=pb,
            pb_5yr_avg=pb_5yr_avg,
            ev_ebitda=ev_ebitda,
            market_cap_crores=round(market_cap, 2),
            enterprise_value_crores=round(enterprise_value, 2),
            dividend_yield=div_yield,
            earnings_yield=earnings_yield,
            peg_ratio=peg,
        )

        # P/E band data — quarterly data points for 5 years
        pe_band: List[dict] = []
        base_date = date.today()
        price_base = rng.uniform(200, 5000)
        for i in range(20):
            dt = base_date - timedelta(days=i * 91)
            pe_val = round(pe_5yr_avg + rng.uniform(-12, 15), 2)
            pe_val = max(2, pe_val)
            price = round(price_base + rng.uniform(-price_base * 0.5, price_base * 1.0), 2)
            price = max(5, price)
            pe_band.append({"date": dt.isoformat(), "pe": pe_val, "price": price})
        pe_band.reverse()

        # Peer comparison
        peers = _PEER_GROUPS.get(symbol, _SECTOR_PEERS.get(sector, ["TCS", "INFY", "HDFCBANK", "RELIANCE", "ITC"]))
        peer_table: List[dict] = []
        for peer in peers[:8]:
            prng = _seeded_random(peer)
            peer_table.append({
                "ticker": peer,
                "pe": round(pe_current + prng.uniform(-15, 20), 2),
                "pb": round(pb + prng.uniform(-3, 4), 2),
                "ev_ebitda": round(ev_ebitda + prng.uniform(-10, 12), 2),
                "roce": round(prng.uniform(8, 35), 2),
                "roe": round(prng.uniform(6, 30), 2),
            })
        # Ensure the current stock is in the comparison
        if not any(p["ticker"] == symbol for p in peer_table):
            peer_table.insert(0, {
                "ticker": symbol,
                "pe": round(pe_current, 2),
                "pb": round(pb, 2),
                "ev_ebitda": round(ev_ebitda, 2),
                "roce": round(rng.uniform(10, 30), 2),
                "roe": round(rng.uniform(8, 28), 2),
            })

        return ValuationResponse(
            ticker=symbol,
            snapshot=snapshot,
            pe_band_data=pe_band,
            peer_comparison=peer_table,
        )
    except Exception:
        logger.exception("Failed to build valuation for %s", symbol)
        raise HTTPException(status_code=500, detail="Internal error building valuation")


# ---------------------------------------------------------------------------
# 5. Risk Signals — GET /api/v1/stocks/{symbol}/risk-signals
# ---------------------------------------------------------------------------

_GOVERNANCE_CONCERNS = [
    ("Auditor Resignation", "The statutory auditor resigned mid-term without completing the audit cycle, raising concerns about accounting practices.", "HIGH", 1),
    ("Related-Party Transactions Spike", "Related-party transactions exceeded 25% of revenue in the latest filing, well above the 10% peer average.", "MEDIUM", 0),
    ("SEBI Investigation", "SEBI has initiated an investigation into insider trading allegations involving senior management.", "CRITICAL", 1),
    ("Board Independence Below Threshold", "Independent directors constitute only 33% of the board, below the 50% SEBI recommendation.", "MEDIUM", 0),
    ("CFO Departure — Third in 2 Years", "Frequent CFO turnover may indicate internal control weaknesses or financial reporting disputes.", "HIGH", 1),
    ("Audit Qualifications", "The latest audit report contains qualifications regarding inventory valuation methods.", "MEDIUM", 0),
    ("Whistleblower Complaint", "An anonymous whistleblower complaint regarding revenue recognition was filed with SEBI and audit committee.", "HIGH", 1),
    ("Delayed Annual Report Filing", "The company has delayed filing its annual report by over 60 days for two consecutive years.", "LOW", 0),
]

_PLEDGE_CONCERNS = [
    ("High Promoter Pledge", "Promoter pledge exceeds 50% of promoter holding, indicating potential liquidity stress at the promoter level.", 55.0, 50.0),
    ("Rising Pledge Trend", "Promoter pledge has increased by more than 10 percentage points over the last four quarters.", 15.0, 10.0),
    ("Invocation Risk", "Lenders have invoked pledged shares in one promoter group entity, signalling covenant breaches.", 0.0, 0.0),
]

_DEBT_CONCERNS = [
    ("High Debt-to-Equity", "Debt-to-equity ratio of {}x is significantly above the industry average, raising refinancing risk.", "HIGH"),
    ("Rising Borrowings", "Total borrowings have increased by {}% YoY while EBITDA growth is flat, straining debt service capacity.", "MEDIUM"),
    ("Debt Restructuring", "The company is in discussions with lenders for restructuring of term loans maturing in the next 12 months.", "HIGH"),
    ("Interest Coverage Below 2x", "Interest coverage ratio has fallen below 2.0x, indicating increased default risk.", "MEDIUM"),
    ("Working Capital Stress", "Working capital cycle has stretched to {} days from {} days a year ago, pressuring cash flows.", "LOW"),
]

_FII_SELLING_CONCERNS = [
    ("Sustained FII Outflows", "FIIs have reduced holdings by over 300 bps in the last four quarters, indicating institutional risk-off sentiment.", "HIGH"),
    ("FII Holding at 3-Year Low", "FII holding has fallen to a 3-year low of {:.1f}%, signalling diminished foreign institutional confidence.", "MEDIUM"),
    ("Large Block Deal by FII", "A large FII {:.1f}% block deal was executed at a discount, suggesting a rush to exit.", "HIGH"),
]

_FORENSIC_CONCERNS = [
    ("Promoter Pledge + Loan Default", "Promoter group entities have defaulted on loans against pledged shares, raising forensic concerns.", "CRITICAL"),
    ("Unexplained Inventory Build", "Inventory days have doubled without a corresponding increase in sales, potentially indicating demand weakness or channel stuffing.", "MEDIUM"),
    ("Aggressive Revenue Recognition", "Trade receivables + unbilled revenue as a % of sales is unusually high versus peers, suggesting aggressive recognition.", "MEDIUM"),
    ("Frequent Related-Party Loans", "Loans and advances to related parties have grown disproportionately to business growth.", "HIGH"),
]


@router.get(
    "/api/v1/stocks/{symbol}/risk-signals",
    response_model=RiskSignalsResponse,
    summary="Risk Signals Assessment",
    description="Returns a consolidated risk assessment for a ticker, including governance "
    "signals, promoter pledge risk, FII/DII trends, and debt-related concerns. "
    "Overall risk score is from 0 (safe) to 100 (extreme risk).",
)
def get_risk_signals(symbol: str, user_id: int = Depends(require_auth)):
    """Return risk assessment signals for a given ticker."""
    try:
        symbol = symbol.strip().upper()
        rng = _seeded_random(symbol)
        is_psu = symbol in {"NTPC", "ONGC", "COALINDIA", "SBIN", "PFC", "RECLTD", "NHPC", "SAIL", "NMDC", "HUDCO", "BHEL", "BEL"}
        sector = _sector_for_symbol(symbol)
        today = date.today().isoformat()

        signals: List[RiskSignal] = []
        total_risk = 0.0

        # Governance signals (0-30 points)
        governance_score = 100.0
        gov_signal_count = rng.randint(0, 3)
        gov_sample = rng.sample(_GOVERNANCE_CONCERNS, min(gov_signal_count, len(_GOVERNANCE_CONCERNS)))
        for title, desc, severity, is_active in gov_sample:
            points = {"LOW": 5, "MEDIUM": 10, "HIGH": 15, "CRITICAL": 20}[severity]
            total_risk += points
            governance_score -= points
            signals.append(RiskSignal(
                type="GOVERNANCE",
                severity=severity,
                title=title,
                description=desc,
                detected_at=today,
                metric_value=None,
                threshold=None,
            ))

        # Pledge risk (0-20 points)
        pledge_risk = "NONE"
        if not is_psu:
            pledge_pct = rng.uniform(0, 40) if symbol.startswith("ADANI") else rng.uniform(0, 25)
            if pledge_pct > 50:
                pledge_risk = "HIGH"
                total_risk += 20
                signals.append(RiskSignal(
                    type="PLEDGE",
                    severity="HIGH",
                    title="High Promoter Pledge",
                    description=f"Promoter pledge at {pledge_pct:.1f}% exceeds the 50% threshold for high-risk classification.",
                    detected_at=today,
                    metric_value=round(pledge_pct, 1),
                    threshold=50.0,
                ))
            elif pledge_pct > 20:
                pledge_risk = "MEDIUM"
                total_risk += 10
                signals.append(RiskSignal(
                    type="PLEDGE",
                    severity="MEDIUM",
                    title="Moderate Promoter Pledge",
                    description=f"Promoter pledge at {pledge_pct:.1f}% is above the 20% comfort threshold.",
                    detected_at=today,
                    metric_value=round(pledge_pct, 1),
                    threshold=20.0,
                ))
            elif pledge_pct > 5:
                pledge_risk = "LOW"
                total_risk += 3
        else:
            governance_score = min(100, governance_score + 10)  # PSUs have structural governance score boost

        # FII trend (0-15 points)
        fii_trend_val = rng.uniform(-500, 300)
        fii_trend = "NEUTRAL"
        if fii_trend_val < -200:
            fii_trend = "SELLING"
            total_risk += rng.uniform(10, 15)
            choice = rng.choice(_FII_SELLING_CONCERNS)
            signals.append(RiskSignal(
                type="FII_SELLING",
                severity=choice[2],
                title=choice[0],
                description=choice[1].format(rng.uniform(5, 15)),
                detected_at=today,
                metric_value=round(abs(fii_trend_val), 2),
                threshold=-200.0,
            ))
        elif fii_trend_val > 100:
            fii_trend = "ACCUMULATING"
            total_risk -= rng.uniform(2, 5)  # Slight reduction

        # Debt concerns (0-20 points)
        debt_concern = None
        de_ratio = rng.uniform(0.0, 2.5)
        if de_ratio > 1.5:
            debt_concern = "High D/E"
            severity = "HIGH" if de_ratio > 2.0 else "MEDIUM"
            points = 15 if de_ratio > 2.0 else 8
            total_risk += points
            signals.append(RiskSignal(
                type="DEBT",
                severity=severity,
                title=f"High Debt-to-Equity ({de_ratio:.1f}x)",
                description=f"Debt-to-equity ratio of {de_ratio:.1f}x is significantly above the industry comfort level. Interest coverage has narrowed, increasing refinancing risk.",
                detected_at=today,
                metric_value=round(de_ratio, 2),
                threshold=1.5,
            ))
        elif de_ratio > 0.8:
            debt_concern = "Moderate leverage"
        elif de_ratio < 0.2 and sector not in ("IT", "FMCG", "Consumer Tech"):
            debt_concern = "Low leverage — may indicate under-leveraging"

        # Forensic red flags (0-15 points, rarer)
        if rng.random() > 0.65:
            forensic = rng.choice(_FORENSIC_CONCERNS)
            points = {"CRITICAL": 15, "HIGH": 10, "MEDIUM": 5, "LOW": 2}[forensic[2]]
            total_risk += points
            signals.append(RiskSignal(
                type="FORENSIC",
                severity=forensic[2],
                title=forensic[0],
                description=forensic[1],
                detected_at=today,
                metric_value=None,
                threshold=None,
            ))

        # Clamp risk score
        overall_risk = max(0, min(100, total_risk))
        governance_score = max(0, min(100, governance_score))

        return RiskSignalsResponse(
            ticker=symbol,
            overall_risk_score=round(overall_risk, 1),
            signals=signals,
            governance_score=round(governance_score, 1),
            pledge_risk=pledge_risk,
            fii_trend=fii_trend,
            debt_concern=debt_concern,
        )
    except Exception:
        logger.exception("Failed to build risk signals for %s", symbol)
        raise HTTPException(status_code=500, detail="Internal error building risk signals")


# ---------------------------------------------------------------------------
# 6. ML Signal — GET /api/v1/stocks/{symbol}/ml-signal
# ---------------------------------------------------------------------------

@router.get(
    "/api/v1/stocks/{symbol}/ml-signal",
    response_model=MLSignalResponse,
    summary="ML Signal for Stock",
    description="Returns the ML engine prediction signal for a given ticker. "
    "Proxies to the LightGBM-based ML engine and enriches with reliability metrics.",
)
def get_stock_ml_signal(symbol: str, user_id: int = Depends(require_auth)):
    """Return ML prediction signal for a given ticker."""
    from services.ml_signal_service import get_ml_signal

    return get_ml_signal(symbol)
