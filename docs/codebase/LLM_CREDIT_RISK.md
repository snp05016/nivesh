# LLM/API Credit-Risk Guide

This guide maps out the specific API endpoints, background jobs, and services in the **Nivesh** backend codebase that trigger paid LLM calls (Anthropic, DeepSeek, OpenAI). It is critical for developers and automated test loops to be aware of these triggers to prevent unexpected or runaway API costs.

---

## 🚨 CRITICAL WARNING FOR AUTOMATED TESTING 🚨

**Automated test loops must NEVER hit these endpoints without strict mocking.** 
Running live requests against endpoints that trigger LLM calls inside continuous integration (CI) or local test loops can quickly result in runaway API costs (credit risk).

**Mandatory Practice:** Always mock `services.llm_utils`, `anthropic.Anthropic`, `langchain_anthropic.ChatAnthropic`, and any OpenAI equivalents in your tests (`pytest.patch`, `responses`, or mock wrappers) to prevent actual network calls.

---

## 1. LLM Client Providers & Abstractions
The codebase centrally manages most LLM integrations, but some specific routers and services instantiate clients directly.

* **Single-Source Abstractions:** 
  * `backend/services/llm_utils.py`: Centralized wrappers `deepseek_chat` and `get_deepseek_client` (using DeepSeek V4 Flash / Reasoner).
* **Direct Instantiations:** 
  * `anthropic.Anthropic(api_key=...)` is directly instantiated in several places, including `routers/analysis.py` and `services/orchestrator.py`.
* **LangGraph/LangChain:**
  * `ChatAnthropic` from `langchain_anthropic` is used inside `services/orchestrator.py` for "deep think" capabilities.

---

## 2. API Endpoints Triggering Paid Calls

The following FastAPI routers expose endpoints that perform paid LLM actions:

### `backend/routers/analysis.py`
* **Trigger:** Stock Analysis & Agent Pipelines
* **Action:** Orchestrates LangGraph agents and LLMs to perform fundamental analysis on specific tickers. Uses both Anthropic (for deep thinking/fallback) and DeepSeek (for bulk analysis, Smart Cache Gate, and fast daily actions).
* **Risk Level:** **HIGH** (Analyzes large payloads of stock data and executes multi-agent loops).
* **Known Triggers:** Endpoints triggering full ticker analysis, Batch create, Batch retrieve, and Daily Actions.

### `backend/routers/portfolio.py`
* **Trigger:** Portfolio Insights & Generation
* **Action:** Re-evaluates portfolios and generates insights using LLMs.
* **Risk Level:** **MEDIUM - HIGH**

### `backend/routers/health.py`
* **Trigger:** System Healthcheck
* **Action:** The healthcheck endpoints verify the presence of API keys (e.g., `ANTHROPIC_API_KEY`) and sometimes perform lightweight validation or status checks, though typically they don't invoke full inference, they are tied to LLM availability.
* **Risk Level:** **LOW**

### `backend/main.py`
* **Trigger:** Dashboard / Admin Endpoints
* **Action:** Might trigger metrics scraping or internal token logging that tracks Anthropic and DeepSeek usage.

---

## 3. Background Services & Jobs Triggering Paid Calls

The core business logic resides in `backend/services/`. These services are heavily reliant on paid LLM calls and are frequently triggered by background orchestrators or chron jobs:

### **Orchestration & Smart Cache**
* **`backend/services/orchestrator.py`**
  * **Function:** Main engine for multi-agent workflows. 
  * **LLM Usage:** 
    * `reformat_with_deepseek`: Primary tier 1 reformatter (DeepSeek V4 Flash).
    * `reformat_with_claude_fallback`: Claude Sonnet used as a fallback if DeepSeek fails.
    * Uses `deepseek-reasoner` for "quick think" and Anthropic for "deep think".

### **Harvesting & Summarization Pipelines**
* **`backend/services/advisor_harvester.py`** & **`backend/services/harvester_reformatter.py`**
  * **Function:** Harvests unstructured advisor/financial data and reformats it using LLMs.
* **`backend/services/youtube_harvester.py`** & **`backend/services/youtube_summary/` (`providers.py`, `summarizer.py`)**
  * **Function:** Ingests YouTube transcripts and relies on LLM summarization (Anthropic/DeepSeek) to distill market insights.
  * **Risk Level:** **HIGH** (Transcripts are token-heavy).

### **Screening & Portfolio Snapshots**
* **`backend/services/nl_screener.py`**
  * **Function:** Natural Language screener that parses user queries using LLMs into structured stock screen parameters.
* **`backend/services/portfolio_snapshot.py`**
  * **Function:** Evaluates user portfolios over time, consuming API credits for insights generation.
* **`backend/services/brainstorming.py`** & **`backend/services/copilot_service.py`**
  * **Function:** Real-time user assistance, chat, and brainstorming services. Highly sensitive to user volume.

---

## Summary Checklist to Prevent Credit Risk

1. [ ] **Never run live tests:** Verify that `pytest` suite actively blocks outgoing network connections (e.g. using `pytest-socket`).
2. [ ] **Mock `llm_utils` & `Anthropic`:** Every test touching `orchestrator.py` or `routers/analysis.py` must mock LLM responses.
3. [ ] **Monitor Token Logs:** Track `token_log.jsonl` continuously in dev/staging.
4. [ ] **Enforce Cache:** Ensure the Smart Cache gate (`services/staleness.py:compute_staleness()`) is strictly respected so repeated calls to unchanged data bypass the LLM.
