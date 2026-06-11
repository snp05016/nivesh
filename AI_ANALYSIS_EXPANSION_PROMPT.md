# Nivesh AI Analysis Chain — Comprehensive Audit & Expansion Prompt
# Target: Claude Code (or any capable AI coding agent)

---

# PART 0: THE CURRENT AI ANALYSIS CHAIN (FULL MAP)

Before changing anything, understand what exists. Here is the complete pipeline
traced end-to-end from user tap to iOS render:

## Trigger Path

```
User taps "Deep Analysis" on a stock
  → StockActionHubView.swift
  → AnalysisScreen.swift (pushes via NavigationStack)
  → NetworkManager.shared.analyze(ticker:exchange:userId:deepScan:)
  → POST /analyze  { ticker, exchange, user_id, deep_scan }
  → backend/routers/analysis.py  analyze_endpoint()
```

## Backend Pipeline (8 stages)

### Stage 0 — Cache Gating (`analysis.py`)
1. Rate-limit check (per-user)
2. Quick-info cache hit check (30min TTL)
3. Staleness check → `compute_staleness()` in `services/staleness.py`
4. Smart cache: if existing analysis < 3 days + no material news → serve cached
5. Concurrency guard: one analysis per user at a time

### Stage 1 — Deep Scan Pre-processing (if deep_scan=true)
- **PKScreener** technical pre-scan → technical_score, breakout, RSI, MACD signal,
  MA signal, volume signal, chart pattern
- **FinBERT** sentiment scoring → last 7 days of NewsArticle rows scored [-1,+1],
  injected as sentiment anchor context

### Stage 2 — Subprocess Isolation (`tradingagents/nivesh/subprocess_runner.py`)
- `multiprocessing.Process` spawns child process
- Child imports `TradingAgentsGraph` inside the process (deferred import)
- 300s timeout; per-user concurrency guard (`_running_analyses` set)

### Stage 3 — Graph Initialization (`trading_graph.py`)
- **Factor Engine** (`services/factor_engine.py`) — deterministic pre-computation:
  RSI-14, MACD(12/26/9), ROC-21, SMA-20/50/200, EMA-20/50, ATR-14,
  Bollinger Bands(20,2), Historical Volatility 21d, OBV, Volume Ratio,
  Golden Cross, Death Cross, MACD signal cross, Trend regime,
  Volatility regime, Momentum score (-100 to +100)
  ALL ZERO LLM CALLS — pure numpy/ta calculations
- **Epistemic Feedback** (`services/feedback_injector.py`):
  Loads last analysis for ticker → computes actual price delta since then →
  marks `was_correct` in DB → injects audit requirements into graph state
- **Memory Log** (`agents/utils/memory.py`): past context from TradingMemoryLog
- **Instrument Resolution**: ticker → yfinance instrument identity
- **LangGraph StateGraph** (`graph/setup.py`): builds workflow with all nodes

### Stage 4 — Analyst Committee (Tier 1: DeepSeek V4 Flash via `deepseek_chat`)
4 analysts run SEQUENTIALLY (default `analyst_concurrency_limit=1`):
1. **Market Analyst** (`analysts/market_analyst.py`)
   - Tools: get_stock_data, get_indicators, get_verified_market_snapshot
   - Output: behavioral translation of every technical indicator
2. **Sentiment Analyst** (`analysts/sentiment_analyst.py`)
   - Tools: get_social_media_sentiment (stocktwits, reddit)
   - Output: `SentimentReport` structured via Pydantic schema
3. **News Analyst** (`analysts/news_analyst.py`)
   - Tools: get_news, get_global_news, get_insider_transactions
   - Priority: ⚠ GOVERNANCE prefix for auditor resignations, CFO/MD departures,
     SEBI actions
4. **Fundamentals Analyst** (`analysts/fundamentals_analyst.py`)
   - Tools: get_fundamentals, get_balance_sheet, get_cashflow,
     get_income_statement, get_insider_transactions
   - Rules: Name & Number constraint, risk-first protocol, promoter pledge check,
     M&A detector, data present guard

### Stage 5 — Adversarial Debate (Tier 1: DeepSeek V4 Flash)
- **Bull Researcher** (`researchers/bull_researcher.py`):
  Builds long case from growth potential, competitive advantages, positive
  indicators. Must counter bear arguments with specific data.
  1 round. Receives all 4 analyst reports + epistemic feedback.
- **Bear Researcher** (`researchers/bear_researcher.py`):
  Builds short/avoid case from governance landmines, valuation traps, sector
  headwinds. Must counter bull arguments with quantified impact.
- **Research Manager** (`managers/research_manager.py`, Tier 2: Claude Haiku):
  Weighs the debate. Bear findings carry 1.5x weight. Produces
  `ResearchPlan` structured output (recommendation, rationale, strategic actions).
  Signal-confidence consistency enforced: BUY needs ≥50% confidence.

