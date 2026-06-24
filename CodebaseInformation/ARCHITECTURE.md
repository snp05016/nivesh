# Nivesh — System Architecture

> Document version: 1.0 (June 2026) | Source of truth: actual codebase

---

## Project Overview

**Nivesh** (Hindi: निवेश — *Investment*) is an AI-powered Indian equity analysis platform for the retail investor. It provides institutional-grade stock analysis using a multi-agent LangGraph debate pipeline, a deterministic quantitative pre-pipeline, 14-scenario stress testing, and a premium SwiftUI mobile app with a Banknote Aesthetic design system.

All monetary values use the Indian numbering system: Lakhs and Crores. "Million/Billion/Trillion" are forbidden throughout the codebase.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **iOS App** | SwiftUI · iOS 17+ · Swift · Charts framework · WidgetKit · EventKit · SFSpeechRecognizer |
| **Backend** | Python 3.11 · FastAPI 0.115 · Uvicorn (4–6 workers) |
| **Database** | SQLite (dev) / PostgreSQL 18 + pgvector (prod) · SQLAlchemy ORM · Alembic migrations |
| **ML Engine** | Python 3.10 · Docker microservice · LightGBM · TRA (Temporal Routing Adaptor) · FastAPI |
| **AI Models** | DeepSeek Chat (Tier 1) · Claude Haiku 4.5 (Tier 2) · Claude Sonnet (Tier 3 reformatter) |
| **LLM Orchestration** | LangGraph · LangChain Anthropic |
| **Async/Task Queue** | APScheduler · Celery (Alpha158 nightly) |
| **RAG** | ChromaDB vector store · MiniLM embeddings · pgvector (prod) |
| **Data Sources** | jugaad-data (NSE primary) · yfinance (fallback) · NSE direct APIs · SEBI filings |
| **Sentiment** | FinBERT (HuggingFace, lazy-loaded) |
| **Deployment** | Fedora server · Docker (ml-engine) · Uvicorn · systemd |

---

## System Architecture Diagram

```
+-----------------------------------------------------+
|                  iOS SwiftUI App                    |
|  Banknote Aesthetic  .  7 Theme Presets             |
|  WidgetKit  .  Face ID  .  Push Notifications       |
+---------------------.-------------------------------+
                       | HTTPS / REST
                       v
+-----------------------------------------------------+
|           FastAPI Backend  (port 8000)              |
|  Auth . Routing . Rate Limit . CORS . Telemetry     |
|  CorrelationIDMiddleware . SecurityHeaders           |
+----.----------.----------.----------.--------------+
    |          |          |          |
    v          v          v          v
+--------+ +--------+ +--------+ +-----------------+
|Routers | |Service | |Repos   | |  ML Engine      |
|21 APIs | |Layer   | | + DB   | |  (port 8001)    |
|        | |~60 svc | |        | |  LightGBM / TRA |
+--------+ +---.----+ +---.----+ +-----------------+
               |          |               |
               v          v               v
+--------------------+ +--------------------------+
|  AI Pipeline       | |  PostgreSQL 18           |
|  LangGraph . 8     | |  + pgvector RAG          |
|  agents . DeepSeek | |  + 25 ORM tables         |
|  Haiku . Sonnet    | |  + Alembic migrations    |
+--------------------+ +--------------------------+
               |
               v
+-----------------------------------------------------+
|         Data Harvesting Layer                      |
|  YouTube . SEBI . News . NSE . AMFI . PK           |
|  FinBERT . APScheduler . Celery Nightlies           |
+-----------------------------------------------------+
```

---

## Backend Layer Breakdown

| Layer | Location | Responsibility |
|-------|----------|---------------|
| **Controller** | `backend/routers/` (21 files) | HTTP validation, rate limiting, spawn `multiprocessing.Process` for heavy AI jobs |
| **Service** | `backend/services/` (~60 files) | All business logic, LLM orchestration, computations, data harvesting |
| **Repository** | `backend/repositories/` + `database.py` | `get_session()` context manager, ORM queries, Alembic migrations |
| **Models** | `backend/models/db_models.py` | 25 centralized ORM classes — duplication forbidden |
| **Config** | `backend/config/settings.py` | Sector PE maps, cache TTLs, rate limit configs |
| **Helpers** | `backend/helpers.py` | `EXCHANGE_SUFFIX`, `_resolve_ticker`, `_to_ns`, `_check_rate_limit` |
| **Core** | `backend/core/security.py` | JWT auth: `get_current_user_id`, `require_auth`, `require_admin` |

