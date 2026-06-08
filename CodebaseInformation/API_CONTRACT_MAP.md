# Nivesh — Full-Stack API Contract & Bridge Map

> Generated: 2026-06-06
> Coverage: Every `URLSession` call in Swift ↔ Every `@router`/`@app` route in FastAPI
> Status key: ✅ Match | ⚠️ Mismatch | 🔴 Missing frontend | ❌ Missing backend

---

## Domain: Auth

### 1. Login
- **Swift Caller:** `NetworkManager.login(username:password:)` (NetworkManager.swift:136)
- **Backend Receiver:** `routers/auth.py → login()` (line 11)
- **HTTP Method & Route:** `POST /login`
- **Swift Request Body:** `LoginRequest` (inline JSON: username, password)
- **Swift Response Model:** `LoggedInUser`
- **Backend Request Schema:** `schemas/auth.py → LoginRequest`
- **Backend Response:** `dict` (access_token, user)
- **Auth Required:** No
- **Bridge Status:** ✅ Match

### 2. Register
- **Swift Caller:** `NetworkManager.register(username:displayName:)` (NetworkManager.swift:158)
- **Backend Receiver:** `routers/auth.py → register()` (line 27)
- **HTTP Method & Route:** `POST /register`
- **Swift Request Body:** `RegisterRequest` (inline JSON: username, password, display_name)
- **Swift Response Model:** `LoggedInUser`
- **Backend Request Schema:** `schemas/auth.py → RegisterRequest`
- **Backend Response:** `dict` (access_token, user)
- **Auth Required:** No
- **Bridge Status:** ✅ Match

---

## Domain: Portfolio

### 3. Get Portfolio Holdings
- **Swift Caller:** `NetworkManager.getPortfolio(userId:)` (NetworkManager.swift:291)
- **Backend Receiver:** `routers/portfolio.py → get_portfolio()` (line 291)
- **HTTP Method & Route:** `GET /portfolio/{user_id}`
- **Swift Response Model:** `[PortfolioHolding]`
- **Backend Response:** `List[Portfolio]` (SQLAlchemy model)
- **Auth Required:** Yes
- **Bridge Status:** ✅ Match

### 4. Add Holding
- **Swift Caller:** `NetworkManager.addHolding(...)` (NetworkManager.swift:326)
- **Backend Receiver:** `routers/portfolio.py → add_holding()` (line 648)
- **HTTP Method & Route:** `POST /portfolio` (also aliased as `/portfolio/add`)
- **Swift Request Body:** `PortfolioAddRequest` (inline JSON)
- **Backend Request Schema:** `schemas/portfolio.py → PortfolioAddRequest`
- **Auth Required:** Yes
- **Bridge Status:** ✅ Match

### 5. Remove Holding
- **Swift Caller:** `NetworkManager.removeHolding(userId:ticker:)` (NetworkManager.swift:430)
- **Backend Receiver:** `routers/portfolio.py → remove_holding()` (line 714)
- **HTTP Method & Route:** `DELETE /portfolio/remove`
- **Swift Request Body:** `PortfolioRemoveRequest` (inline JSON)
- **Backend Request Schema:** `schemas/portfolio.py → PortfolioRemoveRequest`
- **Auth Required:** Yes
- **Bridge Status:** ✅ Match

### 6. Update Holding
- **Swift Caller:** `NetworkManager.updateHolding(...)` (NetworkManager.swift:441)
- **Backend Receiver:** `routers/portfolio.py → update_holding()` (line 739)
- **HTTP Method & Route:** `PUT /portfolio/update`
- **Swift Request Body:** `PortfolioUpdateRequest` (inline JSON)
- **Backend Request Schema:** `schemas/portfolio.py → PortfolioUpdateRequest`
- **Auth Required:** Yes
- **Bridge Status:** ✅ Match

### 7. Save Holding Note
- **Swift Caller:** `NetworkManager.saveNote(userId:ticker:note:)` (NetworkManager.swift:351)
- **Backend Receiver:** `routers/portfolio.py → save_note()` (line 795)
- **HTTP Method & Route:** `PUT /portfolio/note`
- **Swift Request Body:** `PortfolioNoteRequest` (inline JSON)
- **Backend Request Schema:** `schemas/portfolio.py → PortfolioNoteRequest`
- **Auth Required:** Yes
- **Bridge Status:** ✅ Match

### 8. Portfolio Valuation History
- **Swift Caller:** `HomeFeedService.fetchValuationHistory(userId:days:)` (HomeFeedService.swift:8)
- **Swift Caller:** `ValuationCalendarService.fetchValuationHistory(userId:days:)` (ValuationCalendarService.swift:7)
- **Backend Receiver:** `routers/portfolio.py → valuation_history()` (line 1379)
- **HTTP Method & Route:** `GET /api/v1/portfolio/valuation-history?user_id={id}&days={days}`
- **Swift Response Model:** `ValuationHistoryResponse`
- **Backend Response:** `dict` (dates, values, peak_date)
- **Auth Required:** Yes
- **Bridge Status:** ✅ Match

### 9. Portfolio Charts
- **Swift Caller:** **(No direct Swift caller found — called by iOS chart views internally)**
- **Backend Receiver:** `routers/portfolio.py → portfolio_charts()` (line 1498)
- **HTTP Method & Route:** `GET /api/v1/portfolio/charts/{user_id}`
- **Swift Response Model:** `PortfolioChartsResponse`
- **Backend Response:** `dict`
- **Auth Required:** Yes
- **Bridge Status:** 🔴 Missing frontend (backend exists, no NetworkManager wrapper found)