### Stage 6 — Trader + Risk Committee
- **Trader** (`trader/trader.py`, Tier 1): Translates research plan into
  Buy/Hold/Sell + entry/stop/sizing. Outputs `TraderProposal` structured.
- **Risk Committee** (3 debaters, Tier 1, sequential chain):
  - Aggressive Debator → Conservative Debator → Neutral Debator
  - Each stress-tests the trader's levels from their risk profile
- **Portfolio Manager** (`managers/portfolio_manager.py`, Tier 2: Claude Haiku):
  Final synthesis. Produces `PortfolioDecision` structured output.
  Rules: signal-confidence consistency, 1.5x bear weight, cannot be overridden
  by a single aggressive node.

### Stage 7 — Reformatter (`services/orchestrator.py`)
1. **Claude Sonnet reformatter** (`reformat_with_claude()`):
   - Dual ephemeral prompt-cache breakpoints (static persona + ticker history)
   - `INDIAN_MARKET_SYSTEM_PROMPT` from `prompts.py`
   - 7-tier Indian Market Priority Weighting Matrix enforced
   - temperature=0 for deterministic output
   - Retry 3x with exponential backoff
   - Falls back to DeepSeek if Claude fails
2. **DeepSeek reformatter** (fallback):
   - Same system prompt, different model
   - Indian numbering conversion
3. **Normalization** (`_normalize_response()`):
   - Signal mapping (BUY→BULLISH, etc.)
   - NaN→None for all float fields
   - Fix 2.8: Inf values → None

### Stage 8 — Post-processing & Persistence
- Piotroski F-Score injection (`_inject_piotroski()`)
- Live price refresh (`_inject_live_data()`)
- Recent news refresh
- Price performance (3m/6m/12m)
- Advisor matrix load (last 14 days of AdvisorInsight rows)
- Save to `AnalysisHistory` table
- Return full JSON to iOS

## iOS Rendering (`AnalysisScreen.swift` → 11 sections)

```
1. heroChartSection          — ImmersiveStockHeroChart, full-bleed
2. stockHeaderSection        — Price, live polling, 3M/6M/1Y chips, 52W range chart
3. aiVerdictCard             — Signal badge, confidence arc, 3/12/36mo targets
4. whatChangedSection        — Previous vs current diff (signal flip, confidence delta)
5. signalTimelineSection     — AnalysisHistoryTimelineView with 90d price overlay
6. dialecticDebateSection    — Bull case / Bear case arguments side by side
7. timeHorizonSection        — Multi-horizon price targets with upside/downside %
8. riskFactorsSection        — Key risks list
9. fundamentalsSection       — Key metrics grid
10. newsSection              — Recent news cards
11. whatToWatchSection       — Triggers to monitor
12. disclaimerSection        — Legal disclaimer
13. (Macro Impact Banner)    — FII/DII flow context
```

---

# PART 1: GAPS & WEAKNESSES IN THE CURRENT CHAIN

## A. Backend Architecture Gaps

### A1. Single Debate Round — Shallow Analysis
The Bull/Bear debate runs exactly 1 round. Both researchers get one shot each.
There's no iterative refinement where the Bull rebuts the Bear's counterarguments.
Multi-round debates produce dramatically better analysis because each side is
forced to address specific criticisms rather than generic position statements.

### A2. No Dedicated Governance Agent
Governance checks are scattered across News Analyst (auditor resignations, CFO
departures) and Fundamentals Analyst (promoter pledging). There's no single agent
with the sole job of: SEBI surveillance lists (ASM/GSM), unsolicited SMS watchlists,
insider trading (SAST disclosures), bulk/block deals, pledged share trends over 8
quarters, independent director resignations, related-party transaction spikes,
audit qualification history. This is the #1 priority for Indian investors.

### A3. No Streaming / Progressive Reveal
The entire analysis runs inside a subprocess and returns as one blob. The iOS
user sees a spinner for 30-90 seconds with no visibility into what's happening.
Streaming would show: "Analyzing technicals… → Evaluating fundamentals… →
Debating bull vs bear case… → Synthesizing final verdict…"

### A4. Epistemic Feedback Is Shallow
The feedback injector only: (a) loads the last analysis, (b) computes price
delta, (c) marks was_correct. It does NOT:
- Track which specific bull/bear arguments were correct
- Learn which analyst types are most accurate per sector
- Adjust confidence calibration based on historical accuracy
- Feed back "this analyst consistently overestimates revenue growth for chemical stocks"

### A5. No Cross-Stock Learning
Each analysis is fully isolated. If the system analyzed 200 chemical stocks,
none of that sector-level knowledge transfers to the 201st. There's no:
- Sector-level knowledge base built from past analyses
- Peer comparison baked into analysis
- "Similar patterns detected" cross-referencing

### A6. No User Feedback Loop
Users can't rate or correct the analysis. No thumbs up/down, no "this target
was wrong because X." Without this, the system never improves from human
feedback. Every AI system that serves users needs a feedback loop.

