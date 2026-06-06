# Earnings Dashboard, Historical Calendar & Telemetry Logs

## PHASE 0: Setup
- [x] Create implementation ledger
- [x] Verify existing code structure

## PHASE 1: Backend (FastAPI)
- [x] Add `EarningsErrorLog` table to `database.py`
- [x] Update `helpers.py` imports for EarningsErrorLog
- [x] Create `/api/v1/earnings/calendar` — merge earnings dates + 7-day price history
- [x] Create `/api/v1/earnings/feed` — sorted: latest, best_performer, worst_performer
- [x] Add `GET /api/v1/admin/earnings-errors` endpoint
- [x] Wrap calendar/feed in try-except, log to EarningsErrorLog
- [x] Verify backend syntax + imports

## PHASE 2: iOS (SwiftUI)
- [x] Add `EarningsCalendarItem` Codable struct to `Models.swift`
- [x] Add `RankedEarningsFeed` (`bestPerformers`, `worstPerformers`) to `EarningsFeedResponse`
- [x] Add `EarningsErrorLogEntry` + `EarningsErrorLogsResponse` Codable structs
- [x] Add NetworkManager functions: `fetchEarningsCalendar()`, `fetchRankedEarningsFeed()`, `fetchEarningsErrorLogs()`
- [x] Build `MiniSparkline` view component
- [x] Calendar day cells show price sparklines inline
- [x] Calendar result rows show 7-day price change + sparkline chart
- [x] Feed result cards show sparkline context when available
- [x] ViewModel uses `EarningsCalendarItem` with sparkline lookup
- [x] All CodingKeys match backend JSON schemas

## PHASE 3: Integration Testing
- [x] Backend syntax verification (all 3 files)
- [x] Route registration verified (calendar, feed, earnings-errors all GET)
- [x] EarningsErrorLog CRUD verified
- [ ] curl-test against running server (requires uvicorn)
- [ ] Xcode build verification

## PHASE 4: State Retention
- [x] Git add + commit
