# Nivesh (निवेश) — Hyper-Detailed Architecture Map

> **Authority:** This is the definitive technical blueprint and "System DNA" of the Nivesh ecosystem.
> **Scope:** Full-stack analysis covering SwiftUI (iOS), FastAPI (Backend), LangGraph (AI Pipeline), and TradingAgents (Multi-Agent Framework).
> **Last Updated:** June 6, 2026.
> **Total Files Indexed:** 260 source files (GitNexus: 11,614 symbols, 24,375 relationships, 179 execution flows)
> **Documentation Target:** 3000-4000 Lines (Density: Maximum)

---

## 1. Project Philosophy & Core Pillars

Nivesh (Sanskrit: निवेश, "Investment") is a **Premium AI-First Wealth Intelligence System** focused exclusively on the Indian Equity Market (Dalal Street). It is architected as a three-pillar system where each pillar reinforces the others:

### Pillar I: The Banknote Aesthetic (Frontend — iOS SwiftUI)

The user interface is designed as a **Financial Instrument** — borrowing visual grammar from the Indian Rupee banknote. This is not decorative; it encodes meaning through visual hierarchy.

**Core Design Principles:**
- **Guilloche Logic:** Procedural drawing of sine-wave pairs (`f(x) = A * sin(omega_x + phi)`) for borders, dividers, and decorative elements. Two overlapping waves create the classic banknote anti-counterfeit pattern. Implemented via Canvas 2D drawing in SwiftUI.
- **Tactile Feedback:** Emil Kowalski-style press interactions (EKPressStyle) that mimic the weight and resistance of paper currency. Scale: 0.96, opacity: 0.88, spring response: 0.35, damping: 0.55.
- **Visual Fidelity:** 500-grain canvas texture noise overlay at 3% opacity (light) / 2.5% (dark). RBI watermark stamps at 10% opacity. Gold security thread with microtext "NIVESH RBI".
- **Denomination-Colored Backgrounds:** 6 distinct color DNAs mapped to Indian currency denominations (Rs 10/50/100/200/500/2000), used as background chapter markers for portfolio sections.
- **Audio & Haptic:** Rupee rustle sound (AVAudioPlayer) triggered on launch and key transactions. Verified chime on analysis completion. Haptic feedback on every button press.

**Design System Architecture:**
- `Theme.swift` (304 lines): Adaptive color system with 20+ tokens (light/dark mode), 4 typography functions (Georgia serif, monospace serial number, official stamp, Hindi italic), spacing system (8 levels), corner radius system (5 levels), gradients, reusable view components (PaperTexture, BanknoteWatermark, GuillocheDivider, CountUpNumber, StaggerAppear).
- `BanknoteDesignSystem.swift` (80+ lines): EKPressStyle, SecurityThread, RupeeWatermark, CornerOrnament, BanknoteSignalBadge, PortfolioValueDisplay, stamp animation, GovernorSealAvatar.
- `DenominationBackground.swift` (70+ lines): 6 denomination color schemes, RBI seal background, microtext strip.
- `SharedComponents.swift` (317 lines): AppHeader, StockPreviewCard, StockRow, IndexChip, SectionHeader, StockIcon.

### Pillar II: Dialectical Reasoning (AI Pipeline — LangGraph Multi-Agent)

Nivesh rejects "one-shot" AI responses. It employs a **Multi-Agent Dialectic Loop** built on LangGraph's StateGraph with cyclic edges:

**The Debate Architecture:**
1. **Adversarial Challenge:** Bull and Bear researchers must attempt to invalidate each other's thesis. Each round forces deeper specificity — vague claims get challenged.
2. **Iterative Risk Review:** A 3-node committee (Aggressive/Neutral/Conservative) reviews the trading proposal. Each member critiques the others until a "Risk Clearance" signal emerges.
3. **Epistemic Feedback:** Past thesis errors are injected back into the current context. The system tracks `was_correct` boolean for every prior analysis and forces reflection on what went wrong.

**Key Innovation:** The debate is NOT symmetrical. The Bear researcher gets the epistemological advantage — the burden of proof is on the Bull to overcome objections.

### Pillar III: Context Stratification (Performance Engineering)

To handle complex Indian market rules without prohibitive latency or cost, the system uses **Prefix-Aligned Prompt Caching** via Anthropic's `cache_control: ephemeral` mechanism:

- **Static Layer (Breakpoint 1):** Hardened persona instructions, tool definitions, behavioral translation rules, and Indian Market Priority Weighting. This is shared across ALL analyses and achieves 80-95% cache hit rate.
- **Ticker History Layer (Breakpoint 2):** Deterministically serialized prior analyses (last 15, sorted keys for stable cache key). Changes only when a ticker gets new analysis.
- **Volatile Layer (No Cache):** Current OHLCV data, date context, instrument identity, news headlines. This is the only uncacheable portion.

**Smart Cache Gate:** Before triggering the full pipeline, a DeepSeek V4 Flash call (cost: ~$0.00014/1K input tokens) determines whether news since last analysis constitutes a "major fundamental shift." If not, the prior analysis is deep-copied with updated price. This saves ~$0.03-0.15 per analysis that doesn't need re-running.

---

## 2. Complete Directory Structure

```
/Users/saumya/Desktop/nivesh/
|
|-- ARCHITECTURE_MAP.md              # (THIS FILE) definitive architecture blueprint
|-- AGENTS.md                        # GitNexus AI coding guidelines for OpenCode
|-- CLAUDE.md                        # GitNexus AI coding guidelines for Claude
|-- MEGA_TODO.md                     # Master project todo list
|-- NIVESH_TODO.md                   # Nivesh-specific todos
|-- OVERNIGHT_LEDGER.md              # Cross-session project ledger
|-- migration_ledger.md              # Database/architecture migration history
|-- commit.sh                        # Git automation script
|
|-- .gitignore                       # Ignores .env, .venv, __pycache__, .db, logs, Xcode build artifacts
|-- .gitnexus/                       # GitNexus index database (11,614 symbols, 24,375 relationships)
|   |-- meta.json                    # Index metadata
|   |-- parse-cache/                 # Parsed symbol cache
|
|-- .opencode/                       # OpenCode editor configuration
|   |-- opencode.json                # Loads graphify.js plugin
|   |-- plugins/graphify.js          # Dependency graph visualization plugin
|
|-- .claude/                         # Claude Code configuration
|   |-- settings.local.json          # Permissions for venv directories
|
|   ### BACKEND (Python FastAPI)
|-- backend/
|   |-- main.py                      # FastAPI app entrypoint (3042 lines) -- GOD NODE
|   |-- main_legacy_backup.py        # Previous monolithic version (archive)
|   |-- main_old_monolithic.py       # Original monolithic version (archive)
|   |-- helpers.py                   # Shared helpers, ticker constants, auth deps (593 lines)
|   |-- database.py                  # SQLAlchemy models, engine, session (800 lines)
|   |-- prompts.py                   # INDIAN_MARKET_SYSTEM_PROMPT + all agent personas (127 lines)
|   |-- requirements.txt             # Python dependency specification
|   |-- Dockerfile                   # Multi-stage Docker build (Python 3.11-slim, port 8000)
|   |-- run.sh                       # Local dev startup script
|   |-- update.sh                    # Deployment update script
|   |-- deploy_update.sh             # Remote deployment script
|   |-- nivesh.service              # systemd unit file (2 workers, auto-restart)
|   |-- .env                         # LIVE credentials (ANTHROPIC, DEEPSEEK, YOUTUBE keys)
|   |-- .env.example                 # Template for required env vars
|   |-- stockapp.db                  # SQLite database (WAL mode)
|   |-- populate_portfolio.py        # Portfolio seed data script
|   |-- portfolio_charts.py          # Portfolio chart generation (Pillow/matplotlib)
|   |-- migrate_trade_journal.py     # Trade journal migration script
|   |-- token_log.jsonl              # AI token usage audit log
|   |
|   |-- routers/                     # FastAPI route handlers (7 routers)
|   |   |-- __init__.py
|   |   |-- auth.py                  # JWT auth (login, register)
|   |   |-- analysis.py              # AI analysis (POST /analyze, GET /quick-info) -- CRITICAL
|   |   |-- portfolio.py             # Portfolio CRUD, P&L, risk, trade journal, exports (2490 lines)
|   |   |-- market.py                # Market data, indices, earnings, F&O (2157 lines)
|   |   |-- alerts.py                # Price alerts CRUD + checking
|   |   |-- user.py                  # User management, watchlist, device tokens
|   |   |-- dashboard.py             # Admin dashboard SSE streaming
|   |   |-- notifications.py         # Push notification registration + dispatch
|   |
|   |-- services/                    # Business logic services (20 files)
|   |   |-- factor_engine.py         # Technical indicators (RSI, MACD, SMA, BB, ATR, OBV, ROC)
|   |   |-- sentiment_engine.py      # FinBERT singleton (yiyanghkust/finbert-tone)
|   |   |-- news_harvester.py        # RSS news pipeline (Moneycontrol, ET, NSE)
|   |   |-- youtube_harvester.py     # YouTube Data API + yt-dlp pipeline
|   |   |-- advisor_harvester.py     # Advisor channel harvesting + stance extraction
|   |   |-- transcript_engine.py     # YouTube transcript (API + Whisper large-v3 fallback)
|   |   |-- ticker_matcher.py        # Fuzzy Hinglish ticker matching (rapidfuzz)
|   |   |-- options_scraper.py       # NSE option chain, PCR, Max Pain
|   |   |-- scraper.py               # Firecrawl + BS4 web scraping (743 lines)
|   |   |-- nse_data_provider.py     # NSE price history + fundamentals (jugaad-data / yfinance)
|   |   |-- piotroski.py             # Piotroski F-Score (9 criteria)
|   |   |-- pkscreener_runner.py     # PKScreener subprocess runner
|   |   |-- feedback_injector.py     # Epistemic feedback loop
|   |   |-- staleness.py             # Analysis staleness scoring
|   |   |-- portfolio_snapshot.py    # Daily portfolio valuation snapshots
|   |   |-- disk_cache.py            # L2 persistent filesystem cache (gzip JSON)
|   |   |-- error_telemetry.py       # Correlation ID middleware + diagnostic logging
|   |   |-- filings_extractor.py     # NSE corporate filings extraction
|   |
|   |-- tradingagents-core/          # FORKED REPO: TauricResearch/TradingAgents v0.2.5
|   |   |-- README.md                # Full TradingAgents framework documentation
|   |   |-- pyproject.toml           # Package config: Python>=3.10, langgraph, yfinance, etc.
|   |   |-- tradingagents/
|   |   |   |-- graph/               # LangGraph state graph orchestration
|   |   |   |   |-- trading_graph.py         # Main orchestrator -- GOD NODE
|   |   |   |   |-- analyst_execution.py     # Analyst node specs + wall-clock tracking
|   |   |   |   |-- conditional_logic.py     # Debate/routing logic -- GOD NODE
|   |   |   |   |-- setup.py                 # Graph wiring (StateGraph builder)
|   |   |   |   |-- propagation.py           # State initialization
|   |   |   |   |-- reflection.py            # Self-reflection on past decisions
|   |   |   |   |-- signal_processing.py     # Rating extraction
|   |   |   |   |-- checkpointer.py          # SQLite checkpoint persistence
|   |   |   |   |-- agents/
|   |   |   |   |   |-- analysts/
|   |   |   |   |   |   |-- market_analyst.py           # Technical analysis
|   |   |   |   |   |   |-- news_analyst.py             # Governance + news scanning
|   |   |   |   |   |   |-- fundamentals_analyst.py     # Financial statements
|   |   |   |   |   |   |-- sentiment_analyst.py        # Social + news sentiment (209 lines)
|   |   |   |   |   |   |-- social_media_analyst.py     # Deprecated wrapper
|   |   |   |   |   |-- managers/
|   |   |   |   |   |   |-- portfolio_manager.py        # Final decision (deep_thinking_llm)
|   |   |   |   |   |   |-- research_manager.py         # Debate synthesis (deep_thinking_llm)
|   |   |   |   |   |-- researchers/
|   |   |   |   |   |   |-- bull_researcher.py          # Bull case advocate
|   |   |   |   |   |   |-- bear_researcher.py          # Bear case advocate
|   |   |   |   |   |-- risk_mgmt/
|   |   |   |   |   |   |-- aggressive_debator.py       # High-risk champion
|   |   |   |   |   |   |-- conservative_debator.py     # Low-risk advocate
|   |   |   |   |   |   |-- neutral_debator.py          # Balanced perspective
|   |   |   |   |   |-- trader/
|   |   |   |   |   |   |-- trader.py                   # Trade proposal
|   |   |   |   |   |-- utils/
|   |   |   |   |   |   |-- agent_states.py             # TypedDicts (InvestDebateState, RiskDebateState, AgentState)
|   |   |   |   |   |   |-- agent_utils.py              # Instrument resolution, language, message clearing
|   |   |   |   |   |   |-- core_stock_tools.py         # Stock data routing
|   |   |   |   |   |   |-- technical_indicators_tools.py # Indicator routing
|   |   |   |   |   |   |-- fundamental_data_tools.py   # Fundamentals routing
|   |   |   |   |   |   |-- news_data_tools.py          # News routing
|   |   |   |   |   |   |-- market_data_validation_tools.py # Verification snapshot
|   |   |   |   |   |   |-- memory.py                   # TradingMemoryLog (append-only markdown)
|   |   |   |   |   |   |-- rating.py                   # 5-tier rating parser
|   |   |   |   |   |   |-- structured.py               # Structured output binding
|   |   |   |   |   |-- schemas.py                      # Pydantic schemas (317 lines)
|   |   |   |   |-- dataflows/                 # Data vendor implementations
|   |   |   |   |   |-- y_finance.py           # Primary yfinance data (422 lines)
|   |   |   |   |   |-- yfinance_news.py       # Yahoo Finance news (202 lines)
|   |   |   |   |   |-- indian_news.py         # Moneycontrol + ET + NSE (262 lines)
|   |   |   |   |   |-- stocktwits.py          # Public StockTwits API
|   |   |   |   |   |-- reddit.py              # Reddit JSON + Atom RSS fallback
|   |   |   |   |   |-- market_data_validator.py # Deterministic verification
|   |   |   |   |   |-- stockstats_utils.py    # Stockstats indicator calculation
|   |   |   |   |   |-- config.py             # Module-level singleton config
|   |   |   |   |   |-- interface.py           # Vendor routing system (162 lines)
|   |   |   |   |   |-- alpha_vantage_*.py     # Alpha Vantage (5 files)
|   |   |   |   |-- llm_clients/              # Multi-provider LLM abstraction
|   |   |   |   |   |-- factory.py            # Client factory (11 providers)
|   |   |   |   |   |-- base_client.py        # Abstract base + content normalization
|   |   |   |   |   |-- openai_client.py      # OpenAI + DeepSeek + xAI + Qwen + GLM + MiniMax + Ollama + OpenRouter (253 lines)
|   |   |   |   |   |-- anthropic_client.py   # Anthropic (Haiku, Sonnet, Opus)
|   |   |   |   |   |-- google_client.py      # Google Gemini
|   |   |   |   |   |-- azure_client.py       # Azure OpenAI
|   |   |   |   |   |-- capabilities.py       # Model capability table (127 lines)
|   |   |   |   |   |-- model_catalog.py      # Compiled model options (197 lines)
|   |   |   |   |   |-- validators.py         # Model validation
|   |   |   |   |   |-- api_key_env.py        # Provider-to-env-var mapping (44 lines)
|   |   |   |   |-- nivesh/                   # Nivesh-specific customizations
|   |   |   |   |   |-- context_cache.py       # Prefix-aligned context stratification (223 lines)
|   |   |   |   |   |-- reformatter.py         # Deterministic JSON reformatter (316 lines)
|   |   |   |   |   |-- subprocess_runner.py   # Subprocess isolation (225 lines)
|   |   |   |   |-- default_config.py          # Default configuration (134 lines)
|   |   |   |-- cli/                           # Interactive CLI (Typer app, 1275 lines)
|   |   |   |   |-- main.py                    # CLI entry point with Rich display
|   |   |   |   |-- utils.py                   # Interactive prompts (560 lines)
|   |   |   |   |-- models.py                  # AnalystType + AssetType enums
|   |   |   |   |-- config.py                 # CLI configuration
|   |   |   |   |-- announcements.py          # Framework announcements
|   |   |   |   |-- stats_handler.py          # Thread-safe LLM/tool call statistics
|   |   |   |   |-- static/                   # CLI static assets
|   |   |   |-- tests/                        # 25+ test files
|   |
|   |-- tests/                            # Backend test suite
|   |   |-- conftest.py                   # Pytest fixtures
|   |   |-- test_api.py                   # API endpoint tests
|   |   |-- test_backend_tasks.py         # Background task tests
|   |   |-- test_comprehensive.py         # Comprehensive integration tests
|   |   |-- test_e2e_api.py              # End-to-end API tests
|   |   |-- TEST_INVENTORY.md            # Test inventory document
|   |   |-- test_model_names.py          # AI model name validation
|   |-- tests_suite/                      # Second test suite
|       |-- test_ai_mock_comprehensive.py
|       |-- test_api_endpoints_comprehensive.py
|       |-- test_database_comprehensive.py
|       |-- test_scraper_mock_comprehensive.py
|       |-- test_staleness_comprehensive.py
|       |-- test_ticker_matcher_comprehensive.py
|
|   ### iOS FRONTEND (SwiftUI)
|-- ios/
|   |-- StockApp/
|   |   |-- stockme/stockme/              # Xcode project root
|   |   |   |-- stockmeApp.swift           # App entry: @main, env objects, onboarding/disclaimer/biometric/content
|   |   |   |-- AppDelegate.swift          # APNs push notification bridge, deep-link handling
|   |   |   |-- ContentView.swift          # Auth gate: login or 5-tab navigation shell
|   |   |   |-- LaunchSequenceView.swift   # Animated Rs medallion + guilloche launch splash (106 lines)
|   |   |   |-- AuthManager.swift          # Login/register/logout, token management, biometric check
|   |   |   |-- NetworkManager.swift        # Singleton async HTTP client (981 lines) -- GOD NODE
|   |   |   |-- NetworkManager+Sidebar.swift # Extended market data fetchers (354 lines)
|   |   |   |-- HomeFeedService.swift       # Direct URLSession feed fetcher (50 lines)
|   |   |   |-- ValuationCalendarService.swift # Valuation history fetcher (22 lines)
|   |   |   |-- Models.swift                # ALL Codable models (1685 lines) -- GOD NODE (CodingKeys)
|   |   |   |-- HomeFeedModels.swift        # Feed-specific models (135 lines)
|   |   |   |-- StockDatabase.swift         # ~290 in-memory NSE stock entries with search (385 lines)
|   |   |   |-- NotificationManager.swift   # APNs auth, token sync, local notifications (101 lines)
|   |   |   |-- AppSoundManager.swift       # Rupee rustle audio (AVAudioPlayer)
|   |   |   |-- HomeFeedViewModel.swift     # Feed VM with 15-min cache cooldown (30 lines)
|   |   |
|   |   |-- Views/                          # 23 SwiftUI screens
|   |   |   |-- HomeScreen.swift            # Dashboard: portfolio hero, indices, watchlist, morning brief, 16 sections
|   |   |   |-- AnalysisScreen.swift        # Stock analysis: 5 sub-tabs, 11 charts, live price polling (1946 lines)
|   |   |   |-- PortfolioScreen.swift       # Holdings, P&L, watchlist, risk analysis, export (1650 lines)
|   |   |   |-- MarketsView.swift           # Markets hub with 5 sub-tabs
|   |   |   |-- EarningsDashboardView.swift # Earnings feed + calendar + progress (1769 lines)
|   |   |   |-- SearchScreen.swift          # Stock search + 8 screener presets (504 lines)
|   |   |   |-- AlertsScreen.swift          # Price alert management
|   |   |   |-- TradeJournalScreen.swift    # Trading journal with stats
|   |   |   |-- ExpertNetworkView.swift     # Advisor intelligence, expert posts
|   |   |   |-- NewsMultimediaView.swift    # Real-time financial newswire
|   |   |   |-- TechnicalMomentumView.swift # MA crossover lists
|   |   |   |-- PreIPOMarketplaceView.swift # Unlisted shares marketplace
|   |   |   |-- CompareScreen.swift         # Side-by-side stock comparison
|   |   |   |-- HistoryScreen.swift         # Past analysis reports
|   |   |   |-- ValuationCalendarView.swift # Portfolio valuation history calendar
|   |   |   |-- SettingsScreen.swift        # Server URL, dark mode, biometric toggles, dev tools
|   |   |   |-- LoginScreen.swift           # Username/password authentication
|   |   |   |-- OnboardingScreen.swift      # First-launch walkthrough
|   |   |   |-- DisclaimerScreen.swift      # SEBI disclaimer acceptance
|   |   |   |-- TutorialOverlayView.swift   # 10-step spotlight tutorial
|   |   |   |-- NiveshNavigationSidebar.swift # Market intelligence sidebar (20 sections)
|   |   |   |-- DalalStreetConsensusCard.swift # Advisory consensus
|   |   |   |-- AdvisoryMatrixCard.swift    # Per-stock street intelligence matrix
|   |   |
|   |   |-- Components/                     # Reusable UI components (5 files)
|   |   |   |-- SharedComponents.swift       # AppHeader, StockRow, IndexChip, SectionHeader (317 lines)
|   |   |   |-- BanknoteErrorCanvas.swift    # Banknote-styled error display card
|   |   |   |-- NewsCardView.swift           # News article card with hero image
|   |   |   |-- YouTubeCardView.swift        # YouTube video card with thumbnail
|   |   |   |-- AdvisorBioCard.swift         # SEBI-registered advisor bio card
|   |   |
|   |   |-- Charts/                         # Swift Charts (1 file, 925 lines)
|   |   |   |-- StockCharts.swift            # 11 native Swift Charts
|   |   |
|   |   |-- Utilities/                      # Utility files (6 files)
|   |   |   |-- Theme.swift                  # Design system: 20+ color tokens, typography, spacing (304 lines)
|   |   |   |-- IndianFormatter.swift        # Indian number formatting (Crores/Lakhs), elapsed time
|   |   |   |-- HapticManager.swift          # Haptic feedback engine + EKPressHapticStyle
|   |   |   |-- Extensions.swift             # Color(hex:), banknoteCard, shimmerPlaceholder, staggerAppear
|   |   |   |-- ErrorDiagnoser.swift         # GlobalErrorDiagnoser singleton, error card UI (290 lines)
|   |   |   |-- TutorialManager.swift        # 10-step tutorial state manager
|   |   |
|   |   |-- stockme.xcodeproj/              # Xcode project metadata
|   |       |-- project.pbxproj             # Build settings, file references, target config
|   |
|   |-- HOW_THE_ANALYSIS_WORKS.md           # User-facing explanation (non-technical)
|   |-- NIVESH_FULL_CONTEXT.md              # Full app context for LLM ingestion (93 lines)
|   |-- LLM_CREDITS_USAGE.md                # Exhaustive LLM API credit usage audit
|   |-- backend_nivesh_context.md           # Backend context for iOS developers
|   |-- frontend_nivesh_context.md          # Frontend context for iOS developers
|   |-- generate_icons.py                   # App icon generation script (Pillow)
|
|   ### TASK FILES & PROJECT MANAGEMENT
|-- tasks_earnings_feed_calendar.md          # Earnings feed + calendar implementation plan
|-- tasks_ideas_sprint.md                    # Ideas sprint tasks
|-- tasks_market_implementation.md           # Market data endpoint implementation
|-- tasks_notifications_system.md            # Push notification system plan
|-- tasks_performance_fixes.md               # Performance optimization tasks
|-- tasks_ui_redesign.md                     # UI redesign tasks
```

