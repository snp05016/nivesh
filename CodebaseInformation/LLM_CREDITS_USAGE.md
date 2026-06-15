# Nivesh — LLM API Credits Usage Map

> **Exhaustive audit of every file consuming LLM API credits and the iOS features that trigger them.**
> Generated: June 2026
> Cost rates: DeepSeek V4 Flash / Claude Haiku / Claude Sonnet / Gemini 3.1 Pro

---

## 1. Provider & Model Overview

| Provider | Model(s) | Cost & Tier | Used In |
|----------|----------|-------------|---------|
| **DeepSeek** | `deepseek-chat` (V4 Flash) | **Tier 1** | 8x LangGraph agents, smart cache gate, daily action, red flags, macro impact, trade journal stats, advisor stance extraction |
| **Anthropic** | `claude-haiku-4-5-20251001` | **Tier 2** | Research Manager, Portfolio Manager (LangGraph), Morning Summary |
| **Anthropic / Google** | `claude-3-5-sonnet-latest` / `gemini-3.1-pro` | **Tier 3** | Fallback reformatter, Batch analysis, PDF export narrative, Extreme Analysis |

**Local AI (zero credit cost):**
- `services/sentiment_engine.py` — FinBERT (HuggingFace pipeline, CPU)
- `services/transcript_engine.py` — faster-whisper large-v3 (CPU, int8 quantized)

---

## 2. Backend: All Credit-Consuming Files

### 2.1 Router Endpoints

#### `routers/analysis.py`

| Endpoint | Model | Cost | What it does |
|----------|-------|------|-------------|
| `_run_analysis_worker()` | LangGraph pipeline | **HIGH** | Subprocess worker for `POST /analyze`. Calls `services.orchestrator.analyze()`. |
| `POST /analyze` | DeepSeek + Haiku + Sonnet/Gemini | **LOW/HIGH** | Instant CACHE HIT returns immediately. Otherwise spawns `multiprocessing.Process`. |
| `POST /analyze/batch` | Claude Sonnet / Gemini | **HIGH** | Message Batch. Each ticker gets full system prompt with ephemeral caching. |
| `GET /daily-action/{id}` | DeepSeek V4 Flash | **LOW** | 1-sentence "most important action today". |

#### `routers/portfolio.py`

| Endpoint | Model | Cost | What it does |
|----------|-------|------|-------------|
| `GET /morning-summary` | Claude Haiku 4.5 | **MEDIUM** | 4-6 bullet morning brief for user's portfolio holdings. |
| `GET /macro-impact` | DeepSeek V4 Flash | **LOW** | Per-holding macro impact statements. |
| `GET /portfolio/export` | Sonnet / Gemini | **HIGH** | Full one-page portfolio review markdown → PDF. |

#### `routers/copilot.py`
| Endpoint | Model | Cost | What it does |
|----------|-------|------|-------------|
| `POST /copilot/query` | Gemini 3.1 Pro / Sonnet | **HIGH** | Global AI assistant responding to user financial queries. |

### 2.2 Services

#### `services/orchestrator.py`

| Function | Model | Cost | What it does |
|----------|-------|------|-------------|
| `run_trading_agents()` | DeepSeek + Haiku | **HIGH** | Instantiates `OptimizedTradingAgentsGraph`. Calls `ta.propagate()` → 12 LLM invocations. |
| `reformat_with_deepseek()` | DeepSeek (primary), Fallback (Tier 3) | **LOW** | Sole active reformatter. Uses DeepSeek for >95% of runs. |
| Smart Cache Gate | DeepSeek V4 Flash | **VERY LOW** | Checks news headlines for "major fundamental shift" to reuse cached analysis. |
| `analyze()` | All of the above | **HIGH** | Main entry. Smart cache → trading agents → reformat → normalize. |

#### `services/advisor_harvester.py`

| Function | Model | Cost | What it does |
|----------|-------|------|-------------|
| `_extract_stance_with_haiku()` | DeepSeek V4 Flash | LOW | Extracts BULLISH/NEUTRAL/BEARISH stance from transcript snippet. |

#### `services/nl_screener.py`

| Function | Model | Cost | What it does |
|----------|-------|------|-------------|
| `translate_nl_to_sql()` | DeepSeek V4 Flash | **LOW** | Translates natural language to SQL queries for screener. |
