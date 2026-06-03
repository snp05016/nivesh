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
    *   **Market Analyst**: Price trends, moving averages (50/200), RSI, Volume, MACD.
    *   **News Analyst**: Scans for **Red Flags** (Auditor resignations, CFO/MD exits, SEBI investigations).
    *   **Fundamentals Analyst**: P/L, Balance Sheet, Cash Flow, and **Promoter stress** (Pledging > 30%).
2.  **The Debate**: `Bull Researcher` vs. `Bear Researcher` (1 round of dialectical challenge).
3.  **Synthesis**: `Research Manager` summary + `Trader` transaction proposal (Buy/Hold/Sell).
4.  **Risk Review (Iterative)**: 3 Risk Analysts (`Aggressive` -> `Conservative` -> `Neutral`) debate the proposal in a circular loop.
5.  **Final Verdict**: `Portfolio Manager` raw decision.
6.  **Reformatting (Sonnet 3.5)**: Applies **Indian Market Weighting** (Management, Institutions, Sentiment, Macro, Policy, Turnaround).

### 2. Advisor Intelligence Pipeline (Nightly)
- **Harvester**: Extracts transcripts from YouTube (SOIC, Basant Maheshwari, Shankar Sharma, etc.) via **YouTube API** or **Whisper large-v3**.
- **Ticker Matcher**: Uses `rapidfuzz` (fuzz.token_set_ratio) to identify tickers in Hinglish commentary.
- **Haiku Extractor**: Structures stances and catalysts with numeric anchors.
- **Aggregator**: `/api/v1/portfolio/advisor-consensus` provides trending signals.

---

## Performance & Optimization

- **Prefix-Aligned Context Stratification**: Anthropic Prompt Caching on analysts (Haiku) and reformatter (Sonnet).
- **Smart Cache**: Haiku-based news check to skip redundant analyses.
- **Quick-Info TTL Cache**: 5-minute in-memory cache for `/quick-info`.
- **Process Isolation**: AI analyses run in `multiprocessing.Process`.

---

## Database Schema (SQLite)

- `users`: Includes SHA-256 hashed passwords.
- `portfolio`: Stores holdings/watchlist with `purchase_date`, `notes`, and `target_price`.
- `analysis_history`: Stores structured JSON reports. (Sonnet pulls last 15 for context).
- `signal_events`: Tracks signal flips (e.g., BULLISH → NEUTRAL).
- `price_targets`: Tracks price alerts.
- `trade_journal`: Logs mood, entry reason, and outcomes.
- `advisor_insights`: Stance data from YouTube experts.

---

## Reliability Features

- **yfinance Retry**: 3-attempt retry with backoff.
- **NSE Session Bootstrap**: Direct NSE API access for surveillance lists.
- **History Fallbacks**: Indices/Sectors use history if `info` fails.
- **BSE Fallback**: Automatic failover to BSE (`.BO`).
