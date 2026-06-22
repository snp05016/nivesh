# Feature Blueprint: AI Data Pipeline & Screener Upgrade

## 1. Objective
Eliminate severe data ingestion bottlenecks that are handicapping the AI agents. This involves migrating synchronous external API calls to asynchronous parallel execution, replacing hardcoded ticker lists with actual database queries, and drafting the RAG architecture for unstructured text.

---

## 2. Requirements & Implementation Steps

### 2.1 Asynchronous Data Fetching
In files like `nl_screener.py` and `correlation_engine.py`, `yf.Ticker(t).info` is currently executed sequentially in a `for` loop.
- **Action:** Refactor these loops to use `asyncio.gather()` and run `yfinance` calls in `asyncio.to_thread()`.
- **Goal:** Analyzing 15 stocks should take the time of 1 request, not 15 requests.

### 2.2 Dynamic NL Screener (Remove Hardcoded Universe)
Currently, `nl_screener.py` searches against an array of 14 hardcoded tickers (Reliance, TCS, etc.).
- **Action:** The LLM still parses the natural language into JSON filters (`pe_max`, `roce_min`). However, instead of iterating a Python list, construct an SQLAlchemy/SQL query.
- **Execution:** Query the local `Database` representing the entire NSE universe (2000+ stocks) using the parsed filters. Only fetch live data for the top 10 results returned by the database.

### 2.3 RAG (Retrieval-Augmented Generation) Architecture
The `TradingAgentsGraph` currently has no access to unstructured text (earnings calls, SEC/NSE filings).
- **Action:** Design and stub out a vector database connection (e.g., using `FAISS` locally or `Qdrant`).
- **Implementation:** Create a new tool for the Bear/Bull researchers: `search_filings(query: str, ticker: str)`. When called, it should semantically search the vector DB and return the 3 most relevant textual chunks to the agent.

---

## 3. Execution Directives (AGENTS.md)
- Follow the **Sequential Subagent Pipeline**.
- **Builder Agent:** Rewrite the async data gathering loops. Modify `nl_screener.py` to use SQLAlchemy queries against the local DB. Stub out the RAG tool in `orchestrator.py`.
- **Reviewer Agent:** Verify that `asyncio` is utilized correctly and no synchronous blocking network calls remain in the hot path.
- **Verifier Agent:** Execute a natural language query ("Find me fast growing auto stocks under 15 PE") and verify it scans the database and returns non-hardcoded results instantly.
