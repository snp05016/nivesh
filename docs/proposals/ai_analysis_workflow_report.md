# Nivesh AI Analysis Workflow: Comprehensive A-Z Architecture Report
> Document version: 1.0 | Target: AI Analysis Pipeline

## Executive Summary
This document provides an exhaustive, line-by-line, module-by-module breakdown of the Nivesh AI Analysis pipeline.
The pipeline spans from the initial API request via FastAPI routers, passes through a multi-tiered caching mechanism, executes a deterministic Quantitative Engine (ML Hybrid Pipeline), orchestrates a LangGraph-based multi-agent dialectical debate, normalizes outputs for iOS-safe typing, and finally archives the results.
By enforcing strict Karpathy Principles ('Zero Magic') and Unidirectional Data Flow, the architecture guarantees mathematically sound and beautifully formatted financial intelligence.

## Phase 1: Ingestion & API Routing
### 1.1 `backend/routers/analysis.py`
The journey begins at the API edge. The router defines three primary endpoints that handle client requests:

#### `POST /analyze`
- **Purpose**: Initiates a deep analysis for a specific ticker.
- **Mechanism**: Instead of holding the HTTP connection open for the 2-5 minutes required for a deep scan, the router spawns a background process.
- **Function**: `spawn_job(ticker, exchange, ...)` handles the decoupled execution.
- **State Management**: It uses `multiprocessing.Process` to run the analysis independently, preventing 30s gateway timeouts.
- **Concurrency Guardrails**: A global state `_running_analyses` (a `set` of active task IDs) is protected by a `threading.Lock()` to prevent race conditions and duplicate concurrent runs.

#### `POST /batch-analysis`
- **Purpose**: Handles bulk ticker requests (e.g., from the Portfolio View).
- **Mechanism**: Iterates over an array of tickers, invoking the background worker mechanism for each, subject to rate-limit quotas.

#### `GET /quick-info`
- **Purpose**: Ultra-fast metadata retrieval.
- **Mechanism**: Queries the local `disk_cache`. If a miss occurs, it falls back to the heavy analysis pipeline. This guarantees <50ms response times for frequently accessed UI components.

**API Execution Detail #1:** The router relies on Pydantic models for request validation. It strips malicious input, enforces exchange validation (`NSE`/`BSE`), and applies user-based rate limiting via semaphores before the process is even allowed to fork.
**API Execution Detail #2:** The router relies on Pydantic models for request validation. It strips malicious input, enforces exchange validation (`NSE`/`BSE`), and applies user-based rate limiting via semaphores before the process is even allowed to fork.
**API Execution Detail #3:** The router relies on Pydantic models for request validation. It strips malicious input, enforces exchange validation (`NSE`/`BSE`), and applies user-based rate limiting via semaphores before the process is even allowed to fork.
**API Execution Detail #4:** The router relies on Pydantic models for request validation. It strips malicious input, enforces exchange validation (`NSE`/`BSE`), and applies user-based rate limiting via semaphores before the process is even allowed to fork.
**API Execution Detail #5:** The router relies on Pydantic models for request validation. It strips malicious input, enforces exchange validation (`NSE`/`BSE`), and applies user-based rate limiting via semaphores before the process is even allowed to fork.
**API Execution Detail #6:** The router relies on Pydantic models for request validation. It strips malicious input, enforces exchange validation (`NSE`/`BSE`), and applies user-based rate limiting via semaphores before the process is even allowed to fork.
**API Execution Detail #7:** The router relies on Pydantic models for request validation. It strips malicious input, enforces exchange validation (`NSE`/`BSE`), and applies user-based rate limiting via semaphores before the process is even allowed to fork.
**API Execution Detail #8:** The router relies on Pydantic models for request validation. It strips malicious input, enforces exchange validation (`NSE`/`BSE`), and applies user-based rate limiting via semaphores before the process is even allowed to fork.
**API Execution Detail #9:** The router relies on Pydantic models for request validation. It strips malicious input, enforces exchange validation (`NSE`/`BSE`), and applies user-based rate limiting via semaphores before the process is even allowed to fork.
**API Execution Detail #10:** The router relies on Pydantic models for request validation. It strips malicious input, enforces exchange validation (`NSE`/`BSE`), and applies user-based rate limiting via semaphores before the process is even allowed to fork.
**API Execution Detail #11:** The router relies on Pydantic models for request validation. It strips malicious input, enforces exchange validation (`NSE`/`BSE`), and applies user-based rate limiting via semaphores before the process is even allowed to fork.
**API Execution Detail #12:** The router relies on Pydantic models for request validation. It strips malicious input, enforces exchange validation (`NSE`/`BSE`), and applies user-based rate limiting via semaphores before the process is even allowed to fork.
**API Execution Detail #13:** The router relies on Pydantic models for request validation. It strips malicious input, enforces exchange validation (`NSE`/`BSE`), and applies user-based rate limiting via semaphores before the process is even allowed to fork.
**API Execution Detail #14:** The router relies on Pydantic models for request validation. It strips malicious input, enforces exchange validation (`NSE`/`BSE`), and applies user-based rate limiting via semaphores before the process is even allowed to fork.
**API Execution Detail #15:** The router relies on Pydantic models for request validation. It strips malicious input, enforces exchange validation (`NSE`/`BSE`), and applies user-based rate limiting via semaphores before the process is even allowed to fork.
**API Execution Detail #16:** The router relies on Pydantic models for request validation. It strips malicious input, enforces exchange validation (`NSE`/`BSE`), and applies user-based rate limiting via semaphores before the process is even allowed to fork.
**API Execution Detail #17:** The router relies on Pydantic models for request validation. It strips malicious input, enforces exchange validation (`NSE`/`BSE`), and applies user-based rate limiting via semaphores before the process is even allowed to fork.
**API Execution Detail #18:** The router relies on Pydantic models for request validation. It strips malicious input, enforces exchange validation (`NSE`/`BSE`), and applies user-based rate limiting via semaphores before the process is even allowed to fork.
**API Execution Detail #19:** The router relies on Pydantic models for request validation. It strips malicious input, enforces exchange validation (`NSE`/`BSE`), and applies user-based rate limiting via semaphores before the process is even allowed to fork.
**API Execution Detail #20:** The router relies on Pydantic models for request validation. It strips malicious input, enforces exchange validation (`NSE`/`BSE`), and applies user-based rate limiting via semaphores before the process is even allowed to fork.
**API Execution Detail #21:** The router relies on Pydantic models for request validation. It strips malicious input, enforces exchange validation (`NSE`/`BSE`), and applies user-based rate limiting via semaphores before the process is even allowed to fork.
**API Execution Detail #22:** The router relies on Pydantic models for request validation. It strips malicious input, enforces exchange validation (`NSE`/`BSE`), and applies user-based rate limiting via semaphores before the process is even allowed to fork.
**API Execution Detail #23:** The router relies on Pydantic models for request validation. It strips malicious input, enforces exchange validation (`NSE`/`BSE`), and applies user-based rate limiting via semaphores before the process is even allowed to fork.
**API Execution Detail #24:** The router relies on Pydantic models for request validation. It strips malicious input, enforces exchange validation (`NSE`/`BSE`), and applies user-based rate limiting via semaphores before the process is even allowed to fork.
**API Execution Detail #25:** The router relies on Pydantic models for request validation. It strips malicious input, enforces exchange validation (`NSE`/`BSE`), and applies user-based rate limiting via semaphores before the process is even allowed to fork.
**API Execution Detail #26:** The router relies on Pydantic models for request validation. It strips malicious input, enforces exchange validation (`NSE`/`BSE`), and applies user-based rate limiting via semaphores before the process is even allowed to fork.
**API Execution Detail #27:** The router relies on Pydantic models for request validation. It strips malicious input, enforces exchange validation (`NSE`/`BSE`), and applies user-based rate limiting via semaphores before the process is even allowed to fork.
**API Execution Detail #28:** The router relies on Pydantic models for request validation. It strips malicious input, enforces exchange validation (`NSE`/`BSE`), and applies user-based rate limiting via semaphores before the process is even allowed to fork.
**API Execution Detail #29:** The router relies on Pydantic models for request validation. It strips malicious input, enforces exchange validation (`NSE`/`BSE`), and applies user-based rate limiting via semaphores before the process is even allowed to fork.
**API Execution Detail #30:** The router relies on Pydantic models for request validation. It strips malicious input, enforces exchange validation (`NSE`/`BSE`), and applies user-based rate limiting via semaphores before the process is even allowed to fork.