---

## 3. Complete Tech Stack

```
+--------------------------------------------------------------------------------------+
|                              NIVESH (nivesh) -- TECH STACK                              |
+--------------------------------------------------------------------------------------+
|                                                                                       |
|  +---- FRONTEND (iOS) ---------------------------------------------------------------------------+
|  |  Language:      Swift 5.9+                                                     |
|  |  Framework:     SwiftUI (iOS 16+) + Swift Charts                                |
|  |  Architecture:  MVVM with @MainActor ViewModels, async/await, singletons        |
|  |  State:         @StateObject, @ObservedObject, @Published, @AppStorage          |
|  |  Persistence:   UserDefaults + @AppStorage + GZIP-compressed JSON file storage  |
|  |  Audio:         AVAudioPlayer (rupee_rustle.mp3)                                |
|  |  Haptics:       UIKit haptics (UIImpactFeedbackGenerator, UISelectionFeedback)  |
|  |  Notifications: UserNotifications (APNs)                                        |
|  |  Auth:          LocalAuthentication (Face ID / Touch ID)                         |
|  |  HTTP:          URLSession async/await with 1200s timeout                       |
|  |  Logging:       os_log (unified logging)                                        |
|  |  Project:       Xcode 15+ (stockme.xcodeproj)                                   |
|  +---------------------------------------------------------------------------------+
|                                                                                       |
|  +---- BACKEND API ----------------------------------------------------------------------------+
|  |  Language:      Python 3.11+                                                    |
|  |  Framework:     FastAPI + uvicorn (2 workers)                                   |
|  |  ORM:           SQLAlchemy 2.0 (declarative, sessionmaker)                      |
|  |  DB:            SQLite (WAL mode, dev) / PostgreSQL (prod via DATABASE_URL)     |
|  |  Auth:          bcrypt (12 rounds) + JWT (HS256, 72h expiry)                    |
|  |  Serialization: Pydantic v2 (21 request/response models)                        |
|  |  Scheduler:     APScheduler (9 recurring jobs)                                  |
|  |  Async:         asyncio + ThreadPoolExecutor (blocking I/O bridge)              |
|  |  Cache:         L1 in-memory dict (per-endpoint TTL), L2 gzip JSON disk cache  |
|  |  Concurrency:   threading.Semaphore (per-user, max 2), multiprocessing.Process  |
|  |  Deployment:    Docker (multi-stage, Python 3.11-slim) / systemd                |
|  |  Reverse Proxy: Nginx (implied by systemd setup on 165.22.221.18)               |
|  |  Middleware:    CORS + rate limiting + security headers + correlation ID        |
|  +---------------------------------------------------------------------------------+
|                                                                                       |
|  +---- AI PIPELINE ----------------------------------------------------------------------------+
|  |  Framework:    LangGraph (StateGraph with cyclic debate loops)                  |
|  |  Orchestrator: TradingAgentsGraph (OptimizedTradingAgentsGraph subclass)        |
|  |  LLMs:         Claude 3.5 Haiku (Tier 2 deep thinking)                         |
|  |                Claude 3.5 Sonnet (reformatter, primary and fallback)              |
|  |                DeepSeek V4 Flash / deepseek-chat (Tier 1 bulk processing)       |
|  |  Providers:    11 supported: OpenAI, Anthropic, Google, xAI, DeepSeek,         |
|  |                Qwen (intl/CN), GLM (intl/CN), MiniMax (intl/CN),               |
|  |                OpenRouter, Azure, Ollama                                       |
|  |  Models:       Catalogs for all providers with quick/deep tier assignments      |
|  |  Graph Nodes:  12 agent nodes + 4 tool nodes + 4 clear nodes + 1 merge node    |
|  |  Parallelism:  configurable analyst_concurrency_limit (default 1, sequential)   |
|  |  Memory:       Append-only TradingMemoryLog (markdown, SQLite checkpoints)      |
|  |  Cost:         ~$0.03-0.15 per analysis (DeepSeek ~21-54x cheaper than Sonnet) |
|  +---------------------------------------------------------------------------------+
|                                                                                       |
|  +---- DATA SOURCES ---------------------------------------------------------------------------+
|  |  Market:       yfinance (Yahoo Finance, primary + BSE fallback)                |
|  |  Options:      nseindia.com/api/option-chain-equities (15-min cache)           |
|  |  Fundamentals: yfinance info + jugaad-data (NSE India)                         |
|  |  News:         Yahoo Finance News + Moneycontrol RSS + Economic Times RSS      |
|  |  YouTube:      YouTube Data API v3 + yt-dlp (fallback)                         |
|  |  Transcripts:  youtube-transcript-api + faster-whisper large-v3 (CPU, int8)    |
|  |  Scraping:     Firecrawl (primary) + requests/BeautifulSoup (fallback)         |
|  |  NLP:          FinBERT (yiyanghkust/finbert-tone) on CPU                       |
|  |  Screening:    PKScreener CLI (subprocess, 30s timeout)                        |
|  |  Matching:     rapidfuzz (token_set_ratio, cutoff=82)                          |
|  |  Technicals:   ta library (RSI, MACD, SMA, BB, ATR, OBV, ROC, volume ratio)   |
|  |  Fundamentals: Piotroski F-Score (9 criteria, yfinance data)                   |
|  |  Social:       StockTwits (public, no API key) + Reddit (JSON/Atom RSS)        |
|  +---------------------------------------------------------------------------------+
|                                                                                       |
|  +---- PROJECT INTELLIGENCE -------------------------------------------------------------------+
|  |  Indexing:     GitNexus (11,614 symbols, 24,375 relations, 179 flows)          |
|  |  Tooling:      OpenCode + Claude Code + graphify.js plugin                     |
|  |  Discipline:   AGENTS.md + CLAUDE.md enforce GitNexus rules                    |
|  |  Arch doc:     ARCHITECTURE_MAP.md (this file, ~3000+ lines)                  |
|  |  Skills:       10+ agent skills (brainstorming, TDD, design-taste, etc.)       |
|  +---------------------------------------------------------------------------------+
+--------------------------------------------------------------------------------------+
```
## 4. Backend Architecture (FastAPI)

### 4.1. Entry Point: `backend/main.py` (2221 lines -- GOD NODE)

This is the **central orchestrator** of the entire backend. It manages:

**Application Lifecycle:**
1. Loads `.env` via `python-dotenv`
2. Initializes database via `database.init_db()` -- creates tables, seeds data
3. Registers 8 routers via `app.include_router()`
4. Configures CORS middleware (allows `*` origins for development)
5. Sets up rate limiting middleware (120 requests/60s per IP)
6. Configures security headers (X-Content-Type-Options, X-Frame-Options, X-XSS-Protection, Referrer-Policy)
7. Installs CorrelationIDMiddleware from `services.error_telemetry`
8. Initializes APScheduler with 9 recurring jobs
9. Loads NSE stock directory into memory (~280 stocks, sub-millisecond search)
10. Fetches ASM/GSM surveillance lists from NSE API (6-hour cache)

**Key Global State (Thread-Safe via `threading.Lock`):**
- `_quick_info_cache`: L1 in-memory cache for `/quick-info` (15-min TTL)
- `_running_analyses`: Set of user IDs currently being analyzed
- `_active_analyses`: Dict tracking analysis progress stages
- `_completed_analyses`: Deque of last 200 completed analyses
- `_request_log`: Deque of last 500 API requests
- `_harvest_status`: Dict tracking 4 harvest pipeline statuses
- `_token_stats`: Cumulative AI token usage + last 50 entries
- `_indices_cache`: Market indices cache (5-min TTL)
- `_asm_gsm_cache`: NSE surveillance lists (6-hour TTL, TTL=21600s)
- `_nse_session`: requests.Session with Chrome UA for NSE APIs

**Key Functions Defined Here:**
- `format_indian_currency(value)` -- Indian number format (lakhs/crores)
- `_ban_western_scale(text)` -- Guard: rejects Million/Billion in output
- `_dash_update_harvest(key, status, result)` -- Dashboard SSE harvest status push
- `_dash_start_job(job_id, ticker, exchange, user_id)` -- Dashboard SSE job start
- `_dash_end_job(job_id, result, error, killed)` -- Dashboard SSE job end
- `_dash_log_request(method, path, params, status, duration_ms)` -- Dashboard SSE request log
- `_log_token_usage(endpoint, usage)` -- Token audit logging to `token_log.jsonl`
- `_check_rate_limit(client_ip)` -- IP-based rate limiting (120/min)
- `get_current_user_id(authorization)` -- Optional JWT auth (dev bypass: "admin" -> user_id=1)
- `require_auth(authorization)` -- Mandatory JWT auth -> 401
- `require_admin(authorization)` -- Admin check (saumya, nirav) -> 403
- `_resolve_ticker(ticker, exchange)` -- NSE/BSE ticker suffix resolution
- `_yf_fetch_info(sym)` -- yfinance info fetch with ticker validation
- `_yf_price(ticker_sym)` -- Current price fetch (yfinance, tuple of (price, change))
- `health_endpoint()` -- GET /health (liveness probe)
- `liveness_probe()` -- GET /api/v1/liveness (detailed health check)
- `dashboard_html()` -- Admin dashboard HTML page
- `dashboard_data()` -- Admin dashboard JSON (analyses, harvest, tokens)
- `admin_harvest_youtube()` -- POST /admin/harvest/youtube (background task trigger)
- `admin_harvest_advisors()` -- POST /admin/harvest/advisors (background task trigger)
- `admin_harvest_news()` -- POST /admin/harvest/news (background task trigger)
- `_run_youtube_harvest_bg()`, `_run_advisor_harvest_bg()`, `_run_news_harvest_bg()` -- Background runners
- `_start_advisor_scheduler()`, `_stop_advisor_scheduler()` -- APScheduler lifecycle

**Note:** The core AI analysis pipeline (`analyze()`, `run_trading_agents()`, `reformat_with_claude()`, `_normalize_response()`, `build_ta_config()` etc.) has been **extracted** to `services/orchestrator.py` (1093 lines). See Section 5 for the full pipeline architecture.

### 4.1a. AI Orchestrator: `backend/services/orchestrator.py` (1093 lines)

The **AI analysis engine** formerly in main.py, extracted to its own service module:

**Key Functions:**
- `analyze(ticker, exchange, user_id, deep_scan)` -- The core AI analysis function (stages 1-7), orchestrates multi-agent debate + reformatting + normalization
- `run_trading_agents(full_ticker, analysis_date)` -- Invokes TradingAgentsGraph LangGraph workflow (12-agent debate)
- `build_ta_config()` -- Builds two-tier AI provider configuration (DeepSeek Flash + Claude Haiku)
- `reformat_with_claude(raw_output, ticker, exchange, prior_analyses)` -- 3-phase reformatter pipeline (Claude Sonnet -> DeepSeek -> fallback)
- `_normalize_response(result)` -- Sanitizes JSON for iOS consumption (signal map, field coercion, defaults)
- `_extract_json_from_text(text)` -- Multi-strategy JSON extraction from LLM output
- `_deepseek_chat(messages, ...)` -- DeepSeek API client with retry logic
- `create_optimized_analyst_node(llm, persona, report_key, tools)` -- LangGraph node factory
- `_get_deepseek_client()` -- Client singleton with auto-reconnect

### 4.2. Authentication System

**Auth Flow:**
1. User sends POST `/login` with `{username, password}`
2. Server looks up `User` in DB, verifies password against `password_hash`
3. Password verification supports THREE formats:
   - **bcrypt** (`$2` prefix) -- current standard, 12 rounds
   - **SHA-256 with salt** (32 hex chars + `:` + hash) -- legacy
   - **Plain SHA-256** (64 hex chars) -- legacy fallback
4. On success: JWT token created with `HS256` algorithm, 72-hour expiry
5. Token contains `{sub: user_id, iat: timestamp, exp: timestamp}`
6. Client stores token in `UserDefaults` (iOS) and sends as `Authorization: Bearer {token}`

**Auth Dependency Injection:**
- `get_current_user_id()` -- Optional auth, returns `int | None`. Reads `Authorization` header, verifies token. Dev bypass: token `"admin"` maps to user_id=1.
- `require_auth()` -- Mandatory auth, raises HTTP 401 if missing
- `require_admin()` -- Checks admin set (populated at startup with "saumya" and "nirav"), raises HTTP 403

### 4.3. Router Subsystem

#### `routers/auth.py` -- Authentication Router
| Endpoint | Method | Rate Limit | Description |
|----------|--------|------------|-------------|
| `/login` | POST | Per-IP | Login with username/password, returns JWT + user profile |
| `/register` | POST | Per-IP | Register new user (rate-limited to prevent spam) |

#### `routers/analysis.py` -- Analysis Router (CRITICAL -- 1460 lines)

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/quick-info` | GET | None | Stock quick info with 2-level cache (L1 in-memory 15min + L2 disk) |
| `/analyze` | POST | Optional | Full AI analysis with multiprocessing isolation |
| `/analyze/batch` | POST | Optional | Batch analysis via Anthropic batch API |
| `/analyze/batch/{batch_id}` | GET | Optional | Poll batch analysis status |
| `/api/v1/technical-signals` | GET | None | PKScreener technical signals for ticker |
| `/api/v1/home-feed` | GET | Auth | Personalized home feed (news, red flags, YouTube) |
| `/screener` | GET | None | Stock screener presets (quality_value, promoter_conviction, fii_accumulation, turnaround, 52w_low_bullish) |
| `/daily-action/{user_id}` | GET | Auth | Daily action items (signal warnings + timeframe conflicts) |
| `/token-stats` | GET | Admin | Cumulative token usage stats (input/output/cost per endpoint) |

**The `/analyze` Endpoint -- Detailed Execution Flow:**

POST /analyze
- Input: {ticker: str, exchange: str="NSE", user_id: int?, deep_scan: bool=false}
- Validation: ticker regex ^[A-Z0-9.&]{1,20}$, exchange in {NSE, BSE}
- Duplicate guard: Check _running_analyses set -> 429 if already running
- Concurrency guard: threading.Semaphore (max 2) -> 429 if limited
- Multiprocessing launch:
  - Create multiprocessing.Queue
  - Spawn Process(target=_run_analysis_worker, args=(queue, ticker, exchange, user_id, deep_scan))
  - Process runs: from main import analyze; result = analyze(...); queue.put(result)
- Poll loop (0.5s interval):
  - Check request.is_disconnected() -> on disconnect: p.terminate(), return 499
  - Check queue for result
- On timeout/error: p.terminate(), return 500 with error details
- On success: return normalized StockAnalysis JSON

**The `/quick-info` Endpoint -- Cache Architecture:**

GET /quick-info?ticker=X&exchange=NSE
- Build cache_key from ticker + exchange
- L1 Check: _quick_info_cache dict -> HIT: return immediately
- L2 Check: disk_cache.get("yfinance", f"quick_info_{cache_key}") -> HIT: populate L1, return
- MISS: Fetch from yfinance:
  - Try ticker.NS (NSE)
  - Fallback: ticker.BO (BSE)
  - Fetch: info, history(90d), recommendations, news, holders
  - Extract: price, change, PE, D/E, promoter holding, week52, sparkline, news
  - Cache in L1 (15min TTL) and L2 (persistent)
  - Return QuickInfo JSON
- Error: Return empty/safe defaults (price=0, no crash)

#### `routers/portfolio.py` -- Portfolio Router (2566 lines -- LARGEST router)

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/portfolio/signal-warnings` | GET | Auth | Signal change warnings for holdings |
| `/portfolio/{user_id}` | GET | Optional | Full portfolio with live prices, P&L, staleness |
| `/portfolio/history/{user_id}` | GET | Auth | Portfolio valuation history over time |
| `/fundamentals/piotroski/{ticker}` | GET | None | Piotroski F-Score (disk-cached) |
| `/morning-summary/{user_id}` | GET | Auth | AI-generated morning brief (2-hour cache) |
| `/portfolio` | POST | Auth | Add holding to portfolio |
| `/portfolio/add` | POST | Auth | Add holding (alternative endpoint) |
| `/portfolio/remove` | DELETE | Auth | Remove holding |
| `/portfolio/update` | PUT | Auth | Update shares/buy price |
| `/portfolio/note` | PUT | Auth | Save note on holding |
| `/portfolio/risk-analysis/{user_id}` | GET | Auth | Portfolio beta, concentration, correlation |
| `/portfolio/red-flags/{user_id}` | GET | Auth | Critical/warning/watch flags for holdings |
| `/portfolio/timeframe-conflicts/{user_id}` | GET | Auth | Short-term vs long-term upside conflicts |
| `/portfolio/export/excel/{user_id}` | GET | Auth | Export portfolio to Excel (openpyxl) |
| `/portfolio/export/pdf/{user_id}` | GET | Auth | Export portfolio to PDF (fpdf2) |
| `/api/v1/portfolio/advisor-consensus` | GET | Optional | Advisor consensus from YouTube harvest |
| `/api/v1/portfolio/charts/{user_id}` | GET | Auth | Portfolio chart images |
| `/api/v1/portfolio/valuation-history` | GET | Auth | Valuation history with summary stats |
| `/macro-impact/{user_id}` | GET | Auth | Macro sensitivity analysis for portfolio holdings |
| `/api/v1/market/net-worth-ledger/{user_id}` | GET | Auth | Latest net worth snapshot with delta/peak/trough |
| `/trade-journal/{user_id}` | GET | Auth | Trade journal entries |
| `/trade-journal` | POST | Auth | Add trade entry |
| `/trade-journal/{entry_id}` | PUT | Auth | Update trade entry |
| `/trade-journal/{entry_id}` | DELETE | Auth | Delete trade entry |
| `/trade-journal/{user_id}/stats` | GET | Auth | Trade journal stats + pattern detection |

**Portfolio Risk Analysis Computation (DETAILED):**

GET /portfolio/risk-analysis/{user_id}
- For each holding:
  - Compute beta: covariance(returns, nifty_returns) / variance(nifty_returns)
    - Uses last 90 days of daily returns (min 10 data points)
  - Annualized volatility: std(returns) * sqrt(252) * 100
  - Sector assignment from in-memory NSE_DIRECTORY
- Portfolio beta: weighted average of individual betas
- Risk score: min(10, max(1, round(beta * 5)))
  - <= 3: "Low"
  - <= 6: "Moderate"
  - <= 8: "High"
  - > 8: "Very High"
- Sector concentration: % of total value per sector
- Concentration risks: stocks >20% of portfolio (max 3)
- Pearson correlation: highest correlated pair (min 10 common trading days)
- Return: {beta, risk_score, risk_score_label, sector_concentration[], concentration_risks[], correlation_pair}

**Morning Summary Generation (DETAILED):**

GET /morning-summary/{user_id}
- Check _morning_cache (TTL=7200s) -> HIT: return cached
- Build portfolio text: for each holding (ticker, price, day_change, P&L, signal)
- Fetch indices: _get_indices_data()
- Build prompt for Claude Haiku:
  - "You are a Dalal Street portfolio analyst... 4-6 bullet points... Indian number format (lakhs/crores)... no text before/after JSON"
- Call Claude Haiku (claude-haiku-4-5-20251001)
  - Fallback if ANTHROPIC_API_KEY missing: generate deterministic summary
- Parse JSON: {summary: str, movers: str, mood: str}
  - Validate mood in {positive, cautious, negative}
- Priority items:
  - Level 1: Triggered price alerts (from PriceTarget table)
  - Level 2: Signal flips in last 24h for held stocks (from SignalEvent table)
- Cache for 2 hours
- Return: {summary, movers, mood, generated_at, priority_items}

**Red Flags Detection (DETAILED):**

GET /portfolio/red-flags/{user_id}
- CRITICAL flags:
  - Promoter pledging > 30% (from AnalysisHistory.promoter_pledged_pct)
  - GSM-listed (from NSE surveillance API, 6h cache)
- WARNING flags:
  - ASM-listed (short or long term)
  - Bearish signal flip in last 30 days (from SignalEvent table)
  - Promoter pledging increase > 5pp in last 3 analyses
- WATCH flags:
  - FII holding declining for 3+ consecutive periods (from last 4 AnalysisHistory entries)
- Summary generation:
  - If DEEPSEEK_API_KEY set: call DeepSeek V4 Flash for 3-sentence risk summary
  - Fallback: concatenate flag descriptions
- Return: {flags[], summary, total_flags, critical, warnings, watches}

#### `routers/market.py` -- Market Data Router (2157 lines)

| Endpoint | Method | Cache | Description |
|----------|--------|-------|-------------|
| `/market-indices` | GET | 5min | Live Nifty/Sensex/Bank/IT/Midcap |
| `/nifty-history` | GET | None | Nifty 50 historical prices |
| `/quarterly-financials` | GET | None | Quarterly revenue/profit + promoter history |
| `/macro-strip` | GET | None | USD/INR, Crude, Brent, India VIX, RBI rate |
| `/earnings-calendar` | GET | None | Upcoming earnings for holdings |
| `/analyst-ratings` | GET | None | Broker recommendations (tail 10) |
| `/ipo-calendar` | GET | None | Upcoming IPOs (hardcoded) |
| `/sector-weekly` | GET | None | 12 sector ETFs weekly change |
| `/search` | GET | None | In-memory NSE search (<5ms) |
| `/sector-performance` | GET | 10min | 8 sector indices |
| `/api/v1/market/pulse` | GET | 15min | Market indices + A/D breadth |
| `/api/v1/market/momentum` | GET | 15min | Bullish/bearish MA crossovers |
| `/api/v1/market/macro-alternatives` | GET | 15min | Commodities, rates, instruments |
| `/api/v1/market/institutional-flow` | GET | 15min | Top 10 mutual funds |
| `/api/v1/market/dashboard` | GET | 15min | All 4 feeds combined (parallel fetch) |
| `/api/v1/market/dashboard-pulse` | GET | 15min | Extended dashboard (pulse + momentum + sync + YoY + cap index) |
| `/api/v1/market/institutional-leaderboard` | GET | 15min | Top FII/DII holdings leaderboard |
| `/api/v1/earnings/progress` | GET | None | Earnings declaration progress |
| `/api/v1/earnings/sync-ratio` | GET | None | Earnings sync ratio between NSE and DB |
| `/api/v1/earnings/yoy-aggregate` | GET | None | YoY earnings aggregate statistics |
| `/api/v1/earnings/feed` | GET | None | Ranked earnings feed (3 sort modes) |
| `/api/v1/earnings/calendar` | GET | None | Earnings calendar with sparklines |
| `/api/v1/earnings/estimates` | GET | None | Forward EPS/revenue estimates |
| `/api/v1/earnings/post-result-movers` | GET | None | Post-result price movers |
| `/api/v1/earnings/alerts` | GET/POST/DELETE | None | Earnings alert CRUD |
| `/api/v1/options/chain/{ticker}` | GET | 15min | F&O option chain with PCR/Max Pain |
| `/api/v1/ideas/advisors` | GET | None | SEBI-registered advisor biographies |
| `/api/v1/ideas/feed` | GET | None | Text advisory feed with sentiment filter |
| `/api/v1/admin/error-logs` | GET | None | Market error logs (admin) |
| `/api/v1/admin/earnings-errors` | GET | None | Earnings error logs (admin) |
| `/api/v1/admin/ideas-errors` | GET | None | Ideas error logs (admin) |