### A7. Risk Committee Is Sequential, Not Parallel
The 3 risk debaters run sequentially: Aggressive → Conservative → Neutral.
Each reads the previous one's output, creating anchoring bias. They should
run in PARALLEL (like the analyst committee can) to produce truly independent
risk assessments, then merge.

### A8. Reformatter Quality Degradation
When Claude Sonnet fails (rate limits, 503s), the DeepSeek fallback produces
lower quality structured JSON. There's no validation step between reformatters.
If both fail, the user gets a generic error.

### A9. No Analysis Comparison Engine
Users can view two analyses of the same stock over time (whatChangedSection)
but cannot compare two different stocks side by side with AI highlighting the
key differences in investment thesis.

### A10. No Multi-Horizon Scenario Trees
Only point targets (3m/12m/36m). No probability distributions, no bull/base/bear
scenarios per horizon, no Monte Carlo-style outcome ranges.

### A11. No Alternative Data
Only yfinance + PKScreener + news. No:
- NSE/BSE block deal data (exists in backend but not injected)
- FII/DII flow data per stock (exists in backend but not per-stock)
- Options chain data for sentiment context (exists in backend but not injected)
- Delivery percentage data (critical for Indian markets)
- Corporate filings text extraction

### A12. Model Temperature Inconsistency
- Tier 1 agents (analysts, debaters): DeepSeek V4 Flash, temp=0.3
- Tier 2 synthesis (Research Manager, Portfolio Manager): Claude Haiku, temp=0
- Tier 3 reformatter: Claude Sonnet, temp=0
But the temperature isn't configurable per-analysis type. Growth stocks may
benefit from higher creativity (temp=0.5); value stocks from strict determinism.

## B. iOS Frontend Gaps

### B1. No Streaming UI
Analysis arrives all at once. No progressive reveal, no stage indicators,
no "live" feel. Users stare at a spinner.

### B2. No Interactive Drill-Down
You can't tap "Bull Case point #2" and get "show me the data behind this claim."
Each AI assertion should be tappable to see the underlying tool output or data
source that generated it.

### B3. No Analysis History Browser
The signal timeline shows past signals as dots on a chart. There's no rich
history browser showing past full analyses with comparison tools.

### B4. No User Feedback Widget
No way to rate analysis quality or flag errors. No "Was this helpful?" or
"Report incorrect analysis."

### B5. No PDF/Report Export
Share as image exists but no professional PDF report generation for sharing
with CA/financial advisors.

### B6. No Offline Analysis Cache
Analysis disappears without network. Should cache last N analyses locally.

### B7. No Notification When Analysis Completes
User must stay on the AnalysisScreen. If they navigate away, they lose the
analysis (no background completion notification).

### B8. AnalysisScreen Is Monolithic
One 1952-line file. No decomposition into reusable components.

---

# PART 2: NEW AI USE CASES (BEYOND SINGLE-STOCK ANALYSIS)

## C1. Portfolio-Level AI Analysis
Analyze the entire portfolio as a system. Identify:
- Sector concentration risk (e.g., "65% of your portfolio is in defence stocks")
- Correlation matrix ("RELIANCE and BPCL move together 78% of the time")
- Portfolio beta and drawdown simulation
- AI suggests rebalancing trades with rationale

## C2. Conversational Stock Analysis ("Ask Nivesh")
Chat interface where users ask follow-up questions after an analysis:
- "What would change your BUY rating to SELL?"
- "Compare RELIANCE's valuation to its 5-year average"
- "What happens to this stock if crude oil drops 20%?"
- "Show me only the governance risks"

## C3. AI-Powered Natural Language Screener
Instead of complex screener UIs:
- "Find chemical stocks with PE < 20, ROCE > 15%, and promoter holding > 50%"
- "Show me stocks similar to PIDILIT but at lower valuations"
- "Which stocks in my watchlist are closest to their 52-week lows?"

## C4. AI Earnings Call Summarizer
- Fetch earnings call transcripts
- Summarize key points, flag management tone changes
- Compare guidance vs actuals from previous quarters
- Extract exact forward guidance numbers

## C5. AI Proactive Risk Alerts
Background analysis that monitors analyzed stocks for:
- Thesis-invalidating events (auditor resignation, CFO departure, pledged share spike)
- Technical breakdowns (price below 200 SMA, death cross)
- FII/DII flow reversals
- Push notification with specific reason: "Your SUZLON BUY thesis may be at risk:
  Promoter pledged +12% this quarter"

## C6. AI Investment Journal
Auto-generate journal entries:
- When you buy: "Bought X shares at ₹Y based on AI BUY signal (confidence Z%)"
- When you sell: "Sold X shares at ₹Y. Gain/Loss: Z%. Original thesis: [AI analysis summary]"
- Periodic review: "3 months ago AI predicted ₹X target for STOCK. Current price: ₹Y.
  Delta: Z%. What went right/wrong: [auto-analysis]"

