import os

prompts = [
    ("Prompt 01: Pre-compute Nightly Indicators", "Performance", "Implement a nightly cron job to pre-compute `compute_indicators()` for the top 500 Nifty stocks and cache them in Redis. This reduces the runtime blocking during user requests."),
    ("Prompt 02: Parallelize Calibration Block", "Performance", "Refactor the 8 sequential HTTP calls in `orchestrator.py`'s calibration block to run concurrently using `concurrent.futures.ThreadPoolExecutor`, saving ~40s per analysis."),
    ("Prompt 03: Background Pre-fetch of Live Data", "Performance", "Start fetching yfinance 1y history and live prices at the beginning of the `analyze()` function in a background thread rather than waiting sequentially at the end."),
    ("Prompt 04: Replace yfinance with unified caching", "Performance", "Replace yfinance calls in critical paths with a robust, cached abstraction layer that pulls from a unified Redis store, mitigating yfinance latency spikes."),
    ("Prompt 05: Batch RRG Quadrant Calculation", "Performance", "Move the Relative Rotation Graph (RRG) calculations out of the request-response cycle and into a nightly batch job that writes to the database."),
    ("Prompt 06: Optimize DeepSeek Reformatter Input", "Performance", "Create an `_extract_final_conclusion` function to truncate the 8000-character raw output sent to the DeepSeek reformatter, sending only the PM decision to save processing time."),
    ("Prompt 07: Reduce LLM Context in Risk Analysts", "Performance", "Enforce strict length limits (e.g. 400 words) for the Aggressive, Neutral, and Conservative risk analysts to drastically reduce token consumption and generation time."),
    ("Prompt 08: Decouple DB reads from Analysis Thread", "Performance", "Run database lookups for Advisor Insights and News Articles asynchronously while the LLM analysis executes."),
    ("Prompt 09: Implement SSE Streaming for UI", "Performance", "Convert the analysis endpoint to Server-Sent Events (SSE) or WebSockets so the frontend receives real-time progressive updates instead of waiting 10 minutes for a single response."),
    ("Prompt 10: Async LangGraph Agent Execution", "Performance", "Refactor `build_analyst_execution_plan()` to execute mutually independent agents (like Governance and News) concurrently using asyncio instead of sequentially."),
    ("Prompt 11: Shift HMM Regime Logic to C/Rust", "Performance", "Migrate the Hidden Markov Model state decoding from pure Python to a compiled C/Rust extension for 10x faster regime classification over long time horizons."),
    ("Prompt 12: Parallelize PDF Filings OCR", "Performance", "Use a multiprocessing pool in `filings_extractor.py` to concurrently OCR and process multiple pages/documents of SEBI filings instead of doing them sequentially."),
    ("Prompt 13: Replace slow Selenium/BS4 scraping", "Performance", "Swap out the blocking BeautifulSoup scraper with asynchronous `aiohttp` requests and strict TTL caching for parsing external news and data sites."),
    ("Prompt 14: Optimize AnalysisHistory JSON Serialization", "Performance", "Use `orjson` or `ujson` for extremely fast serialization/deserialization of massive AnalysisHistory JSON payloads in FastAPI responses."),
    ("Prompt 15: Convert synchronous Requests to aiohttp", "Performance", "Refactor all generic `requests.get` API calls to `aiohttp.ClientSession` across all harvesters and data providers."),

    ("Prompt 16: Math replacing AI - Piotroski/Beneish", "Math/Algo", "Replace subjective AI 'Management Quality' with strict, deterministic calculations of the Piotroski F-score and Beneish M-score from SEC/NSE fundamental data."),
    ("Prompt 17: Math replacing AI - Momentum Divergence", "Math/Algo", "Remove LLM-based technical reading and replace it with mathematical detection of RSI divergence, MACD crossovers, and Bollinger Band squeeze signals."),
    ("Prompt 18: Math replacing AI - PCR and GEX", "Math/Algo", "Calculate exact Put/Call Ratio (PCR) and Gamma Exposure (GEX) across option chains deterministically instead of asking the AI to guess options sentiment."),
    ("Prompt 19: Math replacing AI - Relative Rotation Graph", "Math/Algo", "Replace qualitative AI Sector Rotation guesses with quantitative normalized JdK RS-Ratio and RS-Momentum vector math."),
    ("Prompt 20: Math replacing AI - Conformal Prediction", "Math/Algo", "Implement Conformal Prediction bound algorithms based on historical non-conformity scores instead of having the LLM guess price bounds."),
    ("Prompt 21: Math replacing AI - Euclidean Analogues", "Math/Algo", "Replace the LLM searching for historical analogues with an exact Euclidean distance or Cosine Similarity search over normalized 90-day price vectors."),
    ("Prompt 22: Math replacing AI - Deterministic DCF", "Math/Algo", "Implement a pure mathematical DCF model using the current 10Y Indian G-Sec as the risk-free rate, entirely bypassing LLM valuation guessing."),
    ("Prompt 23: Math replacing AI - Volume Isolation Forest", "Math/Algo", "Use scikit-learn's Isolation Forest algorithm to detect volume and price anomalies instead of asking the LLM to spot 'unusual activity'."),
    ("Prompt 24: Math replacing AI - EPS Drift Model", "Math/Algo", "Apply a standard Post-Earnings Announcement Drift (PEAD) mathematical formula instead of qualitative LLM evaluation of earnings surprises."),
    ("Prompt 25: Math replacing AI - FinBERT Embeddings", "Math/Algo", "Route all news text through pre-trained FinBERT models to get exact +1.0 to -1.0 sentiment scores rather than having a 'News Agent' summarize sentiment."),
    ("Prompt 26: Math replacing AI - Minskyan Risk Flows", "Math/Algo", "Calculate Minskyan Risk deterministically by taking the second derivative of FII/DII net flows rather than qualitative reasoning."),
    ("Prompt 27: Math replacing AI - Signal Agreement Multiplier", "Math/Algo", "Compute the alignment between 4 technical/fundamental signals using vector agreement math rather than using an LLM to evaluate the consensus."),
    ("Prompt 28: Math replacing AI - DTW Pattern Matching", "Math/Algo", "Implement Dynamic Time Warping (DTW) to mathematically align and match chart patterns (Head & Shoulders, etc.) instead of visual AI guesses."),
    ("Prompt 29: Math replacing AI - Portfolio Correlation Matrix", "Math/Algo", "Compute the exact Pearson correlation matrix for the user's portfolio and optimize weights mathematically instead of using AI for diversification advice."),
    ("Prompt 30: Math replacing AI - Auditor Risk Quantification", "Math/Algo", "Calculate auditor risk using a deterministic matrix mapping auditor changes against Big-4 presence and regulatory action history."),

    ("Prompt 31: Remove Hardcoded SECTOR_PE_MAP", "Hardcoding", "Move the hardcoded `SECTOR_PE_MAP` dictionary out of `analysis.py` into a database table that automatically updates using daily market medians."),
    ("Prompt 32: Remove Hardcoded 14-day cutoff", "Hardcoding", "Extract the hardcoded `timedelta(days=14)` for fetching AdvisorInsights into an environment variable or user-configurable setting."),
    ("Prompt 33: Remove Hardcoded NSE/BSE suffixes", "Hardcoding", "Eliminate hardcoded `.NS` and `.BO` string checks in `helpers.py` by centralizing exchange normalization through a single config-driven utility."),
    ("Prompt 34: Remove Hardcoded yfinance sleep intervals", "Hardcoding", "Replace `time.sleep(1.5 * (2 ** attempt))` with a robust configuration-driven exponential backoff library like `tenacity`."),
    ("Prompt 35: Move Signal Maps to DB", "Hardcoding", "Migrate `_BULLISH_SIGNALS` and `_SIGNAL_MAP` dictionaries out of the code and into a database-backed configuration for easier live tuning."),
    ("Prompt 36: Make DeepSeek Truncation Dynamic", "Hardcoding", "Remove the hardcoded 8000-character limit in `reformat_with_deepseek` and implement a dynamic token-counting threshold using tiktoken."),
    ("Prompt 37: Eliminate Hardcoded Token Limits", "Hardcoding", "Extract the `max_tokens=1000` hardcoded limits in the LLM agent configurations and map them to dynamic variables controlled via `.env`."),
    ("Prompt 38: Configurable yfinance Circuit Breaker", "Hardcoding", "Remove the hardcoded `_YF_CIRCUIT_THRESHOLD = 3` and `_YF_CIRCUIT_TIMEOUT = 300` values, making them configurable environment variables."),
    ("Prompt 39: Centralize Cache TTLs", "Hardcoding", "Move `_QUICK_INFO_TTL` and `_ASM_GSM_CACHE_TTL` out of random places in routers and into a centralized `settings.py` or `.env` configuration."),
    ("Prompt 40: Remove Hardcoded User-Agents", "Hardcoding", "Replace the hardcoded 'Mozilla/5.0...' string in `_nse_session()` with the `fake-useragent` package to rotate User-Agents dynamically and avoid blocks."),
    ("Prompt 41: Migrate System Prompts to DB", "Hardcoding", "Move massive hardcoded system prompt strings from `prompts.py` into a Postgres/SQLite table so they can be versioned and hot-reloaded."),
    ("Prompt 42: Refactor Hardcoded Ticker Overrides", "Hardcoding", "Move the `_NSE_TICKER_OVERRIDES` dictionary (e.g. 'JITFINFRA') into the database so new oddball tickers can be fixed without a code deployment."),
    ("Prompt 43: Remove Hardcoded Row Limits", "Hardcoding", "Replace hardcoded `limit(10)` limits on SQL queries (like news and advisors) with standard pagination logic driven by request parameters."),
    ("Prompt 44: Fix Hardcoded HTTP Timeouts", "Hardcoding", "Replace hardcoded `timeout=8` or `timeout=10` values in `requests.get` with centralized global timeout configs to handle slow networks gracefully."),
    ("Prompt 45: Extract max_debate_rounds", "Hardcoding", "Move the hardcoded logic defining `max_debate_rounds` (1 or 2 based on scan type) to a dedicated strategy configuration file."),

    ("Prompt 46: Fix Path Shadowing in Worker", "Bugs/Issues", "Resolve the risky `sys.path.insert(0)` hack in `_run_analysis_worker` that shadows the `tradingagents-core` module, which causes brittle local imports."),
    ("Prompt 47: Robust DeepSeek Error Handling", "Bugs/Issues", "Implement structured try/except blocks and retry dead-lettering for `reformat_with_deepseek`, which currently masks deep LLM failures or crashes silently."),
    ("Prompt 48: Implement SQLAlchemy Connection Pooling", "Bugs/Issues", "Configure `QueuePool` in `database.py` to prevent the current architecture from opening and closing hundreds of expensive TCP database connections per minute."),
    ("Prompt 49: Fix OrderedDict Memory Leak", "Bugs/Issues", "Fix the in-memory `_CACHE` implementation in `scraper.py` by implementing a proper thread-safe LRU Cache with automatic background TTL eviction."),
    ("Prompt 50: Standardize Timezone Awareness", "Bugs/Issues", "Audit all `datetime.now(timezone.utc)` and `datetime.now()` calls across `orchestrator.py` to strictly use `timezone.utc` to prevent localized server time bugs."),
    ("Prompt 51: Background Worker Dead-Letter Queue", "Bugs/Issues", "Build a dead-letter queue (DLQ) in SQLite/Redis to catch and auto-restart analyses that fail inside the detached `multiprocessing.Process` worker."),
    ("Prompt 52: Migrate from Multiprocessing to Celery", "Bugs/Issues", "Replace the fragile native `multiprocessing` spawn logic with Celery or RQ (Redis Queue) for production-grade task tracking and fault tolerance."),
    ("Prompt 53: Fix Pure Function State Mutation", "Bugs/Issues", "Refactor `_inject_live_data` to return a copy of the dictionary instead of mutating the raw dictionary in-place right before caching it."),
    ("Prompt 54: Global yfinance Rate Limit Handling", "Bugs/Issues", "Implement a global Token Bucket rate limiter for `yfinance` to prevent HTTP 429 errors from crashing the backend during extreme volume scans."),
    ("Prompt 55: Add Unit Tests for Calibration Engine", "Bugs/Issues", "Write comprehensive Pytest coverage for the newly added `Calibration Engine` block in `orchestrator.py` to ensure math correctness."),
    ("Prompt 56: Create /healthz System Check", "Bugs/Issues", "Develop a `/healthz` endpoint that actively pings the Database, Redis, yfinance, and Anthropic APIs to accurately report backend readiness."),
    ("Prompt 57: Standardize Structured Logging", "Bugs/Issues", "Replace all generic `print()` statements throughout the backend with `structlog` to enable JSON logging, stack trace capture, and Datadog integration."),
    ("Prompt 58: Strict Pydantic Input Validation", "Bugs/Issues", "Enhance the `AnalyzeRequest` model with strict regex validation for tickers to prevent SQL injection and malformed requests reaching yfinance."),
    ("Prompt 59: Unify the Fragmentation of Caches", "Bugs/Issues", "Consolidate `disk_cache.py`, the in-memory dicts in `scraper.py`, and DB caching into a single `CacheService` interface for predictability."),
    ("Prompt 60: Clean up Monolithic Legacy Code", "Bugs/Issues", "Purge the unused `main_legacy_backup.py` and `main_old_monolithic.py` files and split `main.py` middleware into a dedicated `middleware/` folder.")
]