### 10. Portfolio Risk Analysis
- **Swift Caller:** `NetworkManager.fetchRiskAnalysis(userId:)` (NetworkManager.swift:643)
- **Backend Receiver:** `routers/portfolio.py → risk_analysis()` (line 1607)
- **HTTP Method & Route:** `GET /portfolio/risk-analysis/{user_id}`
- **Swift Response Model:** `RiskAnalysis`
- **Backend Response:** `dict`
- **Auth Required:** Yes
- **Bridge Status:** ✅ Match

### 11. Portfolio Red Flags
- **Swift Caller:** `NetworkManager.fetchRedFlags(userId:)` (NetworkManager.swift:653)
- **Backend Receiver:** `routers/portfolio.py → red_flags()` (line 1769)
- **HTTP Method & Route:** `GET /portfolio/red-flags/{user_id}`
- **Swift Response Model:** `RedFlagsResponse`
- **Backend Response:** `dict`
- **Auth Required:** Yes
- **Bridge Status:** ✅ Match

### 12. Portfolio Timeframe Conflicts
- **Swift Caller:** **(No direct Swift caller — test_new_endpoints.py only)**
- **Backend Receiver:** `routers/portfolio.py → timeframe_conflicts()` (line 2011)
- **HTTP Method & Route:** `GET /portfolio/timeframe-conflicts/{user_id}`
- **Swift Response Model:** `TimeframeConflictsResponse`
- **Backend Response:** `dict`
- **Auth Required:** Yes
- **Bridge Status:** 🔴 Missing frontend

### 13. Portfolio Export Excel
- **Swift Caller:** `NetworkManager.exportPortfolioExcel(userId:)` (NetworkManager.swift:511)
- **Backend Receiver:** `routers/portfolio.py → export_excel()` (line 1256)
- **HTTP Method & Route:** `GET /portfolio/export/excel/{user_id}`
- **Swift Response Model:** `Data` (raw bytes)
- **Backend Response:** `StreamingResponse` (xlsx binary)
- **Auth Required:** Yes
- **Bridge Status:** ✅ Match

### 14. Portfolio Export PDF
- **Swift Caller:** **(No direct Swift caller found)**
- **Backend Receiver:** `routers/portfolio.py → export_pdf()` (line 2350)
- **HTTP Method & Route:** `GET /portfolio/export/pdf/{user_id}`
- **Backend Response:** `StreamingResponse` (PDF binary)
- **Auth Required:** Yes
- **Bridge Status:** 🔴 Missing frontend

### 15. Portfolio Signal Warnings
- **Swift Caller:** `NetworkManager.getSignalWarnings(userId:)` (NetworkManager.swift:591)
- **Backend Receiver:** `routers/portfolio.py → signal_warnings()` (line 268)
- **HTTP Method & Route:** `GET /portfolio/signal-warnings?user_id={id}`
- **Swift Response Model:** `[SignalWarning]`
- **Backend Response:** `dict`
- **Auth Required:** Yes
- **Bridge Status:** ✅ Match

### 16. Morning Summary
- **Swift Caller:** `NetworkManager.getMorningSummary(userId:)` (NetworkManager.swift:366)
- **Backend Receiver:** `routers/portfolio.py → morning_summary()` (line 430)
- **HTTP Method & Route:** `GET /morning-summary/{user_id}`
- **Swift Response Model:** `MorningSummaryResponse`
- **Backend Response:** `dict`
- **Auth Required:** Yes
- **Bridge Status:** ✅ Match

### 17. Piotroski F-Score
- **Swift Caller:** **(No direct Swift caller found — used by analysis views)**
- **Backend Receiver:** `routers/portfolio.py → piotroski()` (line 415)
- **HTTP Method & Route:** `GET /fundamentals/piotroski/{ticker}`
- **Backend Response:** `dict`
- **Auth Required:** Yes
- **Bridge Status:** 🔴 Missing frontend (backend exists)

### 18. Advisor Consensus
- **Swift Caller:** **(No direct Swift caller)**
- **Backend Receiver:** `routers/portfolio.py → advisor_consensus()` (line 1102)
- **HTTP Method & Route:** `GET /api/v1/portfolio/advisor-consensus`
- **Backend Response:** `dict`
- **Auth Required:** Yes
- **Bridge Status:** 🔴 Missing frontend

### 19. Net Worth Ledger
- **Swift Caller:** **(No direct Swift caller)**
- **Backend Receiver:** `routers/portfolio.py → net_worth_ledger()` (line 2523)
- **HTTP Method & Route:** `GET /api/v1/market/net-worth-ledger/{user_id}`
- **Swift Response Model:** (none — backend defines `NetWorthSnapshotResponse`)
- **Backend Response:** `NetWorthSnapshotResponse`
- **Auth Required:** Yes
- **Bridge Status:** 🔴 Missing frontend

### 20. Portfolio History
- **Swift Caller:** **(No direct Swift caller)**
- **Backend Receiver:** `routers/portfolio.py → portfolio_history()` (line 384)
- **HTTP Method & Route:** `GET /portfolio/history/{user_id}`
- **Backend Response:** `dict`
- **Auth Required:** Yes
- **Bridge Status:** 🔴 Missing frontend

---

## Domain: Market Data

### 21. Market Indices
- **Swift Caller:** `NetworkManager.getMarketIndices()` (NetworkManager.swift:379)
- **Backend Receiver:** `routers/market.py → market_indices()` (line 34)
- **HTTP Method & Route:** `GET /market-indices`
- **Swift Response Model:** `MarketIndicesResponse`
- **Backend Response:** `dict` (indices list + fetched_at)
- **Auth Required:** Yes
- **Bridge Status:** ✅ Match

### 22. Nifty History
- **Swift Caller:** `NetworkManager.getNiftyHistory(days:)` (NetworkManager.swift:524)
- **Backend Receiver:** `routers/market.py → nifty_history()` (line 39)
- **HTTP Method & Route:** `GET /nifty-history?days={days}`
- **Swift Response Model:** `[NiftyPricePoint]`
- **Backend Response:** `List[dict]`
- **Auth Required:** No
- **Bridge Status:** ✅ Match

