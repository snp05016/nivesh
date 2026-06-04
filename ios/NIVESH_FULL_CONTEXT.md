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
| Deterministic Engine| Factor Engine (Technical), Options Scraper (Derivatives), Piotroski (Fundamental) |
| Feedback Loop | Epistemic Feedback Injector (Price Delta tracking) |
| NLP Engine | singleton FinBERT (yiyanghkust/finbert-tone) |

---

## Technical Deep Dive: The AI Analysis Engine

The Nivesh AI pipeline is a sophisticated multi-stage orchestration engine designed for high-fidelity financial reasoning, built on a **LangGraph** foundation.

### Step 1: Epistemic Feedback Injection
Before any compute starts, the `feedback_injector` identifies the last report for this ticker. It computes the **Price Delta** since that report and injects a "Performance Review" block into the AI's HumanMessage. This prevents the model from repeating past thesis errors.

### Step 2: The Smart Cache Gatekeeper (Haiku 3.5)
Performs a **Differential News Check** to determine if a trend-changing event has occurred.
- **Outcome**: If "NO", the system skips the AI run, clones the previous report, and updates the price (**SMART CACHE HIT**).

### Step 3: Deterministic Pre-Computation
To ensure mathematical accuracy, several engines run before the agents:
- **Factor Engine**: Mathematical computation of 30+ technical indicators.
- **Options Scraper**: Computes PCR, Max Pain, and **Institutional OI Skew** from NSE option chains.
- **Piotroski**: Calculates 9-point fundamental health score.
- **FinBERT**: Scores top news headlines for institutional sentiment.

### Step 4: Multi-Agent Orchestration (LangGraph Patterns)

#### A. Analyst Team Four-Agent Architecture
Market (Technical), News (Red Flags), Fundamentals (Promoter), and Social (Euphoria) agents run in parallel.

#### B. Bullish vs Bearish Researcher Debate Pattern
Adversarial loop stress-testing the investment thesis before synthesis.

#### C. Risk Management Three-Perspective Analysis
The proposal is reviewed by a 3-agent committee (**Aggressive**, **Conservative**, **Neutral**) in a circular loop managed by `ConditionalLogic` until risks are fully explored.

---

## iOS App — 8 Tabs

| Tab | View | Community Focus |
|---|---|---|
| **Home** | `HomeScreen` | Morning Brief, Indices strip, Sector Pulse heatmap. |
| **Directory** | `SearchScreen` | Bilingual search (खोज) with screener presets. |
| **Assets** | `PortfolioScreen` | Rupee-styled hero card, 10-segment risk meter, Red Flags. |
| **Alerts** | `AlertsScreen` | Auth & Alerts community focus. |
| **Archives** | `HistoryScreen` | Local analysis history cache. |
| **Compare** | `CompareScreen` | Side-by-side comparison of stocks. |
| **Registry** | `SettingsScreen` | App styles, User preferences, Server config. |
| **Journal** | `TradeJournalScreen`| Ledger for trade psychology (FOMO/Confidence). |

---

## Design System (Banknote Aesthetic)

- **Guilloché Patterns**: Animated wave dividers (`GuillocheDivider`).
- **Security Thread**: Gold vertical strip with micro-text (`SecurityThread`).
- **Paper Texture**: 500-grain canvas noise overlay.
- **Rupee Rustle**: Audio feedback for UI interactions (`AppSoundManager`).
- **Haptics**: Centralized engine for `EKPressStyle` spring interactions (`HapticManager`).
