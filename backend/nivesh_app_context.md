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

The Nivesh AI pipeline is a sophisticated multi-stage orchestration engine designed for high-fidelity financial reasoning. It is isolated in a Python subprocess for resource management and uses a 3-layer caching strategy.

### Step 1: The Smart Cache Gatekeeper (Haiku 3.5)
Before executing the expensive graph, the system performs a **Differential News Check**:
- **Logic**: Haiku determines if a "major fundamental shift, severe shock, or significant trend-changing event" has occurred since the last analysis.
- **Outcome**: If "NO", the system skips the AI run, clones the previous report, and updates the price only (**SMART CACHE HIT**).

### Step 2: Deterministic Pre-Computation (The Factor Engine)
To ensure the AI doesn't "hallucinate" technical levels, the **Factor Engine** runs first:
- **Technicals**: Calculates RSI-14, MACD, SMA 50/200, OBV, and Bollinger Bands using mathematical libraries (`ta`/`numpy`).
- **Fundamentals**: `piotroski.py` computes the 9-point health score (0-9).
- **Result**: These numbers are passed into the AI as "ground truth" prose.

### Step 3: Multi-Agent Orchestration (LangGraph)
If a cache miss occurs, the system initializes an `OptimizedTradingAgentsGraph`.

#### A. Parallel Analyst Layer
Four specialized agents run in parallel to gather raw intelligence:
1.  **Market Analyst**: Interprets Factor Engine data into behavioral trends.
2.  **News Analyst**: Scans for corporate announcements and **Red Flags** (Audit Resignations, CFO exits).
3.  **Fundamentals Analyst**: Checks Promoter Pledging (>30% = Bearish) and DII/FII flows.
4.  **Social Analyst**: Measures retail euphoria as a contrarian risk signal.

#### B. The Dialectical Debate
To prevent AI "echo chambers," the system enters a debate phase:
- **Bull Researcher**: Makes the strongest possible case for capital appreciation.
- **Bear Researcher**: Actively tries to invalidate the Bull case, focusing on structural risks.
- **Iteration**: They challenge each other for 1+ rounds to refine the "edges" of the investment thesis.

#### C. Synthesis & Proposal
- **Research Manager**: Reads the entire debate and writes a balanced summary of disagreements.
- **Trader**: Proposes a concrete Buy/Sell/Hold transaction with 3-month, 12-month, and 36-month target prices.

#### D. The Risk Jury (Iterative Loop)
The Trader's proposal is reviewed by a 3-agent Risk Committee in a circular loop:
1.  **Aggressive Analyst**: Looks for high-alpha opportunities.
2.  **Conservative Analyst**: Focuses on capital preservation.
3.  **Neutral Analyst**: Bridges the gap.
They debate the proposal until the judge determines the risk is fully explored, before passing it to the **Portfolio Manager** for the final "raw" verdict.

### Step 4: Deterministic Reformatting & Indian Market Weighting (Sonnet 3.5)
Final structuring using **Dual-Breakpoint Prompt Caching**:
- **Applied Heuristics**: "Minskyan Tension Gauge" (fragile rallies) and "Behavioral Translation" (e.g., RSI < 30 is "Retail capitulation").

---

## Advisor Intelligence — YouTube Harvest Engine

A background CRON job runs the `advisor_harvester.py` to ingest expert sentiment.

1.  **Transcript Extraction**: Fetches transcripts via YouTube API or local **Whisper large-v3** fallback (if captions are disabled).
2.  **Fuzzy Ticker Matching**: Uses `rapidfuzz` to identify stocks mentioned in **Hinglish** commentary (e.g., "HDFC wala bank").
3.  **Stance Extraction**: Haiku extracts the advisor's stance (BULLISH/BEARISH/NEUTRAL) and catalyst summaries.
4.  **Consensus API**: The `/api/v1/portfolio/advisor-consensus` endpoint aggregates this data into "Sector Signals" and "Trending Tickers".

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

## iOS App — 8 Tabs

| Tab | View | Description |
|---|---|---|
| **Home** | `HomeScreen` | Morning Brief (Priority Items), Indices strip, Sector Pulse heatmap. |
| **Directory** | `SearchScreen` | Bilingual search (खोज) with screener presets. |
| **Assets** | `PortfolioScreen` | Rupee-styled hero card, 10-segment risk meter, Red Flags system. |
| **Alerts** | `AlertsScreen` | Manage price targets. Triggered alerts show on Home. |
| **Archives** | `HistoryScreen` | Cached analysis reports with Signal Change diffs. |
| **Compare** | `CompareScreen` | Side-by-side stock comparison (Price, P/E, Signal). |
| **Registry** | `SettingsScreen` | User preferences, App styles, Server configuration. |
| **Journal** | `TradeJournalScreen`| Log entry reasons, moods (FOMO/Confidence), and outcomes. |

---

## Reliability Features

- **yfinance Retry Logic**: 3-attempt retry with backoff.
- **NSE Session Bootstrap**: Direct NSE API access for ASM/GSM lists.
- **History Fallbacks**: Indices/Sectors use history data if `info` fails.
- **BSE Fallback**: Automatic failover to BSE (`.BO`) for missing financial data.
