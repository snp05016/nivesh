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

## 2. Backend Architecture (`/backend`)

The backend is a high-performance FastAPI service that manages all data harvesting, AI orchestration, and user sessions.

### Core Abstractions & "God Nodes" (Graph Insights)
*   **`CodingKeys`**: The most connected node in the system, serving as the bridge between Swift data models and backend JSON schemas.
*   **`get_session()`**: The central hub for all database-driven state transitions across 60+ endpoints.
*   **`TradingAgentsGraph`**: The primary entry point for the AI orchestration layer.
*   **`ConditionalLogic`**: Manages the flow transitions (Debate cycles, Risk jury loops) within the graph.
*   **`AgentState`**: The shared memory object that carries research data between agent nodes.

### Core Server Files
*   **`main.py` (250KB+):** The primary orchestration layer.
    *   **Subprocess Isolation:** AI analyses are run using `multiprocessing.Process` to protect the main FastAPI event loop.
    *   **Market Data Fallbacks:** Contains complex logic to failover from NSE (`.NS`) to BSE (`.BO`) if financials are missing.
*   **`database.py`:** Definitive SQLAlchemy schema.
    *   **`User`**, **`Portfolio`**, **`AnalysisHistory`**, **`AdvisorInsight`**, **`NewsArticle`**: Core entities forming the "Backend Database & State" community.
*   **`prompts.py`**: The instructions repository.

### Specialized Services Layer (`/backend/services`)
*   **`factor_engine.py`**: Deterministic pre-computation of RSI, MACD, SMA, etc.
*   **`piotroski.py`**: 9-point fundamental health check.
*   **`ticker_matcher.py`**: Hinglish ticker matching via `rapidfuzz`.
*   **`transcript_engine.py`**: YouTube Transcript API -> Whisper fallback.
*   **`pkscreener_runner.py`**: Technical breakout and momentum signal harvester.
*   **`sentiment_engine.py`**: FinBERT news sentiment.

---

## 3. AI Intelligence Pipeline (`/backend/tradingagents-core`)

The AI uses a customized fork of the **TradingAgents** framework, orchestrated via **LangGraph**.

### Hyperedge Architectures (Agent Patterns)
1.  **Analyst Team Four-Agent Architecture**:
    *   **Market Analyst**: Interprets technicals.
    *   **News Analyst**: Red Flag hunt.
    *   **Fundamentals Analyst**: Promoter/Financials check.
    *   **Social Analyst**: Contrarian sentiment signal.
2.  **Bullish vs Bearish Researcher Debate Pattern**:
    *   Adversarial loop stress-testing the investment thesis before synthesis.
3.  **Risk Management Three-Perspective Analysis**:
    *   **Aggressive**, **Conservative**, and **Neutral** analysts review the proposal iteratively until `ConditionalLogic` exits the loop.

### Execution Flow
1.  **Initialization**: `GraphSetup` configures nodes and edges based on `AgentState`.
2.  **Propagation**: `Propagator` drives the state through the graph until `Portfolio Manager` delivers the final verdict.
3.  **Reformatting**: Sonnet 3.5 applies "Indian Market Weighting" and structures the final JSON.

---

## 4. iOS Frontend Architecture (`/ios/StockApp/stockme/stockme`)

The frontend is a pure SwiftUI app (iOS 16+) with zero external dependencies.

### Community Hubs (UI Layers)
*   **iOS Analysis Screen**: High-fidelity detail view with 11 native Swift Charts.
*   **iOS Home Screen**: Dashboard for morning briefs, indices, and sector pulse.
*   **iOS Portfolio Screen**: Asset management with Rupee-styled UI and risk meters.
*   **iOS Network Layer**: The `NetworkManager` hub connecting Swift `Codable` models to FastAPI.

### Premium Design System (`/Components` & `/Utilities`)
*   **`BanknoteDesignSystem.swift`**: Defines the `Theme` (Emerald, Ruby, Gold, Canvas).
*   **`DenominationBackground.swift`**: Implements `RBISealBackground`, `SecurityThread`, and `PaperTexture`.
*   **`HapticManager.swift`**: Centralized engine for `EKPressStyle` spring interactions.

---

## 5. Logic Flow: The Lifecycle of an Analysis

1.  **Request**: User triggers "Deep Analysis" from iOS.
2.  **Smart Cache**: Backend checks for recent news shifts via Haiku.
3.  **Factor Compute**: `factor_engine` and `piotroski` calculate ground-truth numbers.
4.  **Graph Propagation**: `TradingAgentsGraph` runs the multi-agent dialectic loop.
5.  **Dual-Breakpoint Cache**: Sonnet 3.5 structures the JSON using cached prompt blueprints.
6.  **Rendering**: iOS app paints the banknote-themed UI from the structured `StockAnalysis` model.
