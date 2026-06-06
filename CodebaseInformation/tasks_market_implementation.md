# Markets Feature Implementation Ledger

## PHASE 0: Setup
- [x] Create implementation ledger
- [x] Verify project structure and imports

## PHASE 1: Backend Telemetry & Extractor Seeding
- [x] Add `market_error_logs` table to `database.py`
- [x] Add `log_market_error()` helper function
- [x] Enhance `/api/v1/market/dashboard-pulse` — Live Reporting Sync section
- [x] Enhance `/api/v1/market/dashboard-pulse` — YoY Market Health section
- [x] Enhance `/api/v1/market/dashboard-pulse` — Cap Index Aggregator section
- [x] Add `GET /api/v1/admin/error-logs` endpoint
- [x] Wrap all new fetchers in error-catching blocks with market_error_logs logging
- [x] Verify backend compiles and starts

## PHASE 2: iOS View Model & Core UI Cards
- [x] Add Codable structs to `Models.swift` (LiveReportingSync, YoYMarketHealth, CapIndexGrid, MarketErrorEntry)
- [x] Add defensive JSON parse logging to `NetworkManager+Sidebar.swift`
- [x] Build banknote-styled error canvas view (`Components/BanknoteErrorCanvas.swift`)
- [x] Wire new endpoints into NetworkManager (`fetchExtendedMarketDashboard()`, `fetchMarketErrorLogs()`)

## PHASE 3: Bug Fix — 405 on /api/v1/earnings/alerts
- [x] Root cause: iOS POST, backend only had GET stub
- [x] Added `EarningsAlert` database table with unique constraint
- [x] Added `POST /api/v1/earnings/alerts` — create alert with dedup
- [x] Updated `GET /api/v1/earnings/alerts` — returns real stored alerts
- [x] Added `DELETE /api/v1/earnings/alerts/{alert_id}`
- [x] Full audit of all iOS HTTP methods vs backend routes (no other mismatches)

## PHASE 4: Systematic Error Diagnostics
- [x] Added `NetworkError.fetchFailed(endpoint:status:body:)` case with exact endpoint/status/body
- [x] Added `NetworkError.displayDetail` computed property
- [x] Created `_fetchDecode()` helper — never returns nil silently
- [x] Updated all 6 earnings fetch functions to throw detailed errors instead of return nil/[]
- [x] Updated `EarningsDashboardViewModel` with per-section `@Published` error properties
- [x] Added `isTotalFailure` computed property
- [x] Updated `EarningsProgressView` to render BanknoteErrorCanvas on total failure
- [x] Updated `MarketSectionErrorRow` display for inline section failures
- [x] Updated alert button to show error on failure instead of silently dropping

## PHASE 5: Parity & Integration Testing
- [x] Run backend compilation check (syntax + import chain verified)
- [ ] curl-test `/api/v1/market/dashboard-pulse` (requires server running)
- [ ] curl-test `/api/v1/admin/error-logs` (requires server running)
- [x] Verify Indian numbering (Lakhs/Crores) in all responses (`_fmt_inr_crores` tested)
- [x] Earnings alerts CRUD verified (POST → GET → DELETE)

## PHASE 6: State Retention
- [ ] Git add + commit
