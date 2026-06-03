# Nivesh (निवेश) — Backend Context

> Paste this into Claude to get backend context before brainstorming next steps.
> Last updated: June 3, 2026. Reflects current shipped state.

---

## What Is This

**Nivesh Backend** is a FastAPI-based server orchestrating a multi-agent AI pipeline for Indian stock market analysis. It connects to yfinance for data and Anthropic's Claude models for analysis, implementing advanced prompt caching and a nightly "Advisor Harvest" engine.

---

## The Intelligence — Multi-Layer AI Pipeline

### 1. 8-Step Core Pipeline
1.  **Expert Research (Parallel)**: Market Analyst (Technical), News Analyst (Red Flags), Fundamentals Analyst (Promoter stress/Pledging).
2.  **The Debate**: Bull Researcher vs. Bear Researcher back-and-forth.
3.  **Synthesis**: Research Manager summary + Trader transaction proposal (Buy/Hold/Sell).
4.  **Risk Review**: 3 Risk Analysts (Aggressive, Neutral, Conservative) debate the proposal.
5.  **Final Verdict**: Portfolio Manager raw decision.
6.  **Reformatting (Sonnet 3.5)**: Applies **Indian Market Weighting** (Management, Institutions, Sentiment, Macro, Policy, Turnaround).

### 2. Advisor Intelligence Pipeline (Nightly)
- **Harvester**: Extracts transcripts from leading Indian financial YouTube channels (SOIC, Basant Maheshwari, Valuepickr, etc.).
- **Ticker Matcher**: Uses `rapidfuzz` to identify tickers in Hinglish commentary (e.g., "HDFC wala bank").
- **Haiku Extractor**: Structures stances and catalysts with numeric anchors.
- **Aggregator**: `/api/v1/portfolio/advisor-consensus` provides trending signals across the "Expert Matrix".

---

## Performance & Optimization

- **Prefix-Aligned Context Stratification**: Anthropic Prompt Caching on analysts (Haiku) and reformatter (Sonnet).
- **Smart Cache**: Haiku-based news check to skip redundant $0.15+ analyses if no major fundamental shifts occurred since the last report.
- **Quick-Info TTL Cache**: 5-minute in-memory cache for `/quick-info`.
- **Message Batches**: Support for `/analyze/batch` via Anthropic's Batch API for nightly processing.

---

## Database Schema (SQLite)

- `users`: Auth with session management.
- `portfolio`: Holdings/Watchlist with `purchase_date`, `notes`, and `target_price`.
- `analysis_history`: Stores structured JSON reports. (Sonnet pulls last 15 for context).
- `advisor_insights`: Stance/Catalyst data harvested from expert transcripts.
- `signal_events`: Tracks signal flips (e.g., BULLISH → NEUTRAL).
- `price_targets`: Tracks price alerts (Above/Below) and triggered status.
- `trade_journal`: Logs psychology, entry reasons, and outcomes.

---

## Key Endpoints (`main.py`)

| Endpoint | Method | Description |
|---|---|---|
| `/analyze` | POST | 8-step agentic analysis with flip detection and smart caching. |
| `/analyze/batch`| POST | Nightly batch analysis for portfolios. |
| `/portfolio/advisor-consensus`| GET | Trending tickers and sector signals across experts. |
| `/portfolio/risk-analysis` | GET | Portfolio Beta, risk score (1-10), and correlation warnings. |
| `/morning-summary` | GET | Prioritised action list: Alerts > Flips > Earnings. |
| `/macro-strip` | GET | Live Brent Crude, India VIX, USD/INR, and RBI rates. |
| `/earnings-calendar`| GET | Upcoming earnings for held stocks. |
| `/quick-info` | GET | Enriched news with images and ASM/GSM surveillance status. |
| `/market-indices` | GET | Live Nifty/Sensex with history-based fallback for reliability. |
| `/portfolio/export/excel` | GET | Returns .xlsx binary of portfolio and history. |
| `/portfolio/export/pdf` | GET | Returns PDF report of holdings. |

---

## Reliability Features

- **yfinance Retry**: 3-attempt retry with backoff.
- **NSE Session Bootstrap**: Direct NSE API access for ASM/GSM surveillance lists.
- **History Fallbacks**: Indices/Sectors use history data if `info` fails.
- **BSE Fallback**: Automatic failover to BSE (`.BO`) for missing financial data.
