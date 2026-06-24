# Nivesh — Architecture File Map

> Quick-reference: every significant file and its purpose.
> Format: `File/Directory | Purpose`

---

## Backend Routers (backend/routers/)

| File | Purpose |
|------|---------|
| `analysis.py` | Stock analysis (v2 async), SSE progress stream, batch analysis, screener, morning brief, signals — 73 KB |
| `market.py` | Market data: indices, Nifty history, option chain, SEBI filings, sector PE, institutional flows — 141 KB |
| `portfolio.py` | Portfolio CRUD: holdings, net worth, performance charts, XLSX/PDF export, trade journal — 145 KB |
| `auth.py` | Login, registration, JWT token generation |
| `user.py` | User profile, settings, admin management, role promotion — 15 KB |
| `alerts.py` | Price alert CRUD, background polling loop — 10 KB |
| `notifications.py` | Device token registration, APNs push notification pipeline — 5 KB |
| `dashboard.py` | Admin HTML dashboard (Chart.js), live job and request monitoring — 4 KB |
| `harvester.py` | Content feed, governance data, search, manual harvest triggers — 8 KB |
| `stress_test.py` | 14-scenario portfolio stress test execution, async job progress — 3 KB |
| `correlation.py` | Correlation matrix computation, diversification score endpoint — 2 KB |
| `sector_rotation.py` | Multi-period sector quadrant analysis (prefix: /api/v1) |
| `earnings_surprise.py` | EPS surprise analysis, historical patterns, post-price impact — 1 KB |
| `nl_screener.py` | Natural language -> SQL stock screening |
| `options_strategy.py` | Multi-leg options payoff computation — 4 KB |
| `anomalies.py` | Market anomaly detection endpoint |
| `brainstorming.py` | AI-powered investment idea generation |
| `copilot.py` | Conversational AI stock market assistant — 2 KB |
| `strategy.py` | Trading strategy backtesting endpoint |
| `health.py` | `/ping` (zero-dependency), `/healthz` (DB-backed liveness) — 2 KB |
| `__init__.py` | Router package init |

---

## Backend Services (backend/services/)

