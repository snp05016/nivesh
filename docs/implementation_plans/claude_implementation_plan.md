# Claude Code Implementation Plan (UI & API Factory)

**Objective:** Build the iOS Frontend and Backend API/Database layer of the Moneycontrol feature stack without overlapping with the Gemini team.
**Boundary Rules:** Claude agents may ONLY modify files in `ios/StockApp/` and `backend/routers/`, `backend/schemas/`, and `backend/models/`. They must NEVER touch `backend/services/math_engines/` or data harvesters.

## Team Roster (4 Subagents)
1. **Frontend UI Agent:** Responsible for static SwiftUI views, components, and layout.
2. **Frontend State Agent:** Responsible for ViewModels, Network layer, and state bindings.
3. **Backend API Agent:** Responsible for SQLAlchemy DB schemas, Pydantic models, and FastAPI routers.
4. **Integration & Review Agent:** Responsible for wiring the iOS app to the backend and running API contract tests.

---

## Phase 1: Core Discovery & Navigation
### Backend API Agent
- [x] Define SQLAlchemy models for `Watchlist` and `UserPreferences`.
- [x] Build FastAPI router for Global Markets overview.
- [x] Build FastAPI router for Universal Search endpoints.
### Frontend UI Agent
- [x] Build `HomeDashboardView.swift` (static UI).
- [x] Build `MarketTickerComponent.swift` (Nifty/Sensex scrolling banner).
- [x] Build `UniversalSearchView.swift` (UI only).
### Frontend State Agent
- [x] Create `HomeDashboardViewModel.swift` with mock networking.
- [x] Bind `UniversalSearchView` to a debounce-enabled search state.
### Integration & Review Agent
- [x] Wire Home Dashboard to real FastAPI endpoints.
- [x] Write integration tests for Universal Search API.

## Phase 2: Stock Detail & Equity Research UI
### Backend API Agent
- [x] Build standard CRUD endpoints for Stock details (Price, VWAP, 52-week).
- [x] Build `CompareStocks` router (accepts up to 3 tickers).
### Frontend UI Agent
- [x] Build the 12 tabs for `StockProfileView.swift` (Overview, Chart, Forecast, MC Insights, etc.).
- [x] Build `PeerComparisonView.swift`.
### Frontend State Agent
- [x] Implement `StockProfileViewModel.swift` to handle tab switching and lazy data loading.
- [x] Implement `ChartViewModel.swift` for interactive charting data structures.
### Integration & Review Agent
- [x] Ensure SwiftUI Charts map correctly to backend JSON arrays.
- [x] Audit memory leaks in the 12-tab architecture.

## Phase 3: Mutual Funds & IPO Hub
### Backend API Agent
- [x] Define DB schema for `MutualFund` and `IPOListing`.
- [x] Build IPO Calendar and Subscription Status API endpoints.
### Frontend UI Agent
- [x] Build `MutualFundDiscoveryView.swift`.
- [x] Build `MutualFundDetailView.swift` (NAV history, Riskometer).
- [x] Build `IPOHubView.swift` (Open, Upcoming, Closed tabs).
### Frontend State Agent
- [x] Wire Mutual Fund search and filtering state.
- [x] Wire IPO subscription status live updates.
### Integration & Review Agent
- [x] Connect iOS Mutual Fund views to backend DB.
- [x] Verify standard 8pt grid compliance on new UI components.

## Phase 4: Portfolio & Wealth Tracking (CRUD)
### Backend API Agent
- [x] Define complex DB schema for `PortfolioTransaction` (Stocks, MFs, Gold, FDs).
- [x] Build transaction entry and history APIs.
### Frontend UI Agent
- [x] Build `PortfolioDashboardView.swift` (Net worth, Asset Allocation).
- [x] Build `ManualTransactionEntrySheet.swift`.
### Frontend State Agent
- [x] Create `PortfolioViewModel.swift` for real-time P&L updates.
### Integration & Review Agent
- [x] Ensure transaction payloads map perfectly to backend Pydantic schemas.

---
*Note: Claude will rely on Gemini's Python modules (which will be imported into Claude's routers) to calculate actual P&L, XIRR, and math logic.*
