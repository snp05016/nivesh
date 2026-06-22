# 50 Improvements — Frontend + Backend
> Created: June 8, 2026  
> Scope: iOS (SwiftUI) + FastAPI backend  
> Status: ✅ Implementation completed (50/50 items finished)

---

## Frontend — iOS / SwiftUI (28 items)

---

### 1. iOS Home Screen Widget (WidgetKit)
Add a WidgetKit extension showing live portfolio P&L and Nifty 50 value on the iOS home screen. Small (2×2): total P&L + Nifty. Medium (4×2): top 3 holdings + indices.

---

### 2. Portfolio Sector Allocation Pie Chart
`PortfolioScreen` has `Charts` imported but no allocation chart. Add a `SectorPieChart` using the Swift Charts framework that breaks down holdings by NSE sector. Use `Theme.bullGreen` / `Theme.bearRed` / `Theme.holdAmber` for sectors.

---

### 3. Swipe-to-Delete on Holdings Row
Replace the trash-button-only delete in the portfolio holdings list with a standard iOS swipe-left gesture using `.swipeActions(edge: .trailing)`. More natural UX. Add `HapticManager.warning()` on swipe reveal.

---

### 4. Wire Dark Mode Toggle in Settings
`SettingsScreen` has `@AppStorage("darkMode")` declared but the value is never passed to `.preferredColorScheme()` in the root `ContentView`. Connect it so the toggle actually switches the app appearance.

---

### 5. Face ID / Touch ID App Lock
`@AppStorage("useBiometrics")` exists in `SettingsScreen` but is never acted on. Wire it to `LocalAuthentication` framework — prompt biometric auth on app foreground after 5+ minutes in background. Add a timeout picker (1 min, 5 min, 15 min, always).

---

### 6. Share Analysis as PDF / Image
Add a share button on `AnalysisScreen` that renders the current analysis card (signal, target prices, bull/bear cases) into a PDF using `UIGraphicsPDFRenderer` or an image snapshot, then invokes `UIActivityViewController`. Backend already exports portfolio PDFs — same FPDF2 pattern could power a server-side share endpoint too.

---

### 7. YouTube Section: Filter by Channel
The `youtube` home section shows videos from all 12 channels. Add a horizontal filter chip bar at the top letting users filter by channel name (e.g., "Capitalmind only", "Yadnya only"). Tags are already in `CHANNEL_REGISTRY` — use them.

---

### 8. Screener: Save Custom Presets
`SearchScreen` has 8 hardcoded screener presets. Let users save their own preset combinations (filter chips state) under a custom name, stored in `UserDefaults` / synced to the backend via a new `POST /user/screener-presets` endpoint.

---

### 9. Compare Screen: Add 3rd Stock
`CompareScreen` currently supports only 2 stocks. Expand to 3-column comparison (A vs B vs C). The `compareGrid` function needs a third column. Use `UIScreen.main.bounds.width` proportional column widths — each column gets ~30% of screen width with `Theme.Spacing.standard` gutters.

---

### 10. Analysis History: Signal Accuracy Timeline
`AnalysisHistory` table exists in the DB. Build a timeline view in the app showing every previous analysis for a ticker with date, signal issued, and (if enough time has passed) actual price outcome — showing whether the BUY/SELL/HOLD was correct. A simple chart with signal markers on the price line.

---

### 11. Trade Journal: Auto P&L on SELL Entries
When a user logs a SELL in `TradeJournalScreen`, auto-populate a "realized P&L" field by looking up the earliest matching BUY entry from the portfolio for that ticker. Show realized gain/loss in Lakhs/Crores using `IndianFormatter.priceCompact`.

---

### 12. Pull-to-Refresh Haptic Feedback
`HomeScreen` and `PortfolioScreen` use `.refreshable {}` but neither fires `HapticManager.impact(.medium)` at refresh start or `HapticManager.success()` at refresh end. Per AGENTS.md §2.3, mandatory haptic pattern for pull-to-refresh.

---

### 13. First-Run Interactive Tutorial
`TutorialManager.swift` and `TutorialOverlayView.swift` exist but aren't triggered on first launch. Wire `TutorialManager` to fire after login when `@AppStorage("hasCompletedTutorial")` is false. Walk new users through: Add Holding → Run Analysis → Set Alert.

