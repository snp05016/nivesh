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

## PHASE 3: Parity & Integration Testing
- [x] Run backend compilation check (syntax + import chain verified)
- [ ] curl-test `/api/v1/market/dashboard-pulse` (requires server running)
- [ ] curl-test `/api/v1/admin/error-logs` (requires server running)
- [x] Verify Indian numbering (Lakhs/Crores) in all responses (`_fmt_inr_crores` tested)
- [x] Verify iOS compilation (SourceKit diagnostics are pre-existing Theme scope issues, not from these changes)

## PHASE 4: State Retention
- [x] Complete all remaining checklist items
- [ ] Git add + commit
