# Nivesh (निवेश) — Hyper-Detailed Architecture Map

> **Authority:** This is the definitive technical blueprint of the Nivesh ecosystem. 
> **Scope:** Full-stack analysis covering SwiftUI (iOS), FastAPI (Backend), and LangGraph (AI Pipeline).
> **Last Updated:** June 3, 2026.

---

## 1. Project Philosophy & System Architecture

Nivesh is designed as a **Premium AI-First Wealth Intelligence System**. It is built on three architectural pillars:
1.  **Banknote Aesthetic (iOS):** A bespoke design system that uses native SwiftUI primitives to mimic the security features, colors, and textures of Indian currency.
2.  **Dialectical AI Pipeline (LangGraph):** A multi-agent graph that moves from raw research (Parallel Analysts) to adversarial synthesis (Bull/Bear Debate) to iterative risk validation (The Jury) and final verdict.
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
    *   **`NewsArticle`**: Stores scraped news with FinBERT sentiment scores and `is_red_flag` detection.
*   **`prompts.py`**: The "Brain" of the reformatting stage.
    *   **`INDIAN_MARKET_SYSTEM_PROMPT`**: 400+ lines of instructions enforcing "Hardened Risk Officer" persona, "Behavioral Translation" (e.g., RSI < 30 is "Retail Capitulation"), and the "Minskyan Tension Gauge" for FII/DII flows.

### Advisor Intelligence Services (`/backend/services`)
*   **`advisor_harvester.py`**: A nightly CRON service. Fetches transcripts via YouTube API, passes them to Claude Haiku to extract structured `stance`, `confidence`, and `catalyst`.
*   **`ticker_matcher.py`**: The "Hinglish" matching engine.
    *   **Mechanism**: Uses `rapidfuzz` (fuzz.token_set_ratio) with a sliding-window (size=6, step=3) to identify tickers in transcripts.
    *   **Alias Table**: Maps spoken nicknames (e.g., "HDFC wala bank" -> `HDFCBANK`, "Sujalon" -> `SUZLON`) to official symbols.
    *   **Snippet Extraction**: Automatically grabs ±60 seconds of text around a match for context.
*   **`transcript_engine.py`**: The two-layer transcription strategy.
    *   **Layer 1 (YouTube API)**: Free, zero compute.
    *   **Layer 2 (Whisper Fallback)**: Uses `faster-whisper` (large-v3) running on CPU (int8) if captions are disabled.
    *   **Quality Gate**: Implements a "Devanagari Ratio" check; if >15% of the text is raw Hindi script, it fails the gate (as the pipeline expects Hinglish/English).

---

## 3. AI Intelligence Pipeline (`/backend/tradingagents-core`)

The AI uses a fork of the **TradingAgents** framework, heavily customized for Indian market nuances.

### The LangGraph Flow (`trading_graph.py`)
1.  **Parallel Analysts**: Market, News (Red Flags), and Fundamentals nodes execute concurrently.
2.  **The Debate Loop**: `Bull Researcher` and `Bear Researcher` engage in a dialectical challenge. The number of rounds is controlled by `should_continue_debate`.
3.  **Synthesis**: `Research Manager` summarizes the debate; `Trader` node proposes target prices.
4.  **The Risk Jury (Iterative)**: A 3-node committee (`Aggressive` -> `Conservative` -> `Neutral`) reviews the proposal in a circular loop until `should_continue_risk_analysis` returns False.
5.  **Final Verdict**: `Portfolio Manager` delivers the final recommendation.
6.  **Deterministic Reformatting**: Claude 3.5 Sonnet applies the Indian Market Weighting and structures the JSON.

---

## 4. iOS Frontend Architecture (`/ios/StockApp/stockme/stockme`)

The frontend is a pure SwiftUI app (iOS 16+) with zero external dependencies.

### Core Architecture
*   **`stockmeApp.swift`**: Initializes `AuthManager`, `NetworkManager`, `TutorialManager`, and `AppSoundManager`.
*   **`ContentView.swift`**: The 8-tab central hub. Manages the `TabView` and tutorial step overlays.
*   **`NetworkManager.swift`**: High-fidelity API wrapper. Contains custom DTOs for `StockAnalysis` and `MorningSummary`.
*   **`Models.swift`**: The Swift schema. Mirrors the backend JSON structure exactly. Defines the `Signal` enum with associated colors and labels.
*   **`StockDatabase.swift`**: A static repository of 400+ NSE stocks used for local search and autocompletion.

### Premium Design System (`/Components` & `/Utilities`)
*   **`BanknoteDesignSystem.swift`**: Core Theme definition (Emerald, Ruby, Gold, Canvas).
*   **`DenominationBackground.swift`**: Implements `RBISealBackground`, `SecurityThread`, and `PaperTexture` noise overlays.
*   **`LaunchSequenceView.swift`**: Animated startup sequence simulating a banknote unfolding.
*   **`GuillocheDivider.swift`**: Custom animated wave dividers.
*   **`Theme.swift`**: Detailed adaptive color palette and typography tokens for the Indian Rupee aesthetic.
*   **`IndianFormatter.swift`**: Specialized logic for Lakh/Crore formatting and Rupee-denominated valuation displays.
*   **`HapticManager.swift`**: Centralized engine for `EKPressStyle` spring interactions and feedback.
*   **`NewsCardView.swift`**: High-fidelity cards for Yahoo Finance news integration.
*   **`YouTubeCardView.swift`**: Specialized components for rendering Advisor Intelligence insights with view counts and advisor stances.

### Specialized Services
*   **`AppSoundManager.swift`**: Manages the "Rupee Rustle" and UI feedback sounds.
*   **`ValuationCalendarService.swift`**: Manages the earnings and IPO calendar data formatting.

---

## 5. Logic Flow: The Lifecycle of an Analysis

1.  **Request**: User triggers "Deep Analysis" from iOS.
2.  **Smart Cache**: Backend checks if news headlines have changed since the last run. If "No", skips graph execution (**Cache Hit**).
3.  **Graph Propagation**: If "Yes", `run_trading_agents` starts the LangGraph subprocess.
4.  **Dual-Breakpoint Cache**: Sonnet 3.5 uses cached prompts (Blueprint) and cached history (Ticker context) for efficient reformatting.
5.  **Rendering**: The iOS app receives structured JSON, updates the local report database, and paints the banknote-themed UI.