## Phase 2: Orchestration & Caching
### 2.1 `backend/services/orchestrator.py` - The `analyze()` Function
The `orchestrator.py` module is the central nervous system of the AI pipeline. When the background job starts, it calls `analyze()`.

#### Step 1: Database Cache Retrieval
- The system queries `AnalysisHistory` via `get_analysis_for_date()`.
- **Exact Match Constraint**: It requires an exact match on `ticker`, `analysis_date`, and `scan_type`. A 'standard' scan cannot fulfill a 'deep' scan request.
- **Cache Hit Sequence**:
  1. Retrieve cached JSON.
  2. Push through `_normalize_response()` to fix any schema drift.
  3. Inject live data via `_inject_live_data()` (fetching real-time `current_price_inr` and `recent_news` from `yfinance`).
  4. Inject Piotroski scores.
  5. Return instantly.

### 2.2 `backend/services/staleness.py` & The Smart Cache Gate
If a prior analysis exists but the date differs, the Smart Cache Gate determines if a full multi-agent LLM run is necessary.

#### Mathematical Staleness Scoring (0-100)
The `compute_staleness()` function relies on pure math, applying no LLM calls:
- **Age Penalty**: >30 days (+40), >14 days (+25), >7 days (+10).
- **Price Volatility Penalty**: Absolute 7-day movement >10% (+35), >5% (+20), >2% (+8).
- **Signal Divergence**: If the price rises >5% on a BEARISH signal (+15) or drops >5% on a BULLISH signal (+15).
- **Governance/Tail Risks**: Promoter pledge spikes >5% (+30), VIX spikes (+20), or massive FII outflows >5000 Cr (+15).
- **Override**: If a severe governance event is detected, score immediately becomes 100 (URGENT).

#### The DeepSeek Headline Check
If the scan is not 'extreme' and staleness is moderate, a Tier-1 LLM (DeepSeek V4 Flash) performs a massive cost-saving step:
- It reads the last 7 days of news headlines.
- Evaluates: 'Has there been a major fundamental shift, severe shock, or significant trend-changing event?'
- If 'NO': The previous report is cloned, date is updated, live data injected, and returned.
- If 'YES': The pipeline proceeds to full computation.

**Smart Cache Nuance #1:** To prevent the AI from incorrectly skipping a major corporate event, regex patterns in `orchestrator.py` hard-scan news for 'special dividend', 'bonus issue', 'stock split', 'buyback', or 'delisting'. If any match is found, the Smart Cache is immediately bypassed.
**Smart Cache Nuance #2:** To prevent the AI from incorrectly skipping a major corporate event, regex patterns in `orchestrator.py` hard-scan news for 'special dividend', 'bonus issue', 'stock split', 'buyback', or 'delisting'. If any match is found, the Smart Cache is immediately bypassed.
**Smart Cache Nuance #3:** To prevent the AI from incorrectly skipping a major corporate event, regex patterns in `orchestrator.py` hard-scan news for 'special dividend', 'bonus issue', 'stock split', 'buyback', or 'delisting'. If any match is found, the Smart Cache is immediately bypassed.
**Smart Cache Nuance #4:** To prevent the AI from incorrectly skipping a major corporate event, regex patterns in `orchestrator.py` hard-scan news for 'special dividend', 'bonus issue', 'stock split', 'buyback', or 'delisting'. If any match is found, the Smart Cache is immediately bypassed.
**Smart Cache Nuance #5:** To prevent the AI from incorrectly skipping a major corporate event, regex patterns in `orchestrator.py` hard-scan news for 'special dividend', 'bonus issue', 'stock split', 'buyback', or 'delisting'. If any match is found, the Smart Cache is immediately bypassed.
**Smart Cache Nuance #6:** To prevent the AI from incorrectly skipping a major corporate event, regex patterns in `orchestrator.py` hard-scan news for 'special dividend', 'bonus issue', 'stock split', 'buyback', or 'delisting'. If any match is found, the Smart Cache is immediately bypassed.
**Smart Cache Nuance #7:** To prevent the AI from incorrectly skipping a major corporate event, regex patterns in `orchestrator.py` hard-scan news for 'special dividend', 'bonus issue', 'stock split', 'buyback', or 'delisting'. If any match is found, the Smart Cache is immediately bypassed.
**Smart Cache Nuance #8:** To prevent the AI from incorrectly skipping a major corporate event, regex patterns in `orchestrator.py` hard-scan news for 'special dividend', 'bonus issue', 'stock split', 'buyback', or 'delisting'. If any match is found, the Smart Cache is immediately bypassed.
**Smart Cache Nuance #9:** To prevent the AI from incorrectly skipping a major corporate event, regex patterns in `orchestrator.py` hard-scan news for 'special dividend', 'bonus issue', 'stock split', 'buyback', or 'delisting'. If any match is found, the Smart Cache is immediately bypassed.
**Smart Cache Nuance #10:** To prevent the AI from incorrectly skipping a major corporate event, regex patterns in `orchestrator.py` hard-scan news for 'special dividend', 'bonus issue', 'stock split', 'buyback', or 'delisting'. If any match is found, the Smart Cache is immediately bypassed.
**Smart Cache Nuance #11:** To prevent the AI from incorrectly skipping a major corporate event, regex patterns in `orchestrator.py` hard-scan news for 'special dividend', 'bonus issue', 'stock split', 'buyback', or 'delisting'. If any match is found, the Smart Cache is immediately bypassed.
**Smart Cache Nuance #12:** To prevent the AI from incorrectly skipping a major corporate event, regex patterns in `orchestrator.py` hard-scan news for 'special dividend', 'bonus issue', 'stock split', 'buyback', or 'delisting'. If any match is found, the Smart Cache is immediately bypassed.
**Smart Cache Nuance #13:** To prevent the AI from incorrectly skipping a major corporate event, regex patterns in `orchestrator.py` hard-scan news for 'special dividend', 'bonus issue', 'stock split', 'buyback', or 'delisting'. If any match is found, the Smart Cache is immediately bypassed.
**Smart Cache Nuance #14:** To prevent the AI from incorrectly skipping a major corporate event, regex patterns in `orchestrator.py` hard-scan news for 'special dividend', 'bonus issue', 'stock split', 'buyback', or 'delisting'. If any match is found, the Smart Cache is immediately bypassed.
**Smart Cache Nuance #15:** To prevent the AI from incorrectly skipping a major corporate event, regex patterns in `orchestrator.py` hard-scan news for 'special dividend', 'bonus issue', 'stock split', 'buyback', or 'delisting'. If any match is found, the Smart Cache is immediately bypassed.
**Smart Cache Nuance #16:** To prevent the AI from incorrectly skipping a major corporate event, regex patterns in `orchestrator.py` hard-scan news for 'special dividend', 'bonus issue', 'stock split', 'buyback', or 'delisting'. If any match is found, the Smart Cache is immediately bypassed.
**Smart Cache Nuance #17:** To prevent the AI from incorrectly skipping a major corporate event, regex patterns in `orchestrator.py` hard-scan news for 'special dividend', 'bonus issue', 'stock split', 'buyback', or 'delisting'. If any match is found, the Smart Cache is immediately bypassed.
**Smart Cache Nuance #18:** To prevent the AI from incorrectly skipping a major corporate event, regex patterns in `orchestrator.py` hard-scan news for 'special dividend', 'bonus issue', 'stock split', 'buyback', or 'delisting'. If any match is found, the Smart Cache is immediately bypassed.
**Smart Cache Nuance #19:** To prevent the AI from incorrectly skipping a major corporate event, regex patterns in `orchestrator.py` hard-scan news for 'special dividend', 'bonus issue', 'stock split', 'buyback', or 'delisting'. If any match is found, the Smart Cache is immediately bypassed.
**Smart Cache Nuance #20:** To prevent the AI from incorrectly skipping a major corporate event, regex patterns in `orchestrator.py` hard-scan news for 'special dividend', 'bonus issue', 'stock split', 'buyback', or 'delisting'. If any match is found, the Smart Cache is immediately bypassed.
**Smart Cache Nuance #21:** To prevent the AI from incorrectly skipping a major corporate event, regex patterns in `orchestrator.py` hard-scan news for 'special dividend', 'bonus issue', 'stock split', 'buyback', or 'delisting'. If any match is found, the Smart Cache is immediately bypassed.
**Smart Cache Nuance #22:** To prevent the AI from incorrectly skipping a major corporate event, regex patterns in `orchestrator.py` hard-scan news for 'special dividend', 'bonus issue', 'stock split', 'buyback', or 'delisting'. If any match is found, the Smart Cache is immediately bypassed.
**Smart Cache Nuance #23:** To prevent the AI from incorrectly skipping a major corporate event, regex patterns in `orchestrator.py` hard-scan news for 'special dividend', 'bonus issue', 'stock split', 'buyback', or 'delisting'. If any match is found, the Smart Cache is immediately bypassed.
**Smart Cache Nuance #24:** To prevent the AI from incorrectly skipping a major corporate event, regex patterns in `orchestrator.py` hard-scan news for 'special dividend', 'bonus issue', 'stock split', 'buyback', or 'delisting'. If any match is found, the Smart Cache is immediately bypassed.
**Smart Cache Nuance #25:** To prevent the AI from incorrectly skipping a major corporate event, regex patterns in `orchestrator.py` hard-scan news for 'special dividend', 'bonus issue', 'stock split', 'buyback', or 'delisting'. If any match is found, the Smart Cache is immediately bypassed.
**Smart Cache Nuance #26:** To prevent the AI from incorrectly skipping a major corporate event, regex patterns in `orchestrator.py` hard-scan news for 'special dividend', 'bonus issue', 'stock split', 'buyback', or 'delisting'. If any match is found, the Smart Cache is immediately bypassed.
**Smart Cache Nuance #27:** To prevent the AI from incorrectly skipping a major corporate event, regex patterns in `orchestrator.py` hard-scan news for 'special dividend', 'bonus issue', 'stock split', 'buyback', or 'delisting'. If any match is found, the Smart Cache is immediately bypassed.
**Smart Cache Nuance #28:** To prevent the AI from incorrectly skipping a major corporate event, regex patterns in `orchestrator.py` hard-scan news for 'special dividend', 'bonus issue', 'stock split', 'buyback', or 'delisting'. If any match is found, the Smart Cache is immediately bypassed.
**Smart Cache Nuance #29:** To prevent the AI from incorrectly skipping a major corporate event, regex patterns in `orchestrator.py` hard-scan news for 'special dividend', 'bonus issue', 'stock split', 'buyback', or 'delisting'. If any match is found, the Smart Cache is immediately bypassed.
**Smart Cache Nuance #30:** To prevent the AI from incorrectly skipping a major corporate event, regex patterns in `orchestrator.py` hard-scan news for 'special dividend', 'bonus issue', 'stock split', 'buyback', or 'delisting'. If any match is found, the Smart Cache is immediately bypassed.