### Middleware Stack (applied in order)

1. `CORSMiddleware` — env-configurable origins
2. `_RequestLogMiddleware` — logs path, method, status, duration to in-memory ring buffer
3. `_SecurityHeadersMiddleware` — rate limiting + `X-Content-Type-Options`, `X-Frame-Options`, `X-XSS-Protection`
4. `CorrelationIDMiddleware` — attaches a correlation ID to every request for tracing

---

## ML Engine Architecture

The `ml-engine/` directory is a **standalone Python 3.10 FastAPI microservice** running in Docker at port 8001. It exists because the main backend uses Python 3.11, which is incompatible with certain Qlib/LightGBM native extensions.

### Directory Layout

```
ml-engine/
├── main.py                    # FastAPI app, lifespan (model load/unload)
├── config.py                  # All constants: model paths, Alpha158 feature list, thresholds
├── Dockerfile                 # Python 3.10 container definition
├── requirements.txt           # Dependencies (lightgbm, polars, numpy, fastapi, etc.)
├── models/
│   ├── lgb_model.py           # LightGBM wrapper: train, predict, SHAP explanations
│   ├── tra.py                 # Temporal Routing Adaptor (TRA) architecture (PyTorch)
│   ├── predictor.py           # Unified predictor: LightGBM + TRA ensemble
│   └── model_loader.py        # Loads trained artifacts from disk at startup
├── pipeline/
│   ├── feature_computer.py    # Computes all 158 Alpha158 features from raw OHLCV
│   ├── inference.py           # End-to-end inference pipeline: OHLCV -> prediction
│   └── tra_sequence.py        # Prepares temporal sequences for TRA input
├── sandbox/
│   ├── Dockerfile.rdagent     # Air-gapped RD-Agent container for research experiments
│   ├── docker-compose.sandbox.yml  # Compose spec for the sandbox environment
│   └── README.md              # Sandbox usage instructions
└── tests/
    └── test_alpha158_pipeline.py  # Integration tests for the full Alpha158 pipeline
```

### Alpha158 Feature Set

158 technical and fundamental factors derived from OHLCV data:

- **Kline Basic** (9 factors): KMID, KLEN, KMID2, KUP, KUP2, KLOW, KLOW2, KSFT, KSFT2 — candlestick geometry
- **Rolling windows**: 5 windows (5, 10, 20, 30, 60 days) applied across return, volatility, correlation, and volume factor families
- **Static price ratios** (4 factors): OPEN0, HIGH0, LOW0, VWAP0
- **Volume-derived factors**: VSUMP, VSUMD, VSTD, VMA, turnover variants

### ML Models

| Model | Role |
|-------|------|
| **LightGBM** | Primary gradient-boosted tree model for cross-sectional ranking |
| **TRA (Temporal Routing Adaptor)** | PyTorch sequence model; routes samples to specialized sub-predictors based on market regime |
| **Ensemble** | `predictor.py` combines LightGBM + TRA signals with configurable weights |

### ML Engine Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Liveness probe — confirms model is loaded |
| `POST` | `/predict/cross-section` | Batch predictions for multiple stocks |
| `POST` | `/predict/single` | Single-stock prediction from raw OHLCV list (returns explicit `ml_engine_mode`) |
| `GET` | `/model/status` | Loaded model metadata (paths, feature count, load time) |

### Backend → ML Engine Client

`backend/services/qlib_engine/ml_client.py` provides the HTTP bridge:

- `predict_cross_section(ticker, ohlcv_data)` — async httpx call to `/predict/single`
- `predict_cross_section_sync(ticker, ohlcv_data)` — synchronous wrapper for `ThreadPoolExecutor`
- All failures (timeout, connection error, malformed response) return `None` — never propagate to the orchestrator

### RD-Agent Sandbox

`ml-engine/sandbox/` contains an air-gapped Docker environment (`Dockerfile.rdagent`, `docker-compose.sandbox.yml`) for Microsoft RD-Agent research experiments. It is isolated from production and runs experiments offline.

---

## Key Services (backend/services/)