| File | Purpose |
|------|---------|
| `orchestrator.py` | Full 8-stage AI analysis pipeline, LangGraph graph, `analyze()` entry — 96 KB |
| `factor_engine.py` | RSI, MACD, Bollinger Bands, ATR, OBV, SMA/EMA, volatility regime — 20 KB |
| `confidence_engine.py` | Signal agreement, conformal prediction, KNN analogues, bear asymmetry — 23 KB |
| `confidence_fusion.py` | Strict fusion formula (0.45*LLM + 0.25*Quant + 0.15*Venn-Abers + 0.10*Signal Agreement + 0.05*ML) |
| `stress_test.py` | 14 scenarios, factor betas, EWMA shrinkage, Almgren-Chriss liquidity, 6 risk scores — 19 KB |
| `stress_test_jobs.py` | Async job state management for stress test runs — 7 KB |
| `correlation_engine.py` | MPT mean-variance, 11-sector proxy, pairwise NaN handling, 1hr TTL — 10 KB |
| `sector_rotation.py` | Multi-period quadrant (1m/3m/6m/1y) with FII/DII flow — 9 KB |
| `sentiment_engine.py` | FinBERT (HuggingFace, lazy-loaded) sentiment scorer — 11 KB |
| `quant_engine.py` | Deterministic quantitative pre-pipeline — 13 KB |
| `piotroski.py` | 9-point Piotroski F-Score (profitability/leverage/efficiency) — 7 KB |
| `options_engine.py` | Multi-leg options payoff (CALL/PUT x LONG/SHORT, full range) — 13 KB |
| `nl_screener.py` | NLP -> SQL -> 2000+ stock filter — 13 KB |
| `nse_data_provider.py` | Primary NSE data (jugaad-data), OHLCV, corporate actions — 20 KB |
| `yfinance_client.py` | yfinance fallback data client — 7 KB |
| `nse_client.py` | Direct NSE API: bulk/block deals, FII/DII flows — 7 KB |
| `scraper.py` | General web scraping utilities — 28 KB |
| `staleness.py` | `compute_staleness()` — cache gate score 0-100; NEVER bypassed — 5 KB |
| `llm_utils.py` | `get_deepseek_client()`, `deepseek_chat()`, HAIKU_MODEL, SONNET_MODEL, DEEPSEEK_MODEL — 6 KB |
| `harvest_worker.py` | APScheduler harvest coordinator, admin trigger routes — 19 KB |
| `harvester_db.py` | DB persistence for harvested content — 11 KB |
| `harvester_expert.py` | Expert content harvest (financial advisors) — 35 KB |
| `harvester_reformatter.py` | Claude-based reformat pass for harvested content — 13 KB |
| `harvester_sebi.py` | SEBI filing fetcher, governance forensics — 6 KB |
| `youtube_harvester.py` | YouTube video metadata + transcript harvest — 21 KB |
| `expert_youtube_harvester.py` | Expert-channel-specific YouTube harvest — 12 KB |
| `news_harvester.py` | Multi-source news ingestion — 8 KB |
| `advisor_harvester.py` | Advisor content harvest and stance extraction — 25 KB |
| `transcript_engine.py` | Video transcript processing, stance extraction — 11 KB |
| `filings_extractor.py` | Corporate filing extractor — 10 KB |
| `portfolio_snapshot.py` | Nightly portfolio valuation snapshots — 11 KB |
| `nightly_pipeline.py` | Full nightly harvest + analysis orchestration — 12 KB |
| `nightly_jobs.py` | APScheduler job definitions — 10 KB |
| `earnings_surprise.py` | EPS surprise, historical patterns, 1d/5d post-price impact — 6 KB |
| `anomaly_scanner.py` | Market anomaly detection and severity classification — 11 KB |
| `microstructure_engine.py` | Order flow, microstructure signals — 9 KB |
| `brainstorming.py` | AI investment idea generation — 2 KB |
| `copilot_service.py` | Conversational stock assistant — 9 KB |
| `strategy_engine.py` | Trading strategy backtesting — 11 KB |
| `extreme_enrichers.py` | Extreme analysis section enrichers — 11 KB |
| `macro_modifiers.py` | Macro factor modifiers — 11 KB |
| `feedback_injector.py` | Analysis feedback loop — 6 KB |
| `rag_ingestion.py` | ChromaDB ingestion pipeline — 5 KB |
| `rag_tools.py` | RAG tool definitions for LangGraph agents — 2 KB |
| `vector_store.py` | ChromaDB store init and query — 5 KB |
| `cache_service.py` | L1 in-memory + L2 disk multi-layer cache — 13 KB |
| `disk_cache.py` | L2 disk cache (get/set/stats) — 1 KB |
| `error_telemetry.py` | CorrelationIDMiddleware, 4 telemetry tables — 11 KB |
| `ai_engine_monitor.py` | AI engine health monitoring — 8 KB |
| `job_manager.py` | AnalysisJob lifecycle (create/update/read) — 2 KB |
| `job_worker.py` | Worker for async job execution — 3 KB |
| `outcome_backfill.py` | Nightly forward-return backfill for calibration — 5 KB |
| `outcome_tracker.py` | Nightly Celery task: actual returns (7/30/90-day) via yfinance for LightGBM |
| `pkscreener_runner.py` | PKScreener signal runner — 7 KB |
| `ticker_matcher.py` | Fuzzy ticker and company name matching — 11 KB |
| `celery_tasks.py` | Canonical Celery app (referenced by tasks/) — 2 KB |
| `checkpoints.py` | LangGraph graph checkpoint utilities — 1 KB |
| `rate_limiter.py` | Per-IP in-memory rate limiter — 1 KB |
| `options_scraper.py` | Options chain scraper — 8 KB |
| `math_engines/` | Specialized math computation sub-package |
| `qlib_engine/ml_client.py` | HTTP client: `predict_cross_section()`, `predict_cross_section_sync()` |

---

## Backend Models and Config

| File | Purpose |
|------|---------|
| `backend/models/db_models.py` | 25 ORM classes: User, Portfolio, AnalysisHistory, AnalysisJob, NewsArticle, AnalysisPrediction (w/ 7d/30d/90d brier, 5 confidence pillars), etc. — 32 KB |
| `backend/models/signal_config.py` | `_SIGNAL_MAP` — sole authority for signal string constants (BULLISH/BEARISH/HOLD/NEUTRAL/WATCHLIST) |

---