---

### 14. Stock Chart Pinch-to-Zoom
`StockCharts.swift` renders price history but has no zoom gesture. Add `.gesture(MagnificationGesture())` to scale the visible time window (1W / 1M / 3M / 1Y / 3Y) and a time-range picker strip below the chart using SF Symbols.

---

### 15. Percentage-Based Price Alerts
`AlertsScreen` only supports absolute price targets ("alert when RELIANCE hits ₹3,000"). Add a second alert type: percentage move (e.g., "alert when stock moves +5% or -5% from current price"). Backend `PriceTarget` model needs a `trigger_type` column: `absolute` | `percent`.

---

### 16. Target Price Visual Indicator on Holdings Row
If a holding has a `target_price` set, render a small progress bar on the holding row showing current price vs target (e.g., "68% of the way to target"). Use `Theme.securityGold` for the fill. Already stored in `Portfolio.target_price`.

---

### 17. Earnings Calendar: "Set iOS Reminder" Button
`ValuationCalendarView` shows upcoming earnings dates but there's no way to act on them. Add a calendar icon button on each event that creates an iOS Calendar reminder 1 day before the earnings release using `EventKit`.

---

### 18. Voice Search via SFSpeechRecognizer
Add a microphone button in `SearchScreen` next to the text field. Use `SFSpeechRecognizer` for live transcription. Auto-uppercase the result (NSE tickers are always uppercase). Trigger the debounced search immediately on recognition.

---

### 19. Morning Brief Custom Delivery Time
The morning brief is fetched on-demand. Let users set a preferred delivery time in Settings (default 8:00 AM IST) and schedule a local `UNUserNotificationRequest` that wakes the app or sends a silent push to pre-fetch the brief. Store preference in `@AppStorage("morningBriefTime")`.

---

### 20. Save News Article to Reading List
Each news card in `NewsCardView` should have a long-press context menu with "Save to Reading List" that invokes `SafariServices` `SSReadingList.default().addItem(with: url)`. The article URL is already in the news model.

---

### 21. iPad / Landscape Layout with NavigationSplitView
The app currently collapses poorly on iPad. Replace `NiveshNavigationSidebar` (hamburger drawer) with a native `NavigationSplitView` on iPad — sidebar always visible in landscape, collapsed in portrait. Use `horizontalSizeClass` environment to branch.

---

### 22. Drag-to-Reorder Home Screen Sections
`NiveshNavigationSidebar` has toggle visibility per section but no ordering. Use `.onMove` on the sidebar list and persist the section order to `UserDefaults` as a `[HomeSectionID]` array. `HomeScreen` reads this order to render sections.

---

### 23. Portfolio Export: WhatsApp Share
The existing export flow produces PDF/XLS. Add a "Share via WhatsApp" shortcut that deep-links to `whatsapp://send?text=<formatted summary>` with portfolio P&L text formatted using `IndianFormatter`. No file needed — just text summary.

---

### 24. Deep Link Support
Add URL scheme `nivesh://` and Universal Links support so that links like `nivesh://analyze/RELIANCE` or `nivesh://watchlist/add/TCS` open directly to the right screen. Wire using `.onOpenURL` in `stockmeApp.swift` and a `DeepLinkHandler` coordinator.

---

### 25. Watchlist Grouping / Tags
The watchlist is a flat list. Add the ability to create named groups (e.g., "Long Term", "Speculative", "Tracking") and assign stocks to groups. Store groups as a JSON column on the backend `User` model or a new `WatchlistGroup` table.

---

### 26. "What Changed Since Last Analysis" Diff View
On `AnalysisScreen`, if a cached analysis exists and a new one was just fetched, show a diff summary: which signals changed (e.g., "BUY → HOLD"), which risk items are new, what the target price moved by. Pull from `AnalysisHistory` table.

---

### 27. Notification Sound Customization
`SettingsScreen` has push notification toggles but no sound settings. Add a `Picker` for notification sound: Default, Chime, Silent. Store in `@AppStorage("alertSound")` and include it in `UNMutableNotificationContent.sound` when constructing alerts.

---

### 28. Configurable App Lock Timeout
Currently `useBiometrics` is binary. Replace with a `Picker` for lock timeout: "Immediately", "After 1 min", "After 5 min", "After 15 min", "Never". Store as `@AppStorage("biometricTimeout")` and track last active timestamp in `ScenePhase.background` handler.

