# Nivesh — LLM API Credits Usage Map

> **Exhaustive audit of every file consuming LLM API credits and the iOS features that trigger them.**
> Generated: June 6, 2026
> Cost rates: DeepSeek V4 Flash $0.00014/Kin / Claude Haiku $0.00025/Kin / Claude Sonnet $0.003/Kin

---

## Contents

1. [Provider & Model Overview](#1-provider--model-overview)
2. [Backend: All Credit-Consuming Files](#2-backend-all-credit-consuming-files)
   - 2.1 Router Endpoints
   - 2.2 Services
   - 2.3 TradingAgents LangGraph Pipeline
3. [iOS: Feature-to-Endpoint Mapping](#3-ios-feature-to-endpoint-mapping)
4. [Cost Per Full Analysis Run](#4-cost-per-full-analysis-run)
5. [Appendix: Triplicated Code Smells](#5-appendix-triplicated-code-smells)

---

## 1. Provider & Model Overview

| Provider | Model(s) | Cost & Tier | Used In |
|----------|----------|-------------|---------|
| **DeepSeek** | `deepseek-chat` (V4 Flash) via `api.deepseek.com/v1` | **Tier 1** — $0.00014/Kin, $0.00028/Kout | 8x LangGraph agents, smart cache gate, daily action, red flags, macro impact, trade journal stats, advisor stance extraction |
| **Anthropic** | `claude-haiku-4-5-20251001` | **Tier 2** — $0.00025/Kin, $0.00125/Kout | Research Manager, Portfolio Manager (LangGraph), Morning Summary |
| **Anthropic** | `claude-3-5-sonnet-latest` | **Tier 3** — $0.003/Kin, $0.015/Kout | Final reformatter (orchestrator), Batch analysis, PDF export narrative |

**Local AI (zero credit cost):**
- `services/sentiment_engine.py` — FinBERT (HuggingFace pipeline, CPU)
- `services/transcript_engine.py` — faster-whisper large-v3 (CPU, int8 quantized)

---

## 2. Backend: All Credit-Consuming Files

### 2.1 Router Endpoints

#### `routers/analysis.py` (1460 lines)

| Line(s) | Endpoint | Model | Cost | What it does |
|---------|----------|-------|------|-------------|
| **74-103** | Helper `_deepseek_chat()` | DeepSeek V4 Flash | LOW | Shared DeepSeek client with 3x retry. Called by daily-action. |
| **202-232** | `_run_analysis_worker()` | LangGraph pipeline | **HIGH** | Subprocess worker for `POST /analyze`. Calls `services.orchestrator.analyze()` — the full multi-agent pipeline. |
| **453-582** | `POST /analyze` | DeepSeek + Haiku + Sonnet | **HIGH** (~$0.03-0.08/req) | Spawns `multiprocessing.Process` → orchestrator.analyze(). Duplicate guard + semaphore (max 2/user). Kills subprocess on client disconnect to save credits. |
| **588-633** | `POST /analyze/batch` | Claude Sonnet | **HIGH** ($0.006-0.03/ticker) | Anthropic Message Batch. Each ticker gets full system prompt with ephemeral caching. No iOS call found. |
| **639-672** | `GET /analyze/batch/{id}` | Anthropic (poll) | ZERO | Reads batch results. Credits consumed at submission time. |
| **1316-1339** | `GET /daily-action/{user_id}` | DeepSeek V4 Flash | **LOW** ($0.00007) | 1-sentence "most important action today" from portfolio warnings/signals. `max_tokens=256`. |
| **1352-1459** | `GET /token-stats` | None | ZERO | Admin-only log reader. Hardcoded rates: Haiku $0.001/M, Sonnet $0.003/M. |

#### `routers/portfolio.py` (2566 lines)

| Line(s) | Endpoint | Model | Cost | What it does |
|---------|----------|-------|------|-------------|
| **60-89** | Helper `_deepseek_chat()` | DeepSeek V4 Flash | LOW | Third copy of same utility. Called by red-flags, macro-impact, trade-journal. |
| **548-569** | `GET /morning-summary/{user_id}` | Claude Haiku 4.5 | **MEDIUM** (~$0.0004) | 4-6 bullet morning brief for user's portfolio holdings + indices. `max_tokens=400`. Cached 1h. |
| **1890-1903** | `GET /portfolio/red-flags/{user_id}` | DeepSeek V4 Flash | **LOW** ($0.00007) | 3-sentence summary of portfolio red flags. `max_tokens=200`. |
| **1974-1981** | `GET /macro-impact/{user_id}` | DeepSeek V4 Flash | **LOW** ($0.0005) | Per-holding macro impact statements given Brent/VIX/USDINR rates. `max_tokens=1500`. Cached 1h. |
| **2314-2323** | `GET /trade-journal/{user_id}/stats` | DeepSeek V4 Flash | **LOW** ($0.00007) | 2 patterns from trade journal reasons. `max_tokens=150`. |
| **2420-2452** | `GET /portfolio/export/pdf/{user_id}` | Claude Sonnet | **HIGH** ($0.004-0.02) | Full one-page portfolio review markdown → PDF. `max_tokens=1200`. |

#### `routers/user.py` (368 lines)

| Line(s) | Endpoint | Model | Cost | What it does |
|---------|----------|-------|------|-------------|
| **264-265** | `POST /notifications/morning-summary-push` | Delegates to Haiku | **MEDIUM** | Calls `morning_summary_endpoint()` from portfolio.py — inherits the Haiku call. |

#### Routers with ZERO LLM usage (verified)

- `routers/auth.py` — login/register only
- `routers/alerts.py` — price alert CRUD
- `routers/market.py` — market data aggregation only
- `routers/dashboard.py` — SSE streaming only
- `routers/notifications.py` — device token management only

---

### 2.2 Services

#### `services/orchestrator.py` (1093 lines)

| Line(s) | Function | Model | Cost | What it does |
|---------|----------|-------|------|-------------|
| **118-165** | `_deepseek_chat()` | DeepSeek V4 Flash | LOW | Generic chat with 3x retry. Inflates max_tokens 5x for reasoning. |
| **439-451** | `run_trading_agents()` | DeepSeek + Haiku | **HIGH** | Instantiates `OptimizedTradingAgentsGraph` with 2-tier config. Calls `ta.propagate()` → 12 LLM invocations. |
| **459-603** | `reformat_with_claude()` | Claude Sonnet (primary), DeepSeek (fallback) | **HIGH** (Sonnet) / LOW (DeepSeek) | Reformats raw LangGraph output to structured JSON. 3x retry per phase. Uses prompt caching. |
| **839-857** | Smart Cache Gate | DeepSeek V4 Flash | **VERY LOW** | Checks 5 news headlines for "major fundamental shift" — if NO, reuses cached analysis. `max_tokens=10`. |
| **741-1093** | `analyze()` | All of the above | **HIGH** | Main entry. Smart cache → trading agents → reformat → normalize. Called from router subprocess. |

#### `services/advisor_harvester.py` (722 lines)

| Line(s) | Function | Model | Cost | What it does |
|---------|----------|-------|------|-------------|
| **102-134** | `_deepseek_chat()` | DeepSeek V4 Flash | LOW | Shared DeepSeek client for stance extraction. |
| **396-463** | `_extract_stance_with_haiku()` | DeepSeek V4 Flash (misnamed) | LOW | Extracts BULLISH/NEUTRAL/BEARISH stance + confidence from transcript snippet. Called per (advisor, ticker, video). |

**Nightly cost estimate:** 5 advisors × ~5 videos × ~3 tickers = ~75 calls × $0.00005 ≈ **$0.004/night**

#### `services/feedback_injector.py` (133 lines) — **ZERO LLM**

Pure deterministic data assembly. No LLM calls.

#### `services/staleness.py` (70 lines) — **ZERO LLM**

Pure math: age + price movement + signal mismatch → score 0-100. The smart cache gate's DeepSeek call lives in orchestrator.py, not here.

#### `services/sentiment_engine.py` (133 lines) — **ZERO credits**

Local FinBERT via HuggingFace pipeline (`device=-1` CPU). No API keys.

#### `services/transcript_engine.py` (295 lines) — **ZERO credits**

Layer 1: YouTube Transcript API (free). Layer 2: Local faster-whisper large-v3 (CPU, int8).

#### Services with ZERO LLM usage (verified)

- `factor_engine.py` — ta library for technicals
- `news_harvester.py` — RSS feedparser + newspaper3k
- `youtube_harvester.py` — YouTube Data API + yt-dlp
- `ticker_matcher.py` — rapidfuzz alias→ticker
- `options_scraper.py` — NSE option chain
- `scraper.py` — Firecrawl + BS4
- `nse_data_provider.py` — yfinance wrapper
- `piotroski.py` — deterministic F-Score
- `pkscreener_runner.py` — subprocess runner
- `portfolio_snapshot.py` — yfinance snapshots
- `disk_cache.py` — file system cache
- `error_telemetry.py` — correlation IDs
- `filings_extractor.py` — NSE filings

---

### 2.3 TradingAgents LangGraph Pipeline

**Location:** `backend/tradingagents-core/tradingagents/`

#### Graph Setup (`graph/setup.py`)

12 agent nodes created per analysis run:

| Node | Model | Calls per run |
|------|-------|--------------|
| Market Analyst | DeepSeek V4 Flash | 1 |
| News Analyst | DeepSeek V4 Flash | 1 |
| Fundamentals Analyst | DeepSeek V4 Flash | 1 |
| Sentiment Analyst | DeepSeek V4 Flash | 1 |
| Bull Researcher | DeepSeek V4 Flash | 1 |
| Bear Researcher | DeepSeek V4 Flash | 1 |
| Research Manager | Claude Haiku 4.5 | 1 |
| Trader | DeepSeek V4 Flash | 1 |
| Aggressive Debator | DeepSeek V4 Flash | 1 |
| Neutral Debator | DeepSeek V4 Flash | 1 |
| Conservative Debator | DeepSeek V4 Flash | 1 |
| Portfolio Manager | Claude Haiku 4.5 | 1 |

**Total: 10× DeepSeek + 2× Claude Haiku = 12 LLM calls per analysis**

#### Individual Agent Files

| File | Line | Provider | What it does |
|------|------|----------|-------------|
| `agents/analysts/market_analyst.py` | 103 | DeepSeek | `chain.invoke(state["messages"])` |
| `agents/analysts/news_analyst.py` | 63 | DeepSeek | `chain.invoke(state["messages"])` |
| `agents/analysts/fundamentals_analyst.py` | 64 | DeepSeek | `chain.invoke(state["messages"])` |
| `agents/analysts/sentiment_analyst.py` | — | DeepSeek | `chain.invoke(state["messages"])` |
| `agents/researchers/bull_researcher.py` | 50 | DeepSeek | `llm.invoke(prompt)` |
| `agents/researchers/bear_researcher.py` | 52 | DeepSeek | `llm.invoke(prompt)` |
| `agents/managers/research_manager.py` | 45-51 | Claude Haiku | `structured_llm.invoke(prompt)` with `with_structured_output(ResearchPlan)` |
| `agents/trader/trader.py` | 51-57 | DeepSeek | `structured_llm.invoke(messages)` with `with_structured_output(TraderProposal)` |
| `agents/managers/portfolio_manager.py` | 66-72 | Claude Haiku | `structured_llm.invoke(prompt)` with `with_structured_output(PortfolioDecision)` |
| `agents/risk_mgmt/aggressive_debator.py` | 39 | DeepSeek | `llm.invoke(prompt)` |
| `agents/risk_mgmt/neutral_debator.py` | 39 | DeepSeek | `llm.invoke(prompt)` |
| `agents/risk_mgmt/conservative_debator.py` | 39 | DeepSeek | `llm.invoke(prompt)` |
| `graph/reflection.py` | 57 | DeepSeek | Post-run reflection for memory |
| `nivesh/reformatter.py` | 255 | Claude Sonnet 4.6 | Reformats JSON (duplicate of orchestrator's reformat) |

#### LLM Client Wrappers (zero consumption — thin wrappers)

| File | Purpose |
|------|---------|
| `llm_clients/factory.py` | Routes provider strings → client classes |
| `llm_clients/openai_client.py` | `ChatOpenAI` / `DeepSeekChatOpenAI` |
| `llm_clients/anthropic_client.py` | `NormalizedChatAnthropic` |
| `llm_clients/google_client.py` | `NormalizedChatGoogleGenerativeAI` |
| `llm_clients/base_client.py` | Abstract base + content normalization |
| `llm_clients/capabilities.py` | Model capability lookup table |
| `llm_clients/model_catalog.py` | Model options catalog |

---

## 3. iOS: Feature-to-Endpoint Mapping

### 3.1 High-Cost Endpoints (User-Initiated)

| iOS Screen | File | Trigger | Backend Endpoint | LLM Cost |
|------------|------|---------|-----------------|----------|
| **AnalysisScreen** | `Views/AnalysisScreen.swift:200` | Tap stock → auto-fetch analysis | `POST /analyze` | **HIGH** (~$0.03-0.08) |
| **AnalysisScreen** (Deep Scan) | `Views/AnalysisScreen.swift:213` | Toggle deep scan + regenerate | `POST /analyze?deep_scan=true` | **HIGH** (~$0.03-0.08) |
| **AnalysisScreen** (Regenerate) | `Views/AnalysisScreen.swift:220` | "Regenerate" from cached alert | `POST /analyze` | **HIGH** (~$0.03-0.08) |

**Navigation paths that lead to AnalysisScreen (all user-initiated, all trigger `POST /analyze`):**

| Source | File | Line |
|--------|------|------|
| HomeScreen → watchlist tap | `HomeScreen.swift` | 713-715 |
| HomeScreen → earnings event | `HomeScreen.swift` | 854 |
| HomeScreen → news ticker | `HomeScreen.swift` | 777-778 |
| HomeScreen → YouTube video ticker | `HomeScreen.swift` | 834-835 |
| HomeScreen → Dalal Street card | `HomeScreen.swift` | 802-806 |
| PortfolioScreen → holding tap | `PortfolioScreen.swift` | 178-180 |
| PortfolioScreen → watchlist tap | `PortfolioScreen.swift` | 207 |
| PortfolioScreen → red flag tap | `PortfolioScreen.swift` | 571 |
| SearchScreen → result tap | `SearchScreen.swift` | 225-227 |
| SearchScreen → "Analyse anyway" | `SearchScreen.swift` | 215-219 |
| SearchScreen → screener result | `SearchScreen.swift` | 192-194 |

### 3.2 Medium-Cost Endpoints (Automatic)

| iOS Screen | File | Trigger | Backend Endpoint | LLM Cost |
|------------|------|---------|-----------------|----------|
| **HomeScreen** | `HomeScreen.swift:496,948` | On appear → `fetchData()` | `GET /morning-summary/{user_id}` | **MEDIUM** (Haiku, cached 1h) |
| **AnalysisScreen** | `AnalysisScreen.swift:45` | On analysis load | `GET /macro-impact/{user_id}` | **MEDIUM** (DeepSeek, cached 1h) |
| **Background** (push) | `NetworkManager.swift:715` | Scheduled morning push | `POST /notifications/morning-summary-push` | **MEDIUM** (Haiku) |

### 3.3 Low-Cost Endpoints (Automatic)

| iOS Screen | File | Trigger | Backend Endpoint | LLM Cost |
|------------|------|---------|-----------------|----------|
| **HomeScreen** | `HomeScreen.swift:965` | On appear | `GET /daily-action/{user_id}` | **LOW** (DeepSeek, $0.00007) |
| **PortfolioScreen** | `PortfolioScreen.swift:316` | On appear | `GET /portfolio/red-flags/{user_id}` | **LOW** (DeepSeek, $0.00007) |
| **PortfolioScreen** | `PortfolioScreen.swift:310` | On appear | `GET /portfolio/signal-warnings` | **ZERO** (DB only) |
| **PortfolioScreen** | `PortfolioScreen.swift:315` | On appear | `GET /portfolio/risk-analysis/{user_id}` | **ZERO** (deterministic) |
| **HomeScreen** | `HomeScreen.swift:957` | On appear | `GET /api/v1/portfolio/advisor-consensus` | **ZERO** (pre-processed) |
| **HomeScreen** → all feed | `HomeScreen.swift:958` | On appear | `GET /api/v1/home-feed` | **ZERO** (DB only) |
| **EarningsDashboard** | `EarningsDashboardView.swift:192` | On appear | `GET /api/v1/earnings/*` | **ZERO** (DB only) |
| **MarketsView** | `TechnicalMomentumView.swift:31` | On appear | `GET /api/v1/market/*` | **ZERO** (aggregation) |
| **SearchScreen** | `SearchScreen.swift:129` | Screener preset tap | `GET /screener` | **ZERO** (yfinance + Piotroski) |

---

## 4. Cost Per Full Analysis Run

| Step | Provider | Model | Call count | Cost |
|------|----------|-------|-----------|------|
| Smart Cache Gate (conditional) | DeepSeek | V4 Flash | 1 | $0.00002 |
| Market Analyst | DeepSeek | V4 Flash | 1 | ~$0.0005 |
| News Analyst | DeepSeek | V4 Flash | 1 | ~$0.0005 |
| Fundamentals Analyst | DeepSeek | V4 Flash | 1 | ~$0.0005 |
| Sentiment Analyst | DeepSeek | V4 Flash | 1 | ~$0.0002 |
| Bull Researcher | DeepSeek | V4 Flash | 1 | ~$0.001 |
| Bear Researcher | DeepSeek | V4 Flash | 1 | ~$0.001 |
| Research Manager | Claude | Haiku 4.5 | 1 | ~$0.0008 |
| Trader | DeepSeek | V4 Flash | 1 | ~$0.0003 |
| Risk Debate (3 agents) | DeepSeek | V4 Flash | 3 | ~$0.0003ea = $0.0009 |
| Portfolio Manager | Claude | Haiku 4.5 | 1 | ~$0.001 |
| Reformat (orchestrator) | Claude | Sonnet | 1 | ~$0.005 |
| Reflection (post-run) | DeepSeek | V4 Flash | 1 | ~$0.0001 |
| **TOTAL** | | | **~14 calls** | **~$0.011** |

**Cost ranges by endpoint:**
- `POST /analyze` (full pipeline): **$0.008-0.015** per stock
- `POST /analyze/batch` (Sonnet per ticker): **$0.006-0.03** per ticker
- Morning summary (Haiku): **~$0.0004** per user (cached 1h)
- All DeepSeek-only endpoints: **$0.00007-0.0005** each
- PDF export (Sonnet): **$0.004-0.02** per export

---

## 5. Appendix: Triplicated Code Smells

These files contain duplicated helper code that should be refactored into a single shared module:

| Function | Files |
|----------|-------|
| `_deepseek_chat()` | `services/orchestrator.py:118`, `routers/analysis.py:74`, `routers/portfolio.py:60` |
| `_get_deepseek_client()` | Same 3 files (paired with above) |
| Reformat JSON pipeline | `services/orchestrator.py:459` (Sonnet + DeepSeek fallback), `tradingagents/nivesh/reformatter.py:255` (Sonnet-only) |

See AGENTS.md §3.1 Controller-Service-Repository boundary — these belong in `services/`.
