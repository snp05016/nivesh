# Nivesh App Navigation Map

This document provides a comprehensive map of where every feature is located in the Nivesh iOS App. Use this as context to help users navigate the app and discover tools.

## Global Features
- **AI Copilot**: Accessible from anywhere in the app. Users can trigger it to ask questions about their portfolio, request deep analysis, or ask general financial questions. It is injected via `.withCopilot()` on the root `ContentView`.

## Main Bottom Tab Bar

The app uses a 5-tab bottom navigation bar (`TabView`):

### 1. Home Tab (Index 0)
- **Location:** `HomeScreen`
- **Features:** Main dashboard, personalized widgets, high-level market indices overview, quick access to recent analysis.

### 2. Markets Tab (Index 1)
- **Location:** `MarketsView`
- **Description:** This is the primary hub for all analytical and quantitative tools. It contains a scrollable sidebar/menu mapped to `MarketSection` enum.
- **Sub-Screens inside Markets Tab:**
  - **Earnings Dashboard (`.earnings`)**: Tracks YoY growth, earnings calendar, beat/miss analysis, and post-result movers.
  - **Technical Momentum Scanner (`.technical`)**: OI trends, sector rotation, golden/death cross signals, and momentum scanning.
  - **Pre-IPO Marketplace (`.unlisted`)**: OTC price discovery for pre-IPO, SME board, and upcoming listing advisory.
  - **Screener (`.screener`)**: Standard stock discovery, search any NSE/BSE stock by name or ticker.
  - **Alerts (`.alerts`)**: Price watch, target price triggers, and surveillance flags.
  - **Strategy Lab (`.strategy`)**: Backtest pre-built and custom trading strategies against historical data.
  - **NL Screener (`.nl_screener`)**: Search stocks using Natural Language queries powered by AI (e.g. "profitable midcaps with zero debt").
  - **Correlation Matrix (`.correlation`)**: Cross-Asset Correlation. Analyzes trailing 6-month matrices to diversify portfolio risk.
  - **Market Anomalies (`.anomalies`)**: Scans the market for unusual volume spikes, price breakouts, or order book anomalies.
  - **Sector Rotation (`.sector_rotation`)**: Tracks capital flow across different market sectors visually.
  - **Stress Test (`.stress_test`)**: Simulates portfolio performance and resilience under various macroeconomic shocks.
  - **Earnings Surprise (`.earnings_surprise`)**: Tracks historical earnings beats and misses alongside current quarter estimates.

### 3. Ideas Tab (Index 2)
- **Location:** `ExpertNetworkView`
- **Features:** Expert stock ideas, curated research, and thematic baskets.

### 4. News Tab (Index 3)
- **Location:** `NewsMultimediaView`
- **Features:** Multimedia news feed, articles, and real-time financial updates.

### 5. Portfolio Tab (Index 4)
- **Location:** `PortfolioScreen`
- **Features:** User holdings, net worth, daily P&L, transaction history, and allocation breakdown.