---

## Backend — FastAPI / Python (22 items)

---

### 29. BSE (Bombay Stock Exchange) Full Parity
Most endpoints default to `.NS` suffix (NSE). Several BSE-listed SME stocks only trade on BSE (`.BO`). Audit every `_to_ns()` call in `helpers.py` and ensure all analysis, quick-info, and portfolio endpoints gracefully fall back from `.NS` to `.BO` before raising `DataHarvestingError`.

---

### 30. Redis Caching Layer to Replace In-Memory `_dcache`
`disk_cache.py` and `_dcache` dict don't survive server restarts or multi-worker deployments. Replace with a `redis.asyncio` client behind a `CacheService` wrapper. TTL per key type: quick-info 5 min, sector data 15 min, analysis results 6 hours. Falls back to in-memory if Redis unavailable.

---

### 31. APNs Webhook for Price Alert Triggers
`routers/alerts.py` triggers alerts by polling on user request. Replace with a background `asyncio` task (registered at app startup in `main.py`) that polls every 5 minutes for all active `PriceTarget` rows, checks current price via `_yf_price`, and fires APNs push directly using `httpx` + Apple's HTTP/2 push API. No more client-side polling.

---

### 32. Add Business Standard + LiveMint RSS Feeds
`news_harvester.py` only sources from Moneycontrol and Economic Times. Add:
- Business Standard: `https://www.business-standard.com/rss/markets-106.rss`
- LiveMint Markets: `https://www.livemint.com/rss/markets`
- NDTV Profit: `https://feeds.feedburner.com/ndtvprofit-latest`
Deduplicate on URL hash before inserting to `NewsArticle`.

---

### 33. Dividend History + Upcoming Dividend Calendar Endpoint
Add `GET /market/dividends/{ticker}` that fetches `yf.Ticker.dividends` and upcoming ex-dividend dates. Return last 8 dividends with yield %, and next ex-date if known. `staleness.py` already has an `is_ex_dividend` flag — wire it to this new data source.

---

### 34. Mutual Fund NAV Lookup via AMFI API
Add `GET /market/mf/{scheme_code}` that fetches NAV data from `https://api.mfapi.in/mf/{scheme_code}`. Return 1-year NAV history, AUM, expense ratio, and category. Lets users track MF holdings alongside equity in their portfolio.

---

### 35. SIP Future Value Calculator Endpoint
Add `POST /portfolio/sip-calculator` with inputs: `monthly_amount`, `expected_return_pct`, `years`, `step_up_pct`. Return year-by-year projection table with invested amount vs corpus in Lakhs/Crores via `format_indian_currency`. Pure math — no external API needed.

---

### 36. NSE Bulk/Block Deal Daily Harvesting
NSE publishes bulk and block deal CSVs daily at `https://www.nseindia.com/api/block-deal`. Add a harvest job in `harvest_worker.py` that fetches this daily, stores in a new `BlockDeal` table, and exposes `GET /market/block-deals/{ticker}` to surface insider-scale buying/selling on `AnalysisScreen`.

---

### 37. FII/DII Net Flow Daily Harvesting
NSE publishes FII/DII daily activity. Add a scraper in `scraper.py` for `https://www.nseindia.com/api/fiidiiTradeReact` and store rolling 30-day FII/DII net flow data. Expose as `GET /market/fii-dii-flow` and include trend (accumulating / distributing) in the AI pipeline's `build_ta_config()`.

---

### 38. Historical Signal Accuracy Tracker
Add a background job that runs weekly: for each `AnalysisHistory` row older than 30 days with a BUY/SELL signal, fetch the current price vs price at signal date and compute actual return. Store as `signal_outcome_pct` on the row. Expose `GET /portfolio/signal-accuracy` returning accuracy % by signal type.

---

### 39. APScheduler for Harvest Jobs
Currently harvest jobs are triggered manually via `run_advisor_harvest.py` or from API routes. Replace with `APScheduler` registered at `main.py` startup:
- 06:00 IST: `harvest_youtube_metadata` + `harvest_portfolio_videos`
- 07:00 IST: `news_harvester.harvest_all`
- 22:00 IST: `portfolio_snapshot.take_snapshot_all_users`

