# Nivesh (निवेश) — Definitive App Context

> Authority: This is the definitive project context document.
> Last updated: June 3, 2026. Reflects current implementation.

---

## What Is This

**Nivesh** is a personal Indian stock market analysis iOS app for a small family group (3 users). It wraps a multi-agent AI pipeline in a premium SwiftUI interface styled like an Indian Rupee banknote. Tap any NSE/BSE stock → wait 30–90s → receive structured AI investment analysis.

**Current status:** Fully functional, running locally. iOS app on physical iPhone connects to FastAPI backend on Mac over home WiFi (`192.168.1.97:8000`). Not deployed anywhere. Personal use only.

---

## The Stack

| Layer | Technology |
|---|---|
| iOS frontend | SwiftUI (iOS 16+), Swift Charts, no third-party dependencies |
| Backend API | FastAPI (Python), uvicorn, local only |
| AI pipeline | TradingAgents (LangGraph multi-agent) |
| AI models | Claude 3.5 Haiku (agents) + Claude 3.5 Sonnet (reformatter) |
| Live market data | yfinance (Yahoo Finance) with NSE-session fallbacks |
| News sources | Yahoo Finance News (enriched), Moneycontrol, Economic Times |
| Advisor Intelligence | Claude 3.5 Haiku (YouTube transcript extraction) + rapidfuzz (Hinglish matching) |
| Database | SQLite via SQLAlchemy ORM |
| Charts (iOS) | Swift Charts (native, iOS 16+) |

---

## Technical Deep Dive: The AI Analysis Engine

The Nivesh AI pipeline is a sophisticated multi-stage orchestration engine designed for high-fidelity financial reasoning. It is isolated in a Python subprocess for resource management and uses a 3-layer caching strategy.

### Step 1: The Smart Cache Gatekeeper (Haiku 3.5)
Before executing the expensive multi-agent graph, the system performs a **Differential News Check**:
- **Input**: Last analysis date + Top 5 recent news headlines for the ticker.
- **Logic**: Haiku determines if a "major fundamental shift, severe shock, or significant trend-changing event" has occurred.
- **Outcome**: If "NO", the system skips the AI run, clones the previous report, updates the current price via yfinance, and returns immediately (**SMART CACHE HIT**).

### Step 2: Multi-Agent Orchestration (LangGraph)
If a cache miss occurs, the system initializes an `OptimizedTradingAgentsGraph`.

#### A. Parallel Analyst Layer
Three specialized agents run in parallel to gather raw intelligence:
1.  **Market Analyst**: Computes Technicals (SMA 50/200, RSI-14, MACD, Volume) and identifies chart patterns.
2.  **News Analyst**: Scans for corporate announcements. Specifically hard-coded to hunt for **Audit Resignations**, **CFO/MD Exits**, and **SEBI Actions** (marked with ⚠ GOVERNANCE flags).
3.  **Fundamentals Analyst**: Fetches P/L, Balance Sheet, Cash Flow, and **Promoter Pledging** data.

#### B. The Dialectical Debate
To prevent AI "echo chambers," the system enters a debate phase:
- **Bull Researcher**: Makes the strongest possible case for capital appreciation.
- **Bear Researcher**: Actively tries to invalidate the Bull case, focusing on structural risks.
- **Iteration**: They challenge each other for 1 round (or more) to refine the "edges" of the investment thesis.

#### C. Synthesis & Proposal
- **Research Manager**: Reads the entire debate and writes a balanced summary of disagreements.
- **Trader**: Proposes a concrete Buy/Sell/Hold transaction with 3-month, 12-month, and 36-month target prices.

#### D. The Risk Jury (Iterative Loop)
The Trader's proposal is reviewed by a 3-agent Risk Committee in a circular loop:
1.  **Aggressive Analyst**: Looks for high-alpha opportunities.
2.  **Conservative Analyst**: Focuses on capital preservation.
3.  **Neutral Analyst**: Bridges the gap.
They debate the proposal until the judge determines the risk is fully explored, before passing it to the **Portfolio Manager** for the final "raw" verdict.

### Step 3: Deterministic Reformatting & Indian Market Weighting (Sonnet 3.5)
The raw multi-agent output is passed to Claude 3.5 Sonnet for final structuring. This phase uses a **Dual-Breakpoint Prompt Caching** strategy:

1.  **Breakpoint 1 (The Blueprint)**: Caches the `INDIAN_MARKET_SYSTEM_PROMPT` (Static Layer).
2.  **Breakpoint 2 (Ticker History)**: Fetches and caches the last 15 analyses for that specific ticker, sorted by key for stable hash IDs (Volatile Context Layer).

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
| **Directory** | `SearchScreen` | Bilingual search (खोज) with screener presets (Hidden Gems, Momentum). |
| **Assets** | `PortfolioScreen` | Rupee-styled hero card, 10-segment risk meter, Red Flags system. |
| **Alerts** | `AlertsScreen` | Manage price targets. Triggered alerts show on Home. |
| **Archives** | `HistoryScreen` | Cached analysis reports with Signal Change diffs. |
| **Compare** | `CompareScreen` | Side-by-side stock comparison (Price, P/E, Signal). |
| **Registry** | `SettingsScreen` | User verification, App preferences, APNs registration. |
| **Journal** | `TradeJournalScreen`| Log entry reasons, moods (FOMO/Contrarian), and outcomes. |

---

## Reliability Features

- **yfinance Retry Logic**: 3-attempt retry with backoff.
- **NSE Session Bootstrap**: Direct NSE API access for ASM/GSM lists.
- **History Fallbacks**: Indices/Sectors use history data if `info` fails.
- **BSE Fallback**: Automatic failover to BSE (`.BO`) for missing financial data.
