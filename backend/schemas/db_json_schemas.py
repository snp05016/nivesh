"""Strict Pydantic schemas for JSON database columns.

Enforced on read/write to prevent silent data corruption in columns like
NetWorthLedger.portfolio_json and Alpha158Feature.features.
"""
from pydantic import BaseModel, Field
from typing import List, Optional


class PortfolioPositionSchema(BaseModel):
    """Single position in a portfolio snapshot."""
    ticker: str
    company_name: str = ""
    shares: float
    buy_price: float
    current_price: float
    day_change_pct: float = 0.0
    total_value: float = 0.0
    weight_pct: float = 0.0


class PortfolioSnapshotSchema(BaseModel):
    """Complete portfolio composition at a point in time."""
    date: str
    total_value_inr: float
    total_invested_inr: float = 0.0
    total_pnl_inr: float = 0.0
    pnl_pct: float = 0.0
    positions: List[PortfolioPositionSchema] = Field(default_factory=list)
    nifty_close: Optional[float] = None
    top_gainer_ticker: Optional[str] = None
    top_gainer_pct: Optional[float] = None
    top_loser_ticker: Optional[str] = None
    top_loser_pct: Optional[float] = None


def validate_portfolio_json(data: dict) -> PortfolioSnapshotSchema:
    """Validate and normalize a portfolio JSON dict. Raises ValidationError on failure."""
    return PortfolioSnapshotSchema(**data)


def safe_validate_portfolio_json(data: dict) -> Optional[PortfolioSnapshotSchema]:
    """Validate without raising. Returns None on failure."""
    try:
        return PortfolioSnapshotSchema(**data)
    except Exception as _e:
        return None