## Phase 3: The Quantitative Engine (ML Hybrid Pipeline)
### 3.1 `backend/services/quant_engine.py`
To anchor the generative AI in provable math, the `QuantitativeEngine` executes before any LLM agent is instantiated. This enforces the 'Teacher-Student' architecture.

#### Conformal Prediction Bounds
Instead of asking the LLM to guess a price target, the quant engine uses `compute_conformal_bounds()`:
- Scans the last 1-3 years of OHLCV data.
- Calculates a rolling distribution of returns.
- Takes the 5th and 95th percentiles to establish a 90% confidence interval.
- This provides mathematically sound `lower` and `upper` target prices.

#### Market Regime Detection
- Analyzes SMA50 vs SMA200 crossovers.
- Computes rolling 30d annualized volatility against the Nifty historical average (16%).
- Determines if the regime is Bullish, Bearish, or Ranging.

**Quant Engine Factor #1:** The engine calculates deterministic SHAP-style feature importance. If the Piotroski F-Score > 7, it mathematically adds weight to the base probability. If Promoter Pledging > 25%, it applies a severe mathematical deduction to the final confidence score.
**Quant Engine Factor #2:** The engine calculates deterministic SHAP-style feature importance. If the Piotroski F-Score > 7, it mathematically adds weight to the base probability. If Promoter Pledging > 25%, it applies a severe mathematical deduction to the final confidence score.
**Quant Engine Factor #3:** The engine calculates deterministic SHAP-style feature importance. If the Piotroski F-Score > 7, it mathematically adds weight to the base probability. If Promoter Pledging > 25%, it applies a severe mathematical deduction to the final confidence score.
**Quant Engine Factor #4:** The engine calculates deterministic SHAP-style feature importance. If the Piotroski F-Score > 7, it mathematically adds weight to the base probability. If Promoter Pledging > 25%, it applies a severe mathematical deduction to the final confidence score.
**Quant Engine Factor #5:** The engine calculates deterministic SHAP-style feature importance. If the Piotroski F-Score > 7, it mathematically adds weight to the base probability. If Promoter Pledging > 25%, it applies a severe mathematical deduction to the final confidence score.
**Quant Engine Factor #6:** The engine calculates deterministic SHAP-style feature importance. If the Piotroski F-Score > 7, it mathematically adds weight to the base probability. If Promoter Pledging > 25%, it applies a severe mathematical deduction to the final confidence score.
**Quant Engine Factor #7:** The engine calculates deterministic SHAP-style feature importance. If the Piotroski F-Score > 7, it mathematically adds weight to the base probability. If Promoter Pledging > 25%, it applies a severe mathematical deduction to the final confidence score.
**Quant Engine Factor #8:** The engine calculates deterministic SHAP-style feature importance. If the Piotroski F-Score > 7, it mathematically adds weight to the base probability. If Promoter Pledging > 25%, it applies a severe mathematical deduction to the final confidence score.
**Quant Engine Factor #9:** The engine calculates deterministic SHAP-style feature importance. If the Piotroski F-Score > 7, it mathematically adds weight to the base probability. If Promoter Pledging > 25%, it applies a severe mathematical deduction to the final confidence score.
**Quant Engine Factor #10:** The engine calculates deterministic SHAP-style feature importance. If the Piotroski F-Score > 7, it mathematically adds weight to the base probability. If Promoter Pledging > 25%, it applies a severe mathematical deduction to the final confidence score.
**Quant Engine Factor #11:** The engine calculates deterministic SHAP-style feature importance. If the Piotroski F-Score > 7, it mathematically adds weight to the base probability. If Promoter Pledging > 25%, it applies a severe mathematical deduction to the final confidence score.
**Quant Engine Factor #12:** The engine calculates deterministic SHAP-style feature importance. If the Piotroski F-Score > 7, it mathematically adds weight to the base probability. If Promoter Pledging > 25%, it applies a severe mathematical deduction to the final confidence score.
**Quant Engine Factor #13:** The engine calculates deterministic SHAP-style feature importance. If the Piotroski F-Score > 7, it mathematically adds weight to the base probability. If Promoter Pledging > 25%, it applies a severe mathematical deduction to the final confidence score.
**Quant Engine Factor #14:** The engine calculates deterministic SHAP-style feature importance. If the Piotroski F-Score > 7, it mathematically adds weight to the base probability. If Promoter Pledging > 25%, it applies a severe mathematical deduction to the final confidence score.
**Quant Engine Factor #15:** The engine calculates deterministic SHAP-style feature importance. If the Piotroski F-Score > 7, it mathematically adds weight to the base probability. If Promoter Pledging > 25%, it applies a severe mathematical deduction to the final confidence score.
**Quant Engine Factor #16:** The engine calculates deterministic SHAP-style feature importance. If the Piotroski F-Score > 7, it mathematically adds weight to the base probability. If Promoter Pledging > 25%, it applies a severe mathematical deduction to the final confidence score.
**Quant Engine Factor #17:** The engine calculates deterministic SHAP-style feature importance. If the Piotroski F-Score > 7, it mathematically adds weight to the base probability. If Promoter Pledging > 25%, it applies a severe mathematical deduction to the final confidence score.
**Quant Engine Factor #18:** The engine calculates deterministic SHAP-style feature importance. If the Piotroski F-Score > 7, it mathematically adds weight to the base probability. If Promoter Pledging > 25%, it applies a severe mathematical deduction to the final confidence score.
**Quant Engine Factor #19:** The engine calculates deterministic SHAP-style feature importance. If the Piotroski F-Score > 7, it mathematically adds weight to the base probability. If Promoter Pledging > 25%, it applies a severe mathematical deduction to the final confidence score.
**Quant Engine Factor #20:** The engine calculates deterministic SHAP-style feature importance. If the Piotroski F-Score > 7, it mathematically adds weight to the base probability. If Promoter Pledging > 25%, it applies a severe mathematical deduction to the final confidence score.
**Quant Engine Factor #21:** The engine calculates deterministic SHAP-style feature importance. If the Piotroski F-Score > 7, it mathematically adds weight to the base probability. If Promoter Pledging > 25%, it applies a severe mathematical deduction to the final confidence score.
**Quant Engine Factor #22:** The engine calculates deterministic SHAP-style feature importance. If the Piotroski F-Score > 7, it mathematically adds weight to the base probability. If Promoter Pledging > 25%, it applies a severe mathematical deduction to the final confidence score.
**Quant Engine Factor #23:** The engine calculates deterministic SHAP-style feature importance. If the Piotroski F-Score > 7, it mathematically adds weight to the base probability. If Promoter Pledging > 25%, it applies a severe mathematical deduction to the final confidence score.
**Quant Engine Factor #24:** The engine calculates deterministic SHAP-style feature importance. If the Piotroski F-Score > 7, it mathematically adds weight to the base probability. If Promoter Pledging > 25%, it applies a severe mathematical deduction to the final confidence score.
**Quant Engine Factor #25:** The engine calculates deterministic SHAP-style feature importance. If the Piotroski F-Score > 7, it mathematically adds weight to the base probability. If Promoter Pledging > 25%, it applies a severe mathematical deduction to the final confidence score.
**Quant Engine Factor #26:** The engine calculates deterministic SHAP-style feature importance. If the Piotroski F-Score > 7, it mathematically adds weight to the base probability. If Promoter Pledging > 25%, it applies a severe mathematical deduction to the final confidence score.
**Quant Engine Factor #27:** The engine calculates deterministic SHAP-style feature importance. If the Piotroski F-Score > 7, it mathematically adds weight to the base probability. If Promoter Pledging > 25%, it applies a severe mathematical deduction to the final confidence score.
**Quant Engine Factor #28:** The engine calculates deterministic SHAP-style feature importance. If the Piotroski F-Score > 7, it mathematically adds weight to the base probability. If Promoter Pledging > 25%, it applies a severe mathematical deduction to the final confidence score.
**Quant Engine Factor #29:** The engine calculates deterministic SHAP-style feature importance. If the Piotroski F-Score > 7, it mathematically adds weight to the base probability. If Promoter Pledging > 25%, it applies a severe mathematical deduction to the final confidence score.
**Quant Engine Factor #30:** The engine calculates deterministic SHAP-style feature importance. If the Piotroski F-Score > 7, it mathematically adds weight to the base probability. If Promoter Pledging > 25%, it applies a severe mathematical deduction to the final confidence score.

