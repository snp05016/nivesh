# Earnings Dashboard, Historical Calendar & Telemetry Logs

## PHASE 0: Setup
- [x] Create implementation ledger
- [ ] Verify existing code structure

## PHASE 1: Backend (FastAPI)
- [ ] Add `EarningsErrorLog` table to `database.py`
- [ ] Update `helpers.py` imports for EarningsErrorLog
- [ ] Create `/api/v1/market/earnings-calendar` — merge earnings dates + 7-day price history
- [ ] Create `/api/v1/market/earnings-feed` — sorted: latest, best_performer, worst_performer
- [ ] Add `GET /api/v1/admin/earnings-errors` endpoint
- [ ] Wrap calendar/feed in try-except, log to EarningsErrorLog
- [ ] Verify backend syntax + imports

## PHASE 2: iOS (SwiftUI)
- [ ] Add `EarningsCalendarItem` Codable struct to `Models.swift`
- [ ] Add `RankedEarningsFeed` Codable struct to `Models.swift`
- [ ] Add `EarningsErrorEntry` + `EarningsErrorLogsResponse` Codable structs
- [ ] Add NetworkManager functions for new endpoints
- [ ] Build horizontal scrolling calendar UI with sparklines
- [ ] Build tabbed feed UI (Latest | Best | Worst)
- [ ] Wire BanknoteErrorCanvas for earnings failures
- [ ] Verify all CodingKeys match backend JSON schemas

## PHASE 3: Integration Testing
- [ ] curl-test `/api/v1/market/earnings-calendar`
- [ ] curl-test `/api/v1/market/earnings-feed?sort=best_performer`
- [ ] curl-test `/api/v1/admin/earnings-errors`
- [ ] Verify Indian numbering in all responses

## PHASE 4: State Retention
- [ ] Git add + commit
