# Nivesh LLM Credits Usage Map

> Last verified: 2026-06-15 from `backend/services/llm_utils.py`, routers, and service call sites. Costs are qualitative because actual usage depends on request size, cache hits, retries, and provider pricing.

## Canonical Model Constants

The source of truth is `backend/services/llm_utils.py`:

| Constant | Current model | Intended tier/use |
|---|---|---|
| `DEEPSEEK_MODEL` | `deepseek-chat` | Tier 1 bulk work, cheaper summaries, routing, extraction, natural language translation |
| `HAIKU_MODEL` | `claude-haiku-4-5-20251001` | Tier 2 synthesis and concise Anthropic responses |
| `SONNET_MODEL` | `claude-sonnet-4-6` | Tier 3 batch/reformat/export paths |

Do not use the retired `claude-3-5-sonnet-latest` alias in new code.

## Highest-Cost User Flows

| User action | Main endpoint | Likely model usage | Notes |
|---|---|---|---|
| Run stock analysis | `POST /analyze` | DeepSeek + Haiku + possible Sonnet reformat | Can be low cost on cache hit; high cost on fresh full analysis |
| Batch analysis | `POST /analyze/batch` | Sonnet via Anthropic batch API | High cost by ticker count and prompt size |
| Portfolio PDF export | `GET /portfolio/export/pdf/{user_id}` | Sonnet | High-cost narrative generation |
| Copilot chat | `POST /api/v1/copilot/chat` | DeepSeek for routing/normal replies; Haiku for some handling | Cost grows with conversation/context size |
| Morning summary | `GET /morning-summary/{user_id}` | Haiku | Medium cost, portfolio-size dependent |
| Portfolio red flags | `GET /portfolio/red-flags/{user_id}` | DeepSeek | Low to medium, depends on holdings |
| Macro impact | `GET /macro-impact/{user_id}` | DeepSeek | Low to medium, depends on holdings |
| Trade journal stats | `GET /trade-journal/{user_id}/stats` | DeepSeek in some paths | Low to medium |
| Natural language screener | `POST /api/v1/screener/natural-language` | DeepSeek | Low, one translation/classification style request |
| Daily action | `GET /daily-action/{user_id}` | DeepSeek | Low |
| Advisor stance extraction | harvester services | DeepSeek | Low per transcript/snippet |

## Main Credit-Consuming Files

| File | What consumes credits |
|---|---|
| `backend/services/orchestrator.py` | Main analysis orchestration, Smart Cache Gate, LangGraph model configuration, reformatting |
| `backend/services/llm_utils.py` | DeepSeek client and canonical model constants |
| `backend/routers/analysis.py` | Batch analysis and daily action endpoints |
| `backend/routers/portfolio.py` | Morning summary, red flags, macro impact, trade journal stats, PDF export |
| `backend/services/copilot_service.py` | Copilot intent routing, summarization, navigation/general replies, deep-analysis helper flow |
| `backend/routers/copilot.py` | Copilot API entry point |
| `backend/services/nl_screener.py` | Natural language to screener filters/SQL-like structure |
| `backend/services/advisor_harvester.py` | Advisor stance extraction |
| `backend/services/harvester_reformatter.py` | DeepSeek-based harvester content normalization |
| `backend/services/brainstorming.py` | DeepSeek brainstorming responses |

## Local or Non-LLM AI

| File | Tool/model | Credit impact |
|---|---|---|
| `backend/services/sentiment_engine.py` | FinBERT/HuggingFace pipeline | Local CPU/model load, no LLM API credit by default |
| `backend/services/math_engines/finbert_sentiment.py` | FinBERT/HuggingFace pipeline | Local CPU/model load, no LLM API credit by default |
| `backend/services/transcript_engine.py` | faster-whisper style transcript processing | Local compute unless configured otherwise |
| Quantitative engines | Python deterministic calculations | No LLM API credit |

## Cost Control Gates

- Cache/staleness logic lives around `services/staleness.py` and `services/orchestrator.py`.
- `deepseek_chat()` retries up to 3 times, so transient failures can multiply token spend.
- Copilot summarizes long history, but the summary itself is a DeepSeek call.
- Batch analysis and PDF export should be treated as explicit high-cost actions in UI/ops decisions.

## Quick Audit Commands

```bash
rg -n "HAIKU_MODEL|SONNET_MODEL|DEEPSEEK_MODEL|deepseek_chat\(|anthropic\.Anthropic|client\.messages\.create|OpenAI\(" backend/services backend/routers
rg -n "claude-3-5-sonnet-latest|gemini-3.1-pro|gemini" backend
```