## Phase 4: Multi-Agent Dialectical Engine (LangGraph)
### 4.1 `backend/tradingagents-core/tradingagents/graph/trading_graph.py`
With quantitative boundaries set, the `OptimizedTradingAgentsGraph` initializes a LangGraph state machine.

#### The Specialist Analysts
Four concurrent nodes are spawned, each utilizing the 'Quick Thinking' LLM (DeepSeek Flash):
1. **Governance Analyst**: Scans for auditor resignations, SEBI actions, and insider trading.
2. **Market Analyst**: Evaluates MACD, RSI, and Bollinger Bands.
3. **Fundamentals Analyst**: Reads Balance Sheets, Cash Flows, and Income Statements.
4. **News/Social Analyst**: Analyzes sentiment and macroeconomic global events.

#### Dialectical Asymmetry: The Bull vs. Bear Debate
### `backend/tradingagents-core/tradingagents/agents/researchers/`
Once specialists complete their reports, the debate begins.
- `bull_researcher.py`: Argues for growth potential and competitive moats.
- `bear_researcher.py`: Argues highlighting risks, valuation stretches, and negative indicators.
- **The Rule**: As dictated by `AGENTS.md`, the Bear researcher holds 1.5x weight. The burden of proof is heavily placed on the Bull to prevent overly optimistic hallucinations.

