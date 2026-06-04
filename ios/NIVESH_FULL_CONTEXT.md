# Nivesh (निवेश) — Full App Context

> Paste this into Claude to get full context before brainstorming next steps.
> Last updated: June 3, 2026. Reflects current implemented state.

---

## What Is This

**Nivesh** is a personal Indian stock market analysis iOS app for a small family group (3 users). It wraps a multi-agent AI pipeline in a premium SwiftUI interface styled like an Indian Rupee banknote. Tap any NSE/BSE stock → wait 30–90s → receive structured AI investment analysis.

---

## The Stack

| Layer | Technology |
|---|---|
| iOS frontend | SwiftUI (iOS 16+), Swift Charts, zero dependencies |
| Backend API | FastAPI (Python), uvicorn, subprocess isolation |
| AI pipeline | TradingAgents (LangGraph multi-agent) |
| AI models | Multi-provider (Claude 3.5, DeepSeek-V3, MiniMax, Gemini) |
| Live market data | yfinance + jugaad-data (direct NSE) |
| News sources | Enriched YF News, Moneycontrol, Economic Times |
| Advisor Intelligence | Claude 3.5 Haiku + rapidfuzz (Hinglish matching) |
| Deterministic Engine| Factor Engine, Options Scraper, Piotroski, PKScreener |
| Feedback Loop | Epistemic Feedback Injector (Price Delta tracking) |
| NLP Engine | singleton FinBERT (yiyanghkust/finbert-tone) |

---

## Technical Deep Dive: The AI Analysis Engine

The Nivesh AI pipeline is a sophisticated multi-stage orchestration engine designed for high-fidelity financial reasoning, built on a **LangGraph** foundation with multi-provider LLM support.

### Step 1: Epistemic Feedback Injection
The `feedback_injector.py` service computes the price delta since the last analysis for this ticker. It injects a performance summary into the HumanMessage layer to ground the model in its own historical accuracy.

### Step 2: The Smart Cache Gatekeeper (Haiku 3.5)
Performs a **Differential News Check** vs the last report timestamp to skip redundant deep analyses.

### Step 3: Deterministic Pre-Computation
Mathematical engines provide "ground truth" prose to the analysts:
- **Factor Engine**: 30+ technical indicators.
- **Options Scraper**: PCR, Max Pain, and **Institutional OI Skew**.
- **Piotroski**: 9-point fundamental health score.
- **PKScreener**: Technical breakout and momentum signals.
- **FinBERT**: Institutional sentiment scoring for news.

### Step 4: Multi-Agent Orchestration (LangGraph Patterns)

#### A. Analyst Team Four-Agent Architecture
Market, News (Red Flags), Fundamentals, and Social agents run in parallel to populate the `AgentState`.

#### B. Bullish vs Bearish Researcher Debate Pattern
Adversarial loop stress-testing the investment thesis before synthesis.

#### C. Risk Management Three-Perspective Analysis
The proposal is reviewed by **Aggressive**, **Conservative**, and **Neutral** analysts in a circular loop managed by `ConditionalLogic`.

### Step 5: Deterministic Reformatting (Sonnet 3.5)
Structures the final JSON using **Dual-Breakpoint Prompt Caching** (Blueprint + History).

---

## iOS App — UI Layer Communities

| View | Focus |
|---|---|
| **AnalysisScreen** | 5-tab deep-dive with 11 native Swift Charts. |
| **HomeScreen** | Morning Brief, Indices, and Sector Pulse heatmap. |
| **PortfolioScreen**| Rupee-styled hero card and 10-segment risk meter. |
| **EarningsDashboard**| Corporate filings and regulatory news scraper. |
| **PreIPOMarketplace**| Unlisted/IPO-bound company tracking. |
| **TechnicalMomentum**| Native charts for Factor Engine and PKScreener data. |
| **ExpertNetwork** | Integration of the Advisor Intelligence pipeline. |

---

## Core Abstractions & "God Nodes" (Graph Insights)

*   **`CodingKeys`**: Structural bridge between Swift data models and backend schemas.
*   **`get_session()`**: Central hub for database state transitions.
*   **`TradingAgentsGraph`**: Primary AI orchestration entry point.
*   **`ConditionalLogic`**: Manages the iterative graph transitions.
*   **`AgentState`**: Shared memory carry-object for research data.

---

## Resilience & Monitoring

- **Graph Checkpointing**: Per-ticker SQLite databases allow crash recovery.
- **Token Auditing**: Centralized `token_log.jsonl` for LLM cost tracking.
- **Model Gating**: `capabilities.py` ensures provider-specific features are handled safely.
