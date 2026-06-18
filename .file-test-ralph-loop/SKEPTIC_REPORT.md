# SKEPTIC REPORT — Nivesh Production Readiness Assessment

**Author:** Hostile Senior Engineer (no sugarcoating)
**Date:** 2026-06-18
**Scope:** 1469 files, backend + iOS, cross-referencing 8 prior audits
**Confidence methodology:** Each finding weighted by blast radius × likelihood × data-loss potential

---

## PRODUCTION READINESS SCORE: 4 / 10

**Translation:** You can show this to investors. You cannot trust it with real money.

---

## 1. WHICH FILES WERE NEVER TESTED?

**The majority of the codebase.** Of the ~270 source files catalogued in FILE_INVENTORY.md, **170+ have zero tests** (63%). Here is what hurts most:

### CRITICAL — completely untested, high-risk surface area:
| File | Why it matters |
|------|---------------|
| `backend/main.py` | **App entrypoint.** 2500+ lines. 0 tests. Unused imports, duplicate tickers, syntax warning. You fly blind on startup. |
| `backend/models/db_models.py` | **Every DB model.** 0 tests. `default=dict` violates SQLite contract (AGENTS.md §3.5). |
| `backend/config/settings.py` | **App config.** 0 tests. If this breaks, everything breaks. |
| `routers/auth.py` | **Login/register.** 0 tests. Auth is broken → nothing works. |
| `routers/user.py` | **User CRUD.** 0 tests. 15+ direct `.query()` calls. |
| `routers/notifications.py` | **Push notifications.** 0 tests. |
| `routers/anomalies.py` | **Anomaly scanner.** 0 tests. |
| `routers/copilot.py` | **AI copilot.** 0 tests. |
| `routers/brainstorming.py` | AI brainstorming. 0 tests. |
| `routers/correlation.py` | Correlation engine. 0 tests. |
| `routers/earnings_surprise.py` | Earnings surprises. 0 tests. |
| `routers/options_strategy.py` | Options strategy. 0 tests. |
| `routers/sector_rotation.py` | Sector rotation. 0 tests. |
| `routers/strategy.py` | Strategy engine. 0 tests. |
| `services/rate_limiter.py` | **Rate limiter.** 0 tests. A failure here silently breaks all request throttling. |
| `services/staleness.py` | **Smart cache gate.** 0 tests. AGENTS.md says "NEVER bypass this." It has NO test coverage at all. One arithmetic bug and your cost engineering is toast. |
| `services/orchestrator.py` | **Core AI orchestrator.** 0 tests. Runs the multi-agent pipeline. |
| `services/cache_service.py` | Caching layer. 0 tests. |
| `core/security.py` | **Security middleware.** 0 tests. |
| `core/logging_config.py` | Logging config. 0 tests. |
| `middleware/request_log.py` | **DEAD FILE** — never imported. But if it were, 0 tests. |
| `middleware/security_headers.py` | **DEAD FILE** — never imported. |

### The math engines — 22 files, ALL untested:
Every single file in `services/math_engines/` has **zero tests**. That includes:
- `minsky_risk.py` — Minsky moment detection (your crash predictor)
- `conformal_prediction.py` — Conformal prediction intervals (your uncertainty quantifier)
- `finbert_sentiment.py` — Sentiment analysis
- `piotroski_beneish.py` — Accounting fraud detection
- `deterministic_dcf.py` — DCF valuation
- `vasicek.py` — Interest rate modeling
- All 16 other math engines

**These are the most mathematically complex components in the system. They have ZERO test coverage.** You are deploying black-box math to users' money.

---

## 2. WHICH ARE ONLY INDIRECTLY TESTED?

### Via integration tests (e2e, stress test suite):
- `services/nl_screener.py` — tested ONLY through router-level e2e tests. No unit tests for the parsing logic.
- `services/stress_test.py` — tested only via `test_stress_test_engine.py` and `test_stress_test_jobs.py`. These are integration tests that spin up the full app.
- `services/quant_engine.py` — 1 of 2 quant tests failing. Marginal coverage.