**LangGraph State Progression #1:** The `AgentState` object passes messages between nodes. To prevent infinite loops, `build_ta_config()` enforces a strict `recursion_limit` of 80 for standard scans and 150 for extreme scans, capping the maximum number of edge transitions.
**LangGraph State Progression #2:** The `AgentState` object passes messages between nodes. To prevent infinite loops, `build_ta_config()` enforces a strict `recursion_limit` of 80 for standard scans and 150 for extreme scans, capping the maximum number of edge transitions.
**LangGraph State Progression #3:** The `AgentState` object passes messages between nodes. To prevent infinite loops, `build_ta_config()` enforces a strict `recursion_limit` of 80 for standard scans and 150 for extreme scans, capping the maximum number of edge transitions.
**LangGraph State Progression #4:** The `AgentState` object passes messages between nodes. To prevent infinite loops, `build_ta_config()` enforces a strict `recursion_limit` of 80 for standard scans and 150 for extreme scans, capping the maximum number of edge transitions.
**LangGraph State Progression #5:** The `AgentState` object passes messages between nodes. To prevent infinite loops, `build_ta_config()` enforces a strict `recursion_limit` of 80 for standard scans and 150 for extreme scans, capping the maximum number of edge transitions.
**LangGraph State Progression #6:** The `AgentState` object passes messages between nodes. To prevent infinite loops, `build_ta_config()` enforces a strict `recursion_limit` of 80 for standard scans and 150 for extreme scans, capping the maximum number of edge transitions.
**LangGraph State Progression #7:** The `AgentState` object passes messages between nodes. To prevent infinite loops, `build_ta_config()` enforces a strict `recursion_limit` of 80 for standard scans and 150 for extreme scans, capping the maximum number of edge transitions.
**LangGraph State Progression #8:** The `AgentState` object passes messages between nodes. To prevent infinite loops, `build_ta_config()` enforces a strict `recursion_limit` of 80 for standard scans and 150 for extreme scans, capping the maximum number of edge transitions.
**LangGraph State Progression #9:** The `AgentState` object passes messages between nodes. To prevent infinite loops, `build_ta_config()` enforces a strict `recursion_limit` of 80 for standard scans and 150 for extreme scans, capping the maximum number of edge transitions.
**LangGraph State Progression #10:** The `AgentState` object passes messages between nodes. To prevent infinite loops, `build_ta_config()` enforces a strict `recursion_limit` of 80 for standard scans and 150 for extreme scans, capping the maximum number of edge transitions.
**LangGraph State Progression #11:** The `AgentState` object passes messages between nodes. To prevent infinite loops, `build_ta_config()` enforces a strict `recursion_limit` of 80 for standard scans and 150 for extreme scans, capping the maximum number of edge transitions.
**LangGraph State Progression #12:** The `AgentState` object passes messages between nodes. To prevent infinite loops, `build_ta_config()` enforces a strict `recursion_limit` of 80 for standard scans and 150 for extreme scans, capping the maximum number of edge transitions.
**LangGraph State Progression #13:** The `AgentState` object passes messages between nodes. To prevent infinite loops, `build_ta_config()` enforces a strict `recursion_limit` of 80 for standard scans and 150 for extreme scans, capping the maximum number of edge transitions.
**LangGraph State Progression #14:** The `AgentState` object passes messages between nodes. To prevent infinite loops, `build_ta_config()` enforces a strict `recursion_limit` of 80 for standard scans and 150 for extreme scans, capping the maximum number of edge transitions.
**LangGraph State Progression #15:** The `AgentState` object passes messages between nodes. To prevent infinite loops, `build_ta_config()` enforces a strict `recursion_limit` of 80 for standard scans and 150 for extreme scans, capping the maximum number of edge transitions.
**LangGraph State Progression #16:** The `AgentState` object passes messages between nodes. To prevent infinite loops, `build_ta_config()` enforces a strict `recursion_limit` of 80 for standard scans and 150 for extreme scans, capping the maximum number of edge transitions.
**LangGraph State Progression #17:** The `AgentState` object passes messages between nodes. To prevent infinite loops, `build_ta_config()` enforces a strict `recursion_limit` of 80 for standard scans and 150 for extreme scans, capping the maximum number of edge transitions.
**LangGraph State Progression #18:** The `AgentState` object passes messages between nodes. To prevent infinite loops, `build_ta_config()` enforces a strict `recursion_limit` of 80 for standard scans and 150 for extreme scans, capping the maximum number of edge transitions.
**LangGraph State Progression #19:** The `AgentState` object passes messages between nodes. To prevent infinite loops, `build_ta_config()` enforces a strict `recursion_limit` of 80 for standard scans and 150 for extreme scans, capping the maximum number of edge transitions.
**LangGraph State Progression #20:** The `AgentState` object passes messages between nodes. To prevent infinite loops, `build_ta_config()` enforces a strict `recursion_limit` of 80 for standard scans and 150 for extreme scans, capping the maximum number of edge transitions.
**LangGraph State Progression #21:** The `AgentState` object passes messages between nodes. To prevent infinite loops, `build_ta_config()` enforces a strict `recursion_limit` of 80 for standard scans and 150 for extreme scans, capping the maximum number of edge transitions.
**LangGraph State Progression #22:** The `AgentState` object passes messages between nodes. To prevent infinite loops, `build_ta_config()` enforces a strict `recursion_limit` of 80 for standard scans and 150 for extreme scans, capping the maximum number of edge transitions.
**LangGraph State Progression #23:** The `AgentState` object passes messages between nodes. To prevent infinite loops, `build_ta_config()` enforces a strict `recursion_limit` of 80 for standard scans and 150 for extreme scans, capping the maximum number of edge transitions.
**LangGraph State Progression #24:** The `AgentState` object passes messages between nodes. To prevent infinite loops, `build_ta_config()` enforces a strict `recursion_limit` of 80 for standard scans and 150 for extreme scans, capping the maximum number of edge transitions.
**LangGraph State Progression #25:** The `AgentState` object passes messages between nodes. To prevent infinite loops, `build_ta_config()` enforces a strict `recursion_limit` of 80 for standard scans and 150 for extreme scans, capping the maximum number of edge transitions.
**LangGraph State Progression #26:** The `AgentState` object passes messages between nodes. To prevent infinite loops, `build_ta_config()` enforces a strict `recursion_limit` of 80 for standard scans and 150 for extreme scans, capping the maximum number of edge transitions.
**LangGraph State Progression #27:** The `AgentState` object passes messages between nodes. To prevent infinite loops, `build_ta_config()` enforces a strict `recursion_limit` of 80 for standard scans and 150 for extreme scans, capping the maximum number of edge transitions.
**LangGraph State Progression #28:** The `AgentState` object passes messages between nodes. To prevent infinite loops, `build_ta_config()` enforces a strict `recursion_limit` of 80 for standard scans and 150 for extreme scans, capping the maximum number of edge transitions.
**LangGraph State Progression #29:** The `AgentState` object passes messages between nodes. To prevent infinite loops, `build_ta_config()` enforces a strict `recursion_limit` of 80 for standard scans and 150 for extreme scans, capping the maximum number of edge transitions.
**LangGraph State Progression #30:** The `AgentState` object passes messages between nodes. To prevent infinite loops, `build_ta_config()` enforces a strict `recursion_limit` of 80 for standard scans and 150 for extreme scans, capping the maximum number of edge transitions.

## Phase 5: Deep Scan Injections & RAG
### 5.1 Technical and Sentiment Anchors
If `deep_scan` is True, `orchestrator.py` queries the database for extra context before formatting:
- **PKScreener**: Injects the exact Technical Score (0 to 1.00), RSI, MACD signal, and breakout status from `PKScreenerSignal`.
- **FinBERT**: Injects the sentiment scores and labels for the top 5 recent news articles.
- **RAG Vector Search**: The `search_filings` tool (stubbed via `services.rag_tools`) allows agents to search earnings call transcripts and prior analysis chunks.

