# Nivesh (निवेश) — Definitive App Context

> Authority: This is the definitive project context document.
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
| AI models | Claude 3.5 Haiku (agents) + Claude 3.5 Sonnet (reformatter) |
| Live market data | yfinance (Yahoo Finance) with NSE-session fallbacks |
| News sources | Yahoo Finance News (enriched), Moneycontrol, Economic Times |
| Advisor Intelligence | Claude 3.5 Haiku (YouTube extraction) + rapidfuzz (Hinglish matching) |
| Database | SQLite via SQLAlchemy ORM |
| Deterministic Engine| Factor Engine (Technical), Options Scraper (Derivatives), Piotroski (Fundamental) |
| Feedback Loop | Epistemic Feedback Injector (Price Delta tracking) |
| NLP Engine | singleton FinBERT (yiyanghkust/finbert-tone) |

---

## Technical Deep Dive: The AI Analysis Engine

The Nivesh AI pipeline is a sophisticated multi-stage orchestration engine designed for high-fidelity financial reasoning, built on a **LangGraph** foundation.

### Step 1: Epistemic Feedback Injection
The `feedback_injector.py` service computes the price delta since the last analysis for this ticker. It injects a performance summary into theHumanMessage layer to ground the model in its own historical accuracy.

### Step 2: The Smart Cache Gatekeeper (Haiku 3.5)
Performs a **Differential News Check** vs the last report timestamp.
- **Outcome**: If "NO significant shift", clones the previous report and updates current price (**SMART CACHE HIT**).

### Step 3: Deterministic Pre-Computation
Mathematical engines provide "ground truth" prose to the analysts:
- **Factor Engine**: 30+ technical indicators (RSI, MACD, OBV).
- **Options Scraper**: PCR, Max Pain, and **Institutional OI Skew**.
- **Piotroski**: 9-point fundamental health score.
- **FinBERT**: Headline sentiment scoring.

### Step 4: Multi-Agent Orchestration (LangGraph Patterns)

#### A. Analyst Team Four-Agent Architecture
Market, News (Red Flags), Fundamentals, and Social agents run in parallel to populate the `AgentState`.

#### B. Bullish vs Bearish Researcher Debate Pattern
Adversarial loop stress-testing the investment thesis. Managed by `ConditionalLogic`.

#### C. Risk Management Three-Perspective Analysis
The proposal is reviewed by **Aggressive**, **Conservative**, and **Neutral** analysts in a circular loop until `ConditionalLogic` determines the risk is fully mapped.

### Step 5: Deterministic Reformatting (Sonnet 3.5)
Structures the final JSON using **Dual-Breakpoint Prompt Caching** (Blueprint + History).

---

## Performance & Optimization — Anthropic Prompt Caching

| Optimization | Method | Impact |
|---|---|---|
| **Prompt Caching** | Dual-Breakpoint (Static + History) | 90% reduction in Sonnet input costs |
| **Smart Cache** | Haiku Headline Check | Skips $0.15 analysis for non-events |
| **Process Isolation** | `multiprocessing.Process` | Protects main API from heavy compute |
| **TTL Cache** | 5-minute In-Memory | Reduces yfinance rate-limit risks |

---

## Core Abstractions & "God Nodes" (Graph Insights)

*   **`CodingKeys`**: Structural bridge between Swift data models and backend schemas.
*   **`get_session()`**: Central hub for database state transitions.
*   **`TradingAgentsGraph`**: Primary AI orchestration entry point.
*   **`ConditionalLogic`**: Manages the iterative graph transitions.
*   **`AgentState`**: Shared memory carry-object for research data.

---

## Reliability Features

- **yfinance Retry Logic**: 3-attempt retry with backoff.
- **NSE Session Bootstrap**: Direct NSE API access for ASM/GSM lists.
- **History Fallbacks**: Indices/Sectors use history data if `info` fails.
- **BSE Fallback**: Automatic failover to BSE (`.BO`) if NSE financials are missing.
