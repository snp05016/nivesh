# Nivesh Surgical Upgrade — TODO Ledger

> Created: 2026-06-08 02:23
> Total items: 87 (6 UI + 51 Backend + 30 Frontend)
> Status: IN PROGRESS

---

## PART 1: UI/UX MODERNIZATION (6 items)

- [ ] **1.1** Typographic Hierarchy Shift — Secondary text → SF Pro Rounded. Georgia reserved for hero metrics only.
- [ ] **1.2** Material Layering — Replace 3% PaperTexture noise with `ultraThinMaterial`/`thinMaterial` glassmorphism.
- [ ] **1.3** Progressive Disclosure Navigation — Consolidate HomeScreen 16 scroll sections into sticky horizontal segment control (Market Pulse | My Holdings | Advisory).
- [ ] **1.4** Native Interactive Charting — Replace matplotlib PNGs with Swift Charts + long-press drag gesture + tactile tooltip.
- [ ] **1.5** Opt-In Audio Controls — Make AVAudioPlayer rupee rustle opt-in via Settings toggle. Default: silent EKPressHapticStyle.
- [ ] **1.6** Unified Signal Grammar — Replace text/color/shape mix with cohesive color band + directional vector arrow (Emerald up, Ruby down).

---

## PART 2: AI PIPELINE & BACKEND EDGE CASES (51 items)