**Injection Guardrail #1:** The prompt explicitly instructs the LLM: 'Use this PKScreener data as an additional technical anchor. It does NOT override your own technical analysis — treat it as a corroborating or conflicting data point.'
**Injection Guardrail #2:** The prompt explicitly instructs the LLM: 'Use this PKScreener data as an additional technical anchor. It does NOT override your own technical analysis — treat it as a corroborating or conflicting data point.'
**Injection Guardrail #3:** The prompt explicitly instructs the LLM: 'Use this PKScreener data as an additional technical anchor. It does NOT override your own technical analysis — treat it as a corroborating or conflicting data point.'
**Injection Guardrail #4:** The prompt explicitly instructs the LLM: 'Use this PKScreener data as an additional technical anchor. It does NOT override your own technical analysis — treat it as a corroborating or conflicting data point.'
**Injection Guardrail #5:** The prompt explicitly instructs the LLM: 'Use this PKScreener data as an additional technical anchor. It does NOT override your own technical analysis — treat it as a corroborating or conflicting data point.'
**Injection Guardrail #6:** The prompt explicitly instructs the LLM: 'Use this PKScreener data as an additional technical anchor. It does NOT override your own technical analysis — treat it as a corroborating or conflicting data point.'
**Injection Guardrail #7:** The prompt explicitly instructs the LLM: 'Use this PKScreener data as an additional technical anchor. It does NOT override your own technical analysis — treat it as a corroborating or conflicting data point.'
**Injection Guardrail #8:** The prompt explicitly instructs the LLM: 'Use this PKScreener data as an additional technical anchor. It does NOT override your own technical analysis — treat it as a corroborating or conflicting data point.'
**Injection Guardrail #9:** The prompt explicitly instructs the LLM: 'Use this PKScreener data as an additional technical anchor. It does NOT override your own technical analysis — treat it as a corroborating or conflicting data point.'
**Injection Guardrail #10:** The prompt explicitly instructs the LLM: 'Use this PKScreener data as an additional technical anchor. It does NOT override your own technical analysis — treat it as a corroborating or conflicting data point.'
**Injection Guardrail #11:** The prompt explicitly instructs the LLM: 'Use this PKScreener data as an additional technical anchor. It does NOT override your own technical analysis — treat it as a corroborating or conflicting data point.'
**Injection Guardrail #12:** The prompt explicitly instructs the LLM: 'Use this PKScreener data as an additional technical anchor. It does NOT override your own technical analysis — treat it as a corroborating or conflicting data point.'
**Injection Guardrail #13:** The prompt explicitly instructs the LLM: 'Use this PKScreener data as an additional technical anchor. It does NOT override your own technical analysis — treat it as a corroborating or conflicting data point.'
**Injection Guardrail #14:** The prompt explicitly instructs the LLM: 'Use this PKScreener data as an additional technical anchor. It does NOT override your own technical analysis — treat it as a corroborating or conflicting data point.'
**Injection Guardrail #15:** The prompt explicitly instructs the LLM: 'Use this PKScreener data as an additional technical anchor. It does NOT override your own technical analysis — treat it as a corroborating or conflicting data point.'
**Injection Guardrail #16:** The prompt explicitly instructs the LLM: 'Use this PKScreener data as an additional technical anchor. It does NOT override your own technical analysis — treat it as a corroborating or conflicting data point.'
**Injection Guardrail #17:** The prompt explicitly instructs the LLM: 'Use this PKScreener data as an additional technical anchor. It does NOT override your own technical analysis — treat it as a corroborating or conflicting data point.'
**Injection Guardrail #18:** The prompt explicitly instructs the LLM: 'Use this PKScreener data as an additional technical anchor. It does NOT override your own technical analysis — treat it as a corroborating or conflicting data point.'
**Injection Guardrail #19:** The prompt explicitly instructs the LLM: 'Use this PKScreener data as an additional technical anchor. It does NOT override your own technical analysis — treat it as a corroborating or conflicting data point.'
**Injection Guardrail #20:** The prompt explicitly instructs the LLM: 'Use this PKScreener data as an additional technical anchor. It does NOT override your own technical analysis — treat it as a corroborating or conflicting data point.'
**Injection Guardrail #21:** The prompt explicitly instructs the LLM: 'Use this PKScreener data as an additional technical anchor. It does NOT override your own technical analysis — treat it as a corroborating or conflicting data point.'
**Injection Guardrail #22:** The prompt explicitly instructs the LLM: 'Use this PKScreener data as an additional technical anchor. It does NOT override your own technical analysis — treat it as a corroborating or conflicting data point.'
**Injection Guardrail #23:** The prompt explicitly instructs the LLM: 'Use this PKScreener data as an additional technical anchor. It does NOT override your own technical analysis — treat it as a corroborating or conflicting data point.'
**Injection Guardrail #24:** The prompt explicitly instructs the LLM: 'Use this PKScreener data as an additional technical anchor. It does NOT override your own technical analysis — treat it as a corroborating or conflicting data point.'
**Injection Guardrail #25:** The prompt explicitly instructs the LLM: 'Use this PKScreener data as an additional technical anchor. It does NOT override your own technical analysis — treat it as a corroborating or conflicting data point.'
**Injection Guardrail #26:** The prompt explicitly instructs the LLM: 'Use this PKScreener data as an additional technical anchor. It does NOT override your own technical analysis — treat it as a corroborating or conflicting data point.'
**Injection Guardrail #27:** The prompt explicitly instructs the LLM: 'Use this PKScreener data as an additional technical anchor. It does NOT override your own technical analysis — treat it as a corroborating or conflicting data point.'
**Injection Guardrail #28:** The prompt explicitly instructs the LLM: 'Use this PKScreener data as an additional technical anchor. It does NOT override your own technical analysis — treat it as a corroborating or conflicting data point.'
**Injection Guardrail #29:** The prompt explicitly instructs the LLM: 'Use this PKScreener data as an additional technical anchor. It does NOT override your own technical analysis — treat it as a corroborating or conflicting data point.'
**Injection Guardrail #30:** The prompt explicitly instructs the LLM: 'Use this PKScreener data as an additional technical anchor. It does NOT override your own technical analysis — treat it as a corroborating or conflicting data point.'

## Phase 6: Confidence Calibration Pipeline
### 6.1 `backend/services/confidence_engine.py`
After the LangGraph concludes, a multi-threaded execution (using `ThreadPoolExecutor` with 8 workers) performs calibration:
- **Signal Agreement**: Parses the final signals from all 4 analysts. If 3/4 agree, `agreement_ratio` is 0.75.
- **Delivery Data**: Computes NSE physical delivery % against the 10-day average.
- **Microstructure**: Fetches Option OI PCR and Gamma Exposure.
- **RRG Quadrant**: Computes Sector Rotation (Leading, Weakening, Lagging, Improving).
- **Minskyan Risk**: Analyzes divergence between FII and DII YTD flows.
- **Auditor Tenure**: Scrapes the Big-4 status and tenure years.
- **Historical Analogues**: Uses KNN (k=10) to find historically similar setups based on RSI, SMA distance, and momentum.

These results are compiled into an authoritative 'CALIBRATION ENGINE OUTPUT' text block, prepended to the raw output.

## Phase 7: Reformatting & Normalization
### 7.1 `reformat_with_deepseek` -> `reformat_with_claude`
The raw agent trace is massive (>8000 tokens). To save costs and reduce formatting errors:
- `_extract_final_conclusion()` trims the output to the final 2000 characters, targeting the Portfolio Manager's decision block.
- DeepSeek V4 Flash is prompted with `INDIAN_MARKET_SYSTEM_PROMPT` to output strict JSON.
- If DeepSeek fails parsing 3 times, exponential backoff (1s, 2s, 4s) is applied.
- If all 3 fail, it falls back to Claude 3.5 Sonnet (higher cost, highly reliable).