| Service | Description |
|---------|-------------|
| `orchestrator.py` | 8-stage AI analysis pipeline; LangGraph graph setup, `analyze()` entry point |
| `factor_engine.py` | RSI, MACD, Bollinger Bands, ATR, OBV, SMA/EMA crossovers, volatility regimes |
| `confidence_engine.py` | Signal agreement scoring, conformal prediction bounds, KNN historical analogues |
| `confidence_fusion.py` | Strict fusion formula for confidence calculation: 0.45*LLM + 0.25*Quant + 0.15*Venn-Abers + 0.10*Signal Agreement + 0.05*ML |
| `stress_test.py` | 14 Indian-market stress scenarios; EWMA Vasicek shrinkage, Almgren-Chriss liquidity |
| `stress_test_jobs.py` | Async job management for stress test runs |
| `correlation_engine.py` | MPT mean-variance, 11-sector proxy, pairwise NaN handling, 1hr TTL cache |
| `sector_rotation.py` | Multi-period (1m/3m/6m/1y) quadrant analysis with FII/DII flow |
| `sentiment_engine.py` | FinBERT sentiment scoring (HuggingFace, lazy-loaded) |
| `quant_engine.py` | Deterministic quantitative pre-pipeline (runs before any LLM call) |
| `piotroski.py` | 9-point Piotroski F-Score (profitability, leverage, efficiency) |
| `options_engine.py` | Multi-leg options payoff computation (CALL/PUT x LONG/SHORT) |
| `nl_screener.py` | Natural language -> SQL -> 2000+ stock universe filter |
| `nse_data_provider.py` | Primary NSE data provider (jugaad-data) |
| `yfinance_client.py` | yfinance fallback data client |
| `nse_client.py` | Direct NSE API client (bulk/block deals, FII/DII flows) |
| `scraper.py` | General web scraping utilities |
| `staleness.py` | `compute_staleness()` — cache gate scoring (0-100); NEVER bypassed |
| `llm_utils.py` | `get_deepseek_client()`, `deepseek_chat()`, model constants |
| `harvest_worker.py` | APScheduler-backed background harvest coordinator |
| `harvester_db.py` | Database persistence for harvested content |
| `harvester_expert.py` | Financial expert content harvesting |
| `harvester_reformatter.py` | Claude-based reformat pass for harvested content |
| `harvester_sebi.py` | SEBI filing fetcher and governance forensics |
| `youtube_harvester.py` | YouTube financial video transcript and metadata harvest |
| `expert_youtube_harvester.py` | Expert-specific YouTube channel harvest |
| `news_harvester.py` | Multi-source news ingestion |
| `advisor_harvester.py` | Financial advisor content harvest and stance extraction |
| `transcript_engine.py` | Video transcript processing and stance extraction |
| `filings_extractor.py` | Corporate filing extractor |
| `portfolio_snapshot.py` | Nightly portfolio valuation snapshots for all users |
| `nightly_pipeline.py` | Orchestrates nightly harvest and analysis pipeline |
| `nightly_jobs.py` | APScheduler job definitions for nightly tasks |
| `earnings_surprise.py` | EPS surprise detection, historical patterns, post-price impact |
| `anomaly_scanner.py` | Market anomaly detection and severity classification |
| `microstructure_engine.py` | Order flow, microstructure signals |
| `brainstorming.py` | AI-generated investment idea exploration |
| `copilot_service.py` | Conversational stock assistant service |
| `strategy_engine.py` | Trading strategy backtesting engine |
| `extreme_enrichers.py` | Enrichers for extreme analysis sections |
| `macro_modifiers.py` | Macro factor modifiers for analysis |
| `feedback_injector.py` | Analysis feedback loop injection |
| `rag_ingestion.py` | ChromaDB vector store ingestion |
| `rag_tools.py` | RAG tool definitions for LangGraph agents |
| `vector_store.py` | ChromaDB store init and query |
| `cache_service.py` | Multi-layer cache service (L1 in-memory, L2 disk) |
| `disk_cache.py` | L2 persistent disk cache (get/set/stats) |
| `error_telemetry.py` | CorrelationIDMiddleware, error logging to 4 telemetry tables |
| `ai_engine_monitor.py` | AI engine health monitoring |
| `job_manager.py` | AnalysisJob lifecycle management |
| `job_worker.py` | Worker for async job execution |
| `outcome_backfill.py` | Nightly forward-return backfill for resolved analyses |
| `outcome_tracker.py` | Nightly Celery task calculating actual returns (7, 30, 90-day) via yfinance to build LightGBM training datasets |
| `pkscreener_runner.py` | PKScreener technical signal runner |
| `ticker_matcher.py` | Fuzzy ticker/company name matching |
| `celery_tasks.py` | Celery app definition (canonical, referenced by tasks/) |
| `checkpoints.py` | LangGraph checkpoint utilities |
| `rate_limiter.py` | Per-IP rate limiter helper |
| `options_scraper.py` | Options chain data scraper |
| `math_engines/` | Subdirectory: specialized math computation engines |
| `qlib_engine/` | Subdirectory: ML client (ml_client.py) for the ml-engine microservice |