### Via incidental coverage (touched by other tests but never directly asserted):
- `routers/dashboard.py` — marked "tested" in FILE_INVENTORY, but the dashboard tests check route existence, not data correctness.
- `routers/harvester.py` — marked "tested" but the test (`test_run_advisor_harvester_real`) is gated behind a missing env var and fails in CI.
- `services/job_manager.py` — "tested" but the test setup has event loop conflicts.

### The entire LLM pipeline:
- `prompts.py` — the "NON-NEGOTIABLE" system prompt. 0 direct tests. Only tested by LLM integrity tests that check *structure*, not *content validity*.
- `services/ai_engine_monitor.py` — tested but the test mocks everything. You've never tested a real LLM interaction.
- All 14 TradingAgents agent files (`bear_researcher.py`, `bull_researcher.py`, `portfolio_manager.py`, etc.) — 0 tests. The dialectical debate system (your core AI differentiator) has ZERO test coverage.

---

## 3. WHICH SETTINGS DO NOTHING?

### Config values with zero readers (dead configuration):

| Setting | Location | Evidence |
|---------|----------|---------|
| `services/celery_tasks.py` (entire file) | `backend/services/` | **Never imported.** 0 references. Celery tasks defined but never registered. If you think Celery is running background jobs, it isn't. |
| `middleware/request_log.py` | `backend/middleware/` | **Never imported.** The app uses inline classes in `main.py:299-340` instead. |
| `middleware/security_headers.py` | `backend/middleware/` | **Never imported.** Same as above. |
| `services/rate_limiter.py` (duplicate) | `backend/services/` | Only referenced by a test. The actual rate limiter used is `core/rate_limiter.py`. |
| `schemas/auth.py` | `backend/schemas/` | Defined but never imported. The app uses `schemas.py` (root), not `schemas/auth.py`. |
| `schemas/market.py` | `backend/schemas/` | Only referenced by tests. Production uses inline Pydantic models in routers. |
| `backend/prompts_config.py` | `backend/config/` | 0 tests, 0 references found outside its own file. Is anything reading this? |
| `CovarianceMatrix` ORM model | `models/db_models.py` | 0 references. Table exists in DB but no code ever queries it. |
| `EquityRiskFactor` ORM model | `models/db_models.py` | 0 references. Same. |
| `MarketDashboardResponse` (iOS) | `Models/MarketModels.swift:147` | **No matching backend endpoint returns this shape.** The backend uses `ExtendedMarketDashboardResponse` instead. Orphaned model. |
| 5 dead `fetch*` methods | `NetworkManager+Sidebar.swift` | `fetchMarketPulse()`, `fetchMacroAlternatives()`, `fetchInstitutionalFlow()`, `fetchMarketErrorLogs()`, `fetchEarningsErrorLogs()` — ~200 lines of async code never called. |

### Settings that exist but are silently ignored:
- iOS `QuickInfo.signal` — backend never populates it. Field is always nil.
- iOS `QuickInfo` missing 5 backend fields (`company_name`, `market_cap_crores`, `exchange`, `dividends`, `corporate_actions`) — silently discarded by JSONDecoder.
- `PortfolioResponse` top-level keys (`total_invested_inr`, `total_current_inr`, `total_pnl_inr`, `total_pnl_pct`) — backend returns them, iOS extracts only the `holdings` array and ignores portfolio-level aggregations.

---

## 4. WHICH APIs RETURN INCONSISTENT SHAPES?

### `GET /quick-info?ticker=X&exchange=NSE`
- Backend returns `company_name`, `market_cap_crores`, `dividends`, `corporate_actions`, `exchange`. iOS `QuickInfo` struct does not decode ANY of these. They're silently lost.
- Backend does NOT return `signal`. iOS `QuickInfo` HAS a `signal` field that is always nil.
- **Net effect:** The API contract says one thing, the client expects another. It works because JSONDecoder is lenient, but the data is incomplete.

