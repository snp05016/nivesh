# Nivesh App Navigation Map

> **Generated:** June 2026
> **Scope:** Full mapping of SwiftUI routing, TabView structure, and Sidebar layouts in the current iOS app.

This document provides a comprehensive map of where every feature is located in the Nivesh iOS App. Use this as context to help users navigate the app and discover tools.

## Global Features & Injections
- **AI Copilot (`CopilotScreen`)**: Accessible globally. Triggered to ask questions about portfolio, deep analysis, or financial queries. Injected via `.withCopilot()` on the root `ContentView`.
- **Global Search (`SearchScreen`)**: Accessible from the App Header, overriding the current view to search NSE/BSE tickers.
- **Authentication (`LoginScreen`, `OnboardingScreen`)**: Root guard views before the main `TabView` is loaded.

---

## Main Bottom Tab Bar (`ContentView.swift`)

The app uses a 5-tab bottom navigation bar (`TabView`):

### 1. Home Tab (Index 0)
- **Location:** `HomeScreen`
- **Features:** 
  - Main personalized dashboard.
  - High-level market indices overview (`IndexChip`).
  - Quick access to recent analysis (`AnalysisHistoryScreen`).
  - Home layout editing (`HomeLayoutEditorSheet`).
  - Advisory matrix (`AdvisoryMatrixCard`).

### 2. Markets Tab (Index 1)
- **Location:** `MarketsView` (Sidebar / Split View on iPad)
- **Description:** Primary hub for analytical and quantitative tools. Contains a scrollable sidebar mapped to the `MarketSection` enum.
- **Sub-Screens inside Markets Tab:**
  - **Earnings Dashboard (`EarningsDashboardView`)**: YoY growth, earnings calendar, beat/miss analysis, and post-result movers.
  - **Technical Momentum (`TechnicalMomentumView`)**: OI trends, golden/death cross signals, momentum scanning.
  - **Pre-IPO Marketplace (`PreIPOMarketplaceView`)**: OTC price discovery for pre-IPO, SME board, upcoming listings.
  - **Standard Screener (`SearchScreen` reused)**: Stock discovery.
  - **Alerts (`AlertsScreen`)**: Price watch, target triggers, surveillance flags.
  - **Strategy Lab (`StrategyLabScreen`)**: Backtest pre-built and custom trading strategies.
  - **Options Strategy (`OptionsStrategyScreen`)**: Greeks, implied volatility, payoff charts.
  - **NL Screener (`NLScreenerScreen`)**: Search stocks using Natural Language queries powered by AI.
  - **Correlation Matrix (`CorrelationMatrixScreen`)**: Analyzes trailing 6-month matrices to diversify risk.
  - **Market Anomalies (`MarketAnomalyScreen`)**: Scans for unusual volume spikes, breakouts, order book anomalies.
  - **Sector Rotation (`SectorRotationScreen`)**: Tracks capital flow across market sectors visually.
  - **Stress Test (`StressTestScreen`)**: Simulates portfolio performance under macroeconomic shocks.
  - **Earnings Surprise (`EarningsSurpriseScreen`)**: Tracks historical earnings beats/misses.

### 3. Ideas Tab (Index 2)
- **Location:** `ExpertNetworkView`
- **Features:** 
  - Expert stock ideas and curated research.
  - YouTube expert video embeds (`YouTubeCardView`).
  - Thematic baskets and Dalal Street Consensus (`DalalStreetConsensusCard`).

### 4. News Tab (Index 3)
- **Location:** `NewsMultimediaView`
- **Features:** 
  - Multimedia news feed and articles (`NewsCardView`).
  - Real-time financial updates.
  - FinBERT sentiment highlights.

### 5. Portfolio Tab (Index 4)
- **Location:** `PortfolioScreen`
- **Features:** 
  - User holdings and net worth.
  - Animated `PortfolioValueDisplay`.
  - Transaction history and allocation breakdown.
  - Trade journaling (`TradeJournalScreen`).
  - Valuation timeline (`ValuationCalendarView`).

---

## Deep-Dive Analysis Flow

When a user taps a specific stock (e.g., from Search or Portfolio):
1. **`StockProfileView`**: High-level overview, quick price charts, live data.
2. **`AnalysisScreen`**: The core AI output screen.
   - **Sections**: Governance, Fundamentals, Market, News, Bear Case, Bull Case.
   - **Widgets**: `DialecticProgressView`, `BanknoteSignalBadge`, `AdvisoryMatrixCard`.
3. **`CompareScreen`**: Triggered to compare two tickers side-by-side.

## Auxiliary Screens & Modals
- **Settings (`SettingsScreen`)**: Server URL overrides, theme toggles.
- **Tutorials (`TutorialOverlayView`, `InteractiveTutorialScreen`)**: User onboarding overlays.
- **Glossary (`GlossaryBrowserView`, `TermDefinitionSheet`)**: Dictionary for complex financial jargon.
- **Quiet Hours (`QuietHoursView`)**: Notification scheduling.
- **Sector Blacklist (`SectorBlacklistView`)**: User preferences to ignore certain sectors.
- **Crash Lab (`CrashLabView`)**: Diagnostics and telemetry testing.
- **Report Manager (`ReportManagerView`)**: Downloadable PDF/JSON AI reports.