### 23. Quarterly Financials
- **Swift Caller:** `NetworkManager.getQuarterlyFinancialsResponse(ticker:exchange:)` (NetworkManager.swift:536)
- **Backend Receiver:** `routers/market.py → quarterly_financials()` (line 98)
- **HTTP Method & Route:** `GET /quarterly-financials?ticker={t}&exchange={ex}`
- **Swift Response Model:** `QuarterlyFinancialsResponse`
- **Backend Response:** `dict`
- **Auth Required:** No
- **Bridge Status:** ✅ Match

### 24. Macro Strip
- **Swift Caller:** `NetworkManager.getMacroStrip()` (NetworkManager.swift:569)
- **Backend Receiver:** `routers/market.py → macro_strip()` (line 155)
- **HTTP Method & Route:** `GET /macro-strip`
- **Swift Response Model:** `MacroStrip`
- **Backend Response:** `dict`
- **Auth Required:** No
- **Bridge Status:** ✅ Match

### 25. Macro Impact
- **Swift Caller:** `NetworkManager.fetchMacroImpact(userId:)` (NetworkManager.swift:663)
- **Backend Receiver:** `routers/portfolio.py → macro_impact()` (line 1925)
- **HTTP Method & Route:** `GET /macro-impact/{user_id}`
- **Swift Response Model:** `MacroImpactResponse`
- **Backend Response:** `dict`
- **Auth Required:** Yes
- **Bridge Status:** ✅ Match

### 26. Analyst Ratings
- **Swift Caller:** `NetworkManager.getAnalystRatings(ticker:exchange:)` (NetworkManager.swift:580)
- **Backend Receiver:** `routers/market.py → analyst_ratings()` (line 268)
- **HTTP Method & Route:** `GET /analyst-ratings?ticker={t}&exchange={ex}`
- **Swift Response Model:** `AnalystRatingsResponse`
- **Backend Response:** `dict`
- **Auth Required:** No
- **Bridge Status:** ✅ Match

### 27. Sector Performance
- **Swift Caller:** `NetworkManager.getSectorPerformance()` (NetworkManager.swift:497)
- **Backend Receiver:** `routers/market.py → sector_performance()` (line 591)
- **HTTP Method & Route:** `GET /sector-performance`
- **Swift Response Model:** `[SectorPerformance]`
- **Backend Response:** `List[dict]`
- **Auth Required:** No
- **Bridge Status:** ✅ Match

### 28. Sector Weekly
- **Swift Caller:** **(No direct Swift caller)**
- **Backend Receiver:** `routers/market.py → sector_weekly()` (line 324)
- **HTTP Method & Route:** `GET /sector-weekly`
- **Backend Response:** `dict`
- **Auth Required:** No
- **Bridge Status:** 🔴 Missing frontend

### 29. Quick Info
- **Swift Caller:** `NetworkManager.quickInfo(ticker:exchange:)` (NetworkManager.swift:612)
- **Backend Receiver:** `routers/analysis.py → quick_info()` (line 237)
- **HTTP Method & Route:** `GET /quick-info?ticker={t}&exchange={ex}`
- **Swift Response Model:** `QuickInfo`
- **Backend Response:** `dict`
- **Auth Required:** No
- **Bridge Status:** ✅ Match

### 30. Market Dashboard (Legacy)
- **Swift Caller:** `NetworkManager+Sidebar.fetchMarketDashboard()` (NetworkManager+Sidebar.swift:161)
- **Backend Receiver:** `routers/market.py → market_dashboard()` (line 818)
- **HTTP Method & Route:** `GET /api/v1/market/dashboard`
- **Swift Response Model:** `MarketDashboardResponse`
- **Backend Response:** `dict`
- **Auth Required:** No
- **Bridge Status:** ✅ Match

### 31. Market Dashboard Pulse (Extended)
- **Swift Caller:** `NetworkManager+Sidebar.fetchExtendedMarketDashboard()` (NetworkManager+Sidebar.swift:188)
- **Backend Receiver:** `routers/market.py → dashboard_pulse()` (line 840)
- **HTTP Method & Route:** `GET /api/v1/market/dashboard-pulse`
- **Swift Response Model:** `ExtendedMarketDashboardResponse`
- **Backend Response Schema:** `schemas/market.py → DashboardPulseResponse`
- **Auth Required:** No
- **Bridge Status:** ✅ Match

### 32. Market Pulse
- **Swift Caller:** `NetworkManager+Sidebar.fetchMarketPulse()` (NetworkManager+Sidebar.swift:61)
- **Backend Receiver:** `routers/market.py → market_pulse()` (line 651)
- **HTTP Method & Route:** `GET /api/v1/market/pulse`
- **Swift Response Model:** `MarketPulseResponse`
- **Backend Response:** `dict`
- **Auth Required:** No
- **Bridge Status:** ✅ Match

### 33. Market Momentum
- **Swift Caller:** `NetworkManager+Sidebar.fetchMomentum()` (NetworkManager+Sidebar.swift:86)
- **Backend Receiver:** `routers/market.py → market_momentum()` (line 659)
- **HTTP Method & Route:** `GET /api/v1/market/momentum`
- **Swift Response Model:** `MomentumResponse`
- **Backend Response:** `dict`
- **Auth Required:** No
- **Bridge Status:** ✅ Match

### 34. Macro Alternatives
- **Swift Caller:** `NetworkManager+Sidebar.fetchMacroAlternatives()` (NetworkManager+Sidebar.swift:111)
- **Backend Receiver:** `routers/market.py → macro_alternatives()` (line 667)
- **HTTP Method & Route:** `GET /api/v1/market/macro-alternatives`
- **Swift Response Model:** `MacroAlternativesResponse`
- **Backend Response:** `dict`
- **Auth Required:** No
- **Bridge Status:** ✅ Match