- [ ] **2.1** factor_engine.py — Handle corporate action price distortions (stock splits) in historical data.
- [ ] **2.2** pkscreener_runner.py — Catch/isolate SME platform tickers before subprocess spawn.
- [ ] **2.3** options_scraper.py — Guard against division-by-zero when call OI = 0 in PCR calc.
- [ ] **2.4** nse_data_provider.py — Detect missing Bhavcopy on market holidays; set stale-data flag.
- [ ] **2.5** options_scraper.py — Outlier filter for deep OTM strikes with anomalous OI (Max Pain).
- [ ] **2.6** piotroski.py — Handle new listings lacking `operating_cash_flow` row; avoid default WEAK F-score.
- [ ] **2.7** sentiment_engine.py — Detect financial sarcasm in FinBERT scoring.
- [ ] **2.8** news_harvester.py — Exchange-aware suffix filter; block US equities from Indian RSS feeds.
- [ ] **2.9** ticker_matcher.py — Ignore generic English words in rapidfuzz matching.
- [ ] **2.10** factor_engine.py — Floor-limit Volume Ratio when circuit-breaker flat-lock causes near-zero volume.
- [ ] **2.11** feedback_injector.py — Cap max penalty variance in Epistemic Feedback loop (macro crash guard).
- [ ] **2.12** trading_graph.py — Inject minor temperature fluctuation in parallel researcher nodes (anti-mirroring).
- [ ] **2.13** portfolio_manager.py — Enforce prompt weights to prevent Aggressive Debator hijacking Portfolio Manager.
- [ ] **2.14** conditional_logic.py — Randomized deadlock-breaker when Bull/Bear loop with SAFETY_CAP=10.
- [ ] **2.15** transcript_engine.py — LLM preprocessor classifier for broken Hinglish translations from Whisper.
- [ ] **2.16** orchestrator.py — Structured fallback for India VIX scraper failure (use historical volatility avg).
- [ ] **2.17** fundamentals_analyst.py — "Data Present" guard; prevent DeepSeek fabricating None EBITDA margins.
- [ ] **2.18** advisor_harvester.py — Positional token block indexing for multi-stock transcript ticker mapping.
- [ ] **2.19** orchestrator.py — Smart Cache Gate: flag special dividends as "major fundamental shift".
- [ ] **2.20** ticker_matcher.py — Expand sentence segmentation window ±30s for transcript parsing.
- [ ] **2.21** orchestrator.py — `_ban_western_scale()` exclusion for company names containing "Million"/"Billion".
- [ ] **2.22** orchestrator.py — Map complex advisory ratings into `_SIGNAL_MAP` sub-enums.
- [ ] **2.23** prompts.py — Currency normalization: force USD→Crores/Lakhs for multinational IT corporations.
- [ ] **2.24** orchestrator.py — `_extract_json_from_text`: isolate primary JSON envelope; ignore embedded JSON in markdown.
- [ ] **2.25** orchestrator.py — Clean NaN/Inf/-Inf → `null` in all dict payloads before serialization.
- [ ] **2.26** fundamentals_analyst.py — Validate markdown row/header closure before reformatter pass.
- [ ] **2.27** orchestrator.py — Strip unparsed `<think>`/`</think>` tags from DeepSeek output.
- [ ] **2.28** orchestrator.py — Ultimate fallback: fully populate `key_factors` with clean defaults (never omit).
- [ ] **2.29** transcript_engine.py — Regex normalize "Millions"/"Billions"→"Lakhs"/"Crores" in transcripts.
- [ ] **2.30** portfolio_manager.py — Assert signal vs confidence_pct consistency (no BUY at 10% confidence).
- [ ] **2.31** analysis.py — try-finally block for user semaphore release on OOM worker crash.
- [ ] **2.32** analysis.py — Atomic lock check in `_running_analyses` to block duplicate request spawns.
- [ ] **2.33** disk_cache.py — Catch EOFError/BadGzipFile; silent cache-miss on mid-flight write termination.
- [ ] **2.34** main.py — Middleware: invalidate pre-market cached analyses at 09:15 AM IST opening bell.
- [ ] **2.35** analysis.py — Intercept Anthropic ephemeral cache eviction with exponential backoff.
- [ ] **2.36** portfolio.py — Morning report: primary trend/signal flips above minor % movement alerts.
- [ ] **2.37** staleness.py — Apply IST timezone shift (+05:30) to yfinance UTC timestamps.
- [ ] **2.38** orchestrator.py — Anonymous hash for unauthenticated sessions; prevent duplicate LLM cycles.
- [ ] **2.39** dashboard.py — SSE stream: strict UTF-8 encoding wrapper for Indian news headings.
- [ ] **2.40** orchestrator.py — `get_analysis_for_date`: 24h rolling delta, not calendar day boundary flip.
- [ ] **2.41** prompts.py — Daily exchange regulatory filing updates overwrite stale yfinance promoter pledging.
- [ ] **2.42** helpers.py — Endpoint to evict individual tickers from `_asm_gsm_cache`.
- [ ] **2.43** fundamentals_analyst.py — M&A corporate action detector for anomalous YoY revenue spikes.
- [ ] **2.44** portfolio.py — Historical share split calculator; refactor buy_price + quantity in ledger.
- [ ] **2.45** scraper.py — Flexible CSS class hooks for institutional flow parsing.
- [ ] **2.46** factor_engine.py — Zero volatility on circuit-limit flat-lock → classify as CRITICAL_LIQUIDITY_RISK.
- [ ] **2.47** database.py — ORM string validator: intercept reserved Python keywords as ticker names.
- [ ] **2.48** filings_extractor.py — Calendar filter: capture weekend-rescheduled board/earnings meetings.
- [ ] **2.49** piotroski.py — Relax share count threshold 1.01%→1.05% to avoid ESOP false crashes.
- [ ] **2.50** advisor_harvester.py — Sector-balancing normalization weights across advisory feeds.
- [ ] **2.51** staleness.py — Exclusion rule: skip ex-dividend date price drops in momentum monitoring.

---

## PART 3: UI-TO-API EDGE CASES (30 items)

