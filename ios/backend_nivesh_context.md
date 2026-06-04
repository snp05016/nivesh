# Nivesh (निवेश) — Backend Context

> Paste this into Claude to get backend context before brainstorming next steps.
> Last updated: June 3, 2026. Reflects current implemented state.

---

## What Is This

**Nivesh Backend** is a FastAPI-based server orchestrating a multi-agent AI pipeline for Indian stock market analysis. It connects to yfinance for data and Anthropic's Claude models for analysis, implementing advanced prompt caching.

---

## The Intelligence — Multi-Layer AI Pipeline

### 1. 8-Step Core Pipeline
1.  **Expert Research (Parallel)**:
    *   **Market Analyst**: Interprets `factor_engine` pre-computations.
    *   **News Analyst**: Scans for **Red Flags** (Auditor resignations, CFO exits, SEBI investigations).
    *   **Fundamentals Analyst**: P/L, Balance Sheet, and **Promoter stress** (Pledging > 30%).
    *   **Social Analyst**: Measures retail euphoria (contrarian signal).
2.  **The Debate**: `Bull Researcher` vs. `Bear Researcher` (Dialectical challenge pattern).
3.  **Synthesis**: `Research Manager` summary + `Trader` transaction proposal.
4.  **Risk Review (Iterative)**: 3 Risk Analysts (`Aggressive` -> `Conservative` -> `Neutral`) debate the proposal in a circular loop managed by `ConditionalLogic`.
5.  **Final Verdict**: `Portfolio Manager` raw decision.
6.  **Reformatting (Sonnet 3.5)**: Applies **Indian Market Weighting** (Management, Institutions, Sentiment, Macro, Policy, Turnaround).

### 2. Advisor Intelligence Pipeline (Nightly)
- **Harvester**: Extracts transcripts via **YouTube API** or **Whisper large-v3**.
- **Ticker Matcher**: Uses `rapidfuzz` to identify tickers in Hinglish commentary.
- **Haiku Extractor**: Structures stances and catalysts with numeric anchors.
- **Aggregator**: `/api/v1/portfolio/advisor-consensus` provides trending signals.

---

## Performance & Optimization

- **Prefix-Aligned Context Stratification**: Anthropic Prompt Caching on analysts and reformatter.
- **Smart Cache**: Haiku-based news check to skip redundant analyses.
- **Process Isolation**: AI analyses run in `multiprocessing.Process`.
- **God Nodes**: `get_session()` for state, `TradingAgentsGraph` for orchestration.

---

## Database Schema (SQLite)

- `users`, `portfolio`, `analysis_history`, `advisor_insights`, `signal_events`, `trade_journal`.

---

## Reliability Features

- **yfinance Retry**: 3-attempt retry with backoff.
- **NSE Session Bootstrap**: Direct NSE API access for surveillance lists.
- **History Fallbacks**: Indices/Sectors use history if `info` fails.
- **BSE Fallback**: Automatic failover to BSE (`.BO`).