### 35. Institutional Flow
- **Swift Caller:** `NetworkManager+Sidebar.fetchInstitutionalFlow()` (NetworkManager+Sidebar.swift:136)
- **Backend Receiver:** `routers/market.py → institutional_flow()` (line 675)
- **HTTP Method & Route:** `GET /api/v1/market/institutional-flow`
- **Swift Response Model:** `InstitutionalFlowResponse`
- **Backend Response:** `dict`
- **Auth Required:** No
- **Bridge Status:** ✅ Match

### 36. Institutional Leaderboard
- **Swift Caller:** **(No direct Swift caller)**
- **Backend Receiver:** `routers/market.py → institutional_leaderboard()` (line 1170)
- **HTTP Method & Route:** `GET /api/v1/market/institutional-leaderboard`
- **Backend Response:** `InstitutionalLeaderboardResponseLocal`
- **Auth Required:** Yes
- **Bridge Status:** 🔴 Missing frontend

### 37. IPO Calendar
- **Swift Caller:** **(No direct Swift caller)**
- **Backend Receiver:** `routers/market.py → ipo_calendar()` (line 314)
- **HTTP Method & Route:** `GET /ipo-calendar`
- **Backend Response:** `dict`
- **Auth Required:** No
- **Bridge Status:** 🔴 Missing frontend

### 38. Daily Action
- **Swift Caller:** `NetworkManager.fetchDailyAction(userId:)` (NetworkManager.swift:673)
- **Backend Receiver:** `routers/analysis.py → daily_action()` (line 1220)
- **HTTP Method & Route:** `GET /daily-action/{user_id}`
- **Swift Response Model:** `DailyActionResponse`
- **Backend Response:** `dict`
- **Auth Required:** Yes
- **Bridge Status:** ✅ Match

### 39. Technical Signals
- **Swift Caller:** **(No direct Swift caller)**
- **Backend Receiver:** `routers/analysis.py → technical_signals()` (line 678)
- **HTTP Method & Route:** `GET /api/v1/technical-signals`
- **Backend Response:** `dict`
- **Auth Required:** Yes
- **Bridge Status:** 🔴 Missing frontend

---

## Domain: AI Analysis

### 40. Analyze Stock
- **Swift Caller:** `NetworkManager.analyze(ticker:exchange:userId:useMock:deepScan:)` (NetworkManager.swift:176)
- **Backend Receiver:** `routers/analysis.py → analyze()` (line 453)
- **HTTP Method & Route:** `POST /analyze`
- **Swift Request Body:** `AnalyzeRequest` (inline JSON: ticker, exchange, user_id, deep_scan)
- **Swift Response Model:** `StockAnalysis`
- **Backend Request Schema:** `schemas/portfolio.py → AnalyzeRequest`
- **Backend Response:** `dict` (full AI analysis JSON — multiprocessing with Queue)
- **Auth Required:** Optional (user_id optional)
- **SSE/Streaming:** No (polling via multiprocessing.Queue)
- **Bridge Status:** ✅ Match

### 41. Batch Analyze
- **Swift Caller:** **(No direct Swift caller)**
- **Backend Receiver:** `routers/analysis.py → batch_analyze()` (line 588)
- **HTTP Method & Route:** `POST /analyze/batch`
- **Backend Request Schema:** `schemas/portfolio.py → BatchAnalyzeRequest`
- **Backend Response:** `dict` (batch_id)
- **Auth Required:** Yes
- **Bridge Status:** 🔴 Missing frontend

### 42. Batch Analyze Status
- **Swift Caller:** **(No direct Swift caller)**
- **Backend Receiver:** `routers/analysis.py → batch_status()` (line 639)
- **HTTP Method & Route:** `GET /analyze/batch/{batch_id}`
- **Backend Response:** `dict`
- **Auth Required:** Yes
- **Bridge Status:** 🔴 Missing frontend

---

## Domain: Watchlist

### 43. Get Watchlist
- **Swift Caller:** `NetworkManager.getWatchlist(userId:)` (NetworkManager.swift:417)
- **Backend Receiver:** `routers/user.py → get_watchlist()` (line 108)
- **HTTP Method & Route:** `GET /watchlist/{user_id}`
- **Swift Response Model:** `[WatchlistItem]`
- **Backend Response:** `List[WatchlistItem]`
- **Auth Required:** Yes
- **Bridge Status:** ✅ Match

### 44. Add to Watchlist
- **Swift Caller:** `NetworkManager.addToWatchlist(...)` (NetworkManager.swift:392)
- **Backend Receiver:** `routers/user.py → add_to_watchlist()` (line 58)
- **HTTP Method & Route:** `POST /watchlist/add`
- **Swift Request Body:** `WatchlistAddRequest` (inline JSON)
- **Backend Request Schema:** `schemas/portfolio.py → WatchlistAddRequest`
- **Auth Required:** Yes
- **Bridge Status:** ✅ Match

### 45. Remove from Watchlist
- **Swift Caller:** `NetworkManager.removeFromWatchlist(userId:ticker:)` (NetworkManager.swift:406)
- **Backend Receiver:** `routers/user.py → remove_from_watchlist()` (line 87)
- **HTTP Method & Route:** `DELETE /watchlist/remove`
- **Swift Request Body:** `WatchlistRemoveRequest` (inline JSON)
- **Backend Request Schema:** `schemas/portfolio.py → WatchlistRemoveRequest`
- **Auth Required:** Yes
- **Bridge Status:** ✅ Match

---

## Domain: Alerts

