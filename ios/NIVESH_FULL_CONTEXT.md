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
They debate the proposal until `ConditionalLogic` determines the risk is fully explored.

### Step 4: Deterministic Reformatting (Sonnet 3.5)
The raw verdict is structured using a **Dual-Breakpoint Prompt Caching** strategy:
1.  **Breakpoint 1 (The Blueprint)**: Caches the `INDIAN_MARKET_SYSTEM_PROMPT` (Static Layer).
2.  **Breakpoint 2 (Ticker History)**: Caches the last 15 analyses for that specific ticker.

---

## iOS App — 8 Tabs (UI Communities)

| Tab | View | Community Focus |
|---|---|---|
| **Home** | `HomeScreen` | Morning Brief, Indices strip, Sector Pulse heatmap. |
| **Directory** | `SearchScreen` | Bilingual search (खोज) with screener presets. |
| **Assets** | `PortfolioScreen` | Rupee-styled hero card, 10-segment risk meter, Red Flags. |
| **Alerts** | `AlertsScreen` | Auth & Alerts community focus. |
| **Archives** | `HistoryScreen` | Local analysis history cache. |
| **Compare** | `CompareScreen` | Side-by-side comparison of stocks. |
| **Registry** | `SettingsScreen` | App styles, User preferences, Server config. |
| **Journal** | `TradeJournalScreen`| Ledger for trade psychology logging. |

---

## Design System (Banknote Aesthetic)

- **Guilloché Patterns**: Animated dividers and borders (`GuillocheDivider`).
- **Security Thread**: Gold vertical strip with micro-text (`SecurityThread`).
- **Paper Texture**: 500-grain canvas noise overlay.
- **Rupee Rustle**: Audio feedback for UI interactions (`AppSoundManager`).
- **Indian Formatter**: Specialized logic for Lakh/Crore formatting.
- **Haptics**: Centralized engine for `EKPressStyle` spring interactions (`HapticManager`).