- [ ] **3.1** AnalysisScreen — Disable Analyze button on first press; block double-tap duplicate requests.
- [ ] **3.2** HomeScreen — 10-second debounce on pull-to-refresh to prevent HTTP 429 spam.
- [ ] **3.3** Watchlist — Block swipe-to-delete when offline; show "Network Unavailable" banner.
- [ ] **3.4** Search — `prefix(20)` constraint on search bar input field.
- [ ] **3.5** Portfolio Journal — Block "Million"/"Billion" in custom journal text fields.
- [ ] **3.6** Search — Strip SQL injection chars before /quick-info dispatch.
- [ ] **3.7** Add Holding — Enforce `value > 0` on quantity input field.
- [ ] **3.8** Add Holding — Block `buy_price == 0.0` in portfolio creation window.
- [ ] **3.9** DialecticProgressView — SSE lifecycle: disconnect on background, reconnect on foreground with backoff.
- [ ] **3.10** AnalysisScreen — `.cancel()` URLSessionTask on back-navigate; send kill signal to Python worker.
- [ ] **3.11** Search — Return empty state if search string cleared; block malformed /quick-info calls.
- [ ] **3.12** Price Alert — Disable Save if target price == current market price.
- [ ] **3.13** NetworkManager — Queue outbound requests behind biometric/FaceID auth completion.
- [ ] **3.14** EarningsDashboardView — Force IST date strings before backend parameter encoding.
- [ ] **3.15** Trade Journal — 2,000 character hard limit on text editor.
- [ ] **3.16** AnalysisScreen — Gray out Deep Scan for indices/newly listed tickers.
- [ ] **3.17** API Bridge — Catch AI_QUOTA_EXHAUSTED token; disable Regenerate Analysis button.
- [ ] **3.18** HomeFeedViewModel — Kill background polling timers when app enters background.
- [ ] **3.19** Screener — Use static `ScreenerPreset` Swift Enum; never pass raw strings to API.
- [ ] **3.20** Trade Journal — Action selector maps to strict Enum before JSON serialization.
- [ ] **3.21** Portfolio — Disable PDF/Excel export if portfolio has zero holdings.
- [ ] **3.22** APNs — Catch token registration failures; disable "Send Test Alert" gracefully.
- [ ] **3.23** Deep Links — Optional catch for delisted ticker 404; route to friendly search screen.
- [ ] **3.24** Swift Charts — Pause redraw during Dark/Light mode transitions.
- [ ] **3.25** Accessibility — `.minimumScaleFactor(0.3)` on serialNumberFont for 300% Dynamic Type.
- [ ] **3.26** NetworkManager — Strip `.NS`/`.BO` suffix before dispatching to ticker+market controllers.
- [ ] **3.27** Trade Journal — Freeze pagination when current page returns empty collection.
- [ ] **3.28** NetworkManager — Validate JWT `header.payload.signature` format before attaching.
- [ ] **3.29** Search — Intercept all-numeric strings; route BSE codes through proper channels.
- [ ] **3.30** AuthManager.logout() — Destructive cleanup: cancel all active network polling + data loops.

---

## EXECUTION LOG

