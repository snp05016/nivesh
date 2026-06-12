# Extreme Analysis (Deep Scan) Implementation Prompt

You are tasked with implementing the "Extreme Analysis" (Deep Scan) feature for the Nivesh platform. We have already finalized the architectural design and business logic. Follow the instructions below strictly.

## Core Objective
Upgrade the LangGraph pipeline to support a high-depth, high-cost "Extreme" scan that utilizes advanced reasoning models across all agent nodes, increases debate depth, expands data ingestion, and outputs a long-form markdown thesis without breaking the existing iOS JSON schema.

## 1. Backend API & Routing (`routers/analysis.py`)
- **Query Parameter:** Update the `POST /api/v1/analyze` endpoint to accept an optional query parameter `scan_type: str = Query("standard", pattern="^(standard|extreme)$")`.
- Pass this `scan_type` down to the `multiprocessing` worker and subsequently into `services/orchestrator.py`.

## 2. Model & Pipeline Configuration (`services/orchestrator.py` & `backend/config.py`)
When `scan_type == "extreme"`:
- **Full Pipeline Upgrade:** Override the `quick_think_llm` (which normally uses `deepseek-chat`) to use the **DeepSeek V4 Pro** model (e.g., `deepseek-reasoner` or equivalent pro configuration) for all 8 agents (Market, News, Fundamentals, Bull, Bear, Trader, Risk, Portfolio Manager). The API key is already configured.
- **Debate Depth:** Override the default LangGraph configuration to set `max_debate_rounds = 3` (up from 1) allowing the Bull and Bear agents to deeply interrogate each other.

## 3. Expanded Data Ingestion
Modify the data ingestion utilities (e.g., `helpers.py`, `services/news.py`, `services/fundamentals.py`) to adjust their payload when `scan_type == "extreme"`:
- **Financials:** Fetch 5 years of historical financial data (instead of the standard 1 year).
- **News:** Scrape up to 50 recent news articles (instead of 10).
- **Institutional & Macro:** Ensure FII/DII flow data, insider trading history, and sector competitor comparisons are included in the agent context.

## 4. Database Storage & Caching (`database.py` / `models/`)
- **Schema Update:** Update the `StockAnalysis` (or equivalent caching table) to include a `scan_type` column (String, default `"standard"`).
- **Cache Isolation:** Ensure that `get_analysis_for_date()` and cache saving logic checks the `scan_type`. An "extreme" scan should be stored and retrieved separately from a "standard" scan. Do NOT overwrite standard cache with extreme cache.

## 5. Output Formatting & Prompts (`backend/prompts.py`)
- **JSON Schema:** Do NOT modify or remove any existing fields in `INDIAN_MARKET_SYSTEM_PROMPT`. You must strictly maintain the existing schema.
- **New Field:** If `scan_type == "extreme"`, append a new required field to the JSON output specification: `"extreme_thesis_md"`.
- **Instruction:** Instruct the final Portfolio Manager / Reformatting Agent to populate `"extreme_thesis_md"` with a comprehensive, long-form (1000+ words) Markdown-formatted investment thesis incorporating the multi-round debate points, macro data, and deep risk analysis.

## Critical Guardrails (Reference `AGENTS.md`)
- **Controller-Service-Repository:** Keep business logic out of the routers. All heavy lifting belongs in `services/`. Database queries must strictly use the `get_session()` context manager.
- **Multiprocessing Integrity:** Remember that `orchestrator.py` is run inside a `multiprocessing.Process`. You cannot pass database sessions or unpicklable objects across the process boundary.
- **No Western Scales:** Ensure the new `"extreme_thesis_md"` field output passes through the `_ban_western_scale()` and `IndianFormatter` checks (Lakhs/Crores only; "Million/Billion" is forbidden).