## Backend Tasks

| File | Purpose |
|------|---------|
| `backend/tasks/alpha158_task.py` | Celery task `tasks.materialize_alpha158`: nightly 158-feature computation and upsert for all NSE tickers — 13 KB |

---

## Alembic Migrations (backend/migrations/versions/)

| File | Description |
|------|-------------|
| `0dc3e605ea33_initial_schema.py` | Initial schema |
| `9929cce0b029_add_stockuniverse_model.py` | StockUniverse table (2000+ tickers) |
| `1ad82d60efcc_convert_float_to_numeric_for_precision.py` | Float -> Numeric |
| `323c66c5ca0e_auto.py` | Auto schema sync |
| `a1b2c3d4e5f6_add_missing_columns.py` | Missing columns across tables |
| `b2c3d4e5f6a7_add_analysis_job_ticker_index.py` | Ticker index on analysis_jobs |
| `d4e5f6a7b8c9_sync_missing_indexes.py` | Composite index sync |
| `931cb6d2cbb6_add_alpha158_features.py` | alpha158_features table |
| `cb0f4d2ce6e1_add_alpha158_features_normalized_table.py` | alpha158_features_normalized table |

---

## ML Engine (ml-engine/)

| File | Purpose |
|------|---------|
| `ml-engine/main.py` | FastAPI microservice entry point; lifespan loads LightGBM + TRA + scaler; 4 endpoints — 12 KB |
| `ml-engine/config.py` | All constants: LIGHTGBM_MODEL_PATH, TRA_MODEL_PATH, SCALER_PATH, FEATURE_LIST (158 names), REGIME_THRESHOLDS, CONFIDENCE_CONFIG, LIGHTGBM_PARAMS — 5 KB |
| `ml-engine/Dockerfile` | Python 3.10 container; installs requirements.txt |
| `ml-engine/requirements.txt` | lightgbm, torch, polars, numpy, fastapi, uvicorn, httpx, pydantic |

### ML Engine Models

| File | Purpose |
|------|---------|
| `ml-engine/models/lgb_model.py` | LightGBM wrapper: train, predict, SHAP feature importance — 11 KB |
| `ml-engine/models/tra.py` | Temporal Routing Adaptor (TRA) PyTorch module — 10 KB |
| `ml-engine/models/predictor.py` | Ensemble predictor: LightGBM + TRA with configurable weights — 18 KB |
| `ml-engine/models/model_loader.py` | Loads trained artifacts (lgb_model.txt, tra_model.pt, feature_scaler.json) from disk — 5 KB |

### ML Engine Pipeline

| File | Purpose |
|------|---------|
| `ml-engine/pipeline/feature_computer.py` | Computes all 158 Alpha158 features from raw OHLCV pandas/polars DataFrame — 14 KB |
| `ml-engine/pipeline/inference.py` | End-to-end pipeline: OHLCV list -> feature vector -> ensemble prediction -> response (returns explicit `ml_engine_mode` as lgbm_trained or fallback_technical_heuristic) — 11 KB |
| `ml-engine/pipeline/tra_sequence.py` | Prepares temporal sequences (sliding windows) for TRA model input — 5 KB |

### ML Engine Sandbox (RD-Agent)

| File | Purpose |
|------|---------|
| `ml-engine/sandbox/Dockerfile.rdagent` | Air-gapped container for Microsoft RD-Agent research experiments — 3 KB |
| `ml-engine/sandbox/docker-compose.sandbox.yml` | Compose spec for sandbox environment — 2 KB |
| `ml-engine/sandbox/README.md` | Sandbox usage documentation — 6 KB |

### ML Engine Tests

| File | Purpose |
|------|---------|
| `ml-engine/tests/test_alpha158_pipeline.py` | Integration tests: OHLCV -> features -> prediction; covers feature count, output shape, PIT safety — 14 KB |

---

## Scripts (scripts/)