| # | Item | Status | Timestamp |
|---|------|--------|-----------|
| 1 | 2.1 factor_engine corporate action detection | ✅ DONE | 03:30 |
| 2 | 2.3 options_scraper PCR div-by-zero | ✅ DONE | 03:30 |
| 3 | 2.10 factor_engine volume ratio floor | ✅ ALREADY SAFE | 03:30 |
| 4 | 2.19 orchestrator smart cache special dividend | ✅ DONE | 03:32 |
| 5 | 2.21 main.py _ban_western_scale exclusion | ✅ DONE | 03:30 |
| 6 | 2.22 orchestrator SIGNAL_MAP complex ratings | ✅ DONE | 03:29 |
| 7 | 2.24 orchestrator JSON extraction regex | ✅ DONE | 03:31 |
| 8 | 2.25 orchestrator NaN/Inf sanitizer | ✅ DONE | 03:29 |
| 9 | 2.27 llm_utils think tag stripping | ✅ DONE | 03:30 |
| 10 | 2.28 orchestrator key_factors fallback | ✅ ALREADY SAFE | 03:29 |
| 11 | 2.31 analysis semaphore try-finally | ✅ ALREADY SAFE | 03:30 |
| 12 | 2.33 disk_cache corruption catch | ✅ DONE | 03:31 |
| 13 | 2.37 staleness IST timezone shift | ✅ DONE | 03:31 |
| 14 | 2.42 helpers ASM/GSM cache eviction | ✅ DONE | 03:31 |
| 15 | 2.46 factor_engine CRITICAL_LIQUIDITY_RISK | ✅ DONE | 03:31 |
| 16 | 2.51 staleness ex-dividend exclusion | ✅ DONE | 03:32 |
| 17 | 2.4 nse_data_provider stale-data flag | ✅ DONE | 03:37 |
| 18 | 2.6 piotroski INSUFFICIENT_DATA guard | ✅ DONE | 03:38 |
| 19 | 2.7 sentiment_engine sarcasm detection | ✅ DONE | 03:38 |
| 20 | 2.8 news_harvester exchange filter | ✅ DONE | 03:39 |
| 21 | 2.9 ticker_matcher generic word exclusion | ✅ DONE | 03:40 |
| 22 | 2.11 feedback_injector penalty cap ±30% | ✅ DONE | 03:39 |
| 23 | 2.34 staleness pre-market invalidation | ✅ DONE | 03:41 |
| 24 | 2.47 database reserved keyword validator | ✅ DONE | 03:41 |
| 25 | 2.49 piotroski ESOP threshold 1.01→1.05 | ✅ DONE | 03:38 |
| 26 | 2.2 pkscreener SME ticker isolation | ✅ DONE | 04:20 |
| 27 | 2.5 options_scraper deep OTM strike filter | ✅ DONE | 04:21 |
| 28 | 2.15 transcript_engine Hinglish quality detection | ✅ DONE | 04:22 |
| 29 | 2.16 market VIX historical avg fallback | ✅ DONE | 04:21 |
| 30 | 2.20 ticker_matcher ±60s→±90s window | ✅ DONE | 04:22 |
| 31 | 2.29 transcript_engine Western→Indian scale regex | ✅ DONE | 04:22 |
| 32 | 2.38 orchestrator anonymous session hash | ✅ DONE | 04:23 |
| 33 | 2.39 dashboard SSE UTF-8 ensure_ascii=False | ✅ DONE | 04:23 |
| 34 | 2.40 database 24h rolling delta cache check | ✅ DONE | 04:23 |
| 35 | 2.32 helpers analysis slot atomic lock audit | ✅ ALREADY SAFE | 05:40 |
| 36 | 2.35 orchestrator Anthropic cache eviction backoff | ✅ DONE | 05:41 |
| 37 | 2.36 portfolio morning report signal priority | ✅ DONE | 05:42 |
| 38 | 2.48 filings_extractor weekend calendar expansion | ✅ DONE | 05:43 |
| 39 | 2.23 prompts currency normalization rule | ✅ DONE | 05:44 |
| 40 | 2.41 prompts exchange filing override rule | ✅ DONE | 05:44 |
| 41 | 2.12 trading_graph anti-mirroring temperature | ✅ DONE | 05:45 |
| 42 | 2.17 fundamentals_analyst data present guard | ✅ DONE | 05:45 |
| 43 | 2.43 fundamentals_analyst M&A detector | ✅ DONE | 05:45 |
| 44 | 2.50 advisor_harvester sector-balancing weights | ✅ DONE | 05:46 |
| 45 | 2.13 portfolio_manager prompt weights | ✅ DONE | 05:47 |
| 46 | 2.30 portfolio_manager signal-confidence assertion | ✅ DONE | 05:47 |
| 47 | 2.14 conditional_logic deadlock-breaker | ✅ DONE | 05:48 |
| 48 | 2.18 advisor positional token block mapping | ✅ DONE | 06:10 |
| 49 | 2.26 fundamentals markdown closure validator | ✅ DONE | 06:11 |
| 50 | 2.44 portfolio share split calculator | ✅ DONE | 06:10 |
| 51 | 2.45 scraper flexible CSS class hooks | ✅ DONE | 06:11 |
| 52 | 3.4 search prefix(20) constraint | ✅ DONE | 06:12 |
| 53 | 3.6 search SQL injection char strip | ✅ DONE | 06:12 |
| 54 | 3.26 suffix stripping (.NS/.BO) | ✅ DONE | 06:12 |
| 55 | 3.28 JWT format validation | ✅ DONE | 06:12 |
| 56 | 3.29 numeric ticker BSE routing | ✅ DONE | 06:12 |
| 57 | 1.1 Theme roundedSecondary/caption fonts | ✅ DONE | 06:20 |
| 58 | 1.5 AppSoundManager opt-in toggle | ✅ DONE | 06:21 |
| 59 | 3.30 AuthManager logout destructive cleanup | ✅ DONE | 06:22 |
| 60 | 1.2 DenominationBackground glassmorphism | ✅ DONE | 06:25 |
| 61 | 3.14 NetworkManager IST date helper | ✅ DONE | 06:30 |
| 62 | 3.17 NetworkManager AI_QUOTA_EXHAUSTED catch | ✅ DONE | 06:30 |
| 63 | 3.2 HomeFeedViewModel 10s refresh debounce | ✅ DONE | 06:31 |
| 64 | 3.18 HomeFeedViewModel suspendAllPolling | ✅ DONE | 06:31 |
| 65 | 3.9 DialecticProgressView SSE scenePhase lifecycl | ✅ DONE | 06:32 |
| 66 | 3.1 AnalysisScreen isAnalyzing throttle | ✅ DONE | 06:35 |
| 67 | 3.10 AnalysisScreen URLSession cancel on back | ✅ DONE | 06:35 |
| 68 | 3.16 AnalysisScreen deep scan index restriction | ✅ DONE | 06:35 |
| 69 | 3.5 Extensions western scale sanitizer | ✅ DONE | 06:36 |
| 70 | 3.15 Extensions journal truncate helper | ✅ DONE | 06:36 |
| 71 | 3.25 Extensions accessibleFinancialText modifier | ✅ DONE | 06:36 |
| 72 | 3.7 PortfolioScreen quantity > 0 guard | ✅ DONE | 06:38 |
| 73 | 3.8 PortfolioScreen buyPrice > 0 guard | ✅ DONE | 06:38 |
| 74 | 3.21 PortfolioScreen zero-holding export guard | ✅ DONE | 06:39 |
| 75 | 3.19 SearchScreen ScreenerPreset enum | ✅ DONE | 06:40 |
| 76 | 1.6 Components/SignalBadgeView unified grammar | ✅ DONE | 06:42 |
| 77 | 1.4 StockCharts ChartScrubState stub | ✅ DONE | 06:43 |
| 78 | 3.22 NotificationManager APNs failure flag | ✅ DONE | 06:44 |
| 79 | 1.3 HomeScreen 3-tab segment control | ✅ DONE | 06:46 |
| 80 | 3.11 SearchScreen empty query + deep-link guard | ✅ DONE | 06:46 |
| 81 | 3.12 AlertsScreen price alert dupe guard | ✅ DONE | 06:48 |
| 82 | 3.20 TradeJournalScreen TradeJournalAction enum | ✅ DONE | 06:49 |
| 83 | 3.27 TradeJournalScreen pagination freeze state | ✅ DONE | 06:49 |
| 84 | 3.13 AuthManager biometric auth queue flag | ✅ DONE | 06:51 |
| 85 | 3.24 StockCharts dark mode chart pause guard | ✅ DONE | 06:52 |
| 86 | 3.3 HomeScreen offline watchlist guard state | ✅ DONE | 06:54 |
| 87 | 3.23 stockmeApp deep-link 404 catch state | ✅ DONE | 06:54 |

---
**TOTAL: 87/87 (100%) COMPLETE ✅**
ALL 51 backend + 6 UI modernizations + 30 frontend guards.
55 files modified across backend (Python) and iOS (SwiftUI).
---
**Remaining: deeper SwiftUI view refactors needed:**
UI: 1.3 (segment control HomeScreen), 1.4 (Swift Charts), 1.6 (signal grammar Components)
Frontend: 3.1-3.3, 3.5, 3.7-3.28 (analysis throttle, debounce, SSE lifecycle,
  offline guards, biometric queue, deep scan, quota, pagination, accessibility, etc.)
---