### 46. Get Alerts
- **Swift Caller:** `NetworkManager.getAlerts(userId:)` (NetworkManager.swift:467)
- **Backend Receiver:** `routers/alerts.py → get_alerts()` (line 122)
- **HTTP Method & Route:** `GET /alerts/{user_id}`
- **Swift Response Model:** `[PriceAlert]`
- **Backend Response:** `dict`
- **Auth Required:** Yes
- **Bridge Status:** ✅ Match

### 47. Add Alert
- **Swift Caller:** `NetworkManager.addAlert(...)` (NetworkManager.swift:454)
- **Backend Receiver:** `routers/alerts.py → add_alert()` (line 10)
- **HTTP Method & Route:** `POST /alerts/add`
- **Swift Request Body:** `AlertAddRequest` (inline JSON)
- **Backend Request Schema:** `schemas/portfolio.py → AlertAddRequest`
- **Auth Required:** Yes
- **Bridge Status:** ✅ Match

### 48. Remove Alert
- **Swift Caller:** `NetworkManager.removeAlert(userId:alertId:)` (NetworkManager.swift:475)
- **Backend Receiver:** `routers/alerts.py → remove_alert()` (line 46)
- **HTTP Method & Route:** `DELETE /alerts/remove`
- **Swift Request Body:** `AlertRemoveRequest` (inline JSON)
- **Backend Request Schema:** `schemas/portfolio.py → AlertRemoveRequest`
- **Auth Required:** Yes
- **Bridge Status:** ✅ Match

### 49. Check Alerts (Triggered)
- **Swift Caller:** `NetworkManager.checkAlerts(userId:)` (NetworkManager.swift:486)
- **Backend Receiver:** `routers/alerts.py → check_alerts()` (line 67)
- **HTTP Method & Route:** `GET /alerts/check/{user_id}`
- **Swift Response Model:** `[TriggeredAlert]`
- **Backend Response:** `dict`
- **Auth Required:** Yes
- **Bridge Status:** ✅ Match

---

## Domain: Dashboard / Health

### 50. Health Check
- **Swift Caller:** `NetworkManager.checkHealth()` (NetworkManager.swift:602)
- **Backend Receiver:** `main.py → health_endpoint()` (line 730)
- **HTTP Method & Route:** `GET /health`
- **Swift Response Model:** `Bool` (simplified — inspects HTTP status code only)
- **Backend Response:** `{"status": "ok"}` (lightweight, no DB/disk/yfinance checks)
- **Auth Required:** No
- **Bridge Status:** ✅ Match — simplified to minimal 200 OK; Swift only checks HTTP status code. Rich diagnostics at `GET /health/live`.

### 51. Liveness Probe
- **Swift Caller:** **(No direct Swift caller — used by Docker/k8s)**
- **Backend Receiver:** `main.py → liveness_probe()` (line 791)
- **HTTP Method & Route:** `GET /health/live`
- **Backend Response:** `dict` (status, db, ts)
- **Auth Required:** No
- **Bridge Status:** 🔴 Missing frontend (infrastructure only)

### 52. Ping
- **Swift Caller:** **(No direct Swift caller)**
- **Backend Receiver:** `main.py → ping()` (line 395)
- **HTTP Method & Route:** `GET /ping`
- **Backend Response:** `{"pong": true}`
- **Auth Required:** No
- **Bridge Status:** 🔴 Missing frontend

### 53. Admin Dashboard HTML
- **Swift Caller:** **(No Swift caller — browser only)**
- **Backend Receiver:** `main.py → dashboard_html()` (line 1578)
- **HTTP Method & Route:** `GET /` (HTMLResponse)
- **Auth Required:** No
- **Bridge Status:** 🔴 Missing frontend (browser only)

### 54. Admin Dashboard Data
- **Swift Caller:** **(No Swift caller — browser only)**
- **Backend Receiver:** `main.py → dashboard_data()` (line 1583)
- **HTTP Method & Route:** `GET /dashboard-data`
- **Backend Response:** `dict` (active_analyses, token_stats, harvest_status, etc.)
- **Auth Required:** Yes (admin)
- **Bridge Status:** 🔴 Missing frontend (browser only)

### 55. Dashboard SSE Stream
- **Swift Caller:** **(No direct Swift caller found)**
- **Backend Receiver:** `routers/dashboard.py → dashboard_stream()` (line 43)
- **HTTP Method & Route:** `GET /api/v1/dashboard/stream`
- **Backend Response:** `StreamingResponse` (SSE)
- **Auth Required:** Yes
- **SSE/Streaming:** Yes
- **Bridge Status:** 🔴 Missing frontend

---

## Domain: Notifications

### 56. Register Device Token
- **Swift Caller:** `NetworkManager.registerDeviceToken(token:)` (NetworkManager.swift:684)
- **Backend Receiver:** `routers/user.py → notifications_register_device()` (line 185)
  - **Also:** `routers/notifications.py → register_device()` (line 43)
- **HTTP Method & Route (Swift calls):** `POST /notifications/register-device`
- **HTTP Method & Route (Backend v1):** `POST /api/v1/notifications/register`
- **Swift Response Model:** `Void`
- **Backend Response:** `dict` (`{"success": True, "message": "..."}`)
- **Shared Logic:** `helpers.py → upsert_device_token()` — single source of truth for both routes
- **Auth Required:** Yes
- **Bridge Status:** ✅ Match — both routes now delegate to shared `upsert_device_token()` in helpers.py. Swift-facing route `/notifications/register-device` preserved exactly.

### 57. Send Test Notification
- **Swift Caller:** `NetworkManager.sendTestNotification(ticker:exchange:)` (NetworkManager.swift:702)
- **Backend Receiver:** `routers/user.py → send_test_notification()` (line 217)
- **HTTP Method & Route:** `POST /notifications/test`
- **Swift Response Model:** `NotificationPayload`
- **Backend Response:** `dict`
- **Auth Required:** Yes
- **Bridge Status:** ✅ Match

