# Nivesh (निवेश) — Hyper-Detailed Architecture Map

> **Authority:** This is the definitive technical blueprint and "System DNA" of the Nivesh ecosystem. 
> **Scope:** Full-stack analysis covering SwiftUI (iOS), FastAPI (Backend), and LangGraph (AI Pipeline).
> **Last Updated:** June 4, 2026.
> **Total Files Indexed:** 259
> **Documentation Target:** 4000 Lines (Density: High)

---

## 1. Project Philosophy & Core Pillars

Nivesh is designed as a **Premium AI-First Wealth Intelligence System** focused on the Indian Equity Market. It operates on three non-negotiable architectural principles:

### Pillar I: The Banknote Aesthetic (Frontend)
The user interface is built as a **Financial Instrument**. Using native SwiftUI primitives, it simulates the tactile and visual security features of the Indian Rupee.
*   **Guilloché Logic:** Procedural drawing of sine-wave pairs for borders and dividers.
*   **Tactile Feedback:** Haptic-driven interactions (EKPressStyle) that mimic the weight and resistance of paper currency.
*   **Visual Fidelity:** 500-grain canvas texture noise and 10% opacity RBI watermark stamps.

### Pillar II: Dialectical Reasoning (AI Pipeline)
Nivesh rejects "one-shot" AI responses. It employs a **Multi-Agent Dialectic Loop** built on LangGraph:
1.  **Adversarial Challenge:** Bull and Bear researchers must attempt to invalidate each other's thesis.
2.  **Iterative Risk Review:** A 3-node committee (Aggressive/Neutral/Conservative) iterates on the proposal until a "Risk Clearance" signal is generated.
3.  **Epistemic Feedback:** Past thesis errors are injected back into the current context to prevent repeating historical mistakes.

### Pillar III: Context Stratification (Performance)
To handle complex Indian market rules without high latency, the system uses **Prefix-Aligned Prompt Caching**:
*   **Static Layer:** Hardened persona instructions and tool definitions are cached.
*   **Volatile Layer:** Ticker-specific OHLCV data and news are passed as a final HumanMessage.

---

## 2. Graph Intelligence: God Nodes & Connection Densities

The system graph reveals a complex web of "Strong" and "Weak" nodes.

### 1. God Node: `CodingKeys` (210 Edges)
This is the **Strongest Node** in the entire ecosystem. It exists in `Models.swift`.
*   **Why:** It is the "Structural Glue". Every backend response must perfectly align with this Swift enum. It bridges the Python-to-Swift chasm. A failure here results in a catastrophic UI silent-fail.

### 2. God Node: `get_session()` (93 Edges)
The **Central Hub** for Backend State.
*   **Why:** It connects the "User" community to the "Intelligence" community. Every service (`advisor_harvester`, `portfolio_snapshot`, `feedback_injector`) depends on this to read or write truth.

### 3. God Node: `TradingAgentsGraph` (91 Edges)
*   **Role:** The entry point for the AI dialectic. It connects the "Research" community to the "Persistence" community.

### 4. God Node: `ConditionalLogic` (80 Edges)
*   **Role:** Manages the circular loops (Debate/Risk Jury). Without this node, Nivesh would be a linear "One-Shot" AI app.

---

## 3. Backend Subsystem Architecture (`/backend`)

The backend is a high-performance FastAPI service implementing the "Dalal Street Intelligence" layer.

### 3.1. API Routing Layer (`/backend/routers`)

*   **`auth.py`**: Manages user lifecycle.
    *   *Security Logic:* Uses `passlib.context.CryptContext` with the `bcrypt` scheme. Tokens are generated via `jose.jwt`.
    *   *Graph Connection:* Strong edge to `User` table; Weak edge to `DeviceToken` for push notifications.
*   **`analysis.py`**: The most critical router.
    *   *Logic:* Spawns a `multiprocessing.Process` for every analysis. Uses a `manager.dict()` to communicate progress stages (e.g., "Scanning Technicals...", "Bull/Bear Debate in Progress...") back to the main thread.
    *   *Failover:* Implements a `try-finally` block that clears the user's "active run" lock even if the AI process crashes.
*   **`portfolio.py`**: Performance-heavy calculations.
    *   *Logic:* Merges DB holdings with live prices from `nse_data_provider`. Computes total valuation and P&L in real-time.
    *   *Optimization:* Uses `asyncio.gather` for fetching prices of multiple tickers in parallel.

### 3.2. Data Intelligence Services (`/backend/services`)

*   **`factor_engine.py` (The Mathematical Core)**:
    *   *Algorithm:* Uses the `ta` library (Technical Analysis Library in Python).
    *   *Indicators:* RSI-14, MACD (12, 26, 9), SMA (50, 200), ROC-21, OBV, and Bollinger Bands.
    *   *Stability:* Implements a `_rsi_numpy` fallback in case the `ta` library is unavailable in the environment.
*   **`ticker_matcher.py` (The Linguistic Engine)**:
    *   *Algorithm:* `rapidfuzz.fuzz.token_set_ratio`.
    *   *Mechanism:* Sliding-window scan of transcripts. Uses a manual alias table for Hinglish terms (e.g., "TM" -> `TATAMOTORS`, "hdfc wala bank" -> `HDFCBANK`).
*   **`options_scraper.py` (The Derivatives Layer)**:
    *   *Logic:* Fetches JSON from `nseindia.com/api/option-chain-equities`.
    *   *Metrics:* Computes PCR (Put-Call Ratio) and identifies "Max Pain" levels. Detects institutional positioning by comparing Call OI vs Put OI at the nearest strike.