## C7. AI Tax-Loss Harvesting Suggestions
End of FY (March 31):
- Scan portfolio for unrealized losses
- Suggest tax-loss harvesting trades
- Calculate tax saved in ₹
- Warn about wash sale rules

## C8. Multi-Language Analysis
Generate the same analysis in Hindi, Tamil, Telugu, etc.
The system prompt already has `get_language_instruction()` but it's not wired.
Indian retail investors often prefer vernacular.

## C9. AI-Powered Pre-IPO Analysis
When a DRHP (Draft Red Herring Prospectus) is filed:
- Extract key data points (promoter holding, risk factors, financials)
- Compare to listed peers
- Generate a pre-IPO analysis in the same format as stock analysis

## C10. AI Macro Briefing (Morning Brief)
Already partially exists in HomeScreen. Enhance with:
- Overnight US/Asia market summary → impact on Indian markets
- FII/DII flow data with interpretation
- Sector-specific macro catalysts for the day
- Stock-specific impact predictions: "If crude opens +3%, expect BPCL -1.5%"

## C11. AI Explainability / Traceability
Every AI output should be traceable:
- "Why BUY?" → Expand to show the exact chain: Market Analyst found RSI oversold
  → Bull argued institutional accumulation → Research Manager weighted Bull higher
  due to strong fundamentals → Trader set ₹X target based on 200 SMA resistance
- This builds TRUST with veteran investors who are skeptical of black-box AI

## C12. AI Peer Comparison Engine
Enhanced CompareScreen with AI-generated comparative analysis:
- "INFY vs TCS: Who has better margins, governance, and growth?"
- Side-by-side fundamentals with AI commentary on differences
- "If you own INFY, should you switch to TCS?" analysis

---

# PART 3: IMPLEMENTATION PLAN

## Phase 1: Backend — Governance Agent & Multi-Round Debate (HIGHEST IMPACT)

### 1.1 New: Dedicated Governance Agent
**File:** `backend/tradingagents-core/tradingagents/agents/analysts/governance_analyst.py`

Create a new analyst that runs as the FIRST node in the analyst committee.
It has specialized tools:
- `get_sebi_surveillance(ticker)` → check ASM/GSM lists
- `get_promoter_pledge_history(ticker)` → 8-quarter pledge trend
- `get_insider_transactions(ticker)` → SAST disclosures, bulk deals
- `get_auditor_history(ticker)` → auditor changes, qualifications
- `get_related_party_transactions(ticker)` → RPT spikes
- `get_unsolicited_sms_status(ticker)` → SEBI SMS watchlist

System prompt enforces:
- Governance score 0-100 computed deterministically
- Red flags automatically promoted to `key_risks`
- Promoter pledged ≥30% → automatic confidence reduction of -15%
- Auditor resignation within 2 years → automatic BEARISH bias

### 1.2 Upgrade: Multi-Round Bull/Bear Debate
**Files:** `trading_graph.py`, `setup.py`, `conditional_logic.py`

Change from 1-round to configurable N-rounds (default 2, max 3):
- Round 1: Bull opens, Bear rebuts
- Round 2: Bull must specifically address each bear counterpoint,
  Bear must specifically address each bull counterpoint
- Round 3 (optional, deep_scan only): Both researchers get final
  closing statements
- Research Manager receives richer debate history → higher quality synthesis

### 1.3 Upgrade: Parallel Risk Committee
**File:** `setup.py`

Change risk debaters from sequential to parallel (like analysts):
- All 3 (Aggressive, Conservative, Neutral) run concurrently
- Portfolio Manager receives 3 independent assessments
- No anchoring bias from sequential reading

### 1.4 New: Streaming Analysis Endpoint
**New endpoint:** `GET /analyze/stream/{ticker}` using SSE (Server-Sent Events)

Create a streaming wrapper around the subprocess that emits events:
```
event: stage
data: {"stage": "technicals", "message": "Computing technical indicators…"}

event: stage
data: {"stage": "fundamentals", "message": "Analyzing balance sheet…"}

event: stage
data: {"stage": "debate", "message": "Bull vs Bear debate in progress…"}

event: stage
data: {"stage": "verdict", "message": "Synthesizing final decision…"}

event: complete
data: {full StockAnalysis JSON}
```

The subprocess writes stage markers to a pipe/queue; the SSE handler reads them.

## Phase 2: Backend — Learning & Feedback Systems

### 2.1 Upgrade: Epistemic Feedback 2.0
**File:** `services/feedback_injector.py`

Enhance to:
- Load last 3 analyses (not just 1)
- Track which analyst was most accurate per sector → inject as calibration hint
- Compute: "For chemical stocks, the Fundamentals Analyst's ROCE estimates have
  been within ±5% of actuals 80% of the time. Weight accordingly."
- Track bull vs bear accuracy separately: "Bear arguments have been directionally
  correct 65% of the time for mid-cap stocks. Bull arguments: 45%."
- Inject calibration at agent level, not just debate level