| File | Purpose |
|------|---------|
| `scripts/deploy_ml_engine.sh` | Deploys ml-engine Docker container to server at 192.168.1.122 |
| `scripts/deploy_ml_microservice.sh` | Alternative ml-engine microservice deploy script |
| `scripts/health_check.sh` | Checks /ping and /healthz endpoints |
| `scripts/run_analysis.sh` | Triggers analysis for a given ticker via CLI |
| `scripts/test_all.sh` | Runs the full backend test suite |
| `scripts/commit.sh` | Helper for conventional commit format |
| `scripts/check_stock.sh` | Quick stock data sanity check |
| `scripts/check_stress_test.sh` | Stress test endpoint smoke test |
| `scripts/checklength.sh` | Checks router/service file line lengths |
| `scripts/lint_crash_patterns.sh` | Scans for known crash patterns |
| `scripts/show_analysis.sh` | Displays cached analysis for a ticker |
| `scripts/install-agents.sh` | Installs GitNexus agent tooling |

---

## iOS Views (ios/StockApp/stockme/stockme/Views/)

### Top-level (45 files)

| File | Screen |
|------|--------|
| `HomeScreen.swift` | Main dashboard: market pulse, holdings summary, news feed — 136 KB |
| `PortfolioScreen.swift` | Portfolio management: holdings, P&L, CAGR, net worth — 123 KB |
| `AnalysisScreen.swift` | Analysis request, real-time progress, result display — 56 KB |
| `SearchScreen.swift` | Stock search with voice (SFSpeechRecognizer) — 41 KB |
| `SettingsScreen.swift` | Settings: theme picker, notification prefs, biometric — 19 KB |
| `EarningsDashboardView.swift` | Full earnings calendar and dashboard — 92 KB |
| `ExpertNetworkView.swift` | Expert advisor network and videos — 36 KB |
| `NewsMultimediaView.swift` | News feed and multimedia — 40 KB |
| `StressTestScreen.swift` | 14-scenario stress test UI — 36 KB |
| `TechnicalMomentumView.swift` | Technical indicators and momentum — 31 KB |
| `OptionsStrategyScreen.swift` | Multi-leg options payoff chart builder — 31 KB |
| `StrategyLabScreen.swift` | Strategy backtest configuration and results — 26 KB |
| `CopilotScreen.swift` | Conversational AI chat interface — 26 KB |
| `StockProfileView.swift` | Stock profile with tabbed sections — 28 KB |
| `EarningsSurpriseScreen.swift` | EPS surprise analysis — 23 KB |
| `PreIPOMarketplaceView.swift` | Pre-IPO listings — 20 KB |
| `AlertsScreen.swift` | Price alert management — 26 KB |
| `SettingsScreen.swift` | App settings — 19 KB |
| `NLScreenerScreen.swift` | Natural language stock screener — 17 KB |
| `FeatureHelpViews.swift` | Contextual help modals — 18 KB |
| `CorrelationMatrixScreen.swift` | 11-sector correlation matrix — 16 KB |
| `TradeJournalScreen.swift` | Trade journal and outcome logging — 14 KB |
| `ValuationCalendarView.swift` | EventKit-backed earnings calendar — 17 KB |
| `SectorRotationScreen.swift` | Sector rotation quadrant — 15 KB |
| `MarketAnomalyScreen.swift` | Market anomaly listings — 10 KB |
| `TutorialOverlayView.swift` | Onboarding tutorial overlays — 12 KB |
| `NiveshNavigationSidebar.swift` | App-wide sidebar navigation — 10 KB |
| `DalalStreetConsensusCard.swift` | Dalal Street consensus card — 10 KB |
| `CompareScreen.swift` | Stock side-by-side comparison — 14 KB |
| `LoginScreen.swift` | Auth screen with biometric — 12 KB |
| `AIHowItWorksView.swift` | AI pipeline explainer — 15 KB |
| `StockActionHubView.swift` | Quick action hub — 12 KB |
| `GlossaryBrowserView.swift` | Financial glossary — 9 KB |
| `EngineActivityView.swift` | AI engine live activity — 9 KB |
| `AdvisoryMatrixCard.swift` | Advisor recommendation matrix — 9 KB |
| `BrainstormingView.swift` | Investment idea generator — 7 KB |
| `CrashLabView.swift` | Extreme what-if scenarios — 7 KB |
| `LaunchScreenView.swift` | Splash/launch animation — 9 KB |
| `AnalysisHistoryScreen.swift` | Past analysis list — 5 KB |
| `HistoryScreen.swift` | Activity history — 4 KB |
| `OnboardingScreen.swift` | First-run onboarding — 4 KB |
| `ReportManagerView.swift` | Portfolio report export manager — 4 KB |
| `QuietHoursView.swift` | Notification quiet hours — 4 KB |
| `SectorBlacklistView.swift` | Sector blacklist settings — 3 KB |
| `TermDefinitionSheet.swift` | Term definition bottom sheet — 6 KB |
| `DisclaimerScreen.swift` | Legal disclaimer — 4 KB |

