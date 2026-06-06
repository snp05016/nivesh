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