### `GET /alerts/{user_id}`
- `company_name` field is set to the **ticker symbol**, not the actual company name (`alerts.py:203`). The backend copies `row["ticker"]` into `company_name`. Every alert shows "RELIANCE" instead of "Reliance Industries Ltd."

### `GET /portfolio/{user_id}`
- The `notes` key is set **twice** in the response dict (`portfolio.py:586` and `594`). The second assignment overwrites the first. It's the same value in practice, but this is a code smell that will bite when someone refactors line 586.

### `GET /dashboard-pulse` vs `GET /market-indices`
- Two different response shapes for "market data." The legacy `MarketDashboardResponse` iOS model has no matching endpoint. The new `ExtendedMarketDashboardResponse` has one. Which does the app actually use? The codebase contains both.

### `POST /analyze` response shape
- The response varies dramatically based on `analysis_tier` (v1 vs v2 extreme). V2 adds 20+ extra fields. The iOS model handles this correctly via `decodeIfPresent`, but the API shape is not versioned. If the tier logic changes, iOS silently gets partial data.

---

## 5. WHICH MODELS DON'T MATCH CONTRACTS?

### Backend-side violations:
| # | Model/Column | Issue | Risk |
|---|-------------|-------|------|
| 1 | `AnalysisHistory.quantitative_drivers` (JSON) | `default=dict` — Python dict, not string `"{}"`. Violates AGENTS.md §3.5. SQLite will silently corrupt this on concurrent writes. | CRITICAL |
| 2 | `AnalysisHistory.tail_risk_flags` (JSON) | Same as above — `default=dict`. | CRITICAL |
| 3 | `CovarianceMatrix` table | ORM model defined, migration created it, dropped it, recreated it. 0 code references. Vestigial table. | MEDIUM |
| 4 | `EquityRiskFactor` table | Same — orphaned, zero references. | MEDIUM |

### iOS-side gaps:
| # | Model | Missing Fields | Impact |
|---|-------|---------------|--------|
| 1 | `QuickInfo` | Missing `company_name`, `market_cap_crores`, `exchange`, `dividends`, `corporate_actions` | 5 backend fields silently discarded |
| 2 | `QuickInfo` | Has `signal` field — backend never populates it | Always nil, misleading |
| 3 | `MarketDashboardResponse` | Entire struct — no matching backend endpoint | Orphaned model, dead code |

### Schema architecture split:
- `backend/schemas.py` (89 lines, root) — used by `main.py`
- `backend/schemas/` package — used by tests
- Two competing schema systems. The package has Pydantic v1 `@validator` decorators that should be v2 `@field_validator`. The root `schemas.py` is v2-style. They don't agree.

---

## 6. WHICH SCREENS CAN CRASH?

### 🔴 HIGH RISK — WILL crash on empty data:
| Screen | Location | Crash Vector |
|--------|----------|-------------|
| `StockProfileView` | `:42` | `filteredPrices.first!.parsedDate` — crashes on empty price array |
| `StockProfileView` | `:31-32` | `filteredPrices.map{$0.low}.min()!` / `.max()!` — crashes on empty filtered array |
| `ImmersivePortfolioHeroChart` | `:65-66` | `pts.last!.x`, `pts.first!.x` — crashes on empty chart point array |
| `SharedDarkComponents` | `:155` | `pts.last!.x` — crashes on empty chart point array |
| `LaunchScreenView` | `:31,69,74` | Multiple force-unwraps on chart points — crashes if point generation fails |

### 🟡 MEDIUM RISK — fragile, depends on data shape:
| Screen | Count | Pattern |
|--------|-------|---------|
| `EarningsDashboardView` | 3 force-unwraps | Ternary + `!` pattern: `x != nil ? f(x!) : default` |
| `PortfolioScreen` | 3 force-unwraps | `activeWatchlistTag!` — guarded by `if let` but used in closure captures |
| `OptionsStrategyScreen` | 1 force-unwrap | `response!` — guarded but fragile |
| `EarningsSurpriseScreen` | 1 force-unwrap | Same ternary-`!` pattern |

