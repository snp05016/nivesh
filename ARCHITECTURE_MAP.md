# Nivesh (निवेश) — Hyper-Detailed Architecture Map

> **Authority:** This is the definitive technical blueprint of the Nivesh ecosystem. 
> **Scope:** Full-stack analysis covering SwiftUI (iOS), FastAPI (Backend), and LangGraph (AI Pipeline).
> **Last Updated:** June 3, 2026.

---

## 1. Project Philosophy & System Architecture

Nivesh is designed as a **Premium AI-First Wealth Intelligence System**. It is built on three architectural pillars:
1.  **Banknote Aesthetic (iOS):** A bespoke design system that uses native SwiftUI primitives to mimic the security features, colors, and textures of Indian currency.
2.  **Deterministic AI Pipeline (LangGraph):** A multi-agent graph that moves from raw research (Analysts) to synthesis (Researchers) to risk management (Analyst Jury) to a final reformatted verdict.
3.  **Prefix-Aligned Context Stratification:** A custom prompt caching strategy that minimizes latency and costs by separating static persona layers from volatile ticker-specific history.

---

## 2. Backend Architecture (`/backend`)

The backend is a high-performance FastAPI service that manages all data harvesting, AI orchestration, and user sessions.

### Core Server Files
*   **`main.py` (250KB+):** The primary orchestration layer. It contains 60+ REST endpoints.
    *   **Subprocess Isolation:** AI analyses are run using `multiprocessing.Process` to prevent the AI pipeline (which is resource-intensive) from blocking the async FastAPI event loop.
    *   **Rate Limiting:** Implements `_running_analyses` sets to ensure one concurrent run per user.
    *   **Market Data Fallbacks:** Contains complex logic to failover from NSE (`.NS`) to BSE (`.BO`) if financials are missing.
*   **`database.py`:** Definitive SQLAlchemy schema.
    *   **`User`**: Tracks hashed passwords and relationships to all other data.
    *   **`Portfolio`**: Stores holdings and watchlists. Note the `group_name` differentiator.
    *   **`AnalysisHistory`**: Stores the massive `full_json` reports returned by the AI.
    *   **`AdvisorInsight`**: Stores extracted stances from YouTube experts.
    *   **`NewsArticle`**: Stores scraped news with FinBERT sentiment scores.
    *   **`PortfolioValuationHistory`**: Stores daily snapshots for P&L waterfall charts.
*   **`prompts.py`:** The "Brain" of the reformatting stage.
    *   **`INDIAN_MARKET_SYSTEM_PROMPT`**: 400+ lines of instructions enforcing "Hardened Risk Officer" persona, "Behavioral Translation" (e.g., RSI < 30 is "Retail Capitulation"), and the "Minskyan Tension Gauge" for FII/DII flows.

### Services Layer (`/backend/services`)
*   **`advisor_harvester.py`**: A nightly CRON service. Fetches transcripts via YouTube API, passes them to Claude Haiku to extract structured ` stance`, `confidence`, and `catalyst`.
*   **`ticker_matcher.py`**: Uses `rapidfuzz` (Fuzzy Token Set Ratio) to match spoken names in transcripts (e.g., "Tata Motors", "HDFC wala bank") to official NSE symbols.
*   **`scraper.py`**: Custom scrapers for Moneycontrol and Economic Times RSS feeds.
*   **`transcript_engine.py`**: Manages the logic for fetching YouTube captions or using third-party transcription if captions are disabled.

---

## 3. AI Intelligence Pipeline (`/backend/tradingagents-core`)

The AI uses a fork of the **TradingAgents** framework, heavily customized for Indian market nuances.

### Pipeline Logic
*   **`tradingagents/graph/trading_graph.py`**: The LangGraph state machine.
    *   Defines the `AgentState` which carries the `market_report`, `news_report`, and `debate_history`.
    *   **Parallel Execution**: Analysts (Market/Fundamentals/News) execute concurrently to reduce wait times.
