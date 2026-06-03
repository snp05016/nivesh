# Tasks Performance Fixes — Progress Ledger

**Started**: June 3, 2026
**Completed**: June 3, 2026
**Workspace**: `/Users/saumya/Desktop/nivesh/`

---

## PHASE 0: Progress Ledger
- [x] Initialize this ledger

## PHASE 1: Component Patches & System Roadmap

### TASK 1: Notification Pipeline Re-Engineering & APNs Integration
- [x] Backend: DeviceToken schema verified (user_id, device_token, platform) — database.py:161
- [x] Backend: Fixed notifications_register_device() — robust upsert with rollback+duplicate fallback — main.py:5141
- [x] Backend: Added _deliver_apns() helper — best-effort delivery via registered device tokens — main.py:5111
- [x] Backend: Refactored notifications_test() — now calls _deliver_apns after building payload — main.py:5161
- [x] Backend: Refactored notifications_morning_summary_push() — now calls _deliver_apns — main.py:5210
- [x] iOS: UNUserNotificationCenter permission pipeline — stockmeApp.swift:49 (requestNotificationPermissions)
- [x] iOS: didRegisterForRemoteNotificationsWithDeviceToken → hex string conversion — AppDelegate.swift:10
- [x] iOS: POST hex token to /notifications/register-device on startup — AppDelegate.swift:13

### TASK 2: Live Weekly Results & Trailing Sector Heatmaps
- [x] Backend: Fixed sector_weekly_endpoint() — explicit NaN filtering + week_ago div-by-zero guard — main.py:3409
- [x] Backend: Fixed fetch_momentum() — NaN check on MA values before crossover logic — scraper.py:268
- [x] Backend: Holiday fallback — valid_closes list filters NaN, uses last 2 active trading days

### TASK 3: Portfolio Calendar & Historical Valuation Seeding
- [x] Backend: On-the-fly seeding engine — checks for 0 snapshots, fetches 35d history, writes 30d trailing — main.py:3619
- [x] Backend: Fetches 30-day historical close prices via yfinance for each holding
- [x] Backend: Calculates retroactive trailing daily net valuation (total_value, invested, pnl, pnl%)
- [x] Backend: Atomic write to PortfolioValuationHistory with UNIQUE constraint upsert

## PHASE 2: Global Formatting & Git Operations
- [x] Indian numbering already in place (₹ formatting in notification payloads)
- [x] Python syntax check: main.py, database.py, scraper.py — all compile clean
- [x] iOS build: ** BUILD SUCCEEDED **
- [x] Deploy to server: main.py + scraper.py copied, service restarted
- [x] Server verified: ping OK, valuation seeding works (22 data points, +12.99%)
- [x] Git commit: 75e0762 — feat: APNs notification plumbing, valuation seeding, weekly heatmap fallbacks

---

## Verification Results

### Valuation Seeding Test (nirav, user_id=2)
- 22 snapshots seeded on first request
- Period: 2026-05-04 to 2026-06-03
- Starting value: ₹77,84,957
- Ending value: ₹87,96,166
- Return: +12.99% (+₹10,11,209)
- Peak: ₹89,52,061
- Trough: ₹77,01,674