#### `routers/alerts.py` -- Alerts Router

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/alerts/add` | POST | Auth | Create price alert (direction: above/below) |
| `/alerts/remove` | DELETE | Auth | Remove price alert |
| `/alerts/check/{user_id}` | GET | Auth | Check pending alerts against live prices |
| `/alerts/{user_id}` | GET | Auth | List all alerts with distance % |

**Alert Checking Logic:**

GET /alerts/check/{user_id}
- Fetch all non-triggered PriceTargets for user
- For each alert:
  - Fetch current price via _yf_price(_to_ns(ticker))
  - If direction == "above": triggered if current >= target_price
  - If direction == "below": triggered if current <= target_price
  - If triggered: set alert.triggered = True in DB
- Return: {newly_triggered: [{id, ticker, target_price, direction, current_price}]}

#### `routers/dashboard.py` -- Dashboard Router

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/v1/dashboard/stream` | GET | Admin | SSE stream (2s interval) of active analyses, harvest status, token stats |

**SSE Event Format:**
data: {"active_analyses": [...], "recent_analyses": [...], "harvest_status": {...}, "token_stats": {...}, "timestamp": "..."}
(blank line separator)

#### `routers/notifications.py` -- Notification Router

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/v1/notifications/register` | POST | Auth | Register device token (upsert) |
| `/api/v1/dev/push-mock` | POST | Admin | Send mock push notification (logs only, no real APNs) |
| `/api/v1/admin/notification-errors` | GET | Admin | Fetch 50 most recent notification errors |

### 4.4. Database Schema (SQLAlchemy, 21 Models)

**Table: `users`** -- id (PK), username (UNIQUE), password_hash, display_name, created_at

**Table: `portfolio`** -- id (PK), user_id (FK -> users), ticker, company_name, shares, buy_price, group_name (holdings/watchlist), notes, created_at

**Table: `analysis_history`** -- id (PK), user_id (FK -> users, nullable), ticker (INDEXED), analysis_date, signal, confidence_pct, target_short/medium/long, current_price_inr, promoter_pledged_pct, promoter_pledged_trend, raw_output (TEXT), full_json (GZIP TEXT), outcome_delta_pct, was_correct, outcome_checked_at, created_at

**Table: `signal_events`** -- id (PK), ticker (INDEXED), from_signal, to_signal, event_date, created_at

**Table: `price_targets`** -- id (PK), user_id (FK -> users), ticker, target_price, direction (above/below), triggered (bool), created_at

**Table: `trade_journal`** -- id (PK), user_id (FK -> users), ticker, action (BUY/SELL/HOLD/WATCH), price_at_time, reason_text, outcome_text, company_name, mood, updated_at, created_at

**Table: `device_tokens`** -- id (PK), user_id (FK -> users), device_token (UNIQUE), platform (default "ios"), created_at, updated_at

**Table: `advisor_insights`** -- id (PK), ticker (INDEXED), advisor_name, channel_id, video_id, video_title, video_url, published_at, transcript_source, stance, confidence, catalyst_summary, raw_snippet, view_count, created_at. UNIQUE(video_id, ticker). INDEX(ticker, published_at)

**Table: `news_articles`** -- id (PK), source, ticker (INDEXED), headline, summary, body_text, image_url, article_url (UNIQUE), published_at, sentiment, sentiment_score (-1 to +1), sentiment_label, is_red_flag, created_at

**Table: `youtube_videos`** -- id (PK), video_id (UNIQUE), channel_name, title, description_snippet, channel_url, thumbnail_url, video_url, published_at, view_count, duration_seconds, tickers_mentioned, created_at, harvested_at, matched_ticker (INDEXED), source, sebi_reg

**Table: `portfolio_valuation_history`** -- id (PK), user_id (INDEXED), snapshot_date (ISO), total_value, total_invested, total_pnl, pnl_percent, nifty_close, created_at. UNIQUE(user_id, snapshot_date)

**Table: `pkscreener_signals`** -- id (PK), ticker (INDEXED), signal_date, screen_result, breakout, consolidating, rsi, macd_signal, ma_signal, volume_signal, pattern, technical_score (0.0-1.0), created_at. UNIQUE(ticker, signal_date)

**Additional Tables (9 more):**
- `macro_events`: Economic calendar events (title, date, impact level, consensus, actual, prior)
- `net_worth_ledger`: Daily net worth snapshots (user_id, snapshot_date, total_value, daily_delta, peak/trough, top_gainer/loser)
- `market_error_logs`: Error telemetry (timestamp, component, error_message, context_ticker)
- `earnings_alerts`: User earnings reminders (user_id, ticker, earnings_date)
- `earnings_error_logs`: Earnings pipeline telemetry (timestamp, module, error_trace, failed_ticker)
- `notification_error_logs`: Push notification telemetry (timestamp, failure_point, error_trace, target_device)
- `advisor_biographies`: SEBI advisor details (advisor_name, sebi_reg_number, experience_years, analytical_framework, full_biography_text)
- `text_advisory_insights`: Text-based advisory (advisor_id, timestamp, content_text, target_ticker, extracted_sentiment)
- `ideas_error_logs`: Ideas workspace telemetry (timestamp, module, error_trace, context_ticker)

### 4.5. Services Subsystem (20 Files + orchestrator.py)

| Service | File | Lines | Dependencies | Purpose |
|---------|------|-------|--------------|---------|
| factor_engine | services/factor_engine.py | ~300 | ta, pandas, numpy | Technical indicators (RSI, MACD, SMA, BB, ATR, OBV, ROC) |
| sentiment_engine | services/sentiment_engine.py | ~120 | transformers (FinBERT) | NLP sentiment scoring (singleton) |
| news_harvester | services/news_harvester.py | 173 | feedparser, newspaper3k, database | RSS news pipeline (4 feeds) |
| youtube_harvester | services/youtube_harvester.py | 469 | google-api-python-client, yt-dlp | YouTube channel + portfolio harvesting |
| advisor_harvester | services/advisor_harvester.py | ~700 | yt-dlp, DeepSeek API, database | Advisor stance extraction + outcome evaluation |
| transcript_engine | services/transcript_engine.py | 295 | youtube-transcript-api, faster-whisper | Transcript fetching (API + local Whisper) |
| ticker_matcher | services/ticker_matcher.py | 316 | rapidfuzz, sqlite3, database | Fuzzy Hinglish ticker matching |
| options_scraper | services/options_scraper.py | 192 | requests, disk_cache | NSE option chain, PCR, Max Pain |
| scraper | services/scraper.py | 743 | firecrawl-py, requests, bs4, lxml, yfinance | Web scraping (Firecrawl + BS4 fallback) |
| nse_data_provider | services/nse_data_provider.py | 148 | jugaad-data, yfinance, disk_cache | NSE price history + fundamentals |
| piotroski | services/piotroski.py | ~100 | yfinance, numpy | Piotroski F-Score (9 criteria) |
| pkscreener_runner | services/pkscreener_runner.py | 190 | subprocess, database | PKScreener CLI wrapper |
| feedback_injector | services/feedback_injector.py | 133 | yfinance, database | Epistemic feedback loop |
| staleness | services/staleness.py | 70 | None (pure functions) | Analysis staleness scoring |
| portfolio_snapshot | services/portfolio_snapshot.py | 97 | yfinance, database | Daily portfolio valuation snapshots |
| disk_cache | services/disk_cache.py | 110 | gzip, json, hashlib, pathlib | L2 persistent filesystem cache |
| error_telemetry | services/error_telemetry.py | 211 | database, starlette | Correlation ID middleware + diagnostic logging |
| filings_extractor | services/filings_extractor.py | 142 | requests, bs4, database | NSE corporate filings extraction |
## 5. AI ANALYSIS PIPELINE -- THE COMPLETE ARCHITECTURE

This is the **core differentiator** of the Nivesh system. The pipeline transforms a raw stock ticker into a structured, risk-weighted investment thesis through 8 sequential stages, spanning ~15-90 seconds of wall-clock time depending on cache state.

### 5.1. Stage 0: Pre-flight and Cache Check

**Entry:** `services/orchestrator.py:analyze()` -> `def analyze(ticker, exchange, user_id=None, deep_scan=False)`

**Guard Rails (applied in router before stage entry):**
1. Duplicate analysis guard (same user, same ticker -> HTTP 429)
2. Per-user concurrency semaphore (max 2 concurrent -> HTTP 429)
3. yfinance circuit breaker (3 failures -> 5-min open -> HTTP 503)
4. Client disconnect detection (0.5s poll -> 499 on disconnect)
5. Process crash detection (queue empty after process exit -> HTTP 500)
6. Ticker validation regex (`^[A-Z0-9.&]{1,20}$`)
7. Exchange validation (`NSE` or `BSE`)

**Check 1: Global DB Cache** (AnalysisHistory table)
- If cached analysis for ticker+date exists from ANY user: return immediately with cache_type="CACHE HIT"
- Appends advisor_matrix (last 14 days of AdvisorInsight rows for this ticker)
- Saves user-scoped DB row if not present

**Check 2: Smart Cache Gate** (DeepSeek V4 Flash, max_tokens=10, temperature=0)
- If prior analysis exists for different date:
  - Fetch last 5 news headlines via yfinance
  - Call DeepSeek with: "Based ONLY on these headlines, has there been a major fundamental shift? Answer YES or NO."
  - If "NO": deepcopy last analysis, update date+price, return as cache_type="SMART_CACHE"
  - If "YES" or API error: proceed with full AI analysis
- Cost: ~$0.00014/analysis (10 tokens at DeepSeek rates)
- Saves ~$0.03-0.15 per analysis that doesn't need re-running

### 5.2. Stage 1: Epistemic Feedback Retrieval

**File:** `services/feedback_injector.py`

Before the AI debate begins, the system audits its own prior performance:
- Queries AnalysisHistory for most recent analysis of this ticker
- Fetches current price via yfinance
- Computes delta_pct = ((current - prev) / prev) * 100
- Sets was_correct = (bullish_signal AND delta_pct > 0) OR (bearish_signal AND delta_pct < 0)
- Saves outcome back to DB: outcome_delta_pct, outcome_checked_at, was_correct

**Injected Feedback Block (~200-400 tokens):**
"=== EPISTEMIC FEEDBACK: PREVIOUS ANALYSIS AUDIT ===
Previous signal: {signal} (confidence: {conf}%)
Previous price: Rs{price}
3-month target set: Rs{target_3m}
12-month target set: Rs{target_12m}
Actual outcome: Stock moved UP/DOWN {delta}%
Was directionally correct: {True/False}

MANDATORY AUDIT REQUIREMENT:
Both Bull and Bear researchers MUST address:
1. Was the previous signal directionally correct?
2. Which assumption in the previous thesis proved wrong?
3. What information was available then that should have predicted a different outcome?
=== END EPISTEMIC FEEDBACK ==="

### 5.3. Stage 2: Deterministic Pre-computation

Before the AI agents run, the system pre-computes ground-truth data:

**A. Technical Indicators** (`services/factor_engine.py`)

| Indicator | Parameters | Implementation | Behavioral Translation |
|-----------|-----------|----------------|----------------------|
| RSI-14 | window=14 | ta.momentum.RSIIndicator(close, window=14) with numpy fallback | >70 overbought, <30 oversold |
| MACD | fast=12, slow=26, signal=9 | ta.trend.MACD(close, window_slow=26, window_fast=12, window_sign=9) | Line + signal + histogram |
| MACD Histogram | -- | macd_line - macd_signal | Momentum direction |
| ROC-21 | period=21 | (close[-1] / close[-22] - 1) * 100 | Momentum magnitude |
| Momentum Score | -100 to +100 | (RSI - 50) * 1.0 + clamp(ROC * 2, -50, +50) | Combined momentum |
| SMA-20 | rolling(20) | close.rolling(20).mean() | Short-term trend |
| SMA-50 | rolling(50) | close.rolling(50).mean() | Medium-term trend |
| SMA-200 | rolling(200) | close.rolling(200).mean() | Long-term trend |
| EMA-20 | span=20 | close.ewm(span=20).mean() or ta.trend.EMAIndicator | Short-term momentum |
| EMA-50 | span=50 | Same with span=50 | Medium-term momentum |
| ATR-14 | window=14 | ta.volatility.AverageTrueRange(high, low, close, window=14) | Volatility |
| Bollinger Bands | window=20, std=2 | ta.volatility.BollingerBands(close, window=20, window_dev=2) | Over/under bands |
| BB Position | 0.0-1.0 | (price - lower) / (upper - lower) | Band relative position |
| Historical Vol | 21d annualized | log_ret.rolling(21).std() * sqrt(252) * 100 | Volatility regime |
| Volume Ratio | SMA-20 volume | current_volume / SMA-20-of-volume | Volume anomaly |
| OBV | -- | ta.volume.OnBalanceVolumeIndicator or numpy cumsum | Volume flow |

**Golden/Death Cross Detection (within last 20 sessions):**
- golden_cross = (sma50.shift(1) <= sma200.shift(1)) & (sma50 > sma200)
- death_cross = (sma50.shift(1) >= sma200.shift(1)) & (sma50 < sma200)

**Minimum Data Requirement:** 50 data points minimum; returns None for all values below.

**Trend Regime Classification:**
| Condition | Regime |
|-----------|--------|
| price_vs_sma50_pct > 10% AND roc_21 > 15 | STRONG_UPTREND |
| price_vs_sma50_pct > 3% AND roc_21 > 5 | UPTREND |
| price_vs_sma50_pct < -10% AND roc_21 < -15 | STRONG_DOWNTREND |
| price_vs_sma50_pct < -3% AND roc_21 < -5 | DOWNTREND |
| Otherwise | NEUTRAL |

**Volatility Regime Classification:**
| Condition | Regime |
|-----------|--------|
| hist_vol > 60 | HIGH |
| hist_vol > 40 | ELEVATED |
| hist_vol < 15 | LOW |
| Otherwise | NORMAL |

**B. Options Data** (`services/options_scraper.py`)

Source: https://www.nseindia.com/api/option-chain-equities?symbol={ticker}, cached 15 min.

**Put-Call Ratio (PCR):** pcr = total_put_oi / total_call_oi (rounded to 3 decimal places)

**Max Pain Calculation:**
For each strike price, total_pain = sum(max(0, spot - s) * call_oi + max(0, s - spot) * put_oi)
Max Pain = strike with minimum total_pain

**Institutional Signal Classification:**
| Condition | Signal | Translation |
|-----------|--------|-------------|
| PCR > 1.5 AND max_pain_distance > 3% | BEARISH_TRAP | "Extreme bearish positioning. Max Pain suggests short squeeze." |
| PCR < 0.7 AND max_pain_distance < -3% | BULLISH_TRAP | "Retail piling into calls while institutions write them." |
| PCR > 1.2 | CAUTIOUS_BULLISH | "Moderate put protection; institutional hedging." |
| PCR < 0.8 | CAUTIOUS_BEARISH | "Call buying dominant; limited institutional conviction." |
| 0.8 <= PCR <= 1.2 | NEUTRAL | "Balanced positioning." |

**Note:** "F&O signals override pure price-action signals. BULLISH_TRAP overrides bullish price action. BEARISH_TRAP overrides bearish."

**C. Piotroski F-Score** (`services/piotroski.py`) -- 9 Criteria (Score 0-9):

| # | Criterion | Category | Condition |
|---|-----------|----------|-----------|
| 1 | ROA Positive | Profitability | Net Income / Total Assets > 0 |
| 2 | Operating Cash Flow Positive | Profitability | OCF > 0 |
| 3 | ROA Improving | Profitability | Current Year ROA > Prior Year ROA |
| 4 | Accruals Low | Profitability | OCF/TA > Net Income/TA (cash earnings exceed reported earnings) |
| 5 | Leverage Decreasing | Leverage | LTD/Total Assets decreased YoY |
| 6 | Current Ratio Improving | Leverage | Current Assets / Current Liabilities improved YoY |
| 7 | No Dilution | Leverage | Outstanding Shares <= Prior * 1.01 (max 1% dilution) |
| 8 | Gross Margin Improving | Efficiency | Gross Profit / Revenue improved YoY |
| 9 | Asset Turnover Improving | Efficiency | Revenue / Total Assets improved YoY |

| Score | Grade |
|-------|-------|
| 7-9 | STRONG (fundamentally sound) |
| 4-6 | NEUTRAL (mixed signals) |
| 0-3 | WEAK (fundamental weakness) |

Confidence: >=8 checks available = HIGH, >=5 = MEDIUM, <5 = LOW

**D. Sentiment Scoring** (`services/sentiment_engine.py`)
- Model: yiyanghkust/finbert-tone (FinBERT, HuggingFace)
- Pipeline: text-classification, device=-1 (CPU), max_length=512 (truncation)
- Loading: Singleton pattern -- loaded once at first use to avoid 3-5s cold start
- Output: (label: str, signed_score: float)
- Positive: +confidence (0.0 to +1.0), Negative: -confidence (-1.0 to 0.0), Neutral: 0.0
- Batch processing: score_articles_batch() for 50 articles at a time

**E. PKScreener Technical Signals** (`services/pkscreener_runner.py`)
- Runs `python -m pkscreener -t {ticker}` via subprocess (30s timeout)
- Extracts: RSI, MACD signal (BUY/SELL/NEUTRAL), MA position, chart patterns (8 types), volume signal
- Normalized Technical Score (0.0-1.0), starting at 0.5 (neutral):
  - RSI < 30: +0.15 | RSI > 70: -0.10 | RSI 40-60: +0.05
  - MACD BUY: +0.15 | MACD SELL: -0.15
  - Above200MA: +0.12 | Above50MA: +0.07 | Below50MA: -0.07 | DeathCross: -0.15
  - Breakout: +0.08 | Consolidating: +0.03
  - HighVolume + Breakout: +0.05

### 5.4. Stage 3: Multi-Agent Orchestration (TradingAgentsGraph)

**Entry:** `services/orchestrator.py:run_trading_agents()` -> creates `OptimizedTradingAgentsGraph`

**Two-Tier AI Provider Architecture:**
```python
def build_ta_config():
    return {
        "llm_provider": "deepseek",           # Global fallback provider
        "deep_think_llm": "claude-haiku-4-5-20251001",  # Tier 2: Trust-critical
        "deep_think_provider": "anthropic",              # Research Manager + Portfolio Manager
        "quick_think_llm": "deepseek-chat",              # Tier 1: Bulk processing
        "quick_think_provider": "deepseek",              # All analysts + researchers + trader + risk committee
        "max_debate_rounds": 1,              # 1 round = 2 exchanges (Bull + Bear)
        "max_risk_discuss_rounds": 1,        # 1 round = 3 exchanges (Aggressive + Conservative + Neutral)
        "max_tokens": 4000,
    }