### 58. Morning Summary Push
- **Swift Caller:** `NetworkManager.sendMorningSummaryNotification()` (NetworkManager.swift:715)
- **Backend Receiver:** `routers/user.py → send_morning_summary_push()` (line 254)
- **HTTP Method & Route:** `POST /notifications/morning-summary-push`
- **Swift Response Model:** `NotificationPayload`
- **Backend Response:** `dict`
- **Auth Required:** Yes
- **Bridge Status:** ✅ Match

### 59. Dev Push Mock
- **Swift Caller:** **(No Swift caller)**
- **Backend Receiver:** `routers/notifications.py → dev_push_mock()` (line 85)
- **HTTP Method & Route:** `POST /api/v1/dev/push-mock`
- **Backend Response:** `dict`
- **Auth Required:** No
- **Bridge Status:** 🔴 Missing frontend (dev tool)

---

## Domain: Trade Journal

### 60. Add Trade Journal Entry
- **Swift Caller:** **(No direct Swift caller found in NetworkManager)**
- **Backend Receiver:** `routers/portfolio.py → add_trade_journal()` (line 2091)
- **HTTP Method & Route:** `POST /trade-journal`
- **Backend Request Schema:** `schemas/portfolio.py → TradeJournalAddRequest`
- **Backend Response:** `dict`
- **Auth Required:** Yes
- **Bridge Status:** 🔴 Missing frontend

### 61. Get Trade Journal
- **Swift Caller:** **(No direct Swift caller)**
- **Backend Receiver:** `routers/portfolio.py → get_trade_journal()` (line 2135)
- **HTTP Method & Route:** `GET /trade-journal/{user_id}`
- **Swift Response Model:** `TradeJournalResponse`
- **Backend Response:** `dict`
- **Auth Required:** Yes
- **Bridge Status:** 🔴 Missing frontend

### 62. Update Trade Journal
- **Swift Caller:** **(No direct Swift caller)**
- **Backend Receiver:** `routers/portfolio.py → update_trade_journal()` (line 2184)
- **HTTP Method & Route:** `PUT /trade-journal/{entry_id}`
- **Backend Response:** `dict`
- **Auth Required:** Yes
- **Bridge Status:** 🔴 Missing frontend

### 63. Delete Trade Journal
- **Swift Caller:** **(No direct Swift caller)**
- **Backend Receiver:** `routers/portfolio.py → delete_trade_journal()` (line 2234)
- **HTTP Method & Route:** `DELETE /trade-journal/{entry_id}`
- **Backend Response:** `dict`
- **Auth Required:** Yes
- **Bridge Status:** 🔴 Missing frontend

### 64. Trade Journal Stats
- **Swift Caller:** **(No direct Swift caller)**
- **Backend Receiver:** `routers/portfolio.py → trade_journal_stats()` (line 2259)
- **HTTP Method & Route:** `GET /trade-journal/{user_id}/stats`
- **Swift Response Model:** `TradeJournalStatsResponse`
- **Backend Response:** `dict`
- **Auth Required:** Yes
- **Bridge Status:** 🔴 Missing frontend

---

## Domain: Earnings

### 65. Earnings Calendar (Legacy)
- **Swift Caller:** `NetworkManager.getEarningsCalendar()` (NetworkManager.swift:557)
- **Backend Receiver:** `routers/market.py → earnings_calendar()` (line 219)
- **HTTP Method & Route:** `GET /earnings-calendar`
- **Swift Response Model:** `[EarningsEvent]`
- **Backend Response:** `List[dict]`
- **Auth Required:** No
- **Bridge Status:** ✅ Match

### 66. Earnings Calendar v1 (by date)
- **Swift Caller:** `NetworkManager+Sidebar.fetchEarningsCalendar(date:ticker:)` (NetworkManager+Sidebar.swift:242)
- **Backend Receiver:** `routers/market.py → earnings_calendar_v1()` (line 1544)
- **HTTP Method & Route:** `GET /api/v1/earnings/calendar?date={date}&ticker={t}`
- **Swift Response Model:** `EarningsCalendarDayResponse`
- **Backend Response:** `dict`
- **Auth Required:** Yes
- **Bridge Status:** ✅ Match

### 67. Earnings Feed
- **Swift Caller:** `NetworkManager+Sidebar.fetchRankedEarningsFeed(sort:)` (NetworkManager+Sidebar.swift:273)
- **Backend Receiver:** `routers/market.py → earnings_feed()` (line 1461)
- **HTTP Method & Route:** `GET /api/v1/earnings/feed?sort={sort}`
- **Swift Response Model:** `EarningsFeedResponse`
- **Backend Response:** `dict`
- **Auth Required:** Yes
- **Bridge Status:** ✅ Match

### 68. Earnings Sync Ratio
- **Swift Caller:** **(No direct Swift caller)**
- **Backend Receiver:** `routers/market.py → earnings_sync_ratio()` (line 703)
- **HTTP Method & Route:** `GET /api/v1/earnings/sync-ratio`
- **Backend Response:** `EarningsSyncRatioResponseLocal`
- **Auth Required:** Yes
- **Bridge Status:** 🔴 Missing frontend

### 69. Earnings YoY Aggregate
- **Swift Caller:** **(No direct Swift caller)**
- **Backend Receiver:** `routers/market.py → earnings_yoy_aggregate()` (line 731)
- **HTTP Method & Route:** `GET /api/v1/earnings/yoy-aggregate`
- **Backend Response:** `YoYAggregateResponseLocal`
- **Auth Required:** Yes
- **Bridge Status:** 🔴 Missing frontend