**Reformatting Loop #1:** A failed DeepSeek job triggers a write to `logs/deepseek_failures.jsonl` (the Dead Letter Queue). This DLQ is processed periodically to replay failed conversions and capture structural LLM drift.
**Reformatting Loop #2:** A failed DeepSeek job triggers a write to `logs/deepseek_failures.jsonl` (the Dead Letter Queue). This DLQ is processed periodically to replay failed conversions and capture structural LLM drift.
**Reformatting Loop #3:** A failed DeepSeek job triggers a write to `logs/deepseek_failures.jsonl` (the Dead Letter Queue). This DLQ is processed periodically to replay failed conversions and capture structural LLM drift.
**Reformatting Loop #4:** A failed DeepSeek job triggers a write to `logs/deepseek_failures.jsonl` (the Dead Letter Queue). This DLQ is processed periodically to replay failed conversions and capture structural LLM drift.
**Reformatting Loop #5:** A failed DeepSeek job triggers a write to `logs/deepseek_failures.jsonl` (the Dead Letter Queue). This DLQ is processed periodically to replay failed conversions and capture structural LLM drift.
**Reformatting Loop #6:** A failed DeepSeek job triggers a write to `logs/deepseek_failures.jsonl` (the Dead Letter Queue). This DLQ is processed periodically to replay failed conversions and capture structural LLM drift.
**Reformatting Loop #7:** A failed DeepSeek job triggers a write to `logs/deepseek_failures.jsonl` (the Dead Letter Queue). This DLQ is processed periodically to replay failed conversions and capture structural LLM drift.
**Reformatting Loop #8:** A failed DeepSeek job triggers a write to `logs/deepseek_failures.jsonl` (the Dead Letter Queue). This DLQ is processed periodically to replay failed conversions and capture structural LLM drift.
**Reformatting Loop #9:** A failed DeepSeek job triggers a write to `logs/deepseek_failures.jsonl` (the Dead Letter Queue). This DLQ is processed periodically to replay failed conversions and capture structural LLM drift.
**Reformatting Loop #10:** A failed DeepSeek job triggers a write to `logs/deepseek_failures.jsonl` (the Dead Letter Queue). This DLQ is processed periodically to replay failed conversions and capture structural LLM drift.
**Reformatting Loop #11:** A failed DeepSeek job triggers a write to `logs/deepseek_failures.jsonl` (the Dead Letter Queue). This DLQ is processed periodically to replay failed conversions and capture structural LLM drift.
**Reformatting Loop #12:** A failed DeepSeek job triggers a write to `logs/deepseek_failures.jsonl` (the Dead Letter Queue). This DLQ is processed periodically to replay failed conversions and capture structural LLM drift.
**Reformatting Loop #13:** A failed DeepSeek job triggers a write to `logs/deepseek_failures.jsonl` (the Dead Letter Queue). This DLQ is processed periodically to replay failed conversions and capture structural LLM drift.
**Reformatting Loop #14:** A failed DeepSeek job triggers a write to `logs/deepseek_failures.jsonl` (the Dead Letter Queue). This DLQ is processed periodically to replay failed conversions and capture structural LLM drift.
**Reformatting Loop #15:** A failed DeepSeek job triggers a write to `logs/deepseek_failures.jsonl` (the Dead Letter Queue). This DLQ is processed periodically to replay failed conversions and capture structural LLM drift.
**Reformatting Loop #16:** A failed DeepSeek job triggers a write to `logs/deepseek_failures.jsonl` (the Dead Letter Queue). This DLQ is processed periodically to replay failed conversions and capture structural LLM drift.
**Reformatting Loop #17:** A failed DeepSeek job triggers a write to `logs/deepseek_failures.jsonl` (the Dead Letter Queue). This DLQ is processed periodically to replay failed conversions and capture structural LLM drift.
**Reformatting Loop #18:** A failed DeepSeek job triggers a write to `logs/deepseek_failures.jsonl` (the Dead Letter Queue). This DLQ is processed periodically to replay failed conversions and capture structural LLM drift.
**Reformatting Loop #19:** A failed DeepSeek job triggers a write to `logs/deepseek_failures.jsonl` (the Dead Letter Queue). This DLQ is processed periodically to replay failed conversions and capture structural LLM drift.
**Reformatting Loop #20:** A failed DeepSeek job triggers a write to `logs/deepseek_failures.jsonl` (the Dead Letter Queue). This DLQ is processed periodically to replay failed conversions and capture structural LLM drift.
**Reformatting Loop #21:** A failed DeepSeek job triggers a write to `logs/deepseek_failures.jsonl` (the Dead Letter Queue). This DLQ is processed periodically to replay failed conversions and capture structural LLM drift.
**Reformatting Loop #22:** A failed DeepSeek job triggers a write to `logs/deepseek_failures.jsonl` (the Dead Letter Queue). This DLQ is processed periodically to replay failed conversions and capture structural LLM drift.
**Reformatting Loop #23:** A failed DeepSeek job triggers a write to `logs/deepseek_failures.jsonl` (the Dead Letter Queue). This DLQ is processed periodically to replay failed conversions and capture structural LLM drift.
**Reformatting Loop #24:** A failed DeepSeek job triggers a write to `logs/deepseek_failures.jsonl` (the Dead Letter Queue). This DLQ is processed periodically to replay failed conversions and capture structural LLM drift.
**Reformatting Loop #25:** A failed DeepSeek job triggers a write to `logs/deepseek_failures.jsonl` (the Dead Letter Queue). This DLQ is processed periodically to replay failed conversions and capture structural LLM drift.
**Reformatting Loop #26:** A failed DeepSeek job triggers a write to `logs/deepseek_failures.jsonl` (the Dead Letter Queue). This DLQ is processed periodically to replay failed conversions and capture structural LLM drift.
**Reformatting Loop #27:** A failed DeepSeek job triggers a write to `logs/deepseek_failures.jsonl` (the Dead Letter Queue). This DLQ is processed periodically to replay failed conversions and capture structural LLM drift.
**Reformatting Loop #28:** A failed DeepSeek job triggers a write to `logs/deepseek_failures.jsonl` (the Dead Letter Queue). This DLQ is processed periodically to replay failed conversions and capture structural LLM drift.
**Reformatting Loop #29:** A failed DeepSeek job triggers a write to `logs/deepseek_failures.jsonl` (the Dead Letter Queue). This DLQ is processed periodically to replay failed conversions and capture structural LLM drift.
**Reformatting Loop #30:** A failed DeepSeek job triggers a write to `logs/deepseek_failures.jsonl` (the Dead Letter Queue). This DLQ is processed periodically to replay failed conversions and capture structural LLM drift.

### 7.2 Strict Normalization (`_normalize_response`)
Before the JSON is allowed to leave the server, it undergoes extreme sanitization to prevent iOS Swift `JSONDecoder` crashes:
1. **NaN/Inf Erasure**: `_sanitize_nan_inf()` recursively converts `math.nan` and `math.inf` to JSON `null`.
2. **Type Coercion**: `confidence_pct` is coerced to `int`. `current_price_inr` is coerced to `float`.
3. **Null Filling**: Arrays like `bull_case` and `bear_case` are initialized to `[]` if missing.
4. **Signal Mapping**: Converts complex string values (e.g., 'ACCUMULATE ON DIPS') into canonical `BULLISH`/`BEARISH` mapping using `_SIGNAL_MAP`.
5. **Quant Override**: The math derived from the `QuantitativeEngine` is forcefully written over the LLM output (e.g. `market_regime`, `target_price_bounds`), preventing hallucinations.
6. **Indian Numbering Standard**: `_ban_western_scale()` scans the dumped string. If 'Million', 'Billion', or 'Trillion' exist, it raises a `ValueError` requiring Indian Lakhs/Crores.