### 2.2 New: User Feedback Collection
**New endpoint:** `POST /analysis/{id}/feedback`

Accepts: `{ "rating": 1-5, "corrections": [{ "field": "target_3m", "reason": "..." }] }`
- Stores in new `AnalysisFeedback` table
- Periodically (weekly), a batch job analyzes feedback patterns and generates
  calibration adjustments for the reformatter system prompt

### 2.3 New: Sector Knowledge Base
**File:** `backend/services/sector_knowledge.py`

After every analysis, extract and store:
- Sector-specific metrics (avg PE, avg ROCE, avg promoter holding)
- Common bear arguments that proved correct
- Common bull arguments that proved wrong
- Inject as context into subsequent analyses of same sector

## Phase 3: Backend — New AI Capabilities

### 3.1 New: Conversational Analysis Endpoint
**New endpoint:** `POST /analyze/chat`

```
Request: { ticker, exchange, question, analysis_id (optional) }
Response: { answer, sources_used, confidence }
```

Uses the existing analysis JSON as context + tools for live data.
LLM answers specific follow-up questions about a stock.

### 3.2 New: Natural Language Screener Endpoint
**New endpoint:** `POST /screener/nl`

```
Request: { query: "chemical stocks with PE < 20 and promoter holding > 50%" }
Response: { results: [...], explanation: "..." }
```

LLM translates natural language → structured filter criteria →
queries AnalysisHistory + yfinance → returns matches with explanation.

### 3.3 New: Portfolio Risk Analysis Endpoint
**New endpoint:** `POST /portfolio/analyze`
Analyzes entire portfolio for:
- Sector concentration
- Correlation matrix
- Beta-weighted drawdown simulation
- Rebalancing suggestions with AI rationale

### 3.4 New: Proactive Alert Agent
**File:** `backend/services/alert_agent.py`

CRON job (runs every 2 hours during market hours):
- Fetches all stocks that have been analyzed in the last 90 days
- Checks for thesis-invalidating events:
  - Price moves >2σ from predicted target path
  - New SEBI filings (auditor resignations, pledged share changes)
  - Technical breakdowns (death cross, below 200 SMA)
- Generates push notification with specific reason
- Stores alert in `ThesisAlerts` table

## Phase 4: iOS — Streaming & Interactivity

### 4.1 New: Streaming Analysis UI
**File:** `ios/StockApp/stockme/stockme/Views/AnalysisScreen.swift` (modify)

- Replace single spinner with stage-by-stage progress
- Connect to SSE endpoint via `EventSource` (or custom URLSession streaming)
- Show live stage transitions with elegant animations
- Each stage shows a brief description + animated indicator

### 4.2 New: Interactive Drill-Down
Create a `TraceableClaimView` component:
- Any AI-generated claim can be tapped
- Opens a sheet showing: the analyst who generated it, the tool calls used,
  the raw data, and the LLM's reasoning
- Builds trust through transparency

### 4.3 New: Analysis Feedback Widget
Add to AnalysisScreen:
- Thumbs up/down on overall analysis
- Per-section feedback: "Was the Bull case convincing?"
- "Report error" button that captures the specific issue

### 4.4 New: Analysis History Browser
**File:** `ios/StockApp/stockme/stockme/Views/AnalysisHistoryScreen.swift` (enhance)

- Rich timeline of past analyses with key metrics
- Tap any past analysis to view full details
- Comparison mode: select 2 analyses → side-by-side diff

### 4.5 New: PDF Report Export
Generate a beautifully formatted PDF from the StockAnalysis JSON using
native iOS PDFKit. Professional layout with:
- Nivesh branding, analysis date, ticker header
- Signal badge, confidence gauge
- All sections formatted as in the app
- Disclaimer footer

### 4.6 New: Background Analysis Completion
When user triggers analysis and navigates away:
- Analysis continues in background (URLSession background task)
- Local notification on completion
- Tapping notification opens AnalysisScreen with results
- Results cached locally for offline viewing

## Phase 5: iOS — New Features

### 5.1 New: Conversational Analysis UI ("Ask Nivesh")
**File:** `ios/StockApp/stockme/stockme/Views/AskNiveshView.swift`

Chat-style interface connected to `/analyze/chat`:
- Message bubbles (user questions, AI answers)
- Suggested questions based on current analysis
- Context-aware: if viewing RELIANCE analysis, suggested questions are
  RELIANCE-specific
- History of questions for this stock

### 5.2 New: Natural Language Screener UI
**File:** `ios/StockApp/stockme/stockme/Views/NLScreenerView.swift`

- Search-bar style input: "Find stocks like…"
- Results in same list format as watchlist/screener
- "Explain these results" button that shows AI's reasoning

### 5.3 New: Portfolio Health Dashboard
**File:** `ios/StockApp/stockme/stockme/Views/PortfolioHealthView.swift`

- Sector concentration donut chart
- Correlation heatmap
- Risk score with AI commentary
- Rebalancing suggestions