### 70. Earnings Progress
- **Swift Caller:** **(No direct Swift caller)**
- **Backend Receiver:** `routers/market.py → earnings_progress()` (line 1250)
- **HTTP Method & Route:** `GET /api/v1/earnings/progress`
- **Backend Response:** `dict`
- **Auth Required:** Yes
- **Bridge Status:** 🔴 Missing frontend

### 71. Earnings Estimates
- **Swift Caller:** **(No direct Swift caller)**
- **Backend Receiver:** `routers/market.py → earnings_estimates()` (line 1653)
- **HTTP Method & Route:** `GET /api/v1/earnings/estimates`
- **Backend Response:** `dict`
- **Auth Required:** Yes
- **Bridge Status:** 🔴 Missing frontend

### 72. Post-Result Movers
- **Swift Caller:** **(No direct Swift caller)**
- **Backend Receiver:** `routers/market.py → post_result_movers()` (line 1692)
- **HTTP Method & Route:** `GET /api/v1/earnings/post-result-movers`
- **Swift Response Model:** `PostResultMoversResponse`
- **Backend Response:** `dict`
- **Auth Required:** Yes
- **Bridge Status:** 🔴 Missing frontend

### 73. Earnings Alerts (CRUD)
- **Swift Caller:** **(No direct Swift caller)**
- **Backend Receiver:** `routers/market.py → earnings_alerts_get/post/delete()` (lines 1744/1777/1825)
- **HTTP Method & Route:** `GET|POST /api/v1/earnings/alerts`, `DELETE /api/v1/earnings/alerts/{alert_id}`
- **Backend Response:** `dict`
- **Auth Required:** Yes
- **Bridge Status:** 🔴 Missing frontend

---

## Domain: Ideas / Advisors

### 74. Advisors List
- **Swift Caller:** `NetworkManager+Sidebar.fetchAdvisors()` (NetworkManager+Sidebar.swift:331)
- **Backend Receiver:** `routers/market.py → advisors_list()` (line 2038)
- **HTTP Method & Route:** `GET /api/v1/ideas/advisors`
- **Swift Response Model:** `AdvisorsResponse`
- **Backend Response:** `dict`
- **Auth Required:** No
- **Bridge Status:** ✅ Match

### 75. Ideas Feed
- **Swift Caller:** `NetworkManager+Sidebar.fetchIdeasFeed(limit:sentiment:)` (NetworkManager+Sidebar.swift:343)
- **Backend Receiver:** `routers/market.py → ideas_feed()` (line 2074)
- **HTTP Method & Route:** `GET /api/v1/ideas/feed?limit={n}&sentiment={s}`
- **Swift Response Model:** `IdeasFeedResponse`
- **Backend Response:** `dict`
- **Auth Required:** No
- **Bridge Status:** ✅ Match

### 76. Experts List
- **Swift Caller:** **(No direct Swift caller)**
- **Backend Receiver:** `routers/user.py → experts_list()` (line 292)
- **HTTP Method & Route:** `GET /api/v1/experts`
- **Backend Response:** `dict`
- **Auth Required:** No
- **Bridge Status:** 🔴 Missing frontend

### 77. Expert Posts
- **Swift Caller:** **(No direct Swift caller)**
- **Backend Receiver:** `routers/user.py → expert_posts()` (line 338)
- **HTTP Method & Route:** `GET /api/v1/expert-posts`
- **Backend Response:** `dict`
- **Auth Required:** No
- **Bridge Status:** 🔴 Missing frontend

---

## Domain: Search & Discovery

### 78. Stock Search
- **Swift Caller:** `NetworkManager.searchStocks(q:)` (NetworkManager.swift:623)
- **Backend Receiver:** `routers/market.py → search_stocks()` (line 548)
- **HTTP Method & Route:** `GET /search?q={query}&limit=25`
- **Swift Response Model:** `[StockEntry]`
- **Backend Response:** `List[dict]`
- **Auth Required:** No
- **Bridge Status:** ✅ Match

### 79. Screener
- **Swift Caller:** **(No direct Swift caller in NetworkManager)**
- **Backend Receiver:** `routers/analysis.py → screener()` (line 828)
- **HTTP Method & Route:** `GET /screener`
- **Swift Response Model:** `[ScreenerResult]`
- **Backend Response:** `dict`
- **Auth Required:** No
- **Bridge Status:** 🔴 Missing frontend

### 80. Options Chain
- **Swift Caller:** **(No direct Swift caller)**
- **Backend Receiver:** `routers/market.py → options_chain()` (line 1883)
- **HTTP Method & Route:** `GET /api/v1/options/chain/{ticker}`
- **Backend Response:** `dict`
- **Auth Required:** Yes
- **Bridge Status:** 🔴 Missing frontend

---

## Domain: Home Feed

### 81. Home Feed
- **Swift Caller:** `HomeFeedService.fetchFeed(userId:ticker:)` (HomeFeedService.swift:8)
- **Backend Receiver:** `routers/analysis.py → home_feed()` (line 705)
- **HTTP Method & Route:** `GET /api/v1/home-feed?user_id={id}&ticker={t}`
- **Swift Response Model:** `HomeFeedResponse`
- **Backend Response:** `dict`
- **Auth Required:** Yes
- **Bridge Status:** ✅ Match

---

## Domain: Admin / Error Logs

### 82. YouTube Harvest (Admin)
- **Swift Caller:** **(No Swift caller)**
- **Backend Receiver:** `services/harvest_worker.py → admin_harvest_youtube()` (router)
- **HTTP Method & Route:** `POST /api/v1/admin/harvest-youtube`
- **Auth Required:** Yes (admin)
- **Bridge Status:** 🔴 Missing frontend (admin tool)

### 83. Advisor Harvest (Admin)
- **Swift Caller:** **(No Swift caller)**
- **Backend Receiver:** `services/harvest_worker.py → admin_harvest_advisors()` (router)
- **HTTP Method & Route:** `POST /api/v1/admin/harvest-advisors`
- **Auth Required:** Yes (admin)
- **Bridge Status:** 🔴 Missing frontend (admin tool)