### Analysis/ subdirectory (8 files)

| File | Purpose |
|------|---------|
| `AnalysisFullView.swift` | Full-screen analysis result container |
| `AnalysisCoreSections.swift` | Core analysis sections (signal, thesis, targets) — 31 KB |
| `AnalysisExtremeSections.swift` | Extreme/stress analysis sections — 27 KB |
| `AnalysisLoadingStateView.swift` | Progress bar, stage labels, animated loading — 11 KB |
| `AnalysisErrorStateView.swift` | Error display with retry — 14 KB |
| `QuantInspectorSheet.swift` | Quantitative data inspector bottom sheet — 9 KB |
| `QuantitativeDriversCard.swift` | Key quant drivers summary card — 3 KB |
| `RegimeWarningBanner.swift` | Market regime warning banner — 2 KB |

### StockProfile/ subdirectory (9 files)

| File | Purpose |
|------|---------|
| `OverviewTabView.swift` | Stock overview: price, key metrics — 5 KB |
| `FinancialsTabView.swift` | Financial statements tab — 7 KB |
| `ChartTabView.swift` | Interactive price chart — 24 KB |
| `NewsTabView.swift` | Stock-specific news — 4 KB |
| `GovernanceTabView.swift` | SEBI filings, governance forensics — 23 KB |
| `MacroTabView.swift` | Macro environment context — 14 KB |
| `HoldersTabView.swift` | FII/DII/promoter holdings — 3 KB |
| `UpdatesTabView.swift` | Corporate updates feed |
| `SPSharedViews.swift` | Shared sub-views for stock profile tabs — 3 KB |

---

## iOS Core Files (ios/StockApp/stockme/stockme/)

| File | Purpose |
|------|---------|
| `stockmeApp.swift` | App entry point, environment objects, startup — 17 KB |
| `ContentView.swift` | Root navigation: tab view, deep linking — 28 KB |
| `NetworkManager.swift` | All HTTP calls to FastAPI backend — 68 KB |
| `NetworkManager+Sidebar.swift` | Sidebar-specific network calls — 20 KB |
| `BanknoteDesignSystem.swift` | Theme tokens, spacing, typography, EKPressStyle, GuillocheDivider — 12 KB |
| `AuthManager.swift` | JWT token storage (Keychain), biometric lock — 3 KB |
| `StockDatabase.swift` | Local 628+ ticker lookup database — 405 KB |
| `HomeFeedModels.swift` | Home feed data models — 4 KB |
| `HomeFeedService.swift` | Home feed data service — 2 KB |
| `HomeFeedViewModel.swift` | Home feed view model — 2 KB |
| `StockProfileViewModel.swift` | Stock profile state management — 6 KB |
| `NotificationManager.swift` | APNs registration, local notification handling — 7 KB |
| `DenominationBackground.swift` | Banknote denomination background view — 5 KB |
| `AppDelegate.swift` | UIApplicationDelegate, push notification setup — 2 KB |
| `LaunchSequenceView.swift` | Animated launch/splash sequence — 7 KB |
| `WatchlistScreen.swift` | Watchlist management — 11 KB |

---

## iOS Models (ios/.../Models/)

| File | Purpose |
|------|---------|
| `AnalysisModels.swift` | Analysis response, signal types, LangGraph output structs — 27 KB |
| `MarketModels.swift` | Market data, indices, option chain structs — 12 KB |
| `AlertModels.swift` | Price alert request/response structs — 9 KB |
| `PortfolioModels.swift` | Portfolio and holding data structs — 3 KB |
| `AdvisoryModels.swift` | Advisor and recommendation structs — 7 KB |
| `OptionsModels.swift` | Options strategy data structs — 2 KB |
| `WatchlistModels.swift` | Watchlist entry structs — 4 KB |
| `UtilityModels.swift` | IndianFormatter, shared utilities — 10 KB |
| `Common.swift` | Shared enums and type aliases — 4 KB |
