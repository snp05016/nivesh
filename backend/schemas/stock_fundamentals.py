"""Stock fundamentals Pydantic response schemas.

Financial statements (P&L, balance sheet, cash flow), shareholding patterns,
corporate actions, valuation snapshots, and risk signals — all returned by
the /api/v1/stock-profile and related fundamentals endpoints.

All monetary values use Indian numbering: Lakhs (1,00,000) and Crores (1,00,00,000).
"""

from typing import Dict, List, Optional

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Financial Statements
# ---------------------------------------------------------------------------


class FinancialPeriod(BaseModel):
    """A single reporting period (quarter or fiscal year)."""

    label: str
    """Human-readable period label, e.g. 'Q1 FY25', 'FY24'."""

    end_date: str
    """ISO-format end date of the period, e.g. '2025-06-30'."""

    is_bank: bool = False
    """True when the reporting entity is a bank / financial institution with
    bank-specific line items (NII, provisions, GNPA, etc.)."""


class FinancialLineItem(BaseModel):
    """One row in a financial statement — revenue, EBITDA, borrowings, etc.

    Values, QoQ changes, and YoY changes are keyed by period label so the
    consumer can build tabular or chart views from a single list of line items.
    """

    label: str
    """Display label, e.g. 'Revenue', 'EBITDA', 'Net Profit', 'Borrowings'."""

    group: str
    """Statement group: INCOME, BALANCE_SHEET, CASH_FLOW, or RATIOS."""

    values: Dict[str, Optional[float]]
    """Period label → value. Value is in Crores for absolute items and in
    percentage points (e.g. 15.2 = 15.2%) for margin/ratio items."""

    qoq_change_pct: Dict[str, Optional[float]]
    """Period label → quarter-on-quarter change percentage. None when the
    prior quarter is unavailable or the item is not comparable."""

    yoy_change_pct: Dict[str, Optional[float]]
    """Period label → year-on-year change percentage. None when the prior
    year period is unavailable or the item is not comparable."""

    is_percentage: bool = False
    """True for margin and ratio items (already expressed as percentages).
    Consumers should format these with a '%' suffix rather than 'Cr'."""

    bank_specific: bool = False
    """True when this line item only appears for banks / financials
    (e.g. 'NII', 'GNPA %', 'Provisions')."""


class FinancialStatementResponse(BaseModel):
    """Full financial statement for one ticker, spanning multiple periods."""

    ticker: str
    """Uppercase ticker symbol, e.g. 'RELIANCE'."""

    period_type: str
    """QUARTERLY or ANNUAL."""

    consolidation: str
    """STANDALONE or CONSOLIDATED."""

    periods: List[FinancialPeriod]
    """Ordered list of reporting periods (most recent first)."""

    line_items: List[FinancialLineItem]
    """Ordered list of financial line items, grouped by statement group."""

    available_periods: List[str]
    """All selectable period labels the consumer can switch between, e.g.
    ['Q1 FY25', 'Q4 FY24', 'Q3 FY24', …, 'FY24', 'FY23', 'FY22']."""


# ---------------------------------------------------------------------------
# Shareholding Pattern
# ---------------------------------------------------------------------------


class ShareholderCategory(BaseModel):
    """Aggregated shareholding by investor category for the latest quarter."""

    name: str
    """Category name: PROMOTER, FII, DII, PUBLIC, or OTHERS."""

    current_pct: float
    """Current holding as a percentage of total shares (e.g. 45.20 = 45.20%)."""

    qoq_change_bps: Optional[float] = None
    """Quarter-on-quarter change in basis points. Positive = increase,
    negative = decrease. 100 bps = 1 percentage point."""

    yoy_change_bps: Optional[float] = None
    """Year-on-year change in basis points."""

    warning: Optional[str] = None
    """Semantic trend label when the category shows a concerning pattern:
    'falling', 'rising', 'selling', 'accumulating', or None if neutral."""


class TopHolder(BaseModel):
    """A named significant shareholder (promoter entity, mutual fund, etc.)."""

    name: str
    """Holder name as reported in the shareholding pattern filing."""

    category: str
    """Broad category: PROMOTER, FII, DII, PUBLIC, OTHERS."""

    shares_crores: float
    """Number of shares held in Crores."""

    holding_pct: float
    """Percentage of total outstanding shares."""

    qoq_change_bps: Optional[float] = None
    """Quarter-on-quarter change in basis points. None when unchanged or
    data is unavailable."""