---

## All 21 Routers (backend/routers/)

| Router File | HTTP Prefix | Key Responsibilities |
|-------------|-------------|---------------------|
| `analysis.py` | `/` | Stock analysis (v2 async), SSE progress, batch, screener, morning brief, signals |
| `market.py` | `/` | Indices, Nifty history, option chain, filings, sector PE, institutional flow |
| `portfolio.py` | `/` | Holdings CRUD, net worth, performance charts, XLSX/PDF export, trade journal |
| `auth.py` | `/` | Login, register, JWT token generation |
| `user.py` | `/` | Profile, settings, admin, role promotion |
| `alerts.py` | `/` | Price alerts CRUD, background price poller |
| `notifications.py` | `/` | Device token registration, APNs push pipeline |
| `dashboard.py` | `/` | Admin web dashboard (Chart.js), live job monitoring |
| `harvester.py` | `/` | Content feed, governance, search, trigger scrape |
| `stress_test.py` | `/` | Portfolio stress test execution, job progress |
| `correlation.py` | `/` | Correlation matrix computation, diversification score |
| `sector_rotation.py` | `/api/v1` | Multi-period sector quadrant, FII/DII flow analysis |
| `earnings_surprise.py` | `/` | EPS surprise, historical patterns, post-price impact |
| `nl_screener.py` | `/` | Natural language -> SQL stock filter |
| `options_strategy.py` | `/` | Multi-leg options payoff computation |
| `anomalies.py` | `/` | Market anomaly detection and listing |
| `brainstorming.py` | `/` | AI investment idea generation |
| `copilot.py` | `/` | Conversational AI stock market assistant |
| `strategy.py` | `/` | Trading strategy backtesting |
| `health.py` | `/` | `/ping` (zero-dependency), `/healthz` (DB-backed) |
| `harvest_worker.py` (service) | `/` | Admin harvest trigger endpoints (registered via harvest_router) |

---

## Database

### ORM Models (backend/models/db_models.py) — 25 Classes

All models centralized in one file. Duplication forbidden — never define `class Foo(Base)` in a service file.

| Domain | ORM Classes |
|--------|-------------|
| **User & Auth** | `User`, `DeviceToken` |
| **Portfolio** | `Portfolio`, `PortfolioValuationHistory`, `NetWorthLedger`, `TradeJournal` |
| **Analysis** | `AnalysisHistory`, `AnalysisJob`, `SignalEvent`, `PriceTarget`, `AnalysisPrediction` (with 7d/30d/90d brier scores, hit directions, scan_type, regime_id, and 5 confidence pillars) |
| **Content** | `NewsArticle`, `YouTubeVideo`, `AdvisorInsight`, `AdvisorBiography`, `TextAdvisoryInsight` |
| **Market** | `StockUniverse` (2000+ tickers), `BlockDeal`, `FIIDIIFlow`, `MacroEvent`, `EarningsAlert`, `EarningsSurpriseHistory`, `MarketAnomaly` |
| **Risk** | `EquityRiskFactor`, `CovarianceMatrix` |
| **ML** | `Alpha158Feature`, `Alpha158Features` |
| **Telemetry** | `MarketErrorLog`, `EarningsErrorLog`, `NotificationErrorLog`, `IdeasErrorLog` |
| **Screening** | `PKScreenerSignal` |

### Alembic Migrations (backend/migrations/versions/) — 9 Files