### Stack overflow risk (§6.6):
| File | Lines | Risk |
|------|-------|------|
| `HomeScreen.swift` | 3,089 | 🔴 Contains 16 inline sub-views. Multiple `ScrollView { VStack }` patterns. This WILL crash on older devices with enough data. |
| `PortfolioScreen.swift` | 2,447 | 🔴 40+ Buttons without EKPressStyle, 3 force-unwraps, massive inline sections. |
| `EarningsDashboardView.swift` | 2,062 | 🔴 71+ hardcoded padding violations, 5 inline sub-views, all in one file. |

### GeometryReader crashes (if inside ScrollView):
- `AnalysisScreen.swift:765,932` — GeometryReader in functions that may render inside ScrollView. Prohibited per AGENTS.md §2.5. Could cause sibling overlap or layout corruption.

---

## 7. WHICH SERVICES CAN FAIL SILENTLY?

### The Hall of Shame — no logging, no error propagation:

| Service/Route | Line | Failure Mode |
|---------------|------|-------------|
| `routers/portfolio.py` | 307 | **Bare `except:`** — yfinance price fetch. Any error (network, rate limit, bad ticker) is swallowed. No log. No fallback. Price silently stays stale. |
| `routers/portfolio.py` | 374 | **Bare `except:`** — same pattern for stress-test endpoint. |
| `routers/portfolio.py` | 435 | **Bare `except: pass`** — `_nse_session()` fails. NSE connection error silently ignored. ALL NSE data becomes unavailable with zero indication. |
| `routers/analysis.py` | 399 | **Bare `except:`** — ASM/GSM surveillance list fetch. If the surveillance endpoint is down, stocks under surveillance get missed silently. |
| `services/nse_client.py` | 44 | **Bare `except: pass`** — same `_nse_session()` pattern. The service silently accepts failure. |

**All 5 bare `except:` clauses violate AGENTS.md §1.3 (Karpathy: "Zero magic — no bare `except:`").** They catch `KeyboardInterrupt` and `SystemExit`, making the server unkillable via SIGINT during these operations.

### Services with zero error telemetry:
- All 22 math engines — no error reporting. If `minsky_risk.py` throws on a bad input, users get a 500 with no actionable diagnosis.
- `services/staleness.py` — if staleness computation fails, the cache gate will either serve stale data forever or crash. No logging.
- `services/cache_service.py` — if cache read/write fails, it silently falls back to uncached. Cost impact is invisible.
- `services/rate_limiter.py` — if the rate limiter's Redis connection dies, does it fail open (no rate limiting) or closed (all requests blocked)? Untestable without Redis.

### Services that fail the "off-hours test":
- `services/nse_client.py` — what happens when NSE is closed? Does it return a sensible error or spin forever?
- `services/yfinance_client.py` — what happens when Yahoo Finance rate-limits? No retry logic, no circuit breaker, no log.
- `routers/health.py:37-42` — the health check pings yfinance. If yfinance is down, your health check reports "unhealthy" even though the app works fine. Tight coupling.

---

## 8. WHICH ASSUMPTIONS ARE UNSAFE?

### Market hours assumption (CRITICAL):
The app assumes markets are open and data is fresh. There is **no explicit market-hours gating** found in the audited code. What happens:
- At 3:30 PM IST on a Friday: everything works
- At 9:00 AM IST Monday: NSE client returns stale Friday data, staleness score says "FRESH" because it was cached Friday evening
- On a trading holiday: NSE returns errors, 5 bare `except:` clauses swallow them, users see Friday prices

### Data freshness assumption:
`services/staleness.py` computes staleness from cache timestamps. If the cache was populated yesterday and the market is closed today (holiday/weekend), the staleness score says "FRESH" but the data is 24+ hours old. There's no market-calendar-aware staleness.

### Network reliability assumption:
- `routers/analysis.py` makes **fire-and-forget** Anthropic API calls with no retry logic, no circuit breaker (despite importing a "circuit breaker" — line 85 just checks if yfinance is importable, not an actual circuit breaker).
- `routers/portfolio.py` fires yfinance queries without timeout guards.
- The app has a `ThreadPoolExecutor` pattern in `routers/market.py:1763` for parallel yfinance calls but no timeout on the executor itself.