```

**Tier Allocation Rationale:**
| Tier | Model | ~Cost/1M Input | ~Cost/1M Output | Used For | Count |
|------|-------|---------------|----------------|----------|-------|
| Tier 1 | DeepSeek V4 Flash | $0.14 | $0.28 | Market, News, Fundamentals, Sentiment Analysts; Bull/Bear Researchers; Trader; Risk Committee (3) | 9 agents |
| Tier 2 | Claude Haiku 4.5 | $1.00 | $5.00 | Research Manager, Portfolio Manager | 2 agents |

DeepSeek is ~7x cheaper for input and ~18x cheaper for output than Claude Haiku, and ~21x/54x cheaper than Claude Sonnet.

**The 12-Agent Graph Flow:**

START
  |
  |-- [Phase 1: Analyst Execution -- sequential by default]
  |
  |-- Market Analyst (Tier 1: DeepSeek)
  |     |-- Tools: get_stock_data, get_indicators, get_verified_market_snapshot
  |     |-- Output: market_report (technical analysis with behavioral translation)
  |
  |-- Sentiment Analyst (Tier 1: DeepSeek)
  |     |-- Pre-fetches: Yahoo News (7d) + StockTwits (30 msgs) + Indian News (Moneycontrol + ET + NSE)
  |     |-- Output: sentiment_report (structured SentimentReport with overall_band, score, confidence)
  |
  |-- News Analyst (Tier 1: DeepSeek)
  |     |-- Tools: get_news, get_global_news, get_insider_transactions
  |     |-- Output: news_report (governance-focused, GOVERNANCE prefix for red flags)
  |
  |-- Fundamentals Analyst (Tier 1: DeepSeek)
  |     |-- Tools: get_fundamentals, get_balance_sheet, get_cashflow, get_income_statement
  |     |-- Output: fundamentals_report (with mandatory Markdown table)
  |
  |-- [Phase 2: Dialectical Debate -- up to 2 exchanges]
  |
  |-- Bull Researcher (Tier 1: DeepSeek)
  |     |-- Input: all 4 analyst reports + bear's last argument + epistemic_feedback
  |     |-- Role: Build evidence-based bull case, critically analyze bear counterpoints
  |
  |-- Bear Researcher (Tier 1: DeepSeek)
  |     |-- Input: all 4 analyst reports + bull's last argument + epistemic_feedback
  |     |-- Role: Build evidence-based bear case, critically analyze bull counterpoints
  |
  |-- Research Manager (Tier 2: Claude Haiku)
  |     |-- Input: full debate history
  |     |-- Output: investment_plan (structured ResearchPlan with rating + rationale + actions)
  |
  |-- [Phase 3: Trade Analysis]
  |
  |-- Trader (Tier 1: DeepSeek)
  |     |-- Input: investment_plan
  |     |-- Output: trader_investment_plan (structured TraderProposal with action + entry + SL + sizing)
  |
  |-- [Phase 4: Risk Committee -- up to 3 exchanges, round-robin]
  |
  |-- Aggressive Analyst (Tier 1: DeepSeek)
  |     |-- Role: Champion high-reward opportunities, challenge conservative/neutral
  |
  |-- Conservative Analyst (Tier 1: DeepSeek)
  |     |-- Role: Protect assets, minimize volatility, challenge aggressive/neutral
  |
  |-- Neutral Analyst (Tier 1: DeepSeek)
  |     |-- Role: Balanced perspective, challenge both aggressive and conservative
  |
  |-- [Phase 5: Final Decision]
  |
  |-- Portfolio Manager (Tier 2: Claude Haiku)
  |     |-- Input: trader plan + risk debate history + full analysis context
  |     |-- Output: final_trade_decision (structured PortfolioDecision with rating + thesis + price_target)
  |     |-- End

**Node Count:** 12 agent nodes + 4 tool nodes + 4 message-clear nodes + 1 merge node = 21 nodes total

**Debate Loop Control (`ConditionalLogic`):**
- Investment Debate Bull/Bear: SAFETY_CAP=10, effective_max=min(2*max_debate_rounds, 10) -- default 2
- Risk Debate: SAFETY_CAP=15, effective_max=min(3*max_risk_discuss_rounds, 15) -- default 3

### 5.5. Stage 4: The Reformatter Pipeline (3-Phase Fallback)

**File:** `services/orchestrator.py:reformat_with_claude()`

**Phase 1: Primary -- Claude Sonnet 3.5**
- model: claude-3-5-sonnet-latest, max_tokens=4000, temperature=0
- System prompt: INDIAN_MARKET_SYSTEM_PROMPT with 15 prior analysis entries
- Uses cache_control: ephemeral on system blocks
- Retries: 3 attempts, exponential backoff (1s, 2s, 4s)

**Phase 2: Fallback -- DeepSeek V4 Flash**
- model: deepseek-chat, max_tokens=4000 (inflated to 5120), temperature=0
- Retries: 3 attempts, exponential backoff (2s, 4s, 8s)

**Phase 3: Ultimate Fallback**
- Returns HOLD with confidence_pct=0, disclaimer="Analysis failed due to an API error.", plus raw_output for debugging

**JSON Extraction Strategy (`_extract_json_from_text`):**
1. Try extracting from ```json ... ``` code fence
2. Try extracting from ``` ... ``` code fence
3. Fallback: extract between first { and last }

**Response Sanitization (`_normalize_response`):**
- signal: Normalized via _SIGNAL_MAP (BUY->BULLISH, SELL->BEARISH, AVOID->BEARISH, CAUTIOUS->CAUTIOUSLY_BEARISH)
- confidence_pct: Coerced to int, clamped 0-100
- current_price_inr: Coerced to float
- target_prices: All 3 keys default to 0.0 if null/inf/nan
- upside_downside_pct: All 3 keys default to 0.0 if invalid
- bull_case, bear_case, key_risks: Default to []
- key_factors: 8 string fields default to "Data not available":
  1. management_quality
  2. geopolitical_context
  3. promoter_fii_dii_activity
  4. turnaround_story
  5. fundamentals_summary
  6. global_macro_impact
  7. news_sentiment
  8. indian_market_sentiment
- disclaimer: Defaults to "This is an AI-generated analysis. Do your own research before investing."

**Signal Normalization Map:**
```python
_SIGNAL_MAP = {
    "BUY": "BULLISH",
    "STRONG BUY": "BULLISH",
    "STRONG_BUY": "BULLISH",
    "SELL": "BEARISH",
    "STRONG SELL": "BEARISH",
    "STRONG_SELL": "BEARISH",
    "AVOID": "BEARISH",
    "CAUTIOUS": "CAUTIOUSLY BEARISH",
}
```

### 5.6. Stage 5: Deep Scan (Optional)

If deep_scan=True:
- PKScreener Injection: Queries PKScreenerSignal table, injects technical pre-scan data (Technical Score, Breakout, RSI, MACD Signal, MA Position, Pattern)
- FinBERT Sentiment Injection: Queries NewsArticle for last 7 days. Scores unscored articles. Injects scored headlines.

### 5.7. Stage 6: Save and Return
- Saves to AnalysisHistory table
- Detects signal flips vs previous analysis -> creates SignalEvent row
- Tracks promoter pledging increases > 5pp -> flagged for red flags
- Attaches advisor_matrix (last 14 days of AdvisorInsight rows)
- Attaches deep_scan_used boolean + pkscreener_signals dict

### 5.8. Stage 7: Analysis Staleness Scoring

**File:** `services/staleness.py` -- Composite Score (0-100)

| Component | Weight | Scoring Logic |
|-----------|--------|---------------|
| Age of Analysis | 40% | Never: +40, >30d: +40, >14d: +25, >7d: +10, <7d: 0 |
| Price Movement | 35% | |Delta7d| > 10%: +35, >5%: +20, >2%: +8 |
| Signal Mismatch | 15% | BEARISH + price up >5%: +15, BULLISH + price down >5%: +15 |
| Analyst Coverage | 10% | Reserved for future |

**Urgency Classification:**
| Score | Label | Action |
|-------|-------|--------|
| >= 70 | URGENT | Analysis may be dangerously outdated. Immediate re-analysis recommended. |
| >= 45 | STALE | Analysis shows signs of staleness. Consider re-analysis. |
| >= 20 | AGING | Analysis is aging but likely still valid. |
| < 20 | FRESH | Analysis is current. |

### 5.9. Complete Prompts System

**File:** `backend/prompts.py` + `tradingagents-core/tradingagents/agents/analysts/*.py`

#### `INDIAN_MARKET_SYSTEM_PROMPT` (Reformatter)

**Persona:** "Principal Market Microstructure Analyst for Dalal Street equities" -- hardened risk officer tone.

**Analysis Priorities (highest weight first) -- Indian Market Priority Weighting Matrix:**

| Rank | Factor | Weight Rationale |
|------|--------|-----------------|
| 1 | Management Quality | Governance, capital allocation, promoter pledging. India's #1 risk factor. |
| 2 | Promoter/FII/DII Activity | Stake changes, bulk deals, insider disclosures. Primary liquidity signal. |
| 3 | Indian Market Sentiment | Social buzz, retail herd behavior, Telegram/Twitter chatter. Retail euphoria = contrarian risk. |
| 4 | Fundamentals | Revenue growth, margins, ROE, ROCE, debt, cash flow. Core business health. |
| 5 | Turnaround Signals | Debt reduction, order book growth, capacity utilization improvement. |
| 6 | Geopolitical/Policy | India-specific risks, PLI schemes, government capex, election outcomes. |
| 7 | Global Macro | Fed rates, crude oil (India imports 85%), DXY, risk sentiment. |
| 8 | News Sentiment | Lowest weight -- can be misleading, operator-driven. |

**Mandatory Constraints:**
- NAME AND NUMBER RULE: Every qualitative assertion MUST be paired with a quantitative metric AND specific operational catalyst.
- Risk-First Protocol: Before ANY upside analysis, identify primary vulnerability, quantify exact P&L/capital impact.
- Promoter Pledging >= 30%: MUST be a significant bear case point regardless of other factors.
- Minskyan Tension Gauge: Sustained DII absorption of FII exits WITHOUT fundamental earnings growth = Minskyan fragility.
- Rupee figures in Indian format (lakhs/crores) -- NEVER millions/billions.
- Percentages rounded to one decimal. Dates in DD-MMM-YYYY format.
- Signal must be exactly one of: BULLISH, CAUTIOUSLY BULLISH, NEUTRAL, HOLD, CAUTIOUSLY BEARISH, BEARISH.

**Behavioral Translation of Technical Indicators (MANDATORY):**
| Indicator | Translation Rule |
|-----------|-----------------|
| RSI > 70 | "Retail momentum overextended; institutional profit-booking zone" |
| RSI < 30 | "Retail capitulation zone; potential institutional accumulation" |
| 200 SMA | "Average historical cost-basis of long-term institutional participants" |
| MACD bearish crossover | "Loss of institutional conviction" |
| Volume rising + Price falling | "Smart money distribution under retail cover" |
| Volume falling + Price rising | "Rally structurally hollow; retail trapped at distribution prices" |
| Bollinger Upper Band touch | "Retail breakout zone; elevated probability of institutional mean-reversion selling" |
| ATR spike | "Forced liquidations or institutional repositioning" |

**Forbidden Phrases:** 'strong', 'robust', 'headwinds', 'tailwinds', 'cautiously optimistic', 'value unlocking', 'navigating'

**Required JSON Structure (19+ top-level fields):**
- ticker, company_name, exchange, analysis_date, signal, confidence_pct, current_price_inr
- target_prices: {short_term_3m, medium_term_12m, long_term_36m}
- upside_downside_pct: {short_term, medium_term, long_term}
- bull_case: [string*3], bear_case: [string*3], key_risks: [string*3]
- key_factors: {management_quality, geopolitical_context, promoter_fii_dii_activity, indian_market_sentiment, turnaround_story, fundamentals_summary, global_macro_impact, news_sentiment}
- fundamentals_snapshot: {pe_ratio, debt_to_equity, promoter_holding_pct, fii_holding_pct, dii_holding_pct, revenue_ttm_crores, ebitda_margin_pct, pat_ttm_crores, roe_pct, roce_pct, market_cap_crores}
- what_to_watch: [string*3], recent_news, patterns, confidence_rationale, signal_changed, previous_signal, disclaimer

**Agent Personas:**
- **Market Analyst:** Complete indicator catalog with behavioral translations. Must call get_verified_market_snapshot. Pre-computed indicators are ground truth -- role is behavioral interpretation only.
- **News Analyst:** Governance priority: auditor resignation, CFO/MD resignation, SEBI show-cause notice. Any governance event = mandatory key_risk. Macro translation: Brent crude -> quantify bps margin impact.
- **Fundamentals Analyst:** Mandatory metrics: ROCE, D/E ratio, FCF yield, working capital cycle days, OPM trend (last 4 quarters). Promoter pledge >= 30% = forced-liquidation risk.
- **Sentiment Analyst:** 9 analysis rules. StockTwits bullish ratio >= 70% = cycle-top indicator. Governance override: auditor/CFO/SEBI event -> overall_band = Bearish.
- **Bull Researcher:** Build evidence-based case. Critically analyze bear argument. Must address epistemic feedback.
- **Bear Researcher:** Make case against investing. Identify threats. Must address epistemic feedback.
- **Risk Committee:** Aggressive=high-risk champion, Conservative=low-risk advocate, Neutral=balanced perspective.
## 6. TRADINGAGENTS-CORE FORK -- Detailed Analysis

This is a forked repository from `TauricResearch/TradingAgents v0.2.5`, customized for the Nivesh Indian market context.

### 6.1. What It Provides

The TradingAgents framework provides:
1. **LangGraph-based multi-agent trading system** with configurable agent teams
2. **Dialectical debate** between bull/bear researchers with configurable rounds
3. **Risk committee** with 3 personality types
4. **Multi-provider LLM abstraction** supporting 11 providers
5. **Vendor-agnostic data layer** with routing and fallback
6. **Persistent memory** via append-only markdown decision logs
7. **Graph checkpointing** via SQLite for resumable analyses
8. **CLI tool** with Rich-based interactive interface

### 6.2. Files Added/Modified by Nivesh

| File | Location | Purpose |
|------|----------|---------|
| context_cache.py | tradingagents/nivesh/ | Prefix-aligned context stratification for Anthropic prompt caching (223 lines) |
| reformatter.py | tradingagents/nivesh/ | Deterministic Claude Sonnet reformatter (316 lines) |
| subprocess_runner.py | tradingagents/nivesh/ | Subprocess isolation with per-user concurrency guard (225 lines) |

### 6.3. LLM Client Architecture

**11 Supported Providers with Base URLs and Auth Env Vars:**

| Provider | Client Class | Base URL | Auth Env Var |
|----------|-------------|----------|--------------|
| OpenAI | OpenAIClient | Native API | OPENAI_API_KEY |
| Anthropic | AnthropicClient | Native API | ANTHROPIC_API_KEY |
| Google (Gemini) | GoogleClient | Native API | GOOGLE_API_KEY |
| xAI (Grok) | OpenAIClient | https://api.x.ai/v1 | XAI_API_KEY |
| DeepSeek | OpenAIClient | https://api.deepseek.com | DEEPSEEK_API_KEY |
| Qwen (Intl) | OpenAIClient | dashscope-intl.aliyuncs.com/compatible-mode/v1 | DASHSCOPE_API_KEY |
| Qwen (CN) | OpenAIClient | dashscope.aliyuncs.com/compatible-mode/v1 | DASHSCOPE_CN_API_KEY |
| GLM (Intl) | OpenAIClient | api.z.ai/api/paas/v4/ | ZHIPU_API_KEY |
| GLM (CN) | OpenAIClient | open.bigmodel.cn/api/paas/v4/ | ZHIPU_CN_API_KEY |
| MiniMax (Intl) | OpenAIClient | api.minimax.io/v1 | MINIMAX_API_KEY |
| MiniMax (CN) | OpenAIClient | api.minimaxi.com/v1 | MINIMAX_CN_API_KEY |
| OpenRouter | OpenAIClient | openrouter.ai/api/v1 | OPENROUTER_API_KEY |
| Azure | AzureOpenAIClient | Configurable | AZURE_OPENAI_API_KEY |
| Ollama | OpenAIClient | http://localhost:11434/v1 | None (no auth) |

**Model Capability Table (Critical for Tool/Structured Output Support):**

| Model ID Pattern | supports_tool_choice | requires_reasoning_roundtrip | requires_reasoning_split | preferred_structured_method |
|-----------------|----------------------|------------------------------|-------------------------|------------------------------|
| deepseek-chat | True | False | False | function_calling |
| deepseek-reasoner | False | True | False | json_schema |
| deepseek-v4-flash | False | True | False | json_schema |
| deepseek-v4-pro | False | True | False | json_schema |
| MiniMax-M2.* (7 variants) | False | False | True | json_schema |
| Default (all others) | True | False | False | function_calling |

**Content Normalization:** normalizes list-typed content blocks (OpenAI Responses API, Gemini 3) to plain strings.

### 6.4. Dataflow Vendor Routing

**Tool Categories:**
- core_stock_apis: get_stock_data -> default vendor: yfinance
- technical_indicators: get_indicators -> default vendor: yfinance
- fundamental_data: get_fundamentals, get_balance_sheet, get_cashflow, get_income_statement -> yfinance
- news_data: get_news, get_global_news, get_insider_transactions -> yfinance

**Indian-Specific Dataflows:**
- indian_news.py: 3 free sources (Moneycontrol RSS, Economic Times RSS, NSE Corporate Announcements) -- no API keys
- stocktwits.py: Public API (no key) -- 30 messages per ticker
- reddit.py: Default subreddits = IndiaInvestments, IndianStockMarket, IndiaInvestingClub, stocks, investing

### 6.5. Memory and Persistence

**TradingMemoryLog:** Append-only markdown decision log.
Entry format: [{date} | {ticker} | {rating} | {raw_return:+.1%} | {alpha_return:+.1%} | {holding_days}d]

Key Methods:
- store_decision(): Append pending entry with idempotency guard
- get_past_context(ticker, n_same=5, n_cross=3): Same-ticker + cross-ticker reflection entries
- update_with_outcome(): Atomic update via temp file + os.replace()
- batch_update_with_outcomes(): Batch atomic updates

### 6.6. CLI Tool

Entry: tradingagents = "cli.main:app" (Typer app)
Interactive Flow: ticker selection, date, language, analysts, depth, LLM provider, thinking agents, provider config
Live Display: Rich-based layout with progress table, messages panel, report panel, footer stats

### 6.7. Default Configuration (22 ENV VAR overrides)

| Env Var | Config Key | Default |
|---------|-----------|---------|
| TRADINGAGENTS_LLM_PROVIDER | llm_provider | "openai" |
| TRADINGAGENTS_DEEP_THINK_LLM | deep_think_llm | "gpt-5.5" |
| TRADINGAGENTS_DEEP_THINK_PROVIDER | deep_think_provider | None |
| TRADINGAGENTS_QUICK_THINK_LLM | quick_think_llm | "gpt-5.4-mini" |
| TRADINGAGENTS_QUICK_THINK_PROVIDER | quick_think_provider | None |
| TRADINGAGENTS_OUTPUT_LANGUAGE | output_language | "English" |
| TRADINGAGENTS_MAX_DEBATE_ROUNDS | max_debate_rounds | 1 |
| TRADINGAGENTS_MAX_RISK_ROUNDS | max_risk_discuss_rounds | 1 |
| TRADINGAGENTS_CHECKPOINT_ENABLED | checkpoint_enabled | False |
| TRADINGAGENTS_BENCHMARK_TICKER | benchmark_ticker | None |
| TRADINGAGENTS_TEMPERATURE | temperature | None |

---

## 7. iOS FRONTEND ARCHITECTURE (SwiftUI)

### 7.1. Application Shell

**stockmeApp.swift** -- @main entry point:
1. Creates @StateObject managers: AuthManager, LocalReportManager, TutorialManager, NotificationManager
2. Checks @AppStorage("hasCompletedOnboarding") -> shows OnboardingScreen
3. Checks @AppStorage("hasAcceptedDisclaimer") -> shows DisclaimerScreen
4. Checks @AppStorage("useBiometrics") + @State isBiometricLocked -> shows biometric lock screen
5. Main content: ContentView (5-tab navigation)

**Biometric Lock Flow:**
- `Info.plist` requires `NSFaceIDUsageDescription` ("Unlock Nivesh to access your portfolio") — iOS crashes without it
- Lock screen: faceid SF Symbol + "NIVESH" (Georgia-Bold) + "Authenticate to continue" + "Unlock with Face ID" button (Theme.securityGold bg, Theme.canvas text)
- Auto-triggers `authenticateWithBiometrics()` on `.onAppear` if `useBiometrics` is true
- Uses `LAContext.evaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, ...)` — no passcode fallback
- On success: `isBiometricLocked = false` -> shows ContentView; On failure: stays locked for retry
- If biometrics unavailable device-wide: falls through unlocked

**ContentView.swift** -- Auth gate + tab shell:
- If not logged in: shows LoginScreen
- If logged in: shows TabView with 5 tabs
- Biometric lock overlay via AuthManager

### 7.2. Navigation Structure (5 Tabs)

TabView
- Tab 0: HomeScreen -- 16 sections (Header, DailyAction, Portfolio Hero, Indices, Watchlist, Timeframe Conflicts, Sector Pulse, Morning Brief, Market News, Dalal Street Consensus, YouTube Videos, Earnings, Market Pulse, Momentum Scan, Macro, Institutional Allocation)
- Tab 1: MarketsView -- sub-tab bar with Earnings, Unlisted, Technical, Screener, Alerts
- Tab 2: ExpertNetworkView -- Advisor consensus + expert posts feed
- Tab 3: NewsMultimediaView -- Real-time financial newswire
- Tab 4: PortfolioScreen -- Holdings, P&L, watchlist, risk analysis, red flags, valuation history, net worth, export

### 7.3. ViewModel Architecture

All ViewModels follow @MainActor ObservableObject pattern with async/await and cancellable Tasks:

**HomeViewModel:** @Published portfolioValue, todayPnL, totalPnL, investedValue, stockCount, watchlist, indices, morningBriefData, sectorData, earningsEvents, dashboard. 5-min indices polling timer.

**AnalysisViewModel:** @Published analysis (StockAnalysis?), quickInfo, isLoading, errorInfo, quarterlyFinancials, promoterHistory, niftyPrices, macroStrip, earningsEvents, analystRatings, macroImpacts. Cancellable analysisTask.

**AnalysisScreen Data Fetch Flow (parallel async let):**
1. quickInfo(ticker) -- live price snapshot
2. quarterlyFinancials(ticker) -- balance sheet/P&L history
3. niftyHistory(days:365) -- Nifty benchmark
4. macroStrip() -- USD/INR, crude, RBI rate, VIX
5. earningsCalendar() -- upcoming results
6. analystRatings(ticker) -- broker consensus
7. macroImpacts(userId) -- per-holding macro sensitivity (authenticated)
8. NetworkManager.shared.analyze(ticker, userId, deepScan) -- HEAVY AI call (1200s timeout)
9. reportManager.saveReport(analysis) -- local cache

### 7.4. Network Layer

**NetworkManager** -- Singleton, async/await, correlation ID tracing.
- Base URL: UserDefaults key "serverBaseURL" or default "http://165.22.221.18"
- Timeout: 1200 seconds (20 minutes)
- Auth header: Bearer {token}
- Correlation ID: X-Correlation-ID: nivesh_ios_{subsystem}_{uuid_short}

**48+ API Routes across categories:**
- Auth (2): /login, /register
- Analysis (3): /analyze, /quick-info, /screener
- Portfolio (16): CRUD + risk + red flags + export + advisor consensus + valuation history
- Market (18): Indices, history, financials, macro, earnings, sector, F&O, dashboard
- Alerts (4): Add, remove, check, list
- Watchlist (3): Add, remove, list
- Trade Journal (4): List, add, update, delete, stats
- Notifications (3): Register device, test push, morning summary push
- Admin (1): Harvest YouTube

### 7.5. Data Models (50+ Codable structs)

**Core Models:**
- Stock: ticker, companyName, exchange, currentPrice, changePercent, signal
- StockAnalysis (25+ fields): ticker, signal, confidence_pct, current_price_inr, target_prices, upside_downside_pct, bull_case, bear_case, key_risks, key_factors (8 sub-fields), fundamentals_snapshot (11 metrics), what_to_watch, recent_news, patterns, confidence_rationale, signal_changed, previous_signal, disclaimer, advisor_matrix
- PortfolioHolding: stock, shares, buyPrice, purchaseDate, notes, computed P&L (currentValue, investedValue, pnl, pnlPercent)
- QuickInfo (15+ fields): ticker, price, change, changePercent, signal, sector, peRatio, debtToEquity, promoterHoldingPct, volume, avgVolume, week52High, week52Low, sparkline30d, priceHistory90d, peVsAvg, recentNews

**Signal Enum (6 cases with color mapping):**
BULLISH -> emerald green
CAUTIOUSLY_BULLISH -> emerald 70%
NEUTRAL -> gold
HOLD -> gold
CAUTIOUSLY_BEARISH -> ruby 70%
BEARISH -> ruby

**Error Diagnostics (AnalysisErrorInfo):**
- diagnostic (DiagnosticError?), rawError, httpStatusCode, responseBody, responseHeaders, requestUrl
- elapsedSeconds, quickInfoElapsed, isRetryable, isMockMode, isDeepScan
- Computed: isRateLimit (429), isServerError (503/500), isAIFailure (500/AI_FAILURE), isConnectionError
- displayTitle, displayDetail, suggestedActionText

### 7.6. Chart System (11 Native Swift Charts)

All charts use Swift Charts framework, themed with Theme tokens, Catmull-Rom interpolation:

1. PriceHistoryChart -- Analysis Tab 2 -- 3M/6M/All price with 50 SMA and 200 DMA
2. RSIChart -- Analysis Tab 2 -- 14-period RSI with overbought/oversold zones
3. VolumeChart -- Analysis Tab 2 -- Volume bars with unusual volume markers
4. ShareholdingChart -- Analysis Tab 3 -- Promoter/FII/DII/Public bar chart
5. FinancialsChart -- Analysis Tab 3 -- Quarterly revenue bars + net profit line
6. PriceRangeGauge -- Analysis Tab 2 -- 52-week range with current price and target
7. PortfolioAllocationChart -- Portfolio -- Donut chart of holdings
8. PnLWaterfallChart -- Portfolio -- Horizontal P&L breakdown per holding
9. StockVsNiftyChart -- Analysis Tab 2 -- Indexed comparison vs Nifty 50
10. SectorHeatmapView -- Home -- Grid of sector performance tiles
11. SparklineView -- Home (Momentum) -- Inline sparklines in MomentumRowView

### 7.7. Local Persistence

- User Preferences: @AppStorage for dark mode, biometrics, server URL, tutorial state, last active tab
- Auth Token: UserDefaults key "nivesh_user_v1" (userId) + AuthManager.authToken
- Analysis Cache: LocalReportManager -- GZIP-compressed JSON in Documents directory (saved_reports.json)
- Stock Database: StockDatabase enum -- ~290 stocks hardcoded in-memory

---

## 8. CLONED REPOSITORIES AND KEY DEPENDENCIES

### 8.1. TradingAgents (Forked from TauricResearch/TradingAgents v0.2.5)

**Location:** backend/tradingagents-core/
**Purpose:** Multi-agent LLM financial trading framework with LangGraph orchestration.
**Nivesh additions:**
- tradingagents/nivesh/context_cache.py: Anthropic prompt caching for Indian market context
- tradingagents/nivesh/reformatter.py: Claude Sonnet-based deterministic JSON reformatter
- tradingagents/nivesh/subprocess_runner.py: Subprocess isolation for production API deployment

### 8.2. Key Open-Source Dependencies

| Dependency | Version | Purpose |
|-----------|---------|---------|
| FastAPI | 0.115.5 | Web framework |
| SQLAlchemy | 2.0.36 | ORM |
| LangChain-Anthropic | 0.3.3 | Claude API |
| LangGraph | 0.2.56 | Multi-agent graph |
| yfinance | 0.2.51 | Yahoo Finance data |
| FinBERT | yiyanghkust/finbert-tone | Financial NLP |
| faster-whisper | large-v3 | Speech-to-text |
| rapidfuzz | latest | Fuzzy string matching |
| Firecrawl | latest | Web scraping (JS rendering) |
| PKScreener | >=0.46 | Technical screening |
| ta | latest | Technical analysis library |
| transformers | >=4.40.0 | HuggingFace models |
| APScheduler | 3.10.4 | Job scheduling |
## 9. FILE CONNECTION GRAPH -- GOD NODES AND CONNECTION DENSITIES

### 9.1. GOD NODE: `main.py:analyze()` (Central Orchestrator -- Analysis Pipeline)

**Function:** analyze() at line 1502 of main.py
- Incoming edges: routers/analysis.py:_run_analysis_worker (via multiprocessing)
- Outgoing edges: EVERY service except disk_cache
  - database.py: get_session(), save_analysis(), get_analysis_for_date(), get_all_ticker_history()
  - services/factor_engine.py: compute_indicators()
  - services/feedback_injector.py: get_feedback_block()
  - services/staleness.py: compute_staleness()
  - tradingagents-core: TradingAgentsGraph.propagate()
  - services/piotroski.py: compute_piotroski()
  - services/sentiment_engine.py: score_article()
  - services/options_scraper.py: compute_derivatives_metrics()
  - prompts.py: INDIAN_MARKET_SYSTEM_PROMPT
- **Risk: CRITICAL** -- failure here blocks all AI analysis
- **Blast radius:** All 8 routers depend on this for analysis + quick-info

### 9.2. GOD NODE: `TradingAgentsGraph` (91 Edges)

**File:** tradingagents-core/tradingagents/graph/trading_graph.py
- Incoming: main.py:run_trading_agents() -> creates and invokes the graph
- Outgoing: Every agent (market, news, fundamentals, sentiment, bull, bear, research manager, trader, risk committee, portfolio manager) + ConditionalLogic, Propagator, Reflector, SignalProcessor, TradingMemoryLog
- **Risk: CRITICAL** -- the entire dialectical reasoning engine

### 9.3. GOD NODE: `CodingKeys` (210 Edges -- Strongest Node in Ecosystem)

**File:** ios/StockApp/stockme/stockme/Models.swift (every Codable struct's custom decoder)
- Why 210 edges: Every backend JSON response key must match exactly. A field rename in Python cascades to all 50+ Swift models.
- Impact: Silent decode failure = invisible UI bug. The entire iOS app silently fails to display data.
- Mitigation: NetworkManager+Sidebar.swift:_diagnosticDecode() -- field-level JSON decode failure logging via os_log

### 9.4. GOD NODE: `NetworkManager.shared` (85+ Edges)

**File:** ios/StockApp/stockme/stockme/NetworkManager.swift (981 lines)
- Incoming: All 23 View files + all 5 Components
- Outgoing: 48+ API endpoints
- **Risk: HIGH** -- singleton pattern means all networking shares the same auth state and base URL

### 9.5. GOD NODE: `get_session()` (93 Edges)

**File:** backend/database.py (context manager)
- Incoming: All 8 routers + all services (15 of 18)
- Outgoing: All 19 SQLAlchemy models
- **Risk: CRITICAL** -- wraps every DB transaction; rollback on exception, always close

### 9.6. GOD NODE: `ConditionalLogic` (80 Edges)

**File:** tradingagents-core/tradingagents/graph/conditional_logic.py
- Incoming: TradingAgentsGraph
- Outgoing: All analyst tool nodes + bull/bear researchers + risk committee + research manager + portfolio manager
- **Risk: HIGH** -- incorrect routing causes infinite loops (safety caps at 10/15 prevent)

### 9.7. STRONG NODES (20-50 Edges Each)

| Node | File | Edges | Role |
|------|------|-------|------|
| AgentState | tradingagents/agents/utils/agent_states.py | ~45 | Typed dict flowing through every graph node |
| INDIAN_MARKET_SYSTEM_PROMPT | backend/prompts.py | ~40 | Used by reformatter, morning summary, every Claude call |
| _deepseek_chat() | backend/main.py (line 83) | ~35 | Used by smart cache, reformatter, macro impact, trade stats |
| _get_indices_data() | backend/helpers.py | ~30 | Called by market router, portfolio, morning summary |
| StockDatabase | ios/.../StockDatabase.swift | ~25 | Used by SearchScreen, AlertsScreen, every ticker lookup |
| Theme | ios/.../Theme.swift | ~30 | Used by EVERY SwiftUI view (color tokens) |
| _normalize_response() | backend/main.py (line 1390) | ~25 | Sanitizes analysis before iOS consumption |
| AnalysisHistory | backend/database.py | ~35 | Referenced by 6 routers + 4 services |
| scraper.py (module) | backend/services/scraper.py | ~28 | Provides all 4 market dashboard feeds |
| sentiment_engine.py | backend/services/sentiment_engine.py | ~22 | News scoring + deep scan sentiment |
| factor_engine.py | backend/services/factor_engine.py | ~20 | Pre-computes indicators for AI pipeline |

### 9.8. WEAK NODES (< 10 Edges Each)

| Node | File | Edges | Role |
|------|------|-------|------|
| MarketErrorLog | backend/database.py | ~6 | Error logging only |
| NotificationManager | ios/.../NotificationManager.swift | ~5 | APNs lifecycle |
| AppSoundManager | ios/.../AppSoundManager.swift | ~3 | Rupee rustle audio |
| HapticManager | ios/.../HapticManager.swift | ~5 | Haptic feedback |
| TutorialManager | ios/.../TutorialManager.swift | ~3 | Tutorial state |
| AdvisorBiography | backend/database.py | ~4 | SEBI advisor profiles |
| MacroEvent | backend/database.py | ~3 | Economic calendar |
| IdeasErrorLog | backend/database.py | ~2 | Ideas workspace telemetry |
| ValuationCalendarService | ios/.../ValuationCalendarService.swift | ~2 | Valuation history |
| ErrorDiagnoser | ios/.../Utilities/ErrorDiagnoser.swift | ~8 | Error diagnostic UI |

### 9.9. CROSS-PLATFORM DEPENDENCY GRAPH

Backend Python -> JSON -> iOS SwiftUI:

routers/portfolio.py -> NetworkManager.swift -> PortfolioScreen.swift
routers/analysis.py -> NetworkManager.swift -> AnalysisScreen.swift
routers/market.py -> NetworkManager.swift -> HomeScreen.swift
    -> helpers.py (indices, auth, cache) -> HomeFeedService.swift
    -> services/scraper.py (Firecrawl/BS4) -> HomeFeedViewModel.swift
    -> services/nse_data_provider.py -> StockDatabase.swift
    -> services/options_scraper.py (NSE options) -> ErrorDiagnoser.swift
    -> services/error_telemetry.py -> Models.swift (GOD NODE: CodingKeys)

services/news_harvester.py -> database.py
    -> services/sentiment_engine.py (FinBERT)
    -> services/ticker_matcher.py (rapidfuzz)

services/youtube_harvester.py -> database.py -> yt-dlp / Google API
services/advisor_harvester.py -> database.py -> DeepSeek API
services/transcript_engine.py -> youtube-transcript-api -> faster-whisper large-v3
services/factor_engine.py -> ta library, pandas
services/piotroski.py -> yfinance
services/pkscreener_runner.py -> pkscreener CLI
services/portfolio_snapshot.py -> yfinance
services/staleness.py -> pure logic (no dependencies)
services/disk_cache.py -> filesystem only
services/feedback_injector.py -> yfinance + database

main.py -> tradingagents-core/tradingagents/graph/
    -> TradingAgentsGraph.propagate()
        -> ConditionalLogic (debate routing)
        -> Market, News, Fundamentals, Sentiment Analysts
        -> Bull/Bear Researchers + epistemic feedback
        -> Research Manager -> Trader -> Risk Committee
        -> Portfolio Manager -> signal
        -> Propagator (state init)
        -> Reflector (self-reflection)
        -> TradingMemoryLog (decision persistence)
        -> SignalProcessor (rating extraction)

---

## 10. SCHEDULED JOBS (APScheduler -- 9 Jobs)

All times Indian Standard Time (IST = UTC + 5:30).

| # | Time (IST) | Job | Function | Description |
|---|------------|-----|----------|-------------|
| 1 | 12:30 AM | News harvest | harvest_news() | Scrape 4 RSS feeds, score with FinBERT |
| 2 | 1:00 AM | YouTube channel sweep | harvest_youtube_metadata() | Fetch latest 10 videos from 6 SEBI channels |
| 3 | 1:15 AM | YouTube portfolio search | harvest_portfolio_videos() | Search YouTube for each held ticker |
| 4 | 1:30 AM | Advisor harvest | harvest_all_advisors() | 5 advisor channels, transcript + stance extraction |
| 5 | 2:00 AM | Outcome evaluation | evaluate_analysis_outcomes() | Evaluate last 50 analyses older than 7 days |
| 6 | 4:30 PM | Portfolio snapshots | snapshot_all_users() | Daily portfolio valuation for all users |
| 7 | 4:45 PM | PKScreener nightly scan | run_nightly_screen() | Run PKScreener on all tracked tickers |
| 8 | Every 15 min | Corporate filings | harvest_filings() | Check NSE for new corporate announcements |
| 9 | On-demand | Morning summary refresh | (cache expiry) | 2-hour cache, refreshed on user request |

All jobs run in background ThreadPoolExecutor (max_workers=4), with per-job retry logic (3 attempts).

---

## 11. ERROR HANDLING AND TELEMETRY

### 11.1. Global Error Diagnostic System

**Backend:** services/error_telemetry.py
- Correlation ID Middleware: Reads X-Correlation-ID header, generates nivesh_srv_{uuid4()[:8]} if missing
- Structured Diagnostic Logging: log_diagnostic_error() with fields: subsystem, classification, context (target_ticker, market_hours_state), telemetry (http_method, route, ios_swift_file), exception (type, message, cleaned traceback), correlation_id, automated_recovery
- Returns error_uuid (UUID4) for iOS client to relay
- Traceback Cleaning: Strips uvicorn, starlette, anyio, fastapi noise
- Persistence: Writes to market_error_logs, earnings_error_logs, and stdout simultaneously

**iOS:** ErrorDiagnoser.swift (290 lines)
- GlobalErrorDiagnoser: @MainActor singleton, @Published errors: [TrackedError] capped at 50
- Classification: INFRASTRUCTURE_EXCEPTION, SCHEMA_DRIFT, AUTHENTICATION_FAILURE
- UI: ErrorDiagnoserView -- banknote-styled "DATA FAULT" card with diagnostic expander, copy-to-clipboard, retry button

### 11.2. API Error Codes

| Endpoint | HTTP Status | Error Code | Trigger |
|----------|-------------|------------|---------|
| /analyze | 429 | ALREADY_RUNNING | Duplicate analysis request |
| /analyze | 429 | CONCURRENCY_LIMITED | >2 concurrent per user |
| /analyze | 499 | CLIENT_DISCONNECTED | Client closed connection mid-analysis |
| /analyze | 500 | AI_FAILURE | LLM API error |
| /analyze | 500 | PROCESS_CRASHED | Multiprocessing process died |
| /analyze | 503 | DATA_HARVESTING_ERROR | Market data scraping failure |
| /login | 401 | INVALID_CREDENTIALS | Wrong username/password |
| /register | 400 | USERNAME_EXISTS | Duplicate username |
| /portfolio | 409 | DUPLICATE_HOLDING | Same ticker already in portfolio |
| Any | 401 | UNAUTHORIZED | Missing/invalid JWT |
| Any | 403 | FORBIDDEN | Non-admin accessing admin endpoint |

### 11.3. Rate Limiting and Concurrency Controls

| Control | Scope | Limit | Mechanism |
|---------|-------|-------|-----------|
| Rate limiter | Per IP | 120 req/60s | In-memory dict with window tracking |
| Analysis concurrency | Per user | 2 concurrent | threading.Semaphore per user ID |
| yfinance circuit breaker | Global | 3 failures -> 5min open | Counter + timestamp |
| Analysis duplicate | Per user+ticker | 1 running | _running_analyses set |
| News harvest dedup | Global | URL uniqueness | news_articles.article_url UNIQUE constraint |
| Advisor insight dedup | Global | (video_id, ticker) | advisor_insights UniqueConstraint |
| PKScreener dedup | Per ticker | 1/day | pkscreener_signals UniqueConstraint |
| Portfolio snapshot dedup | Per user | 1/day | portfolio_valuation_history UniqueConstraint |
| Morning summary | Global | 1/2h | _morning_cache with TTL=7200s |

---

## 12. CONFIGURATION AND ENVIRONMENT

### 12.1. Required Environment Variables

| Variable | Required | Default | Used By |
|----------|----------|---------|---------|
| ANTHROPIC_API_KEY | For AI features | -- | Claude API (Haiku, Sonnet) |
| DEEPSEEK_API_KEY | For Tier 1 AI | -- | DeepSeek V4 Flash |
| FIRECRAWL_API_KEY | For scraping | -- | Firecrawl web scraper |
| YOUTUBE_API_KEY | For YouTube | -- | YouTube Data API v3 |
| DATABASE_URL | No | sqlite:///backend/stockapp.db | SQLAlchemy database |
| JWT_SECRET | No | secrets.token_hex(32) | JWT signing |
| ALLOWED_ORIGINS | No | * | CORS configuration |
| ENVIRONMENT | No | development | Runtime environment |

### 12.2. Cache Configuration

| Cache | Type | TTL | Location | Namespace |
|-------|------|-----|----------|-----------|
| Quick Info L1 | In-memory dict | 15 min | main.py _quick_info_cache | -- |
| Quick Info L2 | Disk (gzip JSON) | 6 hours | ~/Library/Caches/nivesh/ | yfinance |
| Analysis DB | Database | Permanent | stockapp.db AnalysisHistory | -- |
| Smart Cache | DeepSeek gate | News-dependent | DeepSeek API call | -- |
| Indices | In-memory | 5 min | helpers.py _indices_cache | -- |
| ASM/GSM | In-memory | 6 hours | helpers.py _asm_gsm_cache | -- |
| Sector Performance | In-memory | 10 min | market.py in-memory | -- |
| Market Dashboard | In-memory | 15 min | scraper.py OrderedDict | -- |
| Piostroski | Disk | 6 hours | disk_cache | yfinance |
| Options Chain | Disk | 15 min | disk_cache | options |
| Morning Summary | In-memory | 2 hours | portfolio.py _morning_cache | -- |
| Macro Impact | In-memory | 2 hours | portfolio.py _MACRO_IMPACT_CACHE | -- |
| News Processed | Disk | 12 hours | disk_cache | news_processed |
| Bhavcopy | Disk | 24 hours | disk_cache | bhavcopy |

### 12.3. Concurrency and Threading

| Component | Mechanism | Max Workers |
|-----------|-----------|-------------|
| AI Analysis | multiprocessing.Process | 1 per analysis (2 per user) |
| Market Dashboard | ThreadPoolExecutor | 4 workers, 25s timeout |
| Earnings Feed | ThreadPoolExecutor | 8 workers, 45s timeout |
| Cap Index Grid | ThreadPoolExecutor | 8 workers, 30s timeout |
| Background Jobs | ThreadPoolExecutor | 4 workers |
| FastAPI Server | uvicorn workers | 2 workers |
| ASM/GSM Lists | 3 retries, 1.5x backoff | Single thread |
| yfinance calls | 3 retries, 2x exponential backoff | Per-call |

---

## 13. DATA FLOW: THE LIFECYCLE OF AN AI ANALYSIS

1. User taps "Analyze" on a stock in iOS AnalysisScreen
2. iOS sends POST /analyze with {ticker, exchange, user_id, deep_scan}
3. FastAPI router validates ticker, checks duplicates, enforces concurrency limit
4. Multiprocessing worker process starts (isolated from main thread)
5. Worker calls analyze() in main.py:
   a. Check global DB cache (today's analysis exists?) -> CACHE HIT: return immediately
   b. Check smart cache (prior analysis + news check via DeepSeek) -> SMART_CACHE: return updated copy
   c. Fetch epistemic feedback: query prior analysis outcome
   d. Pre-compute technical indicators (factor_engine: RSI, MACD, SMA, BB, ATR, OBV, ROC)
   e. Fetch options data (PCR, Max Pain) +/- Piotroski F-Score
   f. Run TradingAgentsGraph.propagate() with 12-agent dialectical debate:
      - 4 Analyst nodes run (Market, Sentiment, News, Fundamentals)
      - Bull/Bear debate with epistemic feedback injection (up to 2 exchanges)
      - Research Manager synthesizes debate
      - Trader proposes specific action
      - Risk Committee debates (Aggressive/Neutral/Conservative)
      - Portfolio Manager delivers final verdict
   g. Optional deep scan: PKScreener + FinBERT sentiment
   h. Reformatter pipeline: Claude Sonnet (primary) -> DeepSeek (fallback) -> HOLD (ultimate fallback)
   i. Sanitize JSON via _normalize_response()
   j. Save to AnalysisHistory table, detect signal flips, create SignalEvents
6. Result returned via multiprocessing.Queue
7. FastAPI returns normalized StockAnalysis JSON to iOS
8. iOS renders analysis in 5 sub-tabs (Overview, Analysis, Charts, Fundamentals, News)
9. User can save locally, set price alerts, or trigger re-analysis

---
*This document is the authoritative source for the Nivesh System DNA. It must be updated immediately upon any architectural shift or service logic change.*
## 14. BACKEND SERVICES -- DEEP DIVE

### 14.1. factor_engine.py -- Technical Analysis Engine

**File:** backend/services/factor_engine.py (~300 lines)
**Dependencies:** ta (Technical Analysis Library), pandas, numpy

**Core Function: compute_indicators(ticker)**
- Fetches 1 year of daily OHLCV data via yfinance
- Minimum 50 data points required; returns None-filled result if insufficient
- Computes ALL indicators listed in section 5.3.A in a single pandas pipeline
- Returns dict with keys: rsi_14, macd, macd_signal, macd_histogram, sma_20/50/200, ema_20/50, bollinger_bands (upper/lower/position), atr_14, obv, volume_ratio, roc_21, historical_volatility_21d, momentum_score, trend_regime, volatility_regime, golden_cross, death_cross

**Trend Regime Algorithm:**
- STRONG_UPTREND: price_vs_sma50_pct > 10% AND roc_21 > 15
- UPTREND: price_vs_sma50_pct > 3% AND roc_21 > 5
- STRONG_DOWNTREND: price_vs_sma50_pct < -10% AND roc_21 < -15
- DOWNTREND: price_vs_sma50_pct < -3% AND roc_21 < -5
- NEUTRAL: everything else

**Volatility Regime Algorithm:**
- HIGH: hist_vol > 60
- ELEVATED: hist_vol > 40
- LOW: hist_vol < 15
- NORMAL: everything else

**Momentum Score Algorithm (-100 to +100):**
- Base: (RSI - 50) * 1.0
- ROC contribution: min(max(ROC * 2, -50), 50)
- Total: clamp(base + roc_contrib, -100, +100)

**Crossover Detection:**
- Golden Cross: SMA-50 crosses ABOVE SMA-200 within last 20 sessions
- Death Cross: SMA-50 crosses BELOW SMA-200 within last 20 sessions
- MACD Bullish Cross: MACD histogram went from negative to positive
- MACD Bearish Cross: MACD histogram went from positive to negative
- Uses pandas shift(1) comparison for crossover detection

**Numpy Fallback for RSI:**
When ta library unavailable, uses pure numpy implementation:
- Compute price changes: delta = np.diff(close)
- Separate gains/losses: gain = np.where(delta > 0, delta, 0), loss = np.where(delta < 0, -delta, 0)
- Average gain/loss over 14 periods using Wilder smoothing
- RS = avg_gain / avg_loss, RSI = 100 - (100 / (1 + RS))

**Numpy Fallback for OBV:**
When ta library unavailable:
- signed_volume = np.where(close_diff > 0, volume, np.where(close_diff < 0, -volume, 0))
- obv = np.cumsum(signed_volume)

### 14.2. sentiment_engine.py -- NLP Sentiment Singleton

**File:** backend/services/sentiment_engine.py (~120 lines)
**Model:** yiyanghkust/finbert-tone (HuggingFace)
**Pipeline:** text-classification, device=-1 (CPU), max_length=512 with truncation

**Singleton Pattern:**
- _model and _tokenizer are None until first call
- score_article() lazy-loads the model on first invocation
- Thread-safe: loading happens under a threading.Lock()
- Cold start latency: 3-5 seconds (model download + load), happens only once per process lifetime

**score_article(headline, summary=None) -> (label: str, score: float):**
- Concatenates headline + summary (truncated to 1200 chars combined)
- Runs through FinBERT pipeline
- Maps output to signed score:
  - If label == "Positive": score = +confidence (0.0 to +1.0)
  - If label == "Negative": score = -confidence (-1.0 to 0.0)
  - If label == "Neutral": score = 0.0
- Returns (label, score)

**score_articles_batch(articles: list) -> list of (label, score):**
- Efficient batch inference for multiple articles
- Same scoring logic but processes in single model call
- Used by backfill_existing_articles() for processing unscored articles

**backfill_existing_articles(session):**
- Queries NewsArticle table for rows with sentiment_score == None
- Processes in batches of 50 at a time
- Commits after each batch
- Runs as part of morning maintenance or on-demand

### 14.3. news_harvester.py -- RSS News Pipeline

**File:** backend/services/news_harvester.py (173 lines)

**RSS Sources (4 feeds):**
1. Moneycontrol latest news: https://www.moneycontrol.com/rss/latestnews.xml
2. Moneycontrol market reports: https://www.moneycontrol.com/rss/marketreports.xml
3. Economic Times markets: https://economictimes.indiatimes.com/markets/rssfeeds/1975241501.cms
4. Economic Times stocks: https://economictimes.indiatimes.com/markets/stocks/rssfeeds/2146842685.cms

**Red Flag Keywords (15 terms):**
auditor resign, auditor quit, cfo resign, cfo quit, md resign, sebi investigation, sebi probe, sebi notice, promoter pledge, stock suspended, trading halt, forensic audit, fraud, embezzlement, governance concern, qualified opinion

**Pipeline: harvest_news(lookback_hours=26):**
1. Parse each RSS feed (max 20 entries per feed)
2. Skip if article_url already exists in DB (dedup via UNIQUE constraint)
3. Skip if published_at is before cutoff_time
4. Scrape full body via newspaper3k (10s timeout, capped at 8000 chars)
5. Score red flags via keyword matching against headline + body
6. Extract tickers: iterate ALIAS_TO_TICKER dict, first match wins (max 5 tickers per article)
7. Score sentiment via sentiment_engine.score_article() (FinBERT)
8. Flush and commit per article (rollback on error, continue to next)
9. Log errors via logging.warning with traceback (never crash the pipeline)

### 14.4. youtube_harvester.py -- YouTube Data Pipeline

**File:** backend/services/youtube_harvester.py (469 lines)

**Two Harvest Modes:**

**Mode 1: Channel Harvest (harvest_youtube_metadata()) -- runs nightly at 1:00 AM:**
- 6 SEBI-registered channels:
  1. SOIC (INH000012582)
  2. Basant Maheshwari (INH000017949)
  3. Capitalmind (INH000014003)
  4. Anand Rathi (INH000000834)
  5. Motilal Oswal (INH000000412)
  6. Yadnya Investment Academy (INH000008349)
- Min subscriber threshold: 100,000
- Fetch via YouTube Data API v3 first, fallback to yt-dlp per channel
- Max 10 videos per channel, 0.5s delay between channels to avoid rate limits
- Upserts by video_id: if exists and matched_ticker is null, update if now matched
- Stores: video_id, channel_name, title, description_snippet, thumbnail_url, published_at, view_count, duration_seconds, sebi_reg

**Mode 2: Portfolio Harvest (harvest_portfolio_videos()) -- runs nightly at 1:15 AM:**
- For each unique ticker across all user portfolios
- Gets company name from TICKER_COMPANY_MAP (28 entries) or yfinance info fallback
- Searches YouTube with query: "{company_name} NSE stock analysis India"
- API v3 first (relevanceLanguage="en", regionCode="IN"), yt-dlp fallback
- 3 videos max per ticker, 1.2s delay between tickers
- Updates matched_ticker field on YouTubeVideo rows

**TICKER_COMPANY_MAP (28 entries):**
Maps tickers to human-readable names for better YouTube search:
RELIANCE -> "Reliance Industries", TCS -> "Tata Consultancy Services", INFY -> "Infosys", HDFCBANK -> "HDFC Bank", ICICIBANK -> "ICICI Bank", SBIN -> "State Bank of India", BHARTIARTL -> "Bharti Airtel", ITC -> "ITC Limited", KOTAKBANK -> "Kotak Mahindra Bank", BAJFINANCE -> "Bajaj Finance", LT -> "Larsen and Toubro", WIPRO -> "Wipro", AXISBANK -> "Axis Bank", TITAN -> "Titan Company", MARUTI -> "Maruti Suzuki", HCLTECH -> "HCL Technologies", SUNPHARMA -> "Sun Pharmaceutical", ONGC -> "Oil and Natural Gas Corporation", NTPC -> "NTPC Limited", POWERGRID -> "Power Grid Corporation", M&M -> "Mahindra and Mahindra", ULTRACEMCO -> "UltraTech Cement", ASIANPAINT -> "Asian Paints", NESTLEIND -> "Nestle India", BAJAJFINSV -> "Bajaj Finserv", JSWSTEEL -> "JSW Steel", ADANIENT -> "Adani Enterprises", TATAMOTORS -> "Tata Motors", SUZLON -> "Suzlon Energy"

### 14.5. advisor_harvester.py -- Advisor Intelligence Pipeline

**File:** backend/services/advisor_harvester.py (~700 lines)

**Advisor Registry (5 channels):**
1. SOIC (soicfinance) -- Technical analysis
2. Basant Maheshwari (bmtheequitydesk) -- Long-term value
3. Shankar Sharma (FirstGlobalAdvisory) -- Contrarian
4. Neeraj Marathe (neerajmarathe) -- Small/mid cap
5. Valuepickr (rupakroyc) -- Value investing

**Video Fetching:**
- Primary: YouTube Data API v3 (search maxResults=10, ordered by date)
- Fallback: yt-dlp (extract_flat=True, filter by upload date)
- Min video duration: 240 seconds (4 minutes) to be processed
- Duration parsing: ISO 8601 PT4M30S format via isodate library or regex

**Transcript Processing:**
- Layer 1: youtube-transcript-api (languages=["en", "hi"])
  - Quality gate: Devanagari ratio <= 15%, word count >= 80 WPM of duration
- Layer 2: faster-whisper large-v3 (CPU, int8 quantized)
  - Initial prompt: "Financial analysis of Indian stock market, NSE BSE companies, crore lakh rupees"
  - Language: Hindi ("hi"), task: transcribe
  - Cleans up temp audio file in finally block

**Stance Extraction via DeepSeek V4 Flash:**
- System prompt: "You are a financial transcript analyst. Extract structured investment stance data..."
- User template: "Transcript snippet from {advisor_name} discussing {ticker}: --- {snippet} --- Extract JSON: {stance: BULLISH|NEUTRAL|BEARISH, confidence: HIGH|MEDIUM|LOW, catalyst_summary: <single bullet, max 120 chars>}"
- Parameters: max_tokens=200, temperature=0.1 (inflated to max(1000, 512)=1000 for reasoning tokens)
- 3 retries with exponential backoff (2s, 4s, 8s)

**Outcome Evaluation (evaluate_analysis_outcomes() -- runs nightly at 2:00 AM):**
- Processes AnalysisHistory rows older than 7 days that haven't been evaluated
- Batch limit: 50 per night (to avoid yfinance rate limits)
- For each analysis:
  1. Extract prev_price and signal from stored JSON
  2. Fetch current price via yfinance (ticker.NS suffix)
  3. Compute delta_pct = ((current - prev) / prev) * 100
  4. Set was_correct = (bullish_signal AND delta > 0) OR (bearish_signal AND delta < 0)
  5. Update outcome_delta_pct, outcome_checked_at, was_correct in DB

### 14.6. transcript_engine.py -- YouTube Transcript Processing

**File:** backend/services/transcript_engine.py (295 lines)

**Two-Layer Strategy:**

**Layer 1: YouTube Transcript API (_fetch_youtube_api):**
- Tries languages=["en", "hi"]
- Handles multiple API versions (static get_transcript, instance fetch, list+find)
- Normalizes segment format: {start, end, text}
- Quality gate: Devanagari ratio <= 15%, word count >= 80 WPM of video duration

**Layer 2: Local Whisper (_fetch_whisper):**
- Downloads audio via yt-dlp (bestaudio/best) to temp file
- Transcribes with faster-whisper large-v3 on CPU, int8 quantized
- Initial prompt: "Financial analysis of Indian stock market, NSE BSE companies, crore lakh rupees"
- Language: Hindi ("hi"), task: transcribe
- Cleans up temp audio file in finally block

**Public API:**
- get_transcript(video_id, duration_seconds=0) -> {source (youtube_api/whisper_local), segments [{start, end, text}], full_text, duration_seconds}
- Raises TranscriptError if both layers fail
- Used by advisor_harvester.py for transcript retrieval

### 14.7. ticker_matcher.py -- Fuzzy Ticker Matching

**File:** backend/services/ticker_matcher.py (316 lines)

**Manual Overrides (10 tickers, 28 aliases):**
Hinglish-friendly aliases for common Indian stocks:
- "hdfc wala bank" -> HDFCBANK
- "bajaj fin" -> BAJFINANCE
- "hindustan aero" -> HAL
- "sujalon" -> SUZLON (corrects common misspelling)
- "railway finance" -> IRFC
- "info sis" -> INFY (Infosys)
- "tata motor" -> TATAMOTORS
- "reliance" -> RELIANCE
- "icici" -> ICICIBANK
- "sbi" -> SBIN
- "ongc" -> ONGC
- "wipro" -> WIPRO

**Database Loading:**
At import time, reads from stockapp.db:
- portfolio table: (ticker, company_name) pairs
- analysis_history table: ticker symbols only
- Falls back silently if DB unavailable

**Alias Table Construction:**
- TICKER_ALIASES: {ticker: [company_name, *manual_aliases]}
- ALIAS_TO_TICKER: {alias_lower: ticker}
- All ticker symbols themselves also registered as aliases
- Deduplicated flat list built at module load

**find_tickers(transcript) -> [{ticker, timestamp, score, alias_used, snippet}]:**
Input: {segments: [{start, end, text}], full_text, duration_seconds}

Algorithm:
1. Sliding window: size=6 words, step=3
2. For each window: process.extractOne() with fuzz.token_set_ratio, cutoff=82
3. Resolve matched alias -> ticker via ALIAS_TO_TICKER
4. Estimate timestamp via linear interpolation, snap to nearest segment start
5. Extract snippet: +/- 60s window around timestamp
6. Deduplication: Same ticker within 30s -> keep highest score entry
7. Returns sorted by timestamp ascending

Helper Functions:
- extract_snippet(segments, timestamp) -> concatenated text from +/- 60s window
- _estimate_timestamp(word_index, total_words, duration, segments) -> linear interpolation with segment snapping

### 14.8. options_scraper.py -- NSE Options Chain

**File:** backend/services/options_scraper.py (~180 lines)

**Data Source:**
URL: https://www.nseindia.com/api/option-chain-equities?symbol={symbol}
HTTP Headers: User-Agent (Chrome), Accept, Referer, Cookie from _nse_session()
Cached: 15 minutes in disk_cache under "options" namespace

**Functions:**

**fetch_option_chain(symbol) -> dict:**
- Parses NSE JSON response
- Extracts: expiry dates, strike prices, CE/PE OI, volume, IV, LTP
- Returns {expiry_dates: [...], records: [{strike_price, expiry_date, CE: {oi, volume, iv, ltp}, PE: {oi, volume, iv, ltp}}]}

**compute_derivatives_metrics(option_chain, current_price) -> dict:**
- total_call_oi = sum of all CE OI across all strikes
- total_put_oi = sum of all PE OI across all strikes
- pcr = total_put_oi / total_call_oi (rounded to 3 decimal places)
- Max Pain: for each strike, compute total_pain = sum(max(0, spot-s)*call_oi + max(0, s-spot)*put_oi); Max Pain = strike with minimum pain
- max_pain_distance_pct = (max_pain - current_price) / current_price * 100
- top_call_oi_strike: strike with highest CE OI
- top_put_oi_strike: strike with highest PE OI
- institutional_signal: classification per table in section 5.3.B

Returns: {pcr, max_pain, max_pain_distance_pct, top_call_oi_strike, top_put_oi_strike, institutional_signal, signal_rationale, expiry_date, total_call_oi, total_put_oi}

### 14.9. scraper.py -- Web Scraper (Firecrawl + BS4 Fallback)

**File:** backend/services/scraper.py (743 lines)

**Cache Layer:**
- In-memory OrderedDict, 900s (15min) TTL, max 50 entries
- LRU eviction: _CACHE.move_to_end() + popitem(last=False)
- Keys: function_name + sorted args as cache key

**Firecrawl Integration:**
- Lazily initialized FirecrawlApp from FIRECRAWL_API_KEY
- _firecrawl_extract(url, schema) -> uses scrape_url with formats=["extract"]
- Returns None if key absent or import fails

**Functions:**

**fetch_market_pulse() -> {indices, advances, declines, unchanged, breadth_ratio}:**
Primary: Firecrawl on Moneycontrol indices page with schema for indices + advance/decline
Fallback: yfinance with 4 index tickers + 20 Nifty50 sample stocks (scaled x10 for Nifty 500)

**fetch_momentum() -> {bullish[8], bearish[8]}:**
- 15 tickers (major Nifty), 3mo history at 1d interval
- Computes MA20, MA50, detects golden/death crosses
- Sparkline: samples closes down to 20 points

**fetch_macro_alternatives() -> {items: [{name, ticker, price, change_pts, change_pct, direction}]}:**
- 10 tickers: Brent Crude, Gold, USD/INR, US 10Y Yield, Nifty BeES, Gold BeES, Nifty IT, India VIX, Silver, Nifty Pharma

**fetch_institutional_flow() -> {funds: [{name, category, oneYearReturnPct, aumCr}]}:**
Primary: Firecrawl on Moneycontrol large-cap fund tracker
Fallback: yfinance download of 8 mutual fund tickers
Hardcoded fallback: 8 well-known funds with approximate returns

**fetch_earnings_sync_ratio() -> {declared_count, total_expected=5042, sync_ratio_pct}:**
Primary: Firecrawl on Moneycontrol earnings page
Fallback 1: BS4 scrape of Moneycontrol earnings table
Fallback 2: yfinance extrapolation from 30 stock sample
Last resort: 60% of 5042 estimate

**fetch_yoy_aggregate_indicators() -> {revenue_yoy_pct, net_profit_yoy_pct, companies_reported, source}:**
Primary: Firecrawl on Moneycontrol with YoY schema
Fallback: yfinance quarterly income statements for 30 stocks

### 14.10. nse_data_provider.py -- NSE Data Provider

**File:** backend/services/nse_data_provider.py (148 lines)

**Data Source Priority:**
1. jugaad-data (jugaad_data.nse.stock_df) -- probed at module load with RELIANCE test
2. yfinance -- universal fallback

**get_price_history(ticker, period_days=365, exchange="NSE") -> pandas.DataFrame:**
- Disk cached under "yfinance" namespace (key: {ticker}_history_{period_days}d)
- jugaad-data path (NSE only): renames columns (OPEN->Open, CLOSE->Close, TOTTRDQTY->Volume)
- yfinance path: tries ticker.NS, falls back to ticker.BO
- Minimum 10 rows required to consider data valid

**get_fundamentals(ticker, exchange="NSE") -> dict:**
- Disk cached under "yfinance" namespace, 6h TTL
- 11 fields extracted from yfinance info: pe_ratio, pb_ratio, eps_ttm, revenue_ttm, debt_to_equity, roe, promoter_pledging_pct, market_cap, dividend_yield
- Falls back to ticker.BO if .NS returns no data

### 14.11. piotroski.py -- Fundamentals Scoring

**File:** backend/services/piotroski.py (~100 lines)

**compute_piotroski(ticker) -> {f_score: 0-9, grade: STRONG/NEUTRAL/WEAK, confidence: HIGH/MEDIUM/LOW, details: {criteria_results}}:**

Fetches 2 years of yfinance financials (income_stmt, balance_sheet, cash_flow):
- income_stmt: net_income, revenue, gross_profit
- balance_sheet: total_assets, total_debt, current_assets, current_liabilities, outstanding_shares
- cash_flow: operating_cash_flow

**9 Criteria Implementation:**
1. ROA Positive: NI_0 / TA_0 > 0 (current year)
2. OCF Positive: OCF_0 > 0
3. ROA Improving: (NI_0 / TA_0) > (NI_1 / TA_1)
4. Accruals Low: OCF_0 / TA_0 > NI_0 / TA_0 (cash earnings exceed reported)
5. Leverage Decreasing: (LTD_0 / TA_0) < (LTD_1 / TA_1)
6. Current Ratio Improving: (CA_0 / CL_0) > (CA_1 / CL_1)
7. No Dilution: Shares_0 <= Shares_1 * 1.01 (max 1% dilution)
8. Gross Margin Improving: (GP_0 / Rev_0) > (GP_1 / Rev_1)
9. Asset Turnover Improving: (Rev_0 / TA_0) > (Rev_1 / TA_1)

Where _0 = current year, _1 = prior year

### 14.12. pkscreener_runner.py -- Technical Screening

**File:** backend/services/pkscreener_runner.py (190 lines)

**run_pkscreener_for_ticker(ticker) -> dict or None:**
- Runs: python -m pkscreener -t {ticker} via subprocess with 30s timeout
- If JSON output: parse directly, extract RSI, breakout, consolidating, pattern
- If text output: regex parsing for:
  - RSI via pattern rsi[:\s]+(\d+\.?\d*)
  - Breakout/consolidating via keyword match
  - MA signal via pattern matching (Above200MA, Above50MA, Below200MA, Below50MA, DeathCross)
  - MACD via BUY/SELL/NEUTRAL keyword
  - Volume via HighVolume keyword
  - Chart patterns from list of 8 (bull_flag, cup_handle, double_bottom, head_and_shoulders, ascending_triangle, descending_triangle, hammer, doji)

**normalize_technical_score(signals) -> float 0.0-1.0:**
Starting at 0.5 (neutral), applies adjustments:
- RSI < 30: +0.15 | RSI > 70: -0.10 | RSI 40-60: +0.05
- MACD BUY: +0.15 | SELL: -0.15
- Above200MA: +0.12 | Above50MA: +0.07 | Below50MA: -0.07 | DeathCross: -0.15
- Breakout: +0.08 | Consolidating: +0.03
- HighVolume + Breakout: +0.05

**run_nightly_screen() -- runs nightly at 4:45 PM:**
- Iterates tracked tickers from NSE_DIRECTORY
- Skips if today's signal already exists (UniqueConstraint enforces 1/day)
- Runs parser, normalizes score, stores in PKScreenerSignal
- Commits per ticker (rollback on error, continue to next)

### 14.13. feedback_injector.py -- Epistemic Feedback Loop

**File:** backend/services/feedback_injector.py (~200 lines)

**get_feedback_block(ticker, session) -> str (or empty string if no prior):**
- Queries AnalysisHistory for the most recent analysis of the given ticker, ordered by created_at desc
- Parses stored JSON report (handles gzip-compressed full_json blobs)
- Extracts: prev_signal, prev_confidence, prev_target_3m, prev_target_12m, prev_price, prev_date
- Fetches current price via yfinance (ticker for NSE, ticker.NS or ticker.BO)
- Computes delta_pct = ((current - prev) / prev) * 100
- Determines direction = "UP" or "DOWN"
- Sets was_correct = (bullish_signal AND delta > 0) OR (bearish_signal AND delta < 0)
  where bullish_signal = signal in {BULLISH, CAUTIOUSLY BULLISH}
  and bearish_signal = signal in {BEARISH, CAUTIOUSLY BEARISH}

**Returns formatted block (~200-400 tokens):**
"=== EPISTEMIC FEEDBACK: PREVIOUS ANALYSIS AUDIT ===
... full block per section 5.2 ...
=== END EPISTEMIC FEEDBACK ==="

### 14.14. staleness.py -- Analysis Staleness Scoring

**File:** backend/services/staleness.py (~100 lines)

**compute_staleness(analysis, current_price) -> {score: 0-100, urgency: URGENT/STALE/AGING/FRESH, breakdown: {age_score, price_score, signal_score, coverage_score}}:**

**Age Component (weight 40):**
- Never analyzed: +40
- Older than 30 days: +40
- Older than 14 days: +25
- Older than 7 days: +10
- Less than 7 days: 0

**Price Movement Component (weight 35):**
- |change_7d| > 10%: +35
- |change_7d| > 5%: +20
- |change_7d| > 2%: +8
- |change_7d| <= 2%: 0

**Signal Mismatch Component (weight 15):**
- BEARISH signal + price up > 5%: +15
- BULLISH signal + price down > 5%: +15
- No mismatch: 0

**Analyst Coverage Component (weight 10):**
- Reserved for future use (currently always 0)

**Total Score: age_score + price_score + signal_score + coverage_score**
- >= 70: URGENT
- >= 45: STALE
- >= 20: AGING
- < 20: FRESH

### 14.15. disk_cache.py -- Filesystem Cache

**File:** backend/services/disk_cache.py (110 lines)

**Cache Directory:**
- macOS: ~/Library/Caches/nivesh/
- Linux: /var/cache/nivesh/
- Override: NIVESH_CACHE_DIR environment variable

**Storage Format:**
- Gzip-compressed JSON files
- Filename: SHA256(first 16 hex chars of key) + readable key (truncated)
- Extension: .json.gz

**Namespaces and TTLs:**
| Namespace | TTL | Purpose |
|-----------|-----|---------|
| yfinance | 6 hours | yfinance ticker responses, quick-info fallback |
| bhavcopy | 24 hours | NSE Bhavcopy daily |
| options | 15 minutes | NSE option chain |
| news_processed | 12 hours | FinBERT results (avoid re-scoring) |

**Functions:**
- get(namespace, key): Checks file exists, checks age vs TTL, unlinks if expired, loads gzip JSON. Returns None on miss/error.
- set(namespace, key, value): Creates namespace dir if needed, writes gzip'd JSON with default=str for non-serializable types
- invalidate(namespace, key): Unlinks cache file
- stats(): Returns per-namespace count and size in MB + total disk usage
- Never raises exceptions -- all errors logged via logger.warning

### 14.16. error_telemetry.py -- Diagnostic Error System

**File:** backend/services/error_telemetry.py (211 lines)

**log_diagnostic_error() Parameters:**
- subsystem (str): e.g. "EARNINGS_CALENDAR", "NSE_DATA_PROVIDER"
- classification (str): e.g. "CONNECTION_TIMEOUT", "API_RATE_LIMIT", "PARSE_FAILURE"
- context (dict, optional): target_ticker, market_hours_state, etc.
- telemetry (dict, optional): http_method, route, ios_swift_file (for iOS error relay)
- exception (dict, optional): {type, message}, traceback auto-cleaned
- correlation_id (str, optional): from request.state.correlation_id
- automated_recovery (str, optional): description of recovery action taken

**Traceback Cleaning:**
Strips internal framework noise: uvicorn, starlette, anyio, fastapi lines
Keeps only: /backend/routers/, /backend/services/, /backend/tradingagents-core/ lines

**Returns:** error_uuid (UUID4 string) for client to relay in support requests

**Writes to:**
1. market_error_logs table: component=subsystem, message truncated to 2000 chars
2. earnings_error_logs table: only when subsystem starts with "EARNINGS"
3. stdout: full JSON payload with [DIAGNOSTIC_ERROR] prefix

**CorrelationIDMiddleware (Starlette BaseHTTPMiddleware):**
- Reads X-Correlation-ID header from incoming request
- Generates nivesh_srv_{uuid4()[:8]} if header missing
- Stores in request.state.correlation_id
- Echoes back in response headers as X-Correlation-ID

### 14.17. portfolio_snapshot.py -- Daily Valuation

**File:** backend/services/portfolio_snapshot.py (97 lines)

**get_current_price(ticker) -> float or None:**
- Tries ticker.NS first, then ticker.BO
- Uses yfinance history(2d), returns Close[-1]
- Returns None on complete failure

**snapshot_all_users() -- runs nightly at 4:30 PM:**
1. Fetches all users from DB
2. Fetches NIFTY close via yfinance ^NSEI (for benchmark comparison)
3. For each user:
   - Skip if today's snapshot already exists (UniqueConstraint guard)
   - For each holding: fetch current price (fallback to buy_price if price missing)
   - Sum total_value from all holdings
   - Sum total_invested from all holdings (shares * buy_price)
   - Compute P&L = total_value - total_invested
   - Compute P&L% = (total_value / total_invested - 1) * 100
   - Create PortfolioValuationHistory row with snapshot_date, total_value, total_invested, total_pnl, pnl_percent, nifty_close
   - Commit per user (rollback on error, continue to next user)

### 14.18. filings_extractor.py -- NSE Corporate Filings

**File:** backend/services/filings_extractor.py (~100 lines)

**Data Source:**
NSE Corporate Announcements API: https://www.nseindia.com/api/corporate-announcements
Uses _nse_session() for cookie-based authentication
Parameters: index=equities, symbol={ticker}

**harvest_filings() -- runs every 15 minutes:**
1. Fetches all unique tickers from portfolio + analysis_history tables
2. For each ticker: fetch from NSE API, check for new announcements since last check
3. Filter for relevant categories: earnings results, board meetings, dividend announcements, stock splits, bonus issues
4. Store relevant filings in memory for earnings calendar population
5. Log errors via logging.warning without crashing

**Key Categories:**
- Earnings Results: "Quarterly Results", "Annual Results"
- Board Meetings: "Board Meeting" (for dividend/bonus/split decisions)
- Corporate Actions: "Dividend", "Stock Split", "Bonus"
- Governance: "Auditor Appointment", "Change in Directorate"
## 15. iOS VIEWS -- COMPLETE REFERENCE

### 15.1. HomeScreen.swift (Main Dashboard)

**File:** ios/StockApp/stockme/stockme/Views/HomeScreen.swift (~1200 lines)

**ViewModel:** HomeViewModel (@MainActor ObservableObject)

**Published Properties:**
- portfolioValue, todayPnL, totalPnL, investedValue, stockCount -- portfolio summary
- watchlist: [Stock] -- list of stocks the user watches
- indices: [LiveMarketIndex] -- market indices (5-min polling via Timer)
- morningBriefData: MorningSummaryResponse? -- AI-generated morning brief
- sectorData: [SectorPerformance] -- sector performance grid
- earningsEvents: [EarningsEvent] -- upcoming earnings for held tickers
- dashboard: MarketDashboardResponse? -- combined market data

**Section Order (16 sections rendered in ScrollView):**

1. AppHeader: Bilingual Hindi/English header, GovernorSealAvatar, account holder name
2. DailyActionCard: High/medium/low urgency action items from /daily-action endpoint
3. Portfolio Hero (PortfolioNoteCard): Uses Rs 2000 note denomination design
   - Shows total value, invested, P&L, P&L% with gold accents
   - Animates number transitions with .contentTransition(.numericText())
4. Market Indices: Horizontal scrolling IndexChip cards
   - Nifty 50, Sensex, Nifty Bank, Nifty IT, Nifty Midcap 100
   - Green/red coloring based on change direction
   - Timer-based polling every 300 seconds
5. Watchlist: Vertical StockRow list
   - Each row shows: ticker, company name, signal badge, ASM/GSM chip
   - Tapping navigates to AnalysisScreen via NavigationStack
6. Timeframe Conflicts: Horizontal scroll of TimeframeConflictCard
   - Shows short-term vs long-term upside conflicts per holding
7. Sector Pulse (SectorHeatmapView): 2-column grid of sectors
   - Each tile: sector name, change%, green/red with opacity based on magnitude
8. Morning Brief (MorningDecreeCard):
   - Priority pills: ALERT (red) for mood=negative, SIGNAL (green) for positive, INFO (amber) for neutral
   - Bullet points with Indian number formatting
   - "TODAY'S PRIORITIES" section with priority items (max 5)
9. Market News: Horizontal scrolling CompactNewsCell (10 items)
   - Shows headline, source badge, sentiment indicator
10. Dalal Street Consensus (DalalStreetConsensusCard):
    - Advisory consensus from YouTube harvest
    - Sector-level bullish/bearish distribution
    - Trending tickers with mention count
11. YouTube Videos: 3 rows x 5 columns of YouTubeCompactCard
    - Thumbnail, channel name, view count (formatted in lakhs/k)
12. This Week's Results: Earnings events 0-14 days away
    - Ticker, earnings date, days away count
13. Market Pulse (MarketPulseDashCard):
    - Advance/decline breadth ratio
    - Index rows with change%
14. Momentum Scan (MomentumDashCard):
    - Bullish section: stocks with golden crosses (limited to 5)
    - Bearish section: stocks with death crosses (limited to 5)
    - Each row: sparkline (20 data points)
15. Macro and Alternatives (MacroDashCard):
    - Brent Crude, Gold, USD/INR, US 10Y Yield, India VIX
    - Color-coded: VIX > 20 = red, > 15 = gold, else green
16. Institutional Allocation (InstitutionalDashCard):
    - Top 6 mutual funds by 1-year return
    - Name, category, return%, AUM

### 15.2. AnalysisScreen.swift -- THE FLAGSHIP VIEW

**File:** ios/StockApp/stockme/stockme/Views/AnalysisScreen.swift (~1946 lines)

**ViewModel:** AnalysisViewModel (@MainActor ObservableObject)

**Published Properties:**
- analysis: StockAnalysis? -- the main AI analysis
- quickInfo: QuickInfo? -- live price snapshot
- isLoading, errorInfo, quarterlyFinancials, promoterHistory, niftyPrices
- macroStrip, earningsEvents, analystRatings, macroImpacts

**Analysis Fetch Flow (parallel async/await):**
1. Cancel any existing Task
2. Set isLoading=true, clear error
3. Parallel fetch via async let:
   - quickInfo(ticker), quarterlyFinancials(ticker), niftyHistory(365)
   - macroStrip(), earningsCalendar(), analystRatings(ticker)
   - macroImpacts(userId) -- authenticated
4. Record quickInfoElapsed for performance diagnostics
5. Call NetworkManager.shared.analyze(ticker, userId, deepScan)
6. On success: save to LocalReportManager, update @Published analysis
7. On error: build AnalysisErrorInfo with timing, retryability, diagnostics
8. Set isLoading=false

**Live Price Polling:**
- Runs every 30 seconds in a Task
- Calls quickInfo endpoint
- Updates livePrice with .contentTransition(.numericText()) animation

**5 Sub-Tabs (horizontal pill selector with gold underline, spring animation):**

**Tab 0: OVERVIEW (lines 504-703):**
- Earnings banner: if earnings event exists for this ticker
- "Should I be worried?" card: portfolio-only, maps signal to worry level
  - Bullish/Cautiously Bullish -> "Low" (green checkmark)
  - Neutral/Hold -> "Medium" (amber triangle)
  - Cautiously Bearish -> "Medium-High" (red triangle)
  - Bearish -> "High" (red X shield)
- Signal Change Diff Card: compares current vs previous signal
  - Shows previousSignal -> currentSignal arrow
  - 3 key factors that changed
- Confidence Card: perforation bar (20 dots)
  - 80-100: "High Confidence" (green)
  - 60-80: "Moderate Confidence" (amber)
  - 40-60: "Uncertain" (red)
  - < 40: "Low Confidence" (red)
- Price Projections: 3 HorizonNoteCards (3M, 12M, 3Y)
- Set Price Alert button -> opens AddAlertSheet
- Personal note if portfolio notes exist

**Tab 1: ANALYSIS (lines 708-857):**
- Macro Strip: horizontal bars for USD/INR, Crude WTI, RBI Repo Rate + Stance, India VIX
- Macro Impact Banner: per-holding macro sensitivity chips
- Key Factor Cards: 3 cards with bilingual headers
  - Geopolitical/Policy, Global Macro Impact, Indian Market Sentiment
- Patterns Detected: sparkle icons if patterns non-empty
- Bull Case / Bear Case / Operational Risks: AnalysisNoteSection with colored left bars
- What to Watch: items flagged with "CORP ACTION" badge if containing split/bonus/rights/dividend
- Broker Consensus: aggregated buy/hold/sell counts, horizontal scrolling broker ratings
- Advisory Matrix Card: YouTube advisor stances per ticker

**Tab 2: CHARTS (lines 862-905):**
- Price Range Gauge: 52-week range slider with current dot and target diamond
- Price History Chart: 3M/6M/All toggle, 50 SMA + 200 DMA overlay
- RSI Chart: 14-period RSI with overbought(70)/oversold(30) zones
- Volume Chart: bars with 2x avg volume highlight
- Stock vs Nifty Chart: indexed comparison (owned stocks only)

**Tab 3: FUNDAMENTALS (lines 910-978):**
- Key Numbers Grid: 2-column, P/E, D/E, Promoter%, FII%, DII%
- Valuation Badge: P/E vs 3Y average
- Insider Trend: Promoter/FII/DII history bars
- Shareholding Chart: Promoter/FII/DII/Public bar chart
- Financials Chart: quarterly revenue bars + net profit line
- AnalysisLimitationsCard: collapsible disclaimer

**Tab 4: NEWS (lines 984-1006):**
- NewsItemCard list from analysis.recentNews or quickInfo?.recentNews
- Each: thumbnail, title, publisher badge, sentiment
- Tapping opens NewsReaderView: fullscreen with hero image, summary, "READ FULL STORY" link

### 15.3. PortfolioScreen.swift

**File:** ios/StockApp/stockme/stockme/Views/PortfolioScreen.swift (~1650 lines)

**Features:**
- Holdings list: StockRow with P&L, signal badge, staleness indicator
- Total portfolio value with Indian formatting (Crores/Lakhs)
- P&L breakdown: total + per-holding, green/red coloring
- Watchlist CRUD: add/remove via swipe actions
- Risk Analysis: beta, risk score, sector concentration, correlation
- Red Flags: critical (red), warning (amber), watch (yellow) sections
- Valuation Calendar: sparkline history with peak/trough markers
- Net Worth Snapshot: daily delta, peak value
- Export: Excel (openpyxl format) and PDF (fpdf2)
- Trade Journal: entry list with action badges, stats summary

### 15.4. EarningsDashboardView.swift

**File:** ios/StockApp/stockme/stockme/Views/EarningsDashboardView.swift (~1769 lines)

**Features:**
- Earnings Feed: Latest results with revenue/profit growth% and sparklines
- Sort modes: Latest, Best Performer (profit growth descending), Worst Performer (profit growth ascending)
- Market cap filter: Nifty 50, Large Cap, Mid Cap, Small Cap, All
- Calendar day view: results grouped by date with estimated vs actual comparison
- Progress bar: reported vs total (5042 tracked companies)
- Post-Result Movers: stocks with significant price moves after earnings (last 14 days, max 15)
- Cap Index Aggregator: 4 cap brackets (NIFTY_50, LARGE, MID, SMALL) with avg PE, revenue, profit growth

### 15.5. TechnicalMomentumView.swift

**File:** ios/StockApp/stockme/stockme/Views/TechnicalMomentumView.swift (~200 lines)

**Features:**
- Index selector: Nifty 50, Bank Nifty, etc.
- 7 sub-tabs: Golden Crosses, Death Crosses, RSI Oversold, RSI Overbought, Volume Spikes, Breakout, 52W High/Low
- Each tab: horizontal scrolling list with sparklines
- Sparkline: 20-point close history

### 15.6. SearchScreen.swift

**File:** ios/StockApp/stockme/stockme/Views/SearchScreen.swift (~504 lines)

**Features:**
- Search bar with in-memory filtering (~290 stocks) + debounced backend merge (350ms)
- Prefix-match priority: ticker matches first, then company name, then sector
- 8 Screener presets: Quality Value, Ghar Ghar Modi, Earnings Pioneers, Inst. Capitulation, Promoter Conviction, FII Accumulation, Turnaround, 52W Low Bullish
- Each preset calls /screener?preset={name} endpoint
- Screener results: fetches from backend, renders ScreenerResultRow (signal, confidence%, F-Score, PE, RSI, PCR)
- Trending stocks: from morning brief movers or fallback list
- Direct "Analyse anyway" NavigationLink for unmatched tickers

### 15.7. AlertsScreen.swift

**File:** ios/StockApp/stockme/stockme/Views/AlertsScreen.swift (~200 lines)

**Features:**
- Active alerts list: ticker, direction (above/below), target price, current price, distance%
- Triggered banner: green/red card showing triggered alerts
- Add alert: bottom sheet with ticker, price, direction selector
- Swipe to delete
- Empty state: "No price alerts set"

### 15.8. TradeJournalScreen.swift

**File:** ios/StockApp/stockme/stockme/Views/TradeJournalScreen.swift (~200 lines)

**Features:**
- Entry list: ticker, action (BUY/SELL/HOLD/WATCH), price, reason, outcome
- Action badges: green for BUY, red for SELL, amber for HOLD, blue for WATCH
- Add entry form: ticker, action picker, price, reason text, mood
- Stats summary: total entries, most journalled ticker, win/loss ratio, action breakdown, pattern detection
## 16. DESIGN SYSTEM -- COMPLETE TOKEN REFERENCE

### 16.1. Color System (Theme.swift)

**Light/Dark Adaptive Colors:**

| Token | Light Hex | Dark Hex | RGB Light | RGB Dark | Usage |
|-------|-----------|----------|-----------|----------|-------|
| Theme.canvas | #F5F0E8 | #1C1A14 | 245,240,232 | 28,26,20 | Main background (aged paper / charcoal) |
| Theme.canvasDeep | #EDE8DC | #242018 | 237,232,220 | 36,32,24 | Card surfaces (deeper paper / dark card) |
| Theme.canvasShadow | #D9D3C4 | #141210 | 217,211,196 | 20,18,16 | Pressed/inset surfaces |
| Theme.inkPrimary | #2C2C2C | #E8E0D0 | 44,44,44 | 232,224,208 | Primary text |
| Theme.inkSecondary | #5C6B5A | #8A9E80 | 92,107,90 | 138,158,128 | Secondary text (sage green) |
| Theme.inkTertiary | #8A8A7A | #5C5C52 | 138,138,122 | 92,92,82 | Tertiary/faded text |
| Theme.securityGold | #B8973A | #C8A84A | 184,151,58 | 200,168,74 | Primary accent (dull gold) |
| Theme.securityGoldLight | #E8C96A | #E8C96A | 232,201,106 | 232,201,106 | Light gold (same both modes) |
| Theme.bullGreen | #2D5A3D | #4A8A5D | 45,90,61 | 74,138,93 | Bullish signal |
| Theme.bullGreenLight | #4A7A5A | #5A9A6A | 74,122,90 | 90,154,106 | Light bullish |
| Theme.bearRed | #8B3A2A | #C05540 | 139,58,42 | 192,85,64 | Bearish signal |
| Theme.bearRedLight | #B55A45 | #D06A55 | 181,90,69 | 208,106,85 | Light bearish |
| Theme.holdAmber | #8B6914 | #B08020 | 139,105,20 | 176,128,32 | Hold/neutral |

**Border Colors:**
- Theme.borderFine: inkPrimary at 10% opacity
- Theme.borderSage: inkSecondary at 20% opacity
- Theme.paperBorder: black 8% (light) / white 6% (dark)
- Theme.paperTexture: black 3% (light) / white 2.5% (dark)

**Gradients:**
- Theme.securityThreadGradient: LinearGradient from securityGold (35%) to clear (8%), vertical

### 16.2. Typography System

**4 Font Functions (all using Dynamic Type scaling):**

| Function | Font Family | Weight | Usage |
|----------|-------------|--------|-------|
| Theme.engravedSerif(size:weight:relativeTo:) | Georgia / Georgia-Bold | Regular / Bold | Primary text, headings, values, "N" logo, prices |
| Theme.serialNumberFont(size:relativeTo:) | System monospaced | .medium | Tickers, percentages, numerical data, serial numbers |
| Theme.officialStampFont(size:relativeTo:) | System default | .medium | Section headers, stamp labels, captions, bilingual |
| Theme.hindiFont(size:relativeTo:) | Georgia Italic | Regular | Hindi/Devanagari text (nivesh, bhaarateey vittiya) |

### 16.3. Spacing System

| Token | Value |
|-------|-------|
| Theme.Spacing.xSmall | 2pt |
| Theme.Spacing.small | 4pt |
| Theme.Spacing.tight | 6pt |
| Theme.Spacing.medium | 8pt |
| Theme.Spacing.standard | 12pt |
| Theme.Spacing.card | 16pt |
| Theme.Spacing.screen | 20pt |
| Theme.Spacing.large | 24pt |
| Theme.Spacing.xLarge | 32pt |

Convenience: Theme.cardPadding = 20pt, Theme.screenPadding = 20pt, Theme.sectionSpacing = 32pt

### 16.4. Corner Radii

| Token | Value |
|-------|-------|
| Theme.CornerRadius.small | 4pt |
| Theme.CornerRadius.tight | 6pt |
| Theme.CornerRadius.medium | 8pt |
| Theme.CornerRadius.large | 12pt |
| Theme.CornerRadius.card | 16pt |

### 16.5. Built-in Reusable Components

**PaperTexture:** Full-screen background with canvas color + noise grain (random dots at paperTexture opacity) + sage tint overlay in top-left. Used as background for every screen.

**BanknoteWatermark:** Rotated text (e.g., "NIVESH") at configurable opacity (default 3%), positioned diagonally across content area.

**GuillocheDivider:** Decorative divider using sine/cosine wave paths. Two overlapping waves with phase offset create anti-counterfeit pattern. Drawn at 1pt with fineBorder color.

**CountUpNumber:** Animated number counting up from zero to target value using spring animation. Used for portfolio value displays.

**StaggerAppear:** ViewModifier that staggers fade-in + slide-up animation across child views. Delay per child: index * 0.1s. Animation: easeOut(duration: 0.5).

**banknoteCard():** ViewModifier applying double-border card style:
- canvasDeep background
- securityGold outer border (1.5pt) + fine inner border (0.5pt)
- canvasShadow shadow (offset y=2, radius=4, opacity=15%)
- 12pt corner radius

**EKPressStyle:** Button press animation:
- Scale: 0.97, opacity: 0.88
- Spring: response=0.35, damping=0.55
- Applied via .ekPress() view modifier

**SecurityThread:** Vertical strip (3pt wide, full height) with repeating "NIVESH RBI" microtext, using securityGoldGradient. Positioned at the leading edge of premium cards.

**RupeeWatermark:** Large faint Rs symbol at 320pt font size, positioned behind hero content at 3% opacity.

**BanknoteSignalBadge:** Signal stamp badge with color coding:
- BULLISH: bullGreen background, "BULLISH" text
- BEARISH: bearRed background, "BEARISH" text
- NEUTRAL/HOLD: holdAmber background
- Rounded rectangle with 4pt corner radius

**GovernorSealAvatar:** RBI-seal-style circular avatar with user initials. Uses securityGold border, canvasDeep background, engravedSerif font for initials.

---

## 17. INDIAN NUMBER FORMATTING SYSTEM

### 29.1. Backend (Python -- main.py and helpers.py)

**Constants:**
```python
LAKH = 100000       # 1,00,000
CRORE = 10000000    # 1,00,00,000
```

**Format Rules:**
- < 1 Lakh: plain number with Indian-style commas (e.g., Rs 75,000)
- 1 Lakh to < 1 Crore: Rs X.XX Lakhs (e.g., Rs 1.50 Lakhs)
- >= 1 Crore: Rs X.XX Crores (e.g., Rs 1.25 Crores)
- Negative: prefix dash (e.g., -Rs 37.50 Lakhs)

**Guard Function (_ban_western_scale()):**
- Raises ValueError if "million", "billion", or "trillion" appears in output
- Used in tests to enforce Indian numbering compliance

### 29.2. iOS (Swift -- IndianFormatter.swift, 92 lines)

**en_IN Locale NumberFormatter:**
- IndianFormatter.price(Double) -> "Rs 1,23,456.78"
- IndianFormatter.percent(Double) -> "+12.3%" (includes sign)
- IndianFormatter.priceWithoutSymbol(Double) -> "1,23,456.78"
- IndianFormatter.priceCompact(Double) -> "1.23 Cr" or "12.3 L" or "123"
- IndianFormatter.formatLakhsCrores(Double) -> "Rs 1.23 Crores"
- IndianFormatter.lakhsCroresNoSymbol(Double) -> "1.23 Crores"
- IndianFormatter.delta(Double) -> "+12.3%" (signed percentage)
- IndianFormatter.elapsed(Date?) -> "just now" / "5 minutes ago" / "3 hours ago" / "2 days ago"

**Double Convenience Extensions:**
- .inrFormatted -> IndianFormatter.price(self)
- .percentFormatted -> IndianFormatter.percent(self)
- .shortFormatted -> IndianFormatter.priceCompact(self)

---

## 18. DATA VALIDATION RULES

### 18.1. Input Validation (Pydantic)

| Field | Type | Validation | Error Code |
|-------|------|------------|------------|
| ticker | str | regex ^[A-Z0-9.&]{1,20}$ | INVALID_TICKER |
| exchange | str | must be NSE or BSE | INVALID_EXCHANGE |
| user_id | int | must be positive (if provided) | INVALID_USER |
| direction | str | must be "above" or "below" | INVALID_DIRECTION |
| action | str | must be BUY/SELL/HOLD/WATCH | INVALID_ACTION |
| shares | float | must be > 0 | INVALID_SHARES |
| buy_price | float | must be > 0 | INVALID_PRICE |
| target_price | float | must be > 0 | INVALID_TARGET |

### 18.2. Response Normalization (Backend)

Every analysis response guarantees these fields exist:
- signal: string (one of 6 valid values)
- confidence_pct: int (0-100)
- current_price_inr: float (>= 0)
- target_prices.short_term_3m: float (default 0.0)
- target_prices.medium_term_12m: float (default 0.0)
- target_prices.long_term_36m: float (default 0.0)
- upside_downside_pct.*: float (default 0.0)
- key_factors.*: string (default "Data not available")
- fundamentals_snapshot.*: float or null (all optional)
- bull_case/bear_case/key_risks: [string] (default [])
- disclaimer: string (default "This is an AI-generated analysis. Do your own research before investing.")

### 18.3. iOS Model Decoding (Models.swift)

Custom Codable init(from:) for every model ensures:
- Missing keys: default values provided (never crash on decode)
- Wrong types: try? coercion with fallback
- Unknown enum values: map to .neutral for Signal
- Optional fields: gracefully nil
- Debug logging: NetworkManager+Sidebar._diagnosticDecode() logs field-level failures

Signal enum custom decoder maps variations:
- "BUY", "STRONG BUY", "STRONG_BUY" -> bullish
- "SELL", "STRONG SELL", "STRONG_SELL", "AVOID" -> bearish
- "CAUTIOUS" -> cautiously_bearish
- Any unknown -> neutral (never crashes)

---

## 19. MIGRATION HISTORY

### 19.1. Architecture Migrations

| Date | Change | Files Modified | Impact |
|------|--------|---------------|--------|
| May 2026 | Monolithic -> Router Architecture | Split main.py into 7 routers | Non-breaking, all endpoints preserved |
| May 2026 | TradingAgents v0.2.5 integration | Added tradingagents-core/ | Non-breaking, AI pipeline enhanced |
| May 2026 | SQLite -> PostgreSQL support | database.py | Configurable via DATABASE_URL |
| Jun 2026 | Smart Cache Gate (DeepSeek) | main.py (analyze function) | Reduced AI costs by ~40% |
| Jun 2026 | Epistemic Feedback Loop | services/feedback_injector.py | Improve analysis quality |
| Jun 2026 | FinBERT Sentiment | services/sentiment_engine.py | Enhanced news scoring |
| Jun 2026 | Two-tier AI provider architecture | main.py build_ta_config() | DeepSeek for bulk, Claude for critical |

### 19.2. Database Migrations

| Date | Table | Change |
|------|-------|--------|
| May 2026 | trade_journal | Added company_name, mood, updated_at columns |
| May 2026 | advisor_insights | Added view_count column |
| May 2026 | analysis_history | Added outcome_delta_pct, was_correct, outcome_checked_at columns |
| Jun 2026 | youtube_videos | Added matched_ticker, source, sebi_reg columns |
| Jun 2026 | net_worth_ledger | Added peak_value_inr, top_gainer_ticker, top_loser_ticker columns |

---

## 20. SECURITY CONSIDERATIONS

### 20.1. API Key Management
- All API keys stored in backend/.env (gitignored)
- TradingAgents framework reads from .env via python-dotenv at import
- Multiple providers supported with per-provider env vars
- Ollama requires no API key (local inference)

### 20.2. JWT Security
- Algorithm: HS256
- Secret: JWT_SECRET env var or secrets.token_hex(32) auto-generation
- Expiry: 72 hours
- Token contains: sub (user_id), iat (issued at), exp (expiry)
- Admin bypass: token "admin" maps to user_id=1 (development only)

### 20.3. Password Security
- Current: bcrypt with 12 rounds ($2b$ prefix)
- Legacy support: SHA-256 with salt, plain SHA-256
- Migration path: old hashes upgrade to bcrypt on successful login

### 20.4. Rate Limiting
- Global: 120 requests per 60 seconds per IP
- Analysis: 2 concurrent analyses per user
- Registration: rate-limited per IP to prevent spam

### 20.5. CORS Configuration
- Default: allow all origins (*) for development
- Production: configured via ALLOWED_ORIGINS env var
- Security headers: X-Content-Type-Options (nosniff), X-Frame-Options (DENY), X-XSS-Protection (1; mode=block), Referrer-Policy (strict-origin-when-cross-origin)

### 20.6. Admin Access
- Admin set populated at startup: "saumya", "nirav"
- require_admin() dependency raises 403 for non-admin users
- Admin endpoints: dashboard stream, error logs, notification management, YouTube harvest trigger

---

*This document is the authoritative source for the Nivesh System DNA. It must be updated immediately upon any architectural shift or service logic change.*

## 21. COMPLETE API ENDPOINT REFERENCE

### 21.1. Authentication (routers/auth.py)

| Method | Endpoint | Auth | Rate Limit | Description |
|--------|----------|------|------------|-------------|
| POST | /login | None | 5/min | Email + password login, returns JWT token |
| POST | /register | None | 3/min | Create new user account |

**Auth Flow:**
- Password hashed via bcrypt (passlib)
- JWT issued with 7-day expiry (python-jose)
- Token stored in iOS Keychain via AuthManager
- All subsequent requests carry `Authorization: Bearer <token>` header

### 21.2. Portfolio (routers/portfolio.py -- 2100+ lines)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /portfolio/analyze | Full AI analysis via DeepSeek agents (8 parallel agents) |
| POST | /portfolio/add | Add stock to portfolio (ticker, quantity, buyPrice, date) |
| POST | /portfolio/remove | Remove holding or reduce quantity |
| POST | /portfolio/update | Update buy price, quantity, or notes |
| POST | /portfolio/add-note | Add free-text note to a holding |
| GET  | /portfolio/valuation-history | Historical portfolio value time series |
| GET  | /portfolio/overview | Current portfolio summary (% returns, sector allocation) |
| POST | /portfolio/snapshot | Trigger manual valuation snapshot |
| POST | /portfolio/export/pdf | Generate matplotlib PDF report (11 chart types) |
| POST | /portfolio/export/xlsx | Generate Excel report with openpyxl |
| POST | /portfolio/analyze/progress | SSE stream for real-time analysis progress |
| GET  | /portfolio/insights | AI-generated portfolio insights |
| POST | /portfolio/morning-brief | Daily morning briefing generation |
| POST | /trade-journal/add | Log trade to journal |
| POST | /trade-journal/update | Update existing trade journal entry |
| GET  | /portfolio/bulk-screener-signals | Bulk screener signals for all holdings |

### 21.3. Market Data (routers/market.py)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /market-indices | Live NSE Nifty 50 and BSE Sensex values |
| GET | /nifty-history | Historical Nifty 50 price data |
| GET | /market-pulse | Aggregate market sentiment (advance/decline, volatility) |
| GET | /market-momentum | Momentum indicators for broad market |
| GET | /macro-alternatives | Macroeconomic alternative data |
| GET | /institutional-flow | FII (Foreign Institutional Investor) / DII (Domestic) flow data |
| GET | /earnings-sync-ratio | Earnings synchronization ratio across sectors |
| GET | /yoy-aggregate | Year-over-year aggregate earnings data |
| GET | /option-chain | NSE option chain data |
| GET | /derivatives-metrics | Futures and Options metrics (OI change, PCR, IV) |
| GET | /price-history/{ticker} | Historical OHLCV for a specific ticker |
| GET | /fundamentals/{ticker} | Fundamental data (PE, PB, ROE, DE, market cap) |
| GET | /asm-gsm-list | ASM (Additional Surveillance Measure) / GSM list |
| GET | /corporate-filings | Recent corporate filings |

### 21.4. AI Analysis (routers/analysis.py)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /analyze | Full AI analysis (Claude Haiku/Sonnet with 8-stage pipeline) |
| POST | /analyze/quick | Lightweight analysis (single LLM call, fewer indicators) |
| POST | /analyze/batch | Batch analysis for multiple tickers |
| POST | /analyze/progress | SSE stream for real-time analysis progress |
| GET  | /analyze/screener | Stock screener results |
| POST | /quick-info | Quick info lookup |
| GET  | /technical-signals | Cached technical signals |

### 21.5. Alerts and Notifications

| Method | Endpoint | File | Description |
|--------|----------|------|-------------|
| POST | /alerts/add | alerts.py | Create price alert |
| DELETE | /alerts/remove | alerts.py | Remove alert |
| GET  | /alerts/list | alerts.py | List user alerts |
| POST | /users | user.py | User profile management |
| POST | /watchlist/add | user.py | Add stock to watchlist |
| DELETE | /watchlist/remove | user.py | Remove from watchlist |
| GET  | /watchlist | user.py | List watchlist with signals |
| POST | /device-token/register | user.py | Register iOS device for push |
| POST | /test-notification | user.py | Send test push notification |
| POST | /morning-summary-push | user.py | Trigger morning summary push |
| POST | /api/v1/notifications/register | notifications.py | Register notification preferences |
| GET  | /api/v1/notifications/logs | notifications.py | View notification delivery logs |
| POST | /api/v1/notifications/push-mock | notifications.py | Mock push for testing |

### 21.6. Dashboard and Feed (main.py inlined routes)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET  | /api/v1/dashboard/stream | SSE live dashboard updates |
| GET  | /api/v1/home-feed | Aggregated feed (news, YouTube, red flags, portfolio warnings) |
| POST | /api/v1/admin/portfolio | Admin portfolio operations |
| POST | /api/v1/admin/broadcast | Admin broadcast to all users |
| POST | /api/v1/admin/harvest | Trigger advisor harvest manually |
| POST | /api/v1/analyze-uncached | Force uncached analysis |
| POST | /api/v1/analyze-diagnostic | Diagnostic analysis with full logging |
| POST | /api/v1/reformat | Reformat analysis response |
| GET  | /api/v1/advisor/list | List available advisors |
| POST | /api/v1/advisor/insights | Get advisor insights for a ticker |
| POST | /api/v1/text-advisory/analyze | Text-based advisory analysis |
| POST | /api/v1/ideas/generate | Generate investment ideas |

---

## 22. iOS SUPPLEMENTARY FILES AND UTILITIES

### 22.1. App Entry and Lifecycle

**stockmeApp.swift (@main)**
- App entry point with WindowGroup
- Onboarding flow: OnboardingScreen -> DisclaimerScreen -> biometric auth -> ContentView
- Enforces disclaimer acceptance check on launch
- Biometric authentication via LAContext (Face ID / Touch ID)

**AppDelegate.swift**
- Push notification registration with APNs
- UNUserNotificationCenter delegate methods
- Token delivery to backend via device-token/register endpoint

**ContentView.swift (Root View)**
- Routes between LoginScreen and main tab interface based on AuthManager.isLoggedIn
- Tab bar with: Home, Portfolio, Analysis, Search, Settings
- Each tab has its own NavigationStack

### 22.2. Network Layer

**NetworkManager.swift (981 lines)**
- Singleton with URLSession configuration
- Base URL configurable per environment (dev/prod)
- JWT token auto-attachment via AuthManager
- All API calls as async throwing functions
- JSON decoding with error context
- SSE stream support for live progress endpoints
- Endpoint coverage: login, register, analyze (all variants), portfolio (CRUD + export), watchlist, market data, alerts, home feed, notifications, advisor

**NetworkManager+Sidebar.swift**
- Diagnostic JSON decoding helper
- Field-level error logging for debugging malformed responses
- Used by NiveshNavigationSidebar view

**ValuationCalendarService.swift**
- Fetches portfolio valuation history from /portfolio/valuation-history
- Returns time-series data for chart rendering

### 22.3. Data Models (Models.swift -- 1685 lines)

**Portfolio Models:**
- PortfolioStatus, PortfolioHolding, PortfolioOverview, PortfolioValuationHistory
- TradeJournalEntry, PortfolioInsight, MorningBrief

**Analysis Models:**
- AnalysisReport, TechnicalSignal, FundamentalData, SentimentData
- AIAnalysisResult, AnalysisProgress (SSE), ScreenerResult

**Market Models:**
- MarketIndex, NiftyHistory, MarketPulse, MarketMomentum
- InstitutionalFlow, OptionChain, DerivativesMetrics
- CorporateFiling, ASMGSMEntry

**User Models:**
- UserProfile, WatchlistEntry, AlertConfig, DeviceToken

**Feed Models (HomeFeedModels.swift):**
- HomeFeedResponse, FeedItem, NewsArticle, YouTubeVideo
- RedFlagAlert, PortfolioWarning

### 22.4. Persistence Layer

**StockDatabase.swift (Static In-Memory DB)**
- ~85+ NSE stocks with: ticker, companyName, exchange (NSE/BSE), sector
- Lookup methods: byTicker(), bySector(), search()
- Used for autocomplete in SearchScreen and watchlist add

**WatchlistStore.swift**
- UserDefaults-backed watchlist persistence
- Array of ticker strings
- Methods: add(), remove(), contains(), all()
- Publishes @Published changes for SwiftUI reactivity

**AuthManager.swift**
- ObservableObject with @Published isLoggedIn
- Token persistence in UserDefaults (Keychain wrapper for production)
- login() and logout() methods
- Biometric auth state management

### 22.5. Services and Managers

**HomeFeedService.swift**
- Fetches aggregated home feed from /api/v1/home-feed
- SSE streaming for real-time updates
- Caching layer (UserDefaults with TTL)

**HomeFeedViewModel.swift**
- ObservableObject driving HomeScreen
- onAppear triggers feed fetch with caching
- Throttling to prevent rapid re-fetches
- Pull-to-refresh support
- Error state management with ErrorDiagnoser

**NotificationManager.swift**
- UNUserNotificationCenter wrapper
- Request authorization on first launch
- Schedule local notifications for price alerts
- Handle incoming remote notifications

**AppSoundManager.swift**
- AVAudioPlayer for rupee_rustle.mp3
- Triggered on portfolio value change, alert triggers
- Haptic co-playback via HapticManager

**TutorialManager.swift (46 lines)**
- ObservableObject with 10-step tutorial flow
- Steps: welcome, portfolio add, analysis, watchlist, alerts, charts, trade journal, settings, notifications, complete
- Current step persisted in UserDefaults

### 22.6. Utilities

**Extensions.swift (240 lines)**
- Color(hex:) initializer for hex color strings
- View extensions: cornerRadius(radius:corners:) for specific corner masking
- HapticManager base class
- hapticOnTap() view modifier
- ViewDidLoad modifier (UIKit bridge)

**IndianFormatter.swift (92 lines)**
- price(_:) -- formats to Indian locale with Rupee symbol (e.g., "Rs 1,23,456.78")
- percentage(_:) -- formats with + prefix for positive, sign for negative
- change(_:) -- colored formatted change (green for positive, red for negative)
- compact(_:) -- compact notation (e.g., "1.2L", "3.5Cr")
- Uses en_IN locale with NumberFormatter

**Theme.swift (304 lines)**
- Full light/dark adaptive color system (see Section 16.1)
- Semantic colors: success, warning, danger, accent
- Background hierarchy: canvas -> canvasDeep -> canvasDeepest
- Text hierarchy: textPrimary -> textSecondary -> textTertiary
- Surface colors for cards, dividers, input fields

**ErrorDiagnoser.swift (290 lines)**
- ErrorDiagnostic struct with properties: endpoint, httpStatus, correlationId, failingContract, rawResponse, errorType
- Diagnostic sheet overlay view
- Automatic error capture in all NetworkManager calls
- Suggested remediation text per error type

**HapticManager.swift (61 lines)**
- Static methods: selection(), soft(), light(), rigid(), heavy(), success(), warning(), error()
- Maps to UIImpactFeedbackGenerator/UINotificationFeedbackGenerator
- Used throughout views for tactile feedback on interactions

### 22.7. Components and Views (Non-Screen)

**AdvisorBioCard.swift** -- Advisor profile card for the advisory matrix
**BanknoteErrorCanvas.swift** -- Banknote-themed full-screen error view with SecurityThread animation
**NewsCardView.swift** -- News article card with headline, source, timestamp
**SharedComponents.swift** -- Reusable UI components (LoadingSpinner, ErrorBanner, EmptyStateView, SectionHeader)
**YouTubeCardView.swift** -- YouTube video card with thumbnail, channel, duration

### 22.8. Charts

**StockCharts.swift**
- LineChart view (portfolio valuation history)
- CandlestickChart view (OHLC data)
- BarChart view (sector allocation)
- PieChart view (holding distribution)
- All charts use Canvas API (not Swift Charts) for custom styling
- Banknote-themed: warm paper backgrounds, SecurityThread accents

---

## 23. TEST COVERAGE LANDSCAPE

### 23.1. Backend Tests (backend/tests/)

### 23.2. Backend Test Suites (backend/tests_suite/)

### 23.3. Standalone Test Scripts (backend/)

### 23.4. iOS Tests

### 23.5. Coverage by Area

| Area | Backend | iOS |
|------|---------|-----|
| Authentication | Good (login, register, token validation) | None |
| Portfolio CRUD | Comprehensive (add, remove, update, export) | None |
| AI Analysis | Good (all pipeline stages, error handling) | None |
| Market Data | Moderate (index endpoints, fundamentals) | None |
| Watchlist | Moderate (CRUD, signal integration) | None |
| Alerts | Minimal (CRUD only) | None |
| Scrapers | Good (RSS, YouTube with mocks) | N/A |
| Database | Comprehensive (schema, constraints, migrations) | N/A |
| iOS UI | N/A | Stub only |

---

## 24. DEVOPS AND DEPLOYMENT

### 24.1. Docker Deployment (backend/Dockerfile)

### 24.2. Production Deployment (DigitalOcean)

### 24.3. Environment Configuration

### 24.4. Deployment Architecture

### 24.5. Push Notification Infrastructure

```
iOS App
   |
   +-- Registers for remote notifications (AppDelegate)
   +-- Sends device token to POST /device-token/register
   |
Backend
   |
   +-- Stores device tokens in UserDevice table
   +-- APNs connection via apns2 Python library
   +-- Auth Key: P8 file (Apple-issued, RSA private key)
   +-- Key ID + Team ID in Authorization header (JWT provider-token)
   +-- Notification types:
       - Price alerts (user-configured thresholds)
       - Morning summary (daily at 7:00 AM IST)
       - Portfolio red flags (AI-detected anomalies)
       - System announcements (admin broadcast)
```

---

## 25. DATA MIGRATION AND SCHEMA HISTORY

### 25.1. Migration Strategy

### 25.2. Schema Evolution (Inferred from Code)

### 25.3. Seed Data

**Stocks Table:**
- ~85+ NSE stocks pre-seeded
- Includes: ticker, company_name, sector, industry, bse_code, isin, face_value
- Sectors covered: IT, Banking, Auto, Pharma, FMCG, Energy, Metals, Telecom, Consumer Durables, Realty, Infrastructure

**Users Table:**
- No seed users (all created via registration)
- Admin user created via .env ADMIN_USERNAME/ADMIN_PASSWORD_HASH

---

## 26. PORTFOLIO CHARTS (matplotlib) -- DETAILED REFERENCE

### 26.1. File: backend/portfolio_charts.py (754 lines)

### 26.2. Chart Theming

```python
# Theme constants used across all charts
BG_COLOR = '#1C1A14'       # Dark charcoal (matches iOS dark canvas)
TEXT_COLOR = '#E8E0D0'     # Warm off-white (matches iOS textPrimary)
ACCENT_COLOR = '#D4A84B'   # Gold (matches Theme.accent)
GREEN_COLOR = '#4CAF50'    # Positive returns
RED_COLOR = '#F44336'      # Negative returns
GRID_COLOR = '#3A3530'     # Subtle grid lines
FONT_FAMILY = 'DejaVu Sans'
```

---

## 27. SECURITY CONSIDERATIONS (DEEP DIVE)

### 27.1. Authentication and Authorization
### 27.2. API Security
### 27.3. Data Protection
### 27.4. iOS Security
### 27.5. Infrastructure Security
### 27.6. Security Review Items (Medium/High Priority)
1. CORS origin should be restricted to known domains
2. JWT token should be stored in iOS Keychain, not UserDefaults
3. No certificate pinning for API communications
4. Rate limiting should be more granular (per-endpoint, per-user)
5. No audit logging for admin operations
6. APNs authentication key path should be verified on startup
7. Add Alembic for schema migrations with version control

---

## 28. ERROR HANDLING PATTERNS (COMPLETE REFERENCE)

### 28.1. Backend Error Handling
### 28.2. iOS Error Handling
### 28.3. Error Types Reference

| Error Type | Source | Recovery | User Message |
|------------|--------|----------|-------------|
| Network Timeout | Client (30s) | Auto-retry (3x) | "Taking longer than usual. Retrying..." |
| HTTP 401 | Backend | Force logout | "Session expired. Please login again." |
| HTTP 429 | Backend | Wait + retry-after | "Too many requests. Please wait." |
| HTTP 5xx | Backend | Retry with backoff | "Server hiccup. Pull to refresh." |
| Decoding Error | Client | Cache fallback | "Unexpected response format." |
| LLM Timeout | Backend | Skip agent + warn | -- (internal, cached) |
| LLM Parse Error | Backend | Regex repair | -- (internal, repaired) |
| Database Error | Backend | Retry (3x) | -- (internal, logged) |

---

## 29. RATE LIMITING AND SCALING

### 29.1. Current Rate Limits

### 29.2. AI API Rate Management

### 29.3. Scaling Considerations

**Current: Single DigitalOcean Droplet (2GB RAM, 1 vCPU)**
- Handles ~50 concurrent users
- AI analysis queue: ~2-3 analyses/min
- Peak usage: 8:00-9:00 AM IST (morning brief generation)
- Database: SQLite (local) -- switches to PostgreSQL at ~100 users

**Scaling Path (100-500 users):**
1. SQLite to PostgreSQL (connection string change, zero code changes)
2. Add Redis cache for market data (reduce yfinance calls)
3. Increase uvicorn workers from 4 to 8
4. Add request queuing for AI analysis (avoid concurrent LLM rate limits)

**Scaling Path (500+ users):**
1. Horizontal scaling: multiple droplets behind nginx load balancer
2. Centralized PostgreSQL (DigitalOcean Managed DB)
3. AI analysis queue via Celery/Redis (decouple from request-response cycle)
4. CDN for static chart exports (PDF, XLSX)
5. Read replicas for market data queries