| File | Description |
|------|-------------|
| `0dc3e605ea33_initial_schema.py` | Initial schema creation |
| `9929cce0b029_add_stockuniverse_model.py` | Adds StockUniverse table (2000+ tickers) |
| `1ad82d60efcc_convert_float_to_numeric_for_precision.py` | Float to Numeric precision upgrade |
| `323c66c5ca0e_auto.py` | Auto-generated schema sync |
| `a1b2c3d4e5f6_add_missing_columns.py` | Adds missing columns across tables |
| `b2c3d4e5f6a7_add_analysis_job_ticker_index.py` | Index on analysis_jobs.ticker |
| `d4e5f6a7b8c9_sync_missing_indexes.py` | Syncs missing composite indexes |
| `931cb6d2cbb6_add_alpha158_features.py` | Adds alpha158_features table |
| `cb0f4d2ce6e1_add_alpha158_features_normalized_table.py` | Adds alpha158_features_normalized table |

Migration policy — never ALTER TABLE manually:

```bash
cd backend
alembic revision --autogenerate -m "description"
alembic upgrade head
alembic check   # verify no drift
```

---

## AI Pipeline

### Smart Cache Gate (services/staleness.py)

`compute_staleness()` returns a score 0-100. Never bypassed.

| Score | Status | Action |
|:-----:|--------|--------|
| 0-19 | **FRESH** | Return cached result. No AI run. |
| 20-44 | **AGING** | Optional: DeepSeek Flash only |
| 45-69 | **STALE** | Full refresh: all DeepSeek agents |
| 70-100 | **URGENT** | Full multi-agent: DeepSeek + Haiku + Sonnet |

### LangGraph 8-Agent Debate Pipeline

```
Quant Pre-Pipeline (deterministic)
         |
         v
Bull Researcher --------+
                        v
                 Research Manager (synthesis)
                        |
Bear Researcher --------+
(1.5x weight, longer prompt)
                        |
                        v
        3 Debaters (Aggressive / Neutral / Conservative)
                        |
                        v
             Portfolio Manager (Bear weighted 1.5x)
                        |
                        v
     Claude Sonnet final reformatting pass
                        |
                        v
     _normalize_response() -> _ban_western_scale()
```

### Language Model Tiers

| Tier | Model | Role |
|:----:|-------|------|
| 1 | `deepseek-chat` ($0.00014/1K input) | 8 bulk analysis agents |
| 2 | `claude-haiku-4-5-20251001` | Research Manager synthesis |
| 3 | `claude-sonnet-4-6` | Final reformatting pass only |

All configuration via `build_ta_config()` — never modify `DEFAULT_CONFIG` directly.

---

## Data Sources

| Source | Library / Method | Used For |
|--------|-----------------|----------|
| **NSE India** | jugaad-data | Primary OHLCV, corporate actions, FII/DII |
| **yfinance** | yfinance | Fallback OHLCV, international data |
| **NSE Direct APIs** | nse_client.py | Bulk/block deals, option chains |
| **SEBI Filings** | harvester_sebi.py | Governance forensics, corporate filings |
| **YouTube** | youtube_harvester.py, expert_youtube_harvester.py | Financial advisor videos, transcripts |
| **News** | news_harvester.py | Multi-source news with FinBERT sentiment |
| **AMFI** | harvest_worker.py | Mutual fund NAV data |
| **PKScreener** | pkscreener_runner.py | Technical screening signals |

---

## Nightly Jobs

### Alpha158 Materialization (Celery)

`backend/tasks/alpha158_task.py` — Celery task `tasks.materialize_alpha158`:

1. For each NSE ticker: fetch 252 trading days of OHLCV via nse_data_provider
2. Apply Point-in-Time (PIT) safety — rows capped at T = most recent date
3. POST OHLCV payload to http://localhost:8001/predict/single
4. Compute 158 Alpha158 feature values locally for storage
5. Upsert into alpha158_features_normalized using get_session() per ticker (isolated failures)

Retries up to 3x on transient failures. Uses httpx with 30-second timeout.

### Outcome Tracking (Celery)

`backend/services/outcome_tracker.py` — Nightly Celery task calculates actual returns across 7, 30, and 90-day horizons using `yfinance` to build LightGBM training datasets.

### APScheduler Jobs

Scheduled via AsyncIOScheduler when ENABLE_SCHEDULER=true:

| Job | Schedule | Service |
|-----|----------|---------|
| YouTube harvest | cron hour=0, min=30 | harvest_worker.harvest_youtube_metadata |
| News harvest | cron hour=1, min=30 | harvest_worker.harvest_news |
| Portfolio snapshots | cron hour=16, min=30 | portfolio_snapshot.snapshot_all_users |
| RAG refresh | cron hour=2, min=0 | rag_ingestion.ingest_new |
| Outcome backfill | cron hour=3, min=0 | outcome_backfill.backfill_outcomes |

`nightly_pipeline.py` provides a standalone orchestration script for the full nightly harvest and analysis run.

---

## iOS App

### App Structure

```
ios/StockApp/stockme/stockme/
├── stockmeApp.swift              # App entry point, environment setup
├── ContentView.swift             # Root navigation container
├── NetworkManager.swift          # All API calls (~68K bytes)
├── NetworkManager+Sidebar.swift  # Sidebar-specific network calls
├── BanknoteDesignSystem.swift    # Theme tokens, spacing, typography definitions
├── AuthManager.swift             # JWT token storage, biometric lock
├── StockDatabase.swift           # Local stock universe (~400KB, 628+ tickers)
├── Models/                       # Swift data models (9 files)
├── Views/                        # All screens (47 files across 3 subdirs)
├── Charts/                       # Custom chart components
├── Components/                   # Reusable UI components
├── Services/                     # iOS-side service classes
└── Utilities/                    # Utility helpers
```

### Views Directory (47 Swift files)

Top-level Views (45 files):

| File | Screen |
|------|--------|
| `HomeScreen.swift` | Main dashboard, market pulse, holdings summary, news feed |
| `PortfolioScreen.swift` | Full portfolio management, holdings, P&L, CAGR |
| `AnalysisScreen.swift` | Stock analysis request and result display |
| `SearchScreen.swift` | Stock search, voice search (SFSpeechRecognizer) |
| `SettingsScreen.swift` | App settings, theme picker, notification prefs |
| `LoginScreen.swift` | Authentication, Face ID / Touch ID |
| `NiveshNavigationSidebar.swift` | App-wide sidebar navigation |
| `AlertsScreen.swift` | Price alert creation and management |
| `CopilotScreen.swift` | Conversational AI stock assistant |
| `BrainstormingView.swift` | AI investment idea generator |
| `StrategyLabScreen.swift` | Trading strategy backtester |
| `StressTestScreen.swift` | 14-scenario portfolio stress test |
| `CorrelationMatrixScreen.swift` | 11-sector correlation matrix |
| `SectorRotationScreen.swift` | Multi-period sector quadrant |
| `EarningsSurpriseScreen.swift` | EPS surprise analysis |
| `EarningsDashboardView.swift` | Full earnings dashboard |
| `MarketAnomalyScreen.swift` | Market anomaly detection |
| `NLScreenerScreen.swift` | Natural language stock screener |
| `OptionsStrategyScreen.swift` | Multi-leg options payoff builder |
| `TechnicalMomentumView.swift` | Technical momentum indicators |
| `StockProfileView.swift` | Stock profile overview |
| `CompareScreen.swift` | Side-by-side stock comparison |
| `NewsMultimediaView.swift` | News and multimedia feed |
| `ExpertNetworkView.swift` | Financial expert advisor network |
| `PreIPOMarketplaceView.swift` | Pre-IPO opportunity listings |
| `AdvisoryMatrixCard.swift` | Advisor recommendation matrix |
| `DalalStreetConsensusCard.swift` | Consensus view from Dalal Street |
| `TradeJournalScreen.swift` | Trade journal with outcome logging |
| `AnalysisHistoryScreen.swift` | Past analysis history |
| `HistoryScreen.swift` | Activity history |
| `ValuationCalendarView.swift` | EventKit earnings calendar |
| `AIHowItWorksView.swift` | AI pipeline explainer |
| `GlossaryBrowserView.swift` | Financial glossary |
| `FeatureHelpViews.swift` | Contextual feature help |
| `TutorialOverlayView.swift` | Onboarding tutorial overlays |
| `OnboardingScreen.swift` | First-run onboarding |
| `LaunchScreenView.swift` | Splash / launch animation |
| `EngineActivityView.swift` | AI engine activity monitor |
| `StockActionHubView.swift` | Quick action hub for a stock |
| `CrashLabView.swift` | Extreme scenario "what-if" lab |
| `ReportManagerView.swift` | Portfolio report manager |
| `QuietHoursView.swift` | Notification quiet hours config |
| `SectorBlacklistView.swift` | Sector blacklist settings |
| `TermDefinitionSheet.swift` | Contextual term definition sheet |
| `DisclaimerScreen.swift` | Legal disclaimer screen |