class ShareholdingQuarter(BaseModel):
    """Snapshot of shareholding categories for a single quarter — used for
    multi-quarter trend charts."""

    quarter: str
    """Quarter label, e.g. 'Q3 FY25'."""

    promoter_pct: float
    fii_pct: float
    dii_pct: float
    public_pct: float
    others_pct: float


class ShareholdingResponse(BaseModel):
    """Complete shareholding pattern for one ticker."""

    ticker: str

    latest_quarter: str
    """Most recent quarter for which shareholding data is available, e.g. 'Q3 FY25'."""

    available_quarters: List[str]
    """All quarters with shareholding data, newest first."""

    categories: List[ShareholderCategory]
    """Aggregated category-level holdings for the latest quarter."""

    top_holders: List[TopHolder]
    """Named significant holders (typically top 10–15)."""

    promoter_pledge_pct: Optional[float] = None
    """Percentage of promoter holding that is pledged as collateral."""

    promoter_pledge_qoq_change: Optional[float] = None
    """Quarter-on-quarter change in promoter pledge percentage."""

    holding_trend: List[ShareholdingQuarter]
    """Quarter-by-quarter holding data for multi-quarter trend charts."""


# ---------------------------------------------------------------------------
# Corporate Actions
# ---------------------------------------------------------------------------


class CorporateAction(BaseModel):
    """A single corporate action event — dividend, split, bonus, buyback, etc."""

    type: str
    """Action type: DIVIDEND, SPLIT, BONUS, RIGHTS, or BUYBACK."""

    announcement_date: str
    """Date the action was announced, ISO format (YYYY-MM-DD)."""

    ex_date: str
    """Ex-date / record eligibility cutoff, ISO format (YYYY-MM-DD)."""

    record_date: str
    """Record date for determining shareholder eligibility."""

    details: str
    """Human-readable description, e.g. 'Interim Dividend of ₹5 per share'."""

    amount: Optional[float] = None
    """Per-share amount in INR (applicable for dividends)."""

    ratio: Optional[str] = None
    """Action ratio, e.g. '2:1' for a 2-for-1 stock split or '1:2' for a
    1:2 bonus issue."""


class CorporateActionsResponse(BaseModel):
    """All corporate actions for one ticker."""

    ticker: str

    actions: List[CorporateAction]
    """All past corporate actions (most recent first)."""

    upcoming: List[CorporateAction]
    """Announced but not yet effective actions."""

    dividend_yield_ttm: Optional[float] = None
    """Trailing twelve-month dividend yield as a percentage, e.g. 1.85 = 1.85%."""

    dividend_payout_ratio: Optional[float] = None
    """Dividend payout ratio as a percentage of net profit, e.g. 35.0 = 35%."""


# ---------------------------------------------------------------------------
# Valuation
# ---------------------------------------------------------------------------


class ValuationSnapshot(BaseModel):
    """Point-in-time valuation metrics for one ticker."""

    ticker: str

    pe_current: Optional[float] = None
    """Current trailing P/E ratio."""

    pe_5yr_avg: Optional[float] = None
    """5-year median P/E ratio."""

    pe_sector_avg: Optional[float] = None
    """Sector median P/E ratio."""

    pe_5yr_high: Optional[float] = None
    """5-year maximum P/E ratio."""

    pe_5yr_low: Optional[float] = None
    """5-year minimum P/E ratio."""

    pb_current: Optional[float] = None
    """Current price-to-book ratio."""

    pb_5yr_avg: Optional[float] = None
    """5-year median price-to-book ratio."""

    ev_ebitda: Optional[float] = None
    """Enterprise value to EBITDA multiple."""

    market_cap_crores: float
    """Market capitalisation in Crores of INR."""

    enterprise_value_crores: Optional[float] = None
    """Enterprise value (market cap + debt - cash) in Crores of INR."""

    dividend_yield: Optional[float] = None
    """Dividend yield as a percentage, e.g. 1.85 = 1.85%."""

    earnings_yield: Optional[float] = None
    """Earnings yield (1 / P/E) as a percentage, e.g. 5.0 = 5%."""

    peg_ratio: Optional[float] = None
    """Price/earnings-to-growth ratio. None when earnings growth is zero or negative."""


class ValuationResponse(BaseModel):
    """Valuation overview with historical P/E band and peer comparison."""

    ticker: str

    snapshot: ValuationSnapshot
    """Current valuation snapshot."""

    pe_band_data: List[dict]
    """Historical P/E band data points for charting. Each entry:
    {'date': str, 'pe': float, 'price': float}."""

    peer_comparison: List[dict]
    """Peer group comparison. Each entry:
    {'ticker': str, 'pe': float, 'pb': float, 'ev_ebitda': float,
     'roce': float, 'roe': float}."""


