# schemas/ — Pydantic request/response validation contracts
# Extracted from main.py and helpers.py per monolith refactor Phase 1

from schemas.auth import LoginRequest, RegisterRequest
from schemas.portfolio import (
    AnalyzeRequest,
    WatchlistAddRequest,
    WatchlistRemoveRequest,
    PortfolioAddRequest,
    PortfolioRemoveRequest,
    PortfolioUpdateRequest,
    PortfolioNoteRequest,
    AlertAddRequest,
    AlertRemoveRequest,
    BatchAnalyzeRequest,
    TradeJournalAddRequest,
    TradeJournalUpdateRequest,
)
from schemas.market import (
    IndexSnapshot,
    BreadthData,
    MomentumSignal,
    DashboardPulseResponse,
    MutualFundEntry,
    InstitutionalLeaderboardResponse,
    NetWorthSnapshotResponse,
    EarningsSyncRatioResponse,
    YoYAggregateResponse,
)
from schemas.stock_fundamentals import (
    # Financial statements
    FinancialPeriod,
    FinancialLineItem,
    FinancialStatementResponse,
    # Shareholding
    ShareholderCategory,
    TopHolder,
    ShareholdingQuarter,
    ShareholdingResponse,
    # Corporate actions
    CorporateAction,
    CorporateActionsResponse,
    # Valuation
    ValuationSnapshot,
    ValuationResponse,
    # Risk signals
    RiskSignal,
    RiskSignalsResponse,
    # Stock profile
    StockProfileBasic,
    StockProfileHoldings,
    StockProfileProfitability,
    StockProfilePriceRange,
    PriceHistoryPoint,
    PriceHistoryData,
    QuarterlyFinancialData,
    StockProfileResponse,
)