*   **`tradingagents/agents/analysts/market_analyst.py`**: The Technical Analyst.
    *   Dynamically selects up to 8 indicators (RSI, SMA, EMA, MACD, etc.).
    *   **Heuristic Logic**: "RSI > 70" is never reported as "Overbought"; it is reported as "Retail momentum overextended; institutional profit-booking zone."
*   **`tradingagents/llm_clients/anthropic_client.py`**: Wrapper for Claude 3.5. Implements `cache_control` headers for the Dual-Breakpoint strategy.

---

## 4. iOS Frontend Architecture (`/ios/StockApp/stockme/stockme`)

The frontend is a pure SwiftUI app (iOS 16+) with zero external dependencies.

### Core Architecture
*   **`stockmeApp.swift`**: The entry point. Initializes `AuthManager`, `NetworkManager`, and `TutorialManager`.
*   **`ContentView.swift`**: The 8-tab central hub. Manages the `TabView` and tutorial step overlays.
*   **`NetworkManager.swift`**: High-fidelity API wrapper.
    *   Uses `async/await` exclusively.
    *   Contains custom DTOs (Data Transfer Objects) to map backend JSON to Swift models.
    *   **Server URL Management**: Allows switching between local Dev and Production (DigitalOcean) via `UserDefaults` without a rebuild.
*   **`Models.swift`**: The Swift schema. Mirrors the backend JSON structure exactly. Defines the `Signal` enum with associated colors and labels.
*   **`StockDatabase.swift`**: A static repository of 400+ NSE stocks used for local search and autocompletion before the backend is even queried.

### Premium Design System (`/Components` & `/Utilities`)
*   **`BanknoteDesignSystem.swift`**: Defines the `Theme` struct (Emerald, Ruby, Gold, Canvas).
*   **`DenominationBackground.swift`**: Uses `RBISealBackground` and `SecurityThread` views to create the banknote texture.
*   **`LaunchSequenceView.swift`**: A complex animated sequence using `withAnimation` and haptics to simulate an app "unfolding" like a fresh banknote.

### Views Layer (`/Views`)
*   **`HomeScreen.swift`**: The Command Center. Displays the "Morning Brief", "Market Indices", and "Sector Pulse".
*   **`PortfolioScreen.swift`**: Displays the "Portfolio Hero" card and the 3-page chart carousel (Allocation, P&L, Sector).
*   **`AnalysisScreen.swift`**: The most complex view in the app.
    *   Features a 5-tab layout (Overview, Analysis, Charts, Fundaments, News).
    *   Uses **Swift Charts** to render 11 distinct native charts (SMA 50/200, RSI, Stock vs Nifty).
*   **`TradeJournalScreen.swift`**: A ledger-style view for logging trade psychology.

---

## 5. Deployment & DevOps

*   **`deploy_update.sh`**: Pushes backend changes to the production server.
*   **`run.sh`**: Local startup script. It kills any existing process on port 8000 using `lsof -ti:8000 | xargs kill -9` before starting `uvicorn`.
*   **`nivesh.service`**: Systemd service file for running the backend on a Linux server.
*   **`token_log.jsonl`**: A local tracker for AI credit consumption.

---

## 6. Logic Flow: The Lifecycle of a Ticker

1.  **Search**: User searches for "SUZLON" in `SearchScreen`. `StockDatabase` provides local results.
2.  **Quick Info**: App calls `/quick-info` for the initial price, sparkline, and news cards.
3.  **Analyze**: User taps "Deep Analysis". `NetworkManager` calls `/analyze`.
4.  **Smart Cache**: Backend checks `AnalysisHistory`. If news headlines are quiet, it clones yesterday's report (**Smart Cache Hit**).
5.  **Graph Execution**: If headlines are busy, `run_trading_agents` starts the LangGraph subprocess.
6.  **Refactor**: Sonnet 3.5 takes raw graph output, applies Indian Market weighting, and returns structured JSON.
7.  **Render**: `AnalysisScreen` receives the JSON and paints the "Banknote" analysis with 11 charts.