# ---------------------------------------------------------------------------
# Risk Signals
# ---------------------------------------------------------------------------


class RiskSignal(BaseModel):
    """A single risk flag detected for a stock — governance, pledge, FII
    selling, debt concern, regulatory action, or forensic red flag."""

    type: str
    """Signal category: GOVERNANCE, PLEDGE, FII_SELLING, DEBT, REGULATORY,
    or FORENSIC."""

    severity: str
    """Severity level: LOW, MEDIUM, HIGH, or CRITICAL."""

    title: str
    """Short signal title, e.g. 'High Promoter Pledge'."""

    description: str
    """Detailed description of the risk signal with context and implications."""

    detected_at: Optional[str] = None
    """Date the signal was detected, ISO format (YYYY-MM-DD)."""

    metric_value: Optional[float] = None
    """The actual value that triggered the signal (e.g. pledge percentage,
    debt/equity ratio)."""

    threshold: Optional[float] = None
    """The threshold that was breached (e.g. 50% for promoter pledge)."""


class RiskSignalsResponse(BaseModel):
    """Consolidated risk assessment for one ticker."""

    ticker: str

    overall_risk_score: float
    """Aggregate risk score from 0 (safe) to 100 (extreme risk). Weighted
    combination of all detected signals."""

    signals: List[RiskSignal]
    """All active risk signals for this ticker."""

    governance_score: Optional[float] = None
    """Governance quality score from 0 (poor) to 100 (excellent). Based on
    board independence, related-party transactions, auditor history, etc."""

    pledge_risk: Optional[str] = None
    """Promoter pledge risk category: NONE, LOW, MEDIUM, or HIGH."""

    fii_trend: Optional[str] = None
    """FII/Foreign portfolio investor trend: ACCUMULATING, NEUTRAL, or SELLING."""

    debt_concern: Optional[str] = None
    """Debt concern summary: None (no concern), 'Moderate leverage',
    'High D/E', 'Rising borrowings', 'Debt restructuring', etc."""


# ---------------------------------------------------------------------------
# Stock Profile (extended response for /api/v1/stock-profile)
# ---------------------------------------------------------------------------


class StockProfileBasic(BaseModel):
    """Core identity and pricing fields returned by /api/v1/stock-profile."""

    ticker: str
    exchange: str
    company_name: str
    current_price: float
    day_change_pct: float
    pe_ratio: Optional[float] = None
    sector: Optional[str] = None
    market_cap_crores: Optional[float] = None
    description: Optional[str] = None


class StockProfileHoldings(BaseModel):
    """Shareholding summary included in stock-profile response."""

    promoter_holding_pct: Optional[float] = None
    fii_holding_pct: Optional[float] = None
    dii_holding_pct: Optional[float] = None


class StockProfileProfitability(BaseModel):
    """Profitability metrics included in stock-profile response."""

    roe_pct: Optional[float] = None
    roce_pct: Optional[float] = None
    ebitda_margin_pct: Optional[float] = None
    debt_to_equity: Optional[float] = None


class StockProfilePriceRange(BaseModel):
    """52-week range included in stock-profile response."""

    week_52_high: Optional[float] = None
    week_52_low: Optional[float] = None


class PriceHistoryPoint(BaseModel):
    """Single OHLCV data point for charting."""

    date: str
    open: float
    high: float
    low: float
    close: float
    volume: float


class PriceHistoryData(BaseModel):
    """Price history container — used in stock-profile response."""

    prices: List[PriceHistoryPoint]
    source: Optional[str] = None
    error: Optional[str] = None


class QuarterlyFinancialData(BaseModel):
    """Quarterly financials container — used in stock-profile response."""

    quarters: List[dict]
    """List of quarter snapshots: {'label': str, 'revenue': float (Cr),
    'net_profit': float (Cr)}."""

    promoter_history: List[dict]
    """Promoter/FII/DII holding trend: {'period': str, 'promoter': float,
    'fii': float, 'dii': float}."""

    error: Optional[str] = None


class StockProfileResponse(BaseModel):
    """Complete response for GET /api/v1/stock-profile.

    Composed of discrete sub-models so consumers can destructure the parts
    they need. The ``errors`` list is always present — an empty list means
    all data sources returned successfully.
    """

    basic: StockProfileBasic
    holdings: StockProfileHoldings
    profitability: StockProfileProfitability
    price_range: StockProfilePriceRange
    price_history: PriceHistoryData
    quarterly_financials: QuarterlyFinancialData
    errors: List[str]
    """Data-source error markers, e.g. ['company_info_unavailable',
    'price_history_unavailable']. Empty list = all sources healthy."""