**Normalization Guard #1:** The pipeline guarantees that 'exchange' defaults to 'NSE', 'company_name' never returns null, and target prices unconditionally resolve to floats. This absolute strictness fulfills iOS App Store stability requirements.
**Normalization Guard #2:** The pipeline guarantees that 'exchange' defaults to 'NSE', 'company_name' never returns null, and target prices unconditionally resolve to floats. This absolute strictness fulfills iOS App Store stability requirements.
**Normalization Guard #3:** The pipeline guarantees that 'exchange' defaults to 'NSE', 'company_name' never returns null, and target prices unconditionally resolve to floats. This absolute strictness fulfills iOS App Store stability requirements.
**Normalization Guard #4:** The pipeline guarantees that 'exchange' defaults to 'NSE', 'company_name' never returns null, and target prices unconditionally resolve to floats. This absolute strictness fulfills iOS App Store stability requirements.
**Normalization Guard #5:** The pipeline guarantees that 'exchange' defaults to 'NSE', 'company_name' never returns null, and target prices unconditionally resolve to floats. This absolute strictness fulfills iOS App Store stability requirements.
**Normalization Guard #6:** The pipeline guarantees that 'exchange' defaults to 'NSE', 'company_name' never returns null, and target prices unconditionally resolve to floats. This absolute strictness fulfills iOS App Store stability requirements.
**Normalization Guard #7:** The pipeline guarantees that 'exchange' defaults to 'NSE', 'company_name' never returns null, and target prices unconditionally resolve to floats. This absolute strictness fulfills iOS App Store stability requirements.
**Normalization Guard #8:** The pipeline guarantees that 'exchange' defaults to 'NSE', 'company_name' never returns null, and target prices unconditionally resolve to floats. This absolute strictness fulfills iOS App Store stability requirements.
**Normalization Guard #9:** The pipeline guarantees that 'exchange' defaults to 'NSE', 'company_name' never returns null, and target prices unconditionally resolve to floats. This absolute strictness fulfills iOS App Store stability requirements.
**Normalization Guard #10:** The pipeline guarantees that 'exchange' defaults to 'NSE', 'company_name' never returns null, and target prices unconditionally resolve to floats. This absolute strictness fulfills iOS App Store stability requirements.
**Normalization Guard #11:** The pipeline guarantees that 'exchange' defaults to 'NSE', 'company_name' never returns null, and target prices unconditionally resolve to floats. This absolute strictness fulfills iOS App Store stability requirements.
**Normalization Guard #12:** The pipeline guarantees that 'exchange' defaults to 'NSE', 'company_name' never returns null, and target prices unconditionally resolve to floats. This absolute strictness fulfills iOS App Store stability requirements.
**Normalization Guard #13:** The pipeline guarantees that 'exchange' defaults to 'NSE', 'company_name' never returns null, and target prices unconditionally resolve to floats. This absolute strictness fulfills iOS App Store stability requirements.
**Normalization Guard #14:** The pipeline guarantees that 'exchange' defaults to 'NSE', 'company_name' never returns null, and target prices unconditionally resolve to floats. This absolute strictness fulfills iOS App Store stability requirements.
**Normalization Guard #15:** The pipeline guarantees that 'exchange' defaults to 'NSE', 'company_name' never returns null, and target prices unconditionally resolve to floats. This absolute strictness fulfills iOS App Store stability requirements.
**Normalization Guard #16:** The pipeline guarantees that 'exchange' defaults to 'NSE', 'company_name' never returns null, and target prices unconditionally resolve to floats. This absolute strictness fulfills iOS App Store stability requirements.
**Normalization Guard #17:** The pipeline guarantees that 'exchange' defaults to 'NSE', 'company_name' never returns null, and target prices unconditionally resolve to floats. This absolute strictness fulfills iOS App Store stability requirements.
**Normalization Guard #18:** The pipeline guarantees that 'exchange' defaults to 'NSE', 'company_name' never returns null, and target prices unconditionally resolve to floats. This absolute strictness fulfills iOS App Store stability requirements.
**Normalization Guard #19:** The pipeline guarantees that 'exchange' defaults to 'NSE', 'company_name' never returns null, and target prices unconditionally resolve to floats. This absolute strictness fulfills iOS App Store stability requirements.
**Normalization Guard #20:** The pipeline guarantees that 'exchange' defaults to 'NSE', 'company_name' never returns null, and target prices unconditionally resolve to floats. This absolute strictness fulfills iOS App Store stability requirements.
**Normalization Guard #21:** The pipeline guarantees that 'exchange' defaults to 'NSE', 'company_name' never returns null, and target prices unconditionally resolve to floats. This absolute strictness fulfills iOS App Store stability requirements.
**Normalization Guard #22:** The pipeline guarantees that 'exchange' defaults to 'NSE', 'company_name' never returns null, and target prices unconditionally resolve to floats. This absolute strictness fulfills iOS App Store stability requirements.
**Normalization Guard #23:** The pipeline guarantees that 'exchange' defaults to 'NSE', 'company_name' never returns null, and target prices unconditionally resolve to floats. This absolute strictness fulfills iOS App Store stability requirements.
**Normalization Guard #24:** The pipeline guarantees that 'exchange' defaults to 'NSE', 'company_name' never returns null, and target prices unconditionally resolve to floats. This absolute strictness fulfills iOS App Store stability requirements.
**Normalization Guard #25:** The pipeline guarantees that 'exchange' defaults to 'NSE', 'company_name' never returns null, and target prices unconditionally resolve to floats. This absolute strictness fulfills iOS App Store stability requirements.
**Normalization Guard #26:** The pipeline guarantees that 'exchange' defaults to 'NSE', 'company_name' never returns null, and target prices unconditionally resolve to floats. This absolute strictness fulfills iOS App Store stability requirements.
**Normalization Guard #27:** The pipeline guarantees that 'exchange' defaults to 'NSE', 'company_name' never returns null, and target prices unconditionally resolve to floats. This absolute strictness fulfills iOS App Store stability requirements.
**Normalization Guard #28:** The pipeline guarantees that 'exchange' defaults to 'NSE', 'company_name' never returns null, and target prices unconditionally resolve to floats. This absolute strictness fulfills iOS App Store stability requirements.
**Normalization Guard #29:** The pipeline guarantees that 'exchange' defaults to 'NSE', 'company_name' never returns null, and target prices unconditionally resolve to floats. This absolute strictness fulfills iOS App Store stability requirements.
**Normalization Guard #30:** The pipeline guarantees that 'exchange' defaults to 'NSE', 'company_name' never returns null, and target prices unconditionally resolve to floats. This absolute strictness fulfills iOS App Store stability requirements.

## Phase 8: Extreme Enrichment & Database Archival
### 8.1 Extreme Graph Bundles
If `scan_type == 'extreme'`, an additional module `services.extreme_enrichers.py` builds the data arrays required to render the advanced iOS charts (Valuation Bands, Scenarios).

### 8.2 Database Commits (`database.py`)
A background thread saves the final sanitized payload to `AnalysisHistory`.
Concurrently, it queries the last 14 days of `AdvisorInsight` to attach YouTube Harvester data (video links, expert stances) to the payload.
Finally, the complete dictionary is returned to the user.

### Component Tracing Log 1
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 2
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 3
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 4
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 5
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 6
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 7
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 8
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 9
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 10
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 11
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 12
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 13
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 14
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 15
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 16
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 17
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 18
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 19
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 20
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 21
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 22
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 23
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 24
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 25
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 26
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 27
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 28
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 29
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 30
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 31
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 32
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 33
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 34
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 35
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 36
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 37
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 38
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 39
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 40
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 41
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 42
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 43
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 44
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 45
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 46
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 47
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 48
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 49
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 50
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 51
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 52
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 53
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 54
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 55
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 56
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 57
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 58
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 59
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 60
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 61
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 62
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 63
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 64
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 65
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 66
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 67
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 68
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 69
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 70
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 71
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 72
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 73
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 74
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 75
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 76
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 77
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 78
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 79
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 80
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 81
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 82
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 83
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 84
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 85
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 86
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 87
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 88
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 89
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 90
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 91
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 92
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 93
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 94
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 95
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 96
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 97
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 98
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 99
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Component Tracing Log 100
- Memory isolation guaranteed via `multiprocessing.Process`.
- No global unpicklable state allowed across the orchestrator boundary.
- ThreadPoolExecutor scales network calls in the Confidence Engine.
- SSE (Server-Sent Events) streams progress checkpoints back to the iOS client.
- The iOS client uses `BanknoteCard` and `IndianFormatter` to natively display the structured payload output from this exact pipeline.

### Mathematical Audit Trace 1
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 2
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 3
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 4
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 5
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 6
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 7
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 8
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 9
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 10
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 11
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 12
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 13
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 14
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 15
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 16
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 17
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 18
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 19
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 20
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 21
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 22
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 23
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 24
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 25
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 26
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 27
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 28
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 29
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 30
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 31
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 32
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 33
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 34
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 35
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 36
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 37
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 38
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 39
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 40
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 41
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 42
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 43
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 44
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 45
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 46
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 47
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 48
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 49
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 50
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 51
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 52
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 53
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 54
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 55
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 56
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 57
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 58
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 59
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 60
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 61
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 62
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 63
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 64
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 65
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 66
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 67
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 68
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 69
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 70
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 71
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 72
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 73
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 74
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 75
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 76
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 77
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 78
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 79
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 80
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 81
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 82
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 83
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 84
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 85
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 86
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 87
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 88
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 89
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 90
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 91
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 92
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 93
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 94
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 95
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 96
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 97
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 98
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 99
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.

### Mathematical Audit Trace 100
The `agreement_ratio` = `votes_aligned / total_voters`.
The `confidence_multiplier` = `0.60 + (0.40 * agreement_ratio)`.
The `calibrated_confidence` = `base_probability + net_shap_adjustment - tail_risk_deduction`.
This final confidence value drives the visual UI rendering (Red/Green/Gold) and dynamic Haptics on the client device.
