"""Market data Pydantic response schemas."""

from typing import Optional, List
from pydantic import BaseModel


class IndexSnapshot(BaseModel):
    name: str
    value: Optional[float]
    change_pct: Optional[float]
    change_abs: Optional[float]


class BreadthData(BaseModel):
    advances: Optional[int]
    declines: Optional[int]
    unchanged: Optional[int]
    ad_ratio: Optional[float]


class MomentumSignal(BaseModel):
    ticker: str
    signal: str          # "GOLDEN_CROSS" | "DEATH_CROSS"
    dma_50: Optional[float]
    dma_200: Optional[float]
    score: Optional[float]


class DashboardPulseResponse(BaseModel):
    indices: List[IndexSnapshot]
    breadth: Optional[BreadthData]
    momentum_signals: List[MomentumSignal]
    fetched_at: str


class MutualFundEntry(BaseModel):
    fund_name: str
    amc: Optional[str]
    return_1y_pct: Optional[float]
    return_3y_pct: Optional[float]
    aum_crores: Optional[float]
    category: Optional[str]


class InstitutionalLeaderboardResponse(BaseModel):
    top_funds: List[MutualFundEntry]
    fetched_at: str


class NetWorthSnapshotResponse(BaseModel):
    user_id: int
    snapshot_date: str
    total_value_formatted: str          # e.g. "₹12.50 Crores"
    daily_delta_formatted: Optional[str]
    daily_delta_pct: Optional[float]
    peak_value_formatted: Optional[str]
    top_gainer_ticker: Optional[str]
    top_gainer_pct: Optional[float]
    top_loser_ticker: Optional[str]
    top_loser_pct: Optional[float]


class EarningsSyncRatioResponse(BaseModel):
    declared_count: int
    total_expected: int
    sync_ratio_pct: float
    fetched_at: str
    source: str


class YoYAggregateResponse(BaseModel):
    revenue_yoy_pct: float
    net_profit_yoy_pct: float
    companies_reported: int
    fetched_at: str
    source: str