---

### 40. Portfolio P&L Attribution by Sector Endpoint
Add `GET /portfolio/attribution/{user_id}` that groups holdings by NSE sector (from `_yf_fetch_info`), computes each sector's weight and contribution to total P&L, and returns a ranked list. Power the new frontend pie chart (item #2).

---

### 41. Expose Piotroski F-Score in Analysis API Response
`services/piotroski.py` computes a full F-score but the score is never included in the `_normalize_response()` output or the `/analyze` JSON. Add `piotroski_score: int` (0-9) and `piotroski_flags: [str]` to the normalized response schema. iOS client can render a 9-point meter on the Fundamentals tab.

---

### 42. Auto Corporate Action Adjustment for Bonus Issues
`portfolio.py` handles stock splits via `_adjust_for_splits()`. Bonus issues (e.g., 1:1 bonus doubles shares, halves effective buy price) are not handled. Add `_adjust_for_bonus()` using `yf.Ticker.actions` (which includes both splits and dividends). Wire into the same adjustment pipeline as splits.

---

### 43. Per-Endpoint Sliding Window Rate Limiter
`_check_rate_limit()` in `helpers.py` uses a fixed count per time window. Upgrade to a proper sliding window using a `collections.deque` of timestamps per user per endpoint. Limits: `/analyze` 10/hour, `/market/quick-info` 60/minute, `/auth/login` 5/minute. Return `Retry-After` header on 429.

---

### 44. `GET /portfolio/benchmark` — Portfolio vs Nifty CAGR
Add an endpoint that computes user portfolio CAGR since earliest holding purchase date and compares to Nifty 50 CAGR over the same period. Return `{ portfolio_cagr, nifty_cagr, alpha, period_days }`. Uses `yf.download("^NSEI")` for Nifty history (already used in `routers/market.py`).

---

### 45. 30-Day Rolling News Sentiment Chart per Ticker
`sentiment_engine.py` scores articles but the scores are never aggregated over time. Add `GET /market/sentiment-trend/{ticker}?days=30` that queries `NewsArticle` for the ticker, groups scores by day, and returns a 30-point sentiment series. Power a new "Sentiment Trend" sparkline on `AnalysisScreen`.

---

### 46. NSE 52-Week High/Low Breakout Screener Preset
Add a `52w_breakout` preset to the screener in `routers/market.py`. Logic: fetch 52-week high for each screened ticker via `yf.Ticker.info["fiftyTwoWeekHigh"]`, flag stocks within 2% of their 52-week high with positive volume confirmation. No new dependency needed — pure yfinance.

---

### 47. `GET /analysis/batch` — Analyze Multiple Tickers at Once
Add `POST /analysis/batch` accepting `{ tickers: ["RELIANCE", "TCS", "INFY"] }` that returns cached analyses for all tickers in one response (no new AI calls — cache hits only). If a ticker has no cached analysis, return `{ ticker, status: "not_cached" }`. Useful for portfolio-wide freshness check.

---

### 48. Error Telemetry REST Endpoint
`services/error_telemetry.py` collects runtime errors but there's no way to query them from the app. Add `GET /api/v1/admin/error-telemetry` (auth-gated to admin users) that returns the last 100 errors with type, endpoint, timestamp, and stack trace summary. Wire into the dev tools section of `SettingsScreen`.

---

### 49. Structured Request Tracing with Request IDs
Every request through the analysis pipeline (`/analyze` → `orchestrator.py` → `reformat_with_claude()`) loses its identity mid-flight. Add a `X-Request-ID` UUID header (generated in `main.py` middleware) that is threaded through every log line, subprocess queue put, and error telemetry entry. Makes debugging multi-process analysis failures dramatically easier.

---

### 50. `GET /portfolio/stress-test` — Scenario Analysis Endpoint
Add a portfolio stress-test endpoint that simulates three scenarios: Nifty -20% correction, INR depreciates 10% vs USD, crude oil spikes to $120/barrel. For each scenario, estimate portfolio P&L impact using sector beta coefficients (hardcoded from historical data). Return `{ scenario, estimated_impact_pct, most_exposed_holding }` for each. Display on a new "Stress Test" card in `PortfolioScreen`.