### 5.4 New: AI Investment Journal
**File:** `ios/StockApp/stockme/stockme/Views/TradeJournalScreen.swift` (enhance)

- Auto-generated entries from trades + analysis
- Periodic review summaries
- Performance tracking vs AI targets

### 5.5 New: Multi-Language Toggle
Add language selector (English / हिंदी / தமிழ்) to analysis view.
Backend already has `get_language_instruction()` — wire it through.

---

# PART 4: FILES TO CREATE/MODIFY

## Backend — New Files

| File | Purpose |
|------|---------|
| `backend/tradingagents-core/tradingagents/agents/analysts/governance_analyst.py` | Dedicated governance analysis agent |
| `backend/services/sector_knowledge.py` | Sector-level knowledge base from past analyses |
| `backend/services/alert_agent.py` | Proactive thesis-invalidation alert agent |
| `backend/routers/analysis_stream.py` | SSE streaming endpoint for analysis progress |
| `backend/routers/analysis_chat.py` | Conversational analysis endpoint |
| `backend/routers/screener_nl.py` | Natural language screener endpoint |
| `backend/routers/analysis_feedback.py` | User feedback collection endpoint |

## Backend — Existing Files to Modify

| File | Change |
|------|--------|
| `backend/tradingagents-core/tradingagents/graph/setup.py` | Add governance agent node; parallel risk committee; multi-round debate config |
| `backend/tradingagents-core/tradingagents/graph/conditional_logic.py` | Multi-round debate logic; governance agent continue conditions |
| `backend/tradingagents-core/tradingagents/graph/trading_graph.py` | Inject governance report; multi-round config; streaming hooks |
| `backend/tradingagents-core/tradingagents/nivesh/subprocess_runner.py` | Add stage-progress queue for SSE streaming |
| `backend/services/feedback_injector.py` | Enhanced feedback with calibration and sector-level learning |
| `backend/services/orchestrator.py` | Wire governance context; multi-round config |
| `backend/routers/analysis.py` | Add streaming trigger; feedback endpoint; chat endpoint |
| `backend/prompts.py` | Add governance agent persona; multi-round debate instructions |
| `backend/tradingagents-core/tradingagents/agents/utils/agent_utils.py` | Add governance tool definitions |
| `backend/database.py` | Add `AnalysisFeedback`, `ThesisAlerts`, `SectorKnowledge` tables |

## iOS — New Files

| File | Purpose |
|------|---------|
| `ios/StockApp/stockme/stockme/Views/AskNiveshView.swift` | Conversational analysis chat UI |
| `ios/StockApp/stockme/stockme/Views/NLScreenerView.swift` | Natural language screener UI |
| `ios/StockApp/stockme/stockme/Views/PortfolioHealthView.swift` | Portfolio risk/health dashboard |
| `ios/StockApp/stockme/stockme/Views/AnalysisFeedbackSheet.swift` | User feedback widget |
| `ios/StockApp/stockme/stockme/Views/AnalysisStreamingOverlay.swift` | Streaming progress UI |
| `ios/StockApp/stockme/stockme/Utilities/SSEClient.swift` | Server-Sent Events client |
| `ios/StockApp/stockme/stockme/Utilities/PDFReportGenerator.swift` | PDF export generator |
| `ios/StockApp/stockme/stockme/Components/TraceableClaimView.swift` | Tappable AI claim drill-down |

## iOS — Existing Files to Modify

| File | Change |
|------|--------|
| `ios/StockApp/stockme/stockme/Views/AnalysisScreen.swift` | Break into components; add streaming; add feedback; add drill-down |
| `ios/StockApp/stockme/stockme/NetworkManager.swift` | Add SSE handler; chat endpoint; NL screener; feedback endpoint |
| `ios/StockApp/stockme/stockme/Models.swift` | Add new response types (streaming events, chat, feedback, etc.) |
| `ios/StockApp/stockme/stockme/Views/TradeJournalScreen.swift` | AI auto-journal entries |
| `ios/StockApp/stockme/stockme/Views/CompareScreen.swift` | AI peer comparison integration |
| `ios/StockApp/stockme/stockme/Views/HomeScreen.swift` | Enhanced Morning Brief with AI macro context |

---

# PART 5: DESIGN CONSTRAINTS (SAME AS STOCK PROFILE PROMPT)

## Typography
- `Theme.officialStampFont(size:)` — section labels, tracking 1.2-1.5
- `Theme.engravedSerif(size:weight:relativeTo:)` — body text, analysis prose
- `Theme.serialNumberFont(size:relativeTo:)` — numbers, prices, metrics
- `Theme.monoTabular(size:)` — tabular data that must align
- `Theme.microLabel(size:)` — tiny annotations

