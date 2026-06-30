# Gemini Implementation Plan (Quant & Data Pipelines)

**Objective:** Build the complex mathematical logic, data scrapers, and document parsing layers of the Moneycontrol feature stack.
**Boundary Rules:** Gemini agents may ONLY modify files in `backend/services/math_engines/`, `backend/services/harvesters/`, `backend/services/parsers/`, and `backend/tests/`. They must NEVER touch `ios/` or `backend/routers/` to guarantee zero merge conflicts with the Claude team.

## Team Roster (4 Subagents)
1. **Quant/Math Agent:** Translates financial whitepapers and formulas into pure Python calculation engines.
2. **Data Ingestion Agent:** Builds web scrapers and external API pullers (NSE, AMFI, etc.).
3. **Document AI Agent:** Specializes in PDF text extraction, Regex, and LLM text summarization.
4. **Data Verification Agent:** Writes exhaustive mathematical and data-integrity unit tests.

---

## Phase 1: Stock Vitals & Fundamental Math Engines
### Quant/Math Agent
- [x] Build `altman_z_score.py` (Bankruptcy prediction model).
- [x] Build `dupont_analysis.py` (ROE breakdown).
- [x] Build `piotroski_score.py` (Financial strength scoring 0-9).
### Data Ingestion Agent
- [x] Build `bse_financials_scraper.py` to pull raw balance sheets required for the math engines.
### Document AI Agent
- [x] Build a pipeline to extract tabular financial data from quarterly earnings PDF reports.
### Data Verification Agent
- [x] Write unit tests passing historical mock data into the Altman/DuPont engines to verify formula accuracy.

## Phase 2: F&O Analytics & Derivatives Engine
### Quant/Math Agent
- [x] Build `black_scholes.py` for Options pricing.
- [x] Build `greeks_calculator.py` (Delta, Gamma, Theta, Vega).
- [x] Build `max_pain_calculator.py` and `implied_volatility_engine.py`.
### Data Ingestion Agent
- [x] Build `nse_option_chain_harvester.py` (Polling NSE endpoints for live OI and volume).
### Document AI Agent
- [x] Build summarization pipeline for daily FII/DII sectoral derivative activity reports.
### Data Verification Agent
- [x] Write boundary value tests for Black-Scholes (e.g., deep ITM vs deep OTM options).

## Phase 3: Portfolio Analytics & Wealth Math
### Quant/Math Agent
- [x] Build `xirr_calculator.py` for accurate portfolio return measurement.
- [x] Build `capital_gains_calculator.py` (FIFO matching for STCG/LTCG Indian taxation).
- [x] Build `portfolio_xray.py` (Asset allocation and MF overlap logic).
### Data Ingestion Agent
- [x] Build `amfi_nav_harvester.py` to daily pull and store Mutual Fund NAVs.
### Document AI Agent
- [x] Build `cams_cas_parser.py` to extract transactions from protected CAMS/Karvy PDF statements.
### Data Verification Agent
- [x] Write tests to ensure capital gains logic respects the grandfathering rules and current tax slabs.

## Phase 4: Super PRO AI & Editorial Automation
### Quant/Math Agent
- [x] Build `seasonality_analysis.py` (Historical monthly return probability).
### Data Ingestion Agent
- [x] Build webhook listeners for BSE/NSE real-time corporate announcements.
### Document AI Agent
- [x] Build `earnings_call_summarizer.py` (LLM prompt chains for Concall transcripts).
- [x] Build `whatsapp_alert_formatter.py` (Compressing complex financial data into readable AI alerts).
### Data Verification Agent
- [x] Write latency tests for the ingestion-to-alert pipeline (must be < 2 seconds).

---
*Note: Gemini exposes these Python modules as clean functions. The Claude team will import these functions into their FastAPI routers to serve them to the iOS App.*
