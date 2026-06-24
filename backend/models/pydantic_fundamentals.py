from pydantic import BaseModel
from typing import List, Optional

class FinancialMetrics(BaseModel):
    period: str
    revenue: Optional[float] = None
    net_income: Optional[float] = None
    eps: Optional[float] = None
    operating_margin: Optional[float] = None
    free_cash_flow: Optional[float] = None

class Shareholding(BaseModel):
    quarter: str
    promoter_pct: Optional[float] = None
    fii_pct: Optional[float] = None
    dii_pct: Optional[float] = None
    public_pct: Optional[float] = None
    pledged_pct: Optional[float] = None

class CorporateActionDTO(BaseModel):
    ex_date: str
    record_date: Optional[str] = None
    purpose: str
    dividend_amount: Optional[float] = None

class ValuationMetrics(BaseModel):
    date: str
    current_pe: Optional[float] = None
    forward_pe: Optional[float] = None
    pb_ratio: Optional[float] = None
    ev_ebitda: Optional[float] = None
    market_cap: Optional[float] = None

class RiskSignalDTO(BaseModel):
    date: str
    signal_type: str
    severity: str
    description: str

class FundamentalsResponse(BaseModel):
    ticker: str
    financials: List[FinancialMetrics]
    shareholding: List[Shareholding]
    corporate_actions: List[CorporateActionDTO]
    valuation: Optional[ValuationMetrics] = None
    risk_signals: List[RiskSignalDTO]