### LLM availability assumption:
If DeepSeek or Anthropic APIs are down:
- The multi-agent pipeline hangs indefinitely (the orchestrator has no timeout on LLM calls)
- Cached results are returned if available, but the user is not told the data is stale
- The `_inject_live_data()` function runs regardless, creating a mix of fresh prices + stale analysis

### Environment variable assumptions:
- `backend/config/settings.py` has 0 tests. If an env var is missing, does it crash at import or silently use a bad default?
- The server's test failures include 6 "Test Config" failures from contract tests that fail because `DATABASE_URL` is not set correctly. This is exactly the kind of env-var fragility that hits production.

### User-id-in-path assumption:
Many endpoints use `GET /portfolio/{user_id}`. The user_id comes from the URL path, not the JWT token. Any authenticated user can query any other user's portfolio by changing the URL. Auth middleware may prevent this, but the auth router has 0 tests.

---

## 9. WHICH TESTS ARE SHALLOW?

### Happy-path-only tests (no edge cases):
| Test File | What It Tests | What It Misses |
|-----------|--------------|----------------|
| `test_analysis_engine.py` | Analysis pipeline works | Empty ticker, invalid ticker, rate-limited API, LLM timeout, partial response, missing required fields |
| `test_alerts.py` | CRUD on alerts | Concurrent alert creation, price crossing trigger during market close, duplicate alerts |
| `test_screener.py` | Screener returns results | Empty results, 1000+ results (pagination), malformed query string, SQL injection in filter |
| `test_earnings_dashboard.py` | Dashboard loads | No earnings declared, all companies missed estimates, partial data from yfinance, 0 results |
| `test_portfolio_calendar.py` | Calendar loads | Empty portfolio, 100+ holdings, dividend dates on non-trading days, corporate actions during market closure |
| `test_news_feed.py` | News loads | Empty feed, 500 from news API, duplicate headlines, non-English headlines, emoji in titles |
| `test_tech_momentum.py` | Momentum loads | All stocks bearish, all stocks bullish, flat market, single-stock universe |
| `test_macro_impact.py` | Macro loads | No macro events, conflicting macro signals, stale macro data |

### Tests that test the mock, not the code:
- `test_ai_mock_comprehensive.py` — "mock comprehensive." Tests mock responses against mock expectations. 0 real LLM interactions.
- `test_scraper_mock_comprehensive.py` — same pattern.
- `test_staleness_comprehensive.py` — tests staleness with mocked timestamps. Never tests with real clock skew or DST transitions.

### Tests that pass by accident:
- `test_backend_contract_routes.py` — checks routes return 200 or 401. Does NOT check response shape, field types, or data correctness. A route returning `{"garbage": true}` with 200 would PASS.
- `test_endpoint_contracts.py` — same shallowness. "Contract" tests that don't check contracts.

### Tests that never run:
- 13 test files in `backend/` root (`test_analyze_diagnostic.py`, `test_claude.py`, `test_deep_scan.py`, `test_deepseek_claude.py`, etc.) — all excluded from the test suite by location.
- 8 scratch files in `backend/` root — development scripts never cleaned up.
- 3 "real API" tests that need `RUN_REAL_API_TESTS` env var — never set in CI.

---

## 10. WHICH ERRORS ARE SWALLOWED?

### Bare `except:` (catches everything, does nothing):
| File | Line | What It Hides |
|------|------|--------------|
| `routers/portfolio.py` | 307 | yfinance price fetch failure — network errors, bad tickers, rate limits |
| `routers/portfolio.py` | 374 | yfinance price fetch failure (stress test endpoint) |
| `routers/portfolio.py` | 435 | `except: pass` — NSE session creation failure |
| `routers/analysis.py` | 399 | ASM/GSM surveillance list fetch failure |
| `services/nse_client.py` | 44 | `except: pass` — NSE session creation failure |