import os
# Since prompts directory might not exist at root, let's create it at root/automated backend improvements
target_dir = "/Users/saumya/Desktop/nivesh/prompts/automated backend improvements"
os.makedirs(target_dir, exist_ok=True)

rankings = []

for i, (title, category, desc) in enumerate(prompts):
    rank = i + 1
    
    # Format the file name cleanly
    clean_title = title.split(': ')[1] if ': ' in title else title
    file_name = f"rank_{rank:02d}_{clean_title.lower().replace(' ', '_').replace('/', '_').replace('-', '_')}.md"
    file_path = os.path.join(target_dir, file_name)
    
    content = f"# {title}\n\n"
    content += f"**Category:** {category}\n\n"
    content += f"**Goal:** Analyze the backend architecture to address this specific issue.\n\n"
    content += f"**Problem Statement / Description:**\n{desc}\n\n"
    content += f"**Why it will improve the system:**\n"
    if category == "Performance":
        content += "It removes severe bottlenecks, blocking I/O, and sequential execution overhead, making the backend rendering extremely fast.\n\n"
    elif category == "Math/Algo":
        content += "It converts qualitative, slow, and expensive LLM reasoning into instant, mathematically verifiable deterministic algorithms.\n\n"
    elif category == "Hardcoding":
        content += "It decouples logic from data, allowing dynamic configuration and reducing the need for code deployments when market conditions change.\n\n"
    else:
        content += "It hardens the system architecture, resolves brittle state handling, and ensures production-level fault tolerance.\n\n"
    content += f"**What you have to do:**\n"
    content += "1. Read the relevant source files.\n"
    content += "2. Design the fix conceptually.\n"
    content += "3. Implement the changes using proper architecture boundaries.\n"
    content += "4. Write tests to verify correctness.\n"
    
    with open(file_path, "w") as f:
        f.write(content)
        
    rankings.append((rank, title, file_name))

rank_file_path = os.path.join(target_dir, "rank.md")
with open(rank_file_path, "w") as f:
    f.write("# Automated Backend Improvements - Ranking (1-60)\n\n")
    for rank, title, file_name in rankings:
        f.write(f"{rank}. [{title}](./{file_name})\n")

print(f"Generated 60 prompts and rank.md in {target_dir}")