## Colors
- NO raw hex. NO `.blue`/`.red`/`.green`.
- Theme tokens only: `Theme.inkPrimary`, `Theme.inkSecondary`, `Theme.inkTertiary`,
  `Theme.bullGreen`, `Theme.bearRed`, `Theme.securityGold`, `Theme.holdAmber`,
  `Theme.canvasDeep`, `Theme.canvas`, `Theme.surfaceElevated`, `Theme.borderFine`,
  `Theme.borderStrong`, `Theme.goldMuted`, `Theme.goldPrimary`,
  `Theme.dataPositive`, `Theme.dataNegative`

## Cards & Layout
- `.banknoteCard()` on every card
- `Theme.Spacing.*` tokens only (xSmall=2, small=4, tight=6, medium=8,
  standard=12, card=16, screen=20, large=24, xLarge=32, sectionGap=28)
- `Theme.CornerRadius.*` (small=4, tight=6, medium=10, large=12, card=14, pill=9999)
- `Theme.screenPadding` = 20 for horizontal margins
- No `Divider()` — use `GuillocheDivider()` or `SectionDivider()`

## Indian Formatting
- ALL prices via `IndianFormatter.price()` / `.priceCompact()`
- ₹ prefix. Lakhs and Crores. "Million"/"Billion" FORBIDDEN.
- `EKPressStyle()` on all interactive elements
- `HapticManager.selection()` on every tap

## Charts
- Swift Charts only (`import Charts`)
- `LineMark`, `BarMark`, `AreaMark`, `PointMark`, `RuleMark`
- Positive = `Theme.bullGreen`, negative = `Theme.bearRed`
- Max chart height: `UIScreen.main.bounds.height * 0.28`

---

# PART 6: IMPLEMENTATION ORDER

## Sprint 1: High-Impact Backend (Week 1)
1. Governance Agent (new analyst, tools, system prompt)
2. Multi-round debate (2 rounds default)
3. Parallel risk committee
4. Wire governance into graph + reformatter

## Sprint 2: Streaming + Feedback (Week 2)
5. SSE streaming endpoint
6. Streaming UI on iOS
7. User feedback collection (endpoint + UI widget)
8. Epistemic feedback 2.0

## Sprint 3: New AI Capabilities (Week 3)
9. Conversational analysis endpoint + UI
10. Natural language screener endpoint + UI
11. Portfolio risk analysis endpoint + UI
12. Proactive alert agent (CRON)

## Sprint 4: Polish + Export (Week 4)
13. PDF report export
14. Analysis history browser enhancements
15. Interactive drill-down (TraceableClaimView)
16. Multi-language toggle
17. AI investment journal auto-entries
18. Background analysis completion notification

---

# PART 7: CRITICAL "DO NOT" RULES

1. **Do NOT remove the epistemic feedback injector.** Enhance it, never delete.
2. **Do NOT change the Indian Market Priority Weighting Matrix order** in any
   system prompt without preserving: Management Quality → Institutional Flow →
   Contrarian Sentiment → Core Fundamentals → Policy Tailwinds → Global Macro.
3. **Do NOT remove the 1.5x bear weight rule.** This is the core risk-first
   design principle of Nivesh.
4. **Do NOT change the signal-confidence consistency rule:** BUY/SELL require
   ≥50% confidence; <30% confidence forces HOLD.
5. **Do NOT remove the factor engine pre-computation.** It guarantees mathematical
   accuracy without LLM cost.
6. **Do NOT convert Indian formatting to Western.** No millions/billions ever.
7. **Do NOT remove `temperature=0` from the reformatter.** Deterministic output
   is essential for trust.
8. **Do NOT break the subprocess isolation model.** Keep LangGraph runs in
   separate processes.
9. **Do NOT remove the dual ephemeral prompt-cache breakpoints.** They save
   60-80% of token costs on the reformatter.
10. **Do NOT deploy without tests.** Every new agent, tool, and endpoint must
    have corresponding tests.

---

# PART 8: SUCCESS CRITERIA

1. Governance agent correctly identifies and flags auditor resignations,
   promoter pledging >30%, and SEBI surveillance status for all analyzed stocks
2. Multi-round debate produces measurably richer bull/bear arguments
   (at least 2 specific counter-arguments addressed per side)
3. Streaming reduces perceived wait time: first stage visible within 5 seconds
4. User feedback collection works end-to-end (submit → store → batch analyze)
5. Conversational analysis answers follow-up questions with source citations
6. NL screener returns correct results for at least 10 test queries
7. Proactive alert agent catches thesis-invalidating events within 2 hours
8. PDF export produces professional reports matching the app's visual design
9. All new code follows Theme tokens, Indian formatting, and Banknote aesthetic
10. No regression in existing analysis quality or response time

---

# APPENDIX A: Complete Agent Architecture (Post-Implementation)