Analysis/ subdirectory (8 files):
AnalysisFullView.swift, AnalysisCoreSections.swift, AnalysisExtremeSections.swift, AnalysisLoadingStateView.swift, AnalysisErrorStateView.swift, QuantInspectorSheet.swift, QuantitativeDriversCard.swift, RegimeWarningBanner.swift

StockProfile/ subdirectory (9 files):
OverviewTabView.swift, FinancialsTabView.swift, ChartTabView.swift, NewsTabView.swift, GovernanceTabView.swift, MacroTabView.swift, HoldersTabView.swift, UpdatesTabView.swift, SPSharedViews.swift

### iOS Models (Models/)

| File | Contents |
|------|---------|
| `AnalysisModels.swift` | Analysis response structs, signal types, LLM output models |
| `MarketModels.swift` | Market data models, indices, option chain |
| `AlertModels.swift` | Price alert models |
| `PortfolioModels.swift` | Portfolio and holding structs |
| `AdvisoryModels.swift` | Advisor and recommendation models |
| `OptionsModels.swift` | Options strategy models |
| `WatchlistModels.swift` | Watchlist entry models |
| `UtilityModels.swift` | Shared utility structs, IndianFormatter |
| `Common.swift` | Shared enums and types |

### Banknote Aesthetic Design System (BanknoteDesignSystem.swift)

```
Theme.canvas          #1C1A14  Aged charcoal background
Theme.securityGold    #C8A84A  Security thread gold
Theme.bullGreen       #2D6A4F  Positive (NSE green)
Theme.bearRed         #C1292E  Negative (loss red)
Theme.inkPrimary      #F5F0E8  Ivory primary text
Theme.inkSecondary             Dimmed text
Theme.inkTertiary              Subtle text
Theme.holdAmber                Neutral amber
Theme.borderFine               Fine rule borders
Theme.borderSage               Sage section borders
```

Spacing (8pt grid): xSmall(2), small(4), tight(6), medium(8), standard(12), card(16), screen(20), large(24), xLarge(32)

Typography: Georgia serif (engravedSerif), Monospaced numbers (serialNumberFont), Condensed medium labels (officialStampFont), Italic Georgia for Hindi (hindiFont)

7 theme presets: Rs.10, Rs.20, Rs.50, Rs.100, Rs.200, Rs.500, Dark

---

## Deployment

### Production Server

| Config | Value |
|--------|-------|
| **API URL** | https://api.nivesh.qzz.io |
| **Server** | Fedora . 16 CPUs . 14 GB RAM |
| **Database** | PostgreSQL 18 + pgvector |
| **Backend workers** | 4 x Uvicorn |
| **Timezone** | UAE (UTC+4) |

### Deploy Commands

```bash
# Backend (main server)
ssh saumyapatel@192.168.1.122
cd /home/saumyapatel/Desktop/nivesh
git pull --ff-only origin main
sudo systemctl restart nivesh

# ML Engine (Docker)
bash scripts/deploy_ml_engine.sh

# Health check
curl https://api.nivesh.qzz.io/ping
curl https://api.nivesh.qzz.io/healthz
```

### iOS

Open `ios/StockApp/stockme.xcodeproj` in Xcode 15+. Configure API URL in `NetworkManager.swift`. Build and run on iOS 17+.

> **NEVER run xcodebuild** — Xcode project compilation must be done only through the Xcode IDE.

---

## Project Stats

```
Backend:    21 routers  .  ~60 services  .  24 ORM models
iOS:        47 View files  .  60+ screens  .  7 theme presets
Database:   9 migration files  .  25 ORM tables
ML Engine:  Python 3.10 Docker  .  158 Alpha158 features  .  LightGBM + TRA
Tests:      103 backend test files  .  1 ML engine test file
Scripts:    13 shell scripts in scripts/
Stock Universe:  628+ tickers  .  12 sectors
```