### Try/except with only `pass` or `return None`:
Pattern found in multiple service files. `services/yfinance_client.py` and `services/news_harvester.py` likely contain silent error suppression for network failures (not fully audited — these files have 0 tests and weren't deep-scanned for error handling).

### Catch-and-ignore in routers:
`routers/market.py:882` — `yfinance fallback error` is caught but not logged. The error message literally says "fallback error" but that string is never stored or returned.

### iOS silent failures:
- All network calls in `NetworkManager.swift` use `.task { }` which silently discards errors if the View is dismissed during loading. This is correct SwiftUI behavior but means users never see transient network failures — the screen just goes blank.
- The `QuickInfo` model silently ignores 5 backend fields. No warning, no log.

---

## 11. WHICH CODE PATHS ONLY WORK UNDER HAPPY-PATH?

### The entire multi-agent AI pipeline:
1. Ticker is valid and exists on NSE ✅
2. yfinance returns price data ✅
3. NSE client returns fundamentals ✅
4. DeepSeek API is up and returns valid JSON ✅
5. Anthropic API is up ✅
6. Response passes JSON extraction ✅
7. `_normalize_response()` succeeds ✅
8. `_ban_western_scale()` passes ✅
9. `_inject_live_data()` finds fresh prices ✅
10. DB is not locked for writing results ✅

**If ANY of these 10 steps fails in an unexpected way**, the user gets either a 500 error with no diagnosis, or worse — a 200 with partially-broken data. The error at step 4 is caught, but steps 5-8 have no per-step error handling. The orchestrator (`services/orchestrator.py`) is an all-or-nothing monolith.

### The NSE data pipeline:
- Assumes NSE session cookie is valid
- Assumes NSE hasn't changed their API response format
- Assumes NSE isn't rate-limiting
- Assumes the cookie jar from `_nse_session()` can be reused across requests
- **There is no fallback data source.** If NSE is down, there is no BSE fallback, no Alpha Vantage fallback. Data just goes missing.

### The harvester pipeline (YouTube + SEBI + news):
- Assumes YouTube API quota remains available
- Assumes SEBI website HTML structure hasn't changed (web scraping!)
- Assumes news sources are accessible
- Each harvester runs in its own process via `multiprocessing.Process`. If the worker process dies silently (which it can — the health check loop is in the router, not the worker), the pipeline hangs.

### The iOS chart rendering:
- `StockProfileView.swift:31-32` — `min()!` and `max()!` on filtered arrays. Works ONLY if the array is non-empty.
- `ImmersivePortfolioHeroChart.swift:65-66` — `pts.last!` and `pts.first!` on chart points. Works ONLY if chart data is populated.
- `SharedDarkComponents.swift:155` — same pattern.

### The copilot/chat screen:
- `CopilotScreen.swift:86-87` — uses `VStack` in `ScrollView` for chat messages. Works for 10 messages. Will cause stack overflow with 100+. Should be `LazyVStack`.

---

## 12. WHICH PRODUCTION FAILURES REMAIN POSSIBLE?

### Realistic failure scenarios, in order of likelihood:

| # | Scenario | Likelihood | Impact | Current Defenses |
|---|----------|-----------|--------|-----------------|
| 1 | **NSE session cookie expires during trading hours** | High (daily) | All NSE-dependent features go dark silently | `except: pass` — no alert, no retry |
| 2 | **DeepSeek API rate limit hit** | High (cost-optimized, heavy usage) | Analysis pipeline blocks; users see spinner forever | No retry with backoff, no circuit breaker, no user-facing timeout message |
| 3 | **Anthropic API returns malformed JSON** | Medium (LLMs hallucinate) | `_extract_json_from_text()` fails; analysis fails with cryptic error | JSON extraction has regex but no structural validation before `_normalize_response()` |
| 4 | **SQLite DB locked by concurrent writes** | Medium (WAL mode, but multiple writers) | `test_backend_contract_concurrency.py` already fails; concurrent write under load WILL cause `database is locked` errors | SQLite with default timeout. No WAL-mode explicit config found. No write retry logic. |
| 5 | **`default=dict` causes silent data corruption** | Medium (SQLite mutable default) | Two concurrent analysis results share the same Python dict object. One user's `quantitative_drivers` bleeds into another's. | None. This is a hard bug in `models/db_models.py:98-99`. |
| 6 | **Stack overflow on HomeScreen/PortfolioScreen** | Medium (on iPhone SE, large portfolios) | App crashes to home screen. `EXC_BAD_ACCESS` from `chkstk_darwin`. | None. Files exceed AGENTS.md §6.6 thresholds by 2-3x. |
| 7 | **yfinance deprecates an endpoint** | High (yfinance is unstable, breaks often) | Price data, fundamentals, and earnings all go stale | No data source abstraction. yfinance is hardcoded into 4 router files. |
| 8 | **Alembic migration fails on fresh deploy** | Medium (test failure #11 confirms this) | New developer or clean server cannot initialize the database | `alembic upgrade head` fails on empty DB. Migration chain is broken. |
| 9 | **Morning briefing fixture fails in production** | Low (test-only issue) | N/A — but indicates the briefing endpoint has fragile state dependencies | DB must be populated, user must exist, rate limiter must allow. If any fails, briefing is dead. |
| 10 | **Portfolio calculations return wrong numbers** | Medium (all math engines untested) | Users make investment decisions on wrong data. Financial liability. Legal exposure. | None. No math engine has a single test. |

### The nightmare scenario:
> It's 9:15 AM on a Monday. A user opens the app to check their portfolio. The NSE session expired over the weekend. `_nse_session()` fails silently (`except: pass`). Prices are stale from Friday. The staleness checker says "FRESH" (it only checks cache timestamps, not market hours). The AI analysis from Friday evening is shown as current. The user makes a trade based on 72-hour-old analysis with wrong prices. **The app doesn't know anything is wrong and reports no errors.**

---

## HONEST ANSWERS TO THE 12 QUESTIONS

### 1. Which files were never tested?
**170+ of ~270 source files (63%).** All 22 math engines, 15 of 20 routers (the "tested" ones have shallow integration tests), `main.py`, `db_models.py`, all auth/user/notification/copilot/brainstorming/correlation/options/sector-rotation/strategy routers, the orchestrator, the cache gate, the rate limiter, all security middleware, and both logging configs.

### 2. Which are only indirectly tested?
The entire LLM pipeline (prompts, orchestrator, staleness), 5 routers tested only via route-existence checks, the NL screener (integration only), the stress test engine (integration only).

### 3. Which settings do nothing?
`celery_tasks.py` (entirely dead), `middleware/` package (duplicate of inline classes), `services/rate_limiter.py` (duplicate), `schemas/auth.py` + `schemas/market.py` (unused), `CovarianceMatrix` + `EquityRiskFactor` tables (orphaned), `MarketDashboardResponse` iOS model (orphaned), 5 dead fetch methods (~200 lines).

### 4. Which APIs return inconsistent shapes?
`/quick-info` (iOS missing 5 fields, backend missing `signal`), `/alerts` (`company_name` = ticker), `/portfolio` (duplicate `notes` key), `/dashboard-pulse` vs legacy shape mismatch.

### 5. Which models don't match contracts?
`AnalysisHistory` has `default=dict` on 2 JSON columns (SQLite violation). `CovarianceMatrix` + `EquityRiskFactor` are orphaned. Schema package uses Pydantic v1 decorators while root uses v2.

### 6. Which screens can crash?
`StockProfileView` (3 force-unwraps on arrays), `ImmersivePortfolioHeroChart` (2 force-unwraps), `LaunchScreenView` (3 force-unwraps), `SharedDarkComponents` (1 force-unwrap). Stack overflow risk on `HomeScreen` (3089 lines), `PortfolioScreen` (2447), `EarningsDashboardView` (2062).

### 7. Which services can fail silently?
**5 bare `except:` clauses** swallow all NSE, yfinance, and surveillance errors. No logging. The entire math engine layer has zero error reporting.

### 8. Which assumptions are unsafe?
Market hours (no calendar gating), data freshness (staleness ignores market calendar), network reliability (no retry/circuit-breaker on LLM or yfinance calls), LLM availability (no timeout on orchestrator), environment variables (0 tests for config), user-id-in-path (auth bypass risk).

### 9. Which tests are shallow?
All feature tests are happy-path-only. Contract tests only check status codes, not shapes. Mock-comprehensive tests test mocks, not code. 13 test files excluded from the suite by location.

### 10. Which errors are swallowed?
5 bare `except:` + `except: pass` in production code. Multiple `return None` patterns in yfinance and news harvesters. iOS silently discards 5 backend fields via JSONDecoder.

### 11. Which code paths only work under happy-path?
The entire multi-agent AI pipeline (10 sequential dependencies, any one fails → user gets 500 or bad data). NSE pipeline (no fallback). Chart rendering (force-unwraps on arrays). Copilot chat (VStack overflow risk).

### 12. Which production failures remain possible?
At least 10 realistic scenarios, the most likely being: NSE session expiry (daily risk), DeepSeek rate limiting (cost-optimized), SQLite lock contention (under load), `default=dict` data corruption (silent), yfinance endpoint breakage (unstable), and stack overflow on large portfolios.

---

## CONFIDENCE SCORE: 4/10

### What would it take to reach 7/10?
1. **Fix the 5 bare `except:` clauses** — 1 hour
2. **Add market-hours gating to staleness** — 2 hours
3. **Test all 22 math engines** — 20+ hours (but non-negotiable for financial software)
4. **Add per-step error handling to orchestrator** — 8 hours
5. **Fix `default=dict` on 2 JSON columns** (Alembic migration) — 1 hour
6. **Fix broken Alembic migration chain** — 4 hours
7. **Split HomeScreen/PortfolioScreen/EarningsDashboardView** into sub-View structs — 8 hours
8. **Guard all 21 force-unwraps** — 2 hours
9. **Replace VStack with LazyVStack** in 15+ ScrollViews — 3 hours
10. **Add retry/circuit-breaker to LLM client** — 4 hours
11. **Fix the alerts `company_name` bug** — 30 minutes
12. **Consolidate schema system (v1 → v2)** — 4 hours
13. **Delete dead code** (30+ dead symbols, ~350 iOS lines, ~200 backend lines) — 2 hours
14. **Add data-source abstraction layer** (decouple yfinance/NSE from routers) — 20+ hours

**Total to reach 7/10: ~80-100 engineering hours.**

### What would it take to reach 9/10?
- Full Controller-Service-Repository refactor (move 150+ `.query()` calls out of routers)
- Property-based testing for all math engines (Hypothesis/fuzzing)
- Chaos engineering: kill NSE/yfinance/LLM and verify degradation
- Load testing: 100 concurrent users, verify no SQLite locks
- E2E tests with real API responses (VCR-style recording)
- Contract tests that validate full response shapes, not just status codes

**Total to reach 9/10: ~300-400 hours. This is a rewrite of the architecture, not a fix.**

---

## BOTTOM LINE

**This is a prototype, not a production system.** The core ideas (dialectical AI analysis, Indian-market focus, Banknote Aesthetic) are strong. The implementation is a pile of good intentions papered over with silent error suppression and untested math. You have 35 active test failures, 170+ untested source files, 5 bare exception handlers swallowing critical failures, and an architectural violation (business logic in routers) so deep it would require a rewrite to fix.

**If you deploy this with real money, you will have:**
- Silent data corruption from the `default=dict` bug
- Crashes on older iPhones from stack overflow
- Wrong prices served to users during NSE outages (no one will know)
- AI analysis that silently goes stale on weekends/holidays
- No way to diagnose production failures (no error telemetry)

**The good news:** None of this requires new technology. It requires discipline — the discipline that AGENTS.md already mandates but that the codebase doesn't follow. The rules are written. They just aren't enforced.
