# Nivesh Architecture Map

> Last verified: 2026-06-15 from local source files. This map is intentionally concise and points to source locations instead of restating every implementation detail.

## Top-Level Directories

| Path | Purpose |
|---|---|
| `backend/` | FastAPI backend, routers, services, models, tests, scripts, and local data |
| `ios/StockApp/stockme/stockme/` | SwiftUI iOS app source |
| `CodebaseInformation/` | Human-readable orientation docs |
| `graphify-out/` | Local knowledge graph output |
| `prompts/` | Planning/checklist prompt docs |
| `scripts/` | Local helper scripts |
| `nivesh-harvester/` | Harvester-related code area |

## Backend Map

| Path | Current role |
|---|---|
| `backend/main.py` | FastAPI app creation, middleware, router inclusion, health/dashboard endpoints |
| `backend/routers/analysis.py` | Analysis job lifecycle, batch analysis, daily actions, home feed, technical signals |
| `backend/routers/portfolio.py` | Holdings, portfolio history/charts, risk, red flags, exports, trade journal, macro impact |
| `backend/routers/market.py` | Search, stock profile, market dashboards, earnings, ideas, options chain, indices |
| `backend/routers/copilot.py` | Copilot chat API |
| `backend/routers/nl_screener.py` | Natural language screener endpoint |
| `backend/routers/stress_test.py` | Portfolio stress test endpoint |
| `backend/routers/sector_rotation.py` | Sector rotation endpoint, included under `/api/v1` prefix |
| `backend/routers/correlation.py` | Portfolio correlation endpoint |
| `backend/routers/options_strategy.py` | Options payoff endpoint, included under `/api/v1` prefix |
| `backend/services/orchestrator.py` | Main AI analysis orchestration and normalization |
| `backend/services/llm_utils.py` | Canonical LLM model constants and DeepSeek client helper |
| `backend/services/nse_data_provider.py` | NSE/yfinance data provider with `jugaad-data` support |
| `backend/services/cache_service.py` | Redis-backed cache with fallback behavior |
| `backend/services/*_engine.py` | Deterministic analysis engines and quantitative helpers |
| `backend/database.py` | SQLAlchemy engine/session setup and ORM models |

## iOS Map

| Path | Current role |
|---|---|
| `ContentView.swift` | Auth-gated root view, 5-tab `TabView`, `MarketsView`, `MarketSection` enum |
| `NetworkManager.swift` | Main API client for auth, analysis, portfolio, market data, alerts, trade journal, exports |
| `NetworkManager+Sidebar.swift` | Market sidebar/dashboard API calls |
| `HomeFeedService.swift` | Home feed and valuation history service |
| `AnalysisEngineManager.swift` | Analysis job/history coordination |
| `Views/HomeScreen.swift` | Main dashboard |
| `Views/PortfolioScreen.swift` | Portfolio, allocation, trade journal, charts |
| `Views/AnalysisScreen.swift` and `Views/Analysis/` | AI analysis screen and extracted sections |
| `Views/CopilotScreen.swift` | Global Copilot overlay and chat surface |
| `Views/ExpertNetworkView.swift` | Ideas tab |
| `Views/NewsMultimediaView.swift` | News tab |
| `Utilities/Theme.swift` | Design tokens and semantic colors/fonts |
| `Utilities/IndianFormatter.swift` | Indian number/currency formatting |
| `Components/` | Shared UI components |

## Primary Execution Flows

### Analysis Job

1. iOS calls `NetworkManager.analyze` or `startAnalysisJob` at `POST /analyze`.
2. `routers/analysis.py::analyze_endpoint` starts or returns a job.
3. iOS polls `GET /analyze/job/{job_id}` and `GET /analyze/active`.
4. Backend services call `services/orchestrator.py::analyze` and related helpers.
5. Results are saved and decoded into Swift `StockAnalysis` models.

### Markets Hub

1. `ContentView.swift` defines `MarketSection` cases.
2. `MarketsView` maps each section to a concrete SwiftUI screen.
3. Screens call `NetworkManager` or `NetworkManager+Sidebar`.
4. FastAPI routers serve `/api/v1/market/*`, earnings, sector rotation, stress test, screener, correlation, and options endpoints.

### Portfolio

1. `PortfolioScreen` and related view models call `NetworkManager` portfolio methods.
2. `routers/portfolio.py` serves holdings, charts, risk analysis, red flags, macro impact, trade journal, and exports.
3. Several expensive summary/export endpoints use LLMs; see `LLM_CREDITS_USAGE.md`.

## Known Architectural Gaps

- Some routers still contain DB queries and substantial logic despite the target Controller-Service-Repository pattern.
- API path conventions are mixed: some routes are unprefixed (`/analyze`, `/portfolio/{user_id}`), while newer routes use `/api/v1/...`.
- Some feature docs and prompt docs may refer to planned endpoints that are not mounted in `backend/main.py`.
