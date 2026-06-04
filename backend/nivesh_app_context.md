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
| Deterministic Engine| Factor Engine (Technical pre-compute), Piotroski (Fundamental) |

---

## Technical Deep Dive: The AI Analysis Engine

The Nivesh AI pipeline is a sophisticated multi-stage orchestration engine designed for high-fidelity financial reasoning, built on a **LangGraph** foundation.

### Step 1: The Smart Cache Gatekeeper (Haiku 3.5)
Before executing the expensive graph, the system performs a **Differential News Check**:
- **Logic**: Haiku determines if a "major fundamental shift" or "significant trend-changing event" has occurred since the last analysis.
- **Outcome**: If "NO", the system skips the AI run, clones the previous report, and updates the price only (**SMART CACHE HIT**).

### Step 2: Deterministic Pre-Computation (The Factor Engine)
To ensure the AI doesn't "hallucinate" technical levels, the **Factor Engine** runs first:
- **Technicals**: Calculates RSI-14, MACD, SMA 50/200, OBV, and Bollinger Bands using mathematical libraries (`ta`/`numpy`).
- **Fundamentals**: `piotroski.py` computes the 9-point health score (0-9).
- **Result**: These numbers are passed into the AI as "ground truth" prose.

### Step 3: Multi-Agent Orchestration (LangGraph Patterns)

#### A. Analyst Team Four-Agent Architecture
Four specialized agents run in parallel to gather raw intelligence:
1.  **Market Analyst**: Interprets Factor Engine data into behavioral trends.
2.  **News Analyst**: Scans for corporate announcements and **Red Flags** (Audit Resignations, CFO exits).
3.  **Fundamentals Analyst**: Checks Promoter Pledging (>30% = Bearish) and DII/FII flows.
4.  **Social Analyst**: Measures retail euphoria as a contrarian risk signal.

#### B. Bullish vs Bearish Researcher Debate Pattern
- **Adversarial Loop**: The `Bull Researcher` and `Bear Researcher` engage in a dialectical challenge to stress-test the investment thesis.
- **Iteration**: They challenge each other for 1+ rounds (managed by `ConditionalLogic`) to refine the "edges" of the thesis.

#### C. Risk Management Three-Perspective Analysis
The proposal is reviewed by a 3-agent committee in a circular loop:
1.  **Aggressive Analyst**: Looks for high-alpha opportunities.
2.  **Conservative Analyst**: Focuses on capital preservation.
3.  **Neutral Analyst**: Bridges the gap.
They debate the proposal until `ConditionalLogic` determines the risk is fully explored, before passing it to the **Portfolio Manager** for the final "raw" verdict.

### Step 4: Deterministic Reformatting & Indian Market Weighting (Sonnet 3.5)
Final structuring using **Dual-Breakpoint Prompt Caching** strategy:
- **Applied Heuristics**: "Minskyan Tension Gauge" (fragile rallies) and "Behavioral Translation" (e.g., RSI < 30 is "Retail capitulation").

---

## Performance & Optimization — Anthropic Prompt Caching

| Optimization | Method | Impact |
|---|---|---|
| **Prompt Caching** | Dual-Breakpoint (Static + History) | 90% reduction in Sonnet input costs |
| **Smart Cache** | Haiku Headline Check | Skips $0.15 analysis for non-events |
| **Process Isolation** | `multiprocessing.Process` | Protects main API from crashes/memory leaks |
| **TTL Cache** | 5-minute In-Memory | Reduces yfinance rate-limit risks |
| **Batching** | Anthropic Batch API | 50% cost reduction for nightly portfolio runs |

---

## Core Abstractions & "God Nodes" (Graph Insights)

*   **`CodingKeys`**: The central bridge between Swift data models and backend JSON schemas.
*   **`get_session()`**: Core dependency for all database-driven state transitions.
*   **`TradingAgentsGraph`**: Primary entry point for AI orchestration.
*   **`ConditionalLogic`**: Manages flow transitions within the graph.
*   **`AgentState`**: Shared memory for agent communication.

---

## Reliability Features

- **yfinance Retry Logic**: 3-attempt retry with backoff.
- **NSE Session Bootstrap**: Direct NSE API access for ASM/GSM lists.
- **History Fallbacks**: Indices/Sectors use history data if `info` fails.
- **BSE Fallback**: Automatic failover to BSE (`.BO`) for missing financial data.
