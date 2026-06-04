# Nivesh (निवेश) — Hyper-Detailed Architecture Map

> **Authority:** This is the definitive technical blueprint of the Nivesh ecosystem. 
> **Scope:** Full-stack analysis covering SwiftUI (iOS), FastAPI (Backend), and LangGraph (AI Pipeline).
> **Last Updated:** June 3, 2026.

---

## 1. Project Philosophy & System Architecture

Nivesh is designed as a **Premium AI-First Wealth Intelligence System** focused on the Indian Equity Market. It is built on three architectural pillars:
1.  **Banknote Aesthetic (iOS):** A bespoke design system using native SwiftUI primitives (`Canvas`, `Path`, `TimelineView`) to mimic the security features, colors, and textures of Indian currency.
2.  **Dialectical AI Pipeline (LangGraph):** A multi-agent graph that moves from raw research (Parallel Analysts) to adversarial synthesis (Bull/Bear Debate) to iterative risk validation (The Jury) and final verdict.
3.  **Prefix-Aligned Context Stratification:** A custom prompt caching strategy that minimizes latency and costs by separating static persona layers from volatile ticker-specific history.

---

## 2. Graph Intelligence & God Nodes

Analysis of the system graph reveals several "God Nodes" that serve as high-centrality bridges between communities:

*   **`CodingKeys` (Central Bridge):** The most connected node (210 edges). It serves as the structural contract between Swift `Codable` models and Python Pydantic/FastAPI schemas.
*   **`get_session()` (State Hub):** The nexus for all database-driven state transitions (93 edges). It bridges "Backend Database" to "Auth & Alerts" and "Portfolio Intelligence".
*   **`TradingAgentsGraph` (Core Logic):** The primary entry point for AI orchestration. It connects the "Graph & Propagation" community to "Test Rationales" and "Memory Logs".
*   **`ConditionalLogic` (Flow Controller):** Manages the iterative loops (Debate cycles, Risk jury loops) within the graph.
*   **`AgentState` (Shared Memory):** The carry-object that preserves state across 10+ specialized AI nodes.

---

## 3. Backend Architecture (`/backend`)

The backend is a high-performance FastAPI service that manages all data harvesting, AI orchestration, and user sessions.

### Core Server Files
*   **`main.py` (250KB+):** The primary orchestration layer.
    *   **Subprocess Isolation:** AI analyses are run using `multiprocessing.Process` to protect the main FastAPI event loop from heavy LLM/LangGraph resource consumption.
    *   **Market Data Fallbacks:** Contains complex logic to failover from NSE (`.NS`) to BSE (`.BO`) if financials are missing.
*   **`database.py`:** Definitive SQLAlchemy schema forming the "Backend Database & State" community.

### Data & Intelligence Services Layer (`/backend/services`)
This layer handles deterministic data processing and background harvesting.

| Service | Community | Functional Detail |
|---|---|---|
| **`nse_data_provider.py`** | Market Data | **Unified Abstraction Layer**. Prioritizes `jugaad-data` (direct NSE) with `yfinance` fallback. Agents must use this instead of direct imports. |
| **`factor_engine.py`** | Technicals | Pre-computes 30+ technical indicators (RSI-14, MACD, BB) using `ta` or `numpy`. Ground-truth for AI. |
| **`options_scraper.py`** | Derivatives | Fetches NSE option chains. Computes PCR, Max Pain, and **Institutional OI Skew**. |
| **`filings_extractor.py`** | Regulatory | Scrapes NSE corporate filings (15-min TTL). Powers the Earnings Dashboard. |
| **`news_harvester.py`** | News | Nightly RSS scraper (Moneycontrol/ET). Identifies **Red Flags** via keyword triggers. |
| **`sentiment_engine.py`** | NLP | Runs a singleton **FinBERT** (yiyanghkust/finbert-tone) for sentiment scoring of news headlines. |
| **`piotroski.py`** | Fundamentals | Calculates the 9-point health score (0-9) from yfinance balance sheets. |
| **`ticker_matcher.py`** | Hinglish | Uses `rapidfuzz` sliding-window matching to identify spoken tickers like "HDFC wala bank" in transcripts. |
| **`transcript_engine.py`** | Harvest | YouTube Transcript API -> Whisper large-v3 fallback with "Devanagari Ratio" quality gate. |
| **`youtube_harvester.py`** | Video | **SEBI-Only Registry**. Curated harvest from 6+ verified channels (SOIC, Basant Maheshwari, etc.) using INH registration numbers. |
| **`portfolio_snapshot.py`** | Reporting | Nightly valuation engine. Takes snapshots at 4:30 PM IST for P&L waterfall charts. |
| **`feedback_injector.py`** | Epistemic | Injects historical analysis outcomes (Price Delta vs AI Signal) back into the AI to prevent repeating errors. |

---

## 4. AI Intelligence Pipeline (`/backend/tradingagents-core`)

The AI uses a customized fork of the **TradingAgents** framework, orchestrated via **LangGraph**.

### Resilience & Monitoring
*   **`checkpointer.py`**: Implements per-ticker SQLite databases for mid-analysis state saving. Allows crashing runs to resume from the last successful node.
*   **`capabilities.py`**: Model-specific feature gating. Ensures tools like `effort` (Anthropic) or `reasoning_content` (DeepSeek) are only sent to supported endpoints.
*   **Token Monitoring**: A centralized `BaseCallbackHandler` logs all LLM calls to `token_log.jsonl` for cost auditing.

### Architectural Patterns (Hyperedges)
1.  **Analyst Team Four-Agent Architecture**: Market, News (Red Flags), Fundamentals, and Social (Euphoria) nodes.
2.  **Bullish vs Bearish Researcher Debate Pattern**: Adversarial stress-test loop before synthesis.
3.  **Risk Management Three-Perspective Analysis**: **Aggressive**, **Conservative**, and **Neutral** analysts review the proposal iteratively until `ConditionalLogic` exits.

---

## 5. iOS Frontend Architecture (`/ios/StockApp/stockme/stockme`)

### UI Layer Communities
*   **iOS Analysis Screen**: 5-tab detail view with 11 native Swift Charts.
*   **iOS Home Screen**: Dashboard for morning briefs (Priority Items) and sector pulse.
*   **iOS Portfolio Screen**: Rupee-styled hero card and 10-segment risk meter.
*   **iOS Network Layer**: `NetworkManager.shared` hub connecting Swift `Codable` models to FastAPI.

### Premium Components
*   **`DenominationBackground.swift`**: Uses `Canvas` drawing for the watermark effect.
*   **`LaunchSequenceView.swift`**: Animated startup sequence using `TimelineView`.
*   **`AppSoundManager.swift`**: Orchestrates "Rupee Rustle" audio feedback.
*   **`generate_icons.py`**: Python utility for automated multi-resolution app icon generation with gradients.

---

## 6. Logic Flow: The Lifecycle of an Analysis

1.  **Request**: User triggers "Deep Analysis" from iOS.
2.  **Checkpoint Check**: `checkpointer` looks for a resumed thread.
3.  **Feedback Check**: `feedback_injector` pulls the last report's outcome.
4.  **Smart Cache**: Haiku checks for news shifts.
5.  **Deterministic Compute**: `factor_engine`, `piotroski`, and `options_scraper` (via `nse_data_provider`) populate the state.
6.  **Graph Propagation**: `TradingAgentsGraph` runs the multi-agent dialectic loop.
7.  **Dual-Breakpoint Cache**: Sonnet 3.5 structures the JSON using cached prompt blueprints.
8.  **Rendering**: iOS app paints the banknote-themed UI from the structured `StockAnalysis` model.