*   **`feedback_injector.py` (The Epistemic Loop)**:
    *   *Logic:* Calculates `outcome_delta_pct` of the previous report. If the signal was BULLISH and price dropped, it forces a "Reflection" prompt into the current run.
*   **`sentiment_engine.py` (The NLP singleton)**:
    *   *Model:* `yiyanghkust/finbert-tone` (HuggingFace).
    *   *Implementation:* Loads the model once into memory (Singleton) to prevent 3-5s load latency on every request.

---

## 4. AI Reasoning Engine: The LangGraph Pipeline

The reasoning engine is a directed acyclic graph (DAG) with cyclic loops for debate.

### 4.1. Step-by-Step AI Execution Protocol

1.  **State Init**: `AgentState` is initialized with ticker, trade_date, and ground-truth numbers from `factor_engine`.
2.  **Parallel Analysts**:
    *   **Market Analyst Node**: Selects up to 8 complementary indicators. Interprets them into Dalal Street behavioral prose.
    *   **News Analyst Node**: Hard-coded to scan for "Auditor resignation," "SEBI probe," and "CFO Exit." Marked as `⚠ GOVERNANCE` red flags.
    *   **Fundamentals Analyst Node**: Analyzes P/L and Balance Sheet. Focuses on **Promoter Pledging** trends.
3.  **The Dialectical Debate (Cycles 1-3)**:
    *   **Bull Researcher**: Makes the case for growth and turnaround.
    *   **Bear Researcher**: Actively looks for reasons the thesis will fail (Sector headwinds, valuation froth).
    *   *Convergence Check:* `ConditionalLogic` determines if they should debate further or if the friction points are clear.
4.  **Synthesis & Proposal**:
    *   **Research Manager**: Writes the executive summary of the debate.
    *   **Trader Node**: Proposes concrete transaction (Buy/Hold/Sell) with entry/SL levels.
5.  **The Risk Committee Review**:
    *   3 nodes (**Aggressive**, **Conservative**, **Neutral**) review the Trader's proposal.
    *   If the Conservative agent flags a "Governance Risk," the signal is automatically downgraded to CAUTIOUS.
6.  **Final Raw Verdict**: `Portfolio Manager` delivers the final recommendation.
7.  **Sonnet 3.5 Reformatting**:
    *   Applies strict **Indian Market Weighting** (Management > Institutions > Sentiment > Fundamentals).
    *   Enforces "Rupee-Denominated Prose" (Lakhs/Crores).

---

## 5. iOS Frontend Architecture (`/ios`)

The iOS app is a high-fidelity SwiftUI masterpiece designed for the Dalal Street professional.

### 5.1. View Logic & State Management

*   **`AnalysisScreen.swift` (The Flagship)**:
    *   *ViewModel:* `AnalysisViewModel` uses `@MainActor` and `async/await` to stream the AI report.
    *   *Tab Structure:* [OVERVIEW | ANALYSIS | CHARTS | FUNDAMENTS | NEWS].
    *   *Visuals:* Renders 11 native Swift Charts, including the "Relative Strength vs Nifty" benchmark.
*   **`HomeScreen.swift`**:
    *   *Priority logic:* Displays "Morning Brief" cards. Priority sequence: [TRIGGERED ALERTS > SIGNAL FLIPS > EARNINGS TODAY].
*   **`PortfolioScreen.swift`**:
    *   *Rupee Styling:* Uses `DenominationBackground` with adaptive colors (Emerald for hundred, Ruby for two-thousand).
    *   *Metrics:* Shows "Worry Level" based on AI signal distribution and ASM/GSM surveillance status.

### 5.2. Design System Components

*   **`DenominationBackground.swift`**:
    *   *Logic:* Implements a `ZStack` of `Canvas` layers. Draws the `RBISealBackground` at 0.018 opacity.
*   **`GuillocheDivider.swift`**:
    *   *Logic:* Uses a `TimelineView` to drive a sine-wave animation for the divider path.
*   **`AppSoundManager.swift`**:
    *   *Audio:* Orchestrates the "Rupee Rustle" and "Verified Chime" sounds using `AVAudioPlayer`.

---

## 6. Data Integrity & Persistence

*   **SQLite DNA**:
    *   The system uses **Deterministically Named Databases** for graph checkpoints (`backend/data/checkpoints/{TICKER}.db`).
    *   The main `stockapp.db` uses WAL (Write-Ahead Logging) mode for concurrent access from multiple harvesters.
*   **Report Caching**:
    *   iOS uses `LocalReportManager` to store GZIP-compressed JSON blobs of analysis history. This allows offline reading and "Signal Diffing."

---

## 7. Operational Flow: The Lifecycle of a Signal

1.  **Detection:** Nightly `news_harvester` or `youtube_harvester` detects a catalyst.
2.  **Notification:** Backend triggers a push to `DeviceToken`.
3.  **Initiation:** User taps notification, opening `AnalysisScreen`.
4.  **AI Subprocess:** `main.py` spawns the LangGraph process.
5.  **Reasoning:** 10+ agents debate Dalal Street nuances.
6.  **Formatting:** Sonnet 3.5 structures the verdict.
7.  **Tactile Delivery:** iOS renders the banknote UI with haptic confirmation and Rupee sound effects.

---

*This document is the authoritative source for the Nivesh System DNA. It must be updated immediately upon any architectural shift or service logic change.*