### 84. News Harvest (Admin)
- **Swift Caller:** **(No Swift caller)**
- **Backend Receiver:** `services/harvest_worker.py → admin_harvest_news()` (router)
- **HTTP Method & Route:** `POST /api/v1/admin/harvest-news`
- **Auth Required:** Yes (admin)
- **Bridge Status:** 🔴 Missing frontend (admin tool)

### 85. Market Error Logs
- **Swift Caller:** `NetworkManager+Sidebar.fetchMarketErrorLogs(limit:)` (NetworkManager+Sidebar.swift:210)
- **Backend Receiver:** `routers/market.py → market_error_logs()` (line 1134)
- **HTTP Method & Route:** `GET /api/v1/admin/error-logs?limit={n}`
- **Swift Response Model:** `MarketErrorLogsResponse`
- **Backend Response:** `dict`
- **Auth Required:** Yes (admin)
- **Bridge Status:** ✅ Match

### 86. Earnings Error Logs
- **Swift Caller:** `NetworkManager+Sidebar.fetchEarningsErrorLogs(limit:)` (NetworkManager+Sidebar.swift:300)
- **Backend Receiver:** `routers/market.py → earnings_error_logs()` (line 1845)
- **HTTP Method & Route:** `GET /api/v1/admin/earnings-errors?limit={n}`
- **Swift Response Model:** `EarningsErrorLogsResponse`
- **Backend Response:** `dict`
- **Auth Required:** Yes (admin)
- **Bridge Status:** ✅ Match

### 87. Ideas Error Logs
- **Swift Caller:** **(No direct Swift caller)**
- **Backend Receiver:** `routers/market.py → ideas_error_logs()` (line 2125)
- **HTTP Method & Route:** `GET /api/v1/admin/ideas-errors`
- **Backend Response:** `dict`
- **Auth Required:** Yes (admin)
- **Bridge Status:** 🔴 Missing frontend

### 88. Notification Error Logs
- **Swift Caller:** **(No direct Swift caller)**
- **Backend Receiver:** `routers/notifications.py → notification_errors()` (line 124)
- **HTTP Method & Route:** `GET /api/v1/admin/notification-errors`
- **Backend Response:** `dict`
- **Auth Required:** Yes (admin)
- **Bridge Status:** 🔴 Missing frontend

### 89. Token Stats (Admin)
- **Swift Caller:** **(No direct Swift caller)**
- **Backend Receiver:** `routers/analysis.py → token_stats()` (line 1352)
- **HTTP Method & Route:** `GET /token-stats`
- **Backend Response:** `dict`
- **Auth Required:** Yes (admin)
- **Bridge Status:** 🔴 Missing frontend

---

## Domain: Users

### 90. Users List (Admin)
- **Swift Caller:** **(No Swift caller)**
- **Backend Receiver:** `routers/user.py → users_list()` (line 51)
- **HTTP Method & Route:** `GET /users`
- **Backend Response:** `dict`
- **Auth Required:** Yes (admin)
- **Bridge Status:** 🔴 Missing frontend

---

## Summary Statistics

| Category | Total | ✅ Matched | ⚠️ Mismatch | 🔴 No Frontend | ❌ No Backend |
|----------|-------|-----------|------------|---------------|--------------|
| Auth | 2 | 2 | 0 | 0 | 0 |
| Portfolio | 18 | 10 | 0 | 8 | 0 |
| Market Data | 19 | 13 | 0 | 6 | 0 |
| AI Analysis | 3 | 1 | 0 | 2 | 0 |
| Watchlist | 3 | 3 | 0 | 0 | 0 |
| Alerts | 4 | 4 | 0 | 0 | 0 |
| Dashboard/Health | 6 | 2 | 0 | 4 | 0 |
| Notifications | 4 | 3 | 0 | 1 | 0 |
| Trade Journal | 5 | 0 | 0 | 5 | 0 |
| Earnings | 8 | 3 | 0 | 5 | 0 |
| Ideas/Advisors | 5 | 2 | 0 | 3 | 0 |
| Search/Discovery | 3 | 1 | 0 | 2 | 0 |
| Home Feed | 1 | 1 | 0 | 0 | 0 |
| Admin/Errors | 8 | 2 | 0 | 6 | 0 |
| Users | 1 | 0 | 0 | 1 | 0 |
| **TOTAL** | **90** | **47** | **0** | **43** | **0** |

## Critical Findings

1. **✅ Notifications double-registration — RESOLVED.** Both `POST /notifications/register-device` (user.py) and `POST /api/v1/notifications/register` (notifications.py) now delegate to shared `upsert_device_token()` in helpers.py. Swift-facing route preserved exactly.

2. **✅ Health endpoint depth mismatch — RESOLVED.** `GET /health` simplified to lightweight `{"status": "ok"}` — no yfinance, DB, or disk checks. Swift only needs HTTP 200. Rich diagnostics still available at `GET /health/live`.

3. **🔴 Trade Journal backend exists but NO Swift NetworkManager methods.** The `TradeJournalResponse`, `TradeJournalStatsResponse` models exist in Swift but no `URLSession` calls reference `/trade-journal` paths.

4. **🔴 43 backend endpoints with no corresponding Swift caller.** Either:
   - Used by browser/admin dashboard only (harvest triggers, /dashboard-data)
   - Infrastructure endpoints (/ping, /health/live)
   - Legacy endpoints pending iOS implementation (IPO calendar, options chain, trade journal CRUD)
   - Dev/debug tools (push-mock, token-stats)

5. **✅ Zero orphaned Swift calls.** Every Swift `URLSession` call has a matching backend route. No 404s expected.