```
                        ┌────────────────────────────┐
                        │   Factor Engine (pre-comp)  │
                        │   Epistemic Feedback 2.0    │
                        │   Sector Knowledge Base     │
                        └────────────┬───────────────┘
                                     │
              ┌──────────────────────┼──────────────────────┐
              │                      │                      │
              ▼                      ▼                      ▼
    ┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
    │ GOVERNANCE       │   │ MARKET          │   │ SENTIMENT       │
    │ (NEW - runs 1st) │   │ ANALYST         │   │ ANALYST         │
    └────────┬────────┘   └────────┬────────┘   └────────┬────────┘
              │                      │                      │
              └──────────────────────┼──────────────────────┘
                                     │
              ┌──────────────────────┼──────────────────────┐
              │                      │                      │
              ▼                      ▼                      ▼
    ┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
    │ NEWS            │   │ FUNDAMENTALS    │   │ (all 4 analysts  │
    │ ANALYST         │   │ ANALYST         │   │  can run PARALLEL│
    └────────┬────────┘   └────────┬────────┘   │  or SEQUENTIAL) │
              │                      │           └─────────────────┘
              └──────────────────────┘
                         │
              ┌──────────┴──────────┐
              │                     │
              ▼                     ▼
    ┌─────────────────┐   ┌─────────────────┐
    │ BULL RESEARCHER  │◄──│ BEAR RESEARCHER │  (2-3 ROUNDS)
    └────────┬────────┘   └────────┬────────┘
              │                     │
              └──────────┬──────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │ RESEARCH MANAGER     │  (Tier 2: Haiku)
              └──────────┬──────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │ TRADER               │  (Tier 1: DeepSeek)
              └──────────┬──────────┘
                         │
         ┌───────────────┼───────────────┐
         │               │               │
         ▼               ▼               ▼
   ┌──────────┐   ┌──────────┐   ┌──────────┐
   │AGGRESSIVE│   │CONSERV.  │   │NEUTRAL   │  (PARALLEL now)
   │DEBATOR   │   │DEBATOR   │   │DEBATOR   │
   └────┬─────┘   └────┬─────┘   └────┬─────┘
         │               │               │
         └───────────────┼───────────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │ PORTFOLIO MANAGER    │  (Tier 2: Haiku)
              └──────────┬──────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │ CLAUDE SONNET        │  (Tier 3: reformatter)
              │ (DeepSeek fallback)  │
              └──────────┬──────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │ POST-PROCESSING      │
              │ Piotroski + live data│
              └──────────┬──────────┘
                         │
                         ▼
                   ┌──────────┐
                   │  iOS UI  │
                   └──────────┘
```

---

# APPENDIX B: Streaming SSE Event Contract

```
event: stage
data: {"stage":"init","message":"Initializing analysis pipeline…","pct":0}

event: stage
data: {"stage":"technicals","message":"Computing technical indicators…","pct":10}

event: stage
data: {"stage":"governance","message":"Scanning corporate governance…","pct":20}

event: stage
data: {"stage":"fundamentals","message":"Analyzing financial statements…","pct":35}

event: stage
data: {"stage":"sentiment","message":"Processing market sentiment…","pct":50}

event: stage
data: {"stage":"debate","message":"Bull vs Bear debate in progress…","pct":65}

event: stage
data: {"stage":"risk","message":"Risk committee evaluating…","pct":80}

event: stage
data: {"stage":"verdict","message":"Synthesizing final analysis…","pct":90}

event: stage
data: {"stage":"formatting","message":"Formatting report…","pct":95}

event: complete
data: {"analysis_id":1234,"ticker":"RELIANCE",...full StockAnalysis JSON...}

event: error
data: {"message":"Analysis failed: ...","diagnostic":"..."}
```

The iOS SSE client connects to `GET /analyze/stream/RELIANCE?exchange=NSE&user_id=42`
and renders each stage as it arrives. If SSE connection drops, fall back to
polling `GET /analyze/status/{job_id}`.

---

# ESTIMATED EFFORT

| Phase | Items | Estimated Days |
|-------|-------|---------------|
| Sprint 1 | Governance Agent + Multi-round debate + Parallel risk | 5-7 days |
| Sprint 2 | SSE streaming + Feedback + Epistemic 2.0 | 5-7 days |
| Sprint 3 | Chat + NL Screener + Portfolio analysis + Alerts | 6-8 days |
| Sprint 4 | PDF + History + Drill-down + Language + Journal | 5-7 days |
| **Total** | | **21-29 days** |

---

# BEGIN IMPLEMENTATION

Start with Sprint 1, Phase 1.1: the Governance Agent. This is the single
highest-impact improvement because Indian investors prioritize governance
above all other factors. The governance agent system prompt must enforce
the Indian Market Priority Weighting Matrix with Management Quality at #1.

Read the existing analyst files first:
- `backend/tradingagents-core/tradingagents/agents/analysts/fundamentals_analyst.py`
  (model for new governance analyst)
- `backend/tradingagents-core/tradingagents/graph/setup.py` (where to register)
- `backend/tradingagents-core/tradingagents/graph/conditional_logic.py`
  (where to add continue conditions)
- `backend/prompts.py` (where to add governance persona)

Then create the governance analyst following the exact same pattern.
