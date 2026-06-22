# Feature Blueprint: Eradicate Hardcoded Magic Values in Backend

## 1. Objective
Identify, extract, and refactor all hardcoded "magic strings" and "magic numbers" across the entire `backend/` directory. All configurations, thresholds, and static lists must be dynamically driven by configuration files, environment variables, or database queries in accordance with the "Zero Magic" Karpathy Principle outlined in `AGENTS.md`.

---

## 2. Scope of Refactoring

### 2.1 Identify Hardcoded Arrays and Lists
Many services currently rely on hardcoded Python lists to define universes or fallback mechanisms.
- **Targets:** Search through all `backend/services/*.py` files. Look specifically for hardcoded arrays of tickers (e.g., `["RELIANCE.NS", "TCS.NS"]`).
- **Fix:** Move these into a dedicated `config.py` file as fallback constants, or preferably fetch them dynamically from the database (`stock_universe` table).

### 2.2 Identify Hardcoded Mathematical Thresholds
Several quantitative models use arbitrary numbers to clamp scores or define risk.
- **Targets:** Search `backend/services/extreme_enrichers.py`, `backend/services/piotroski.py`, and `backend/services/factor_engine.py`. Look for magic numbers like `pe / 40.0`, `pb / 8.0`, or `weight_pct > 40`.
- **Fix:** Replace these magic numbers with named constants at the top of the file (e.g., `MAX_HEALTHY_PE = 40.0`). Even better, refactor the logic to dynamically fetch sector medians.

### 2.3 Identify Hardcoded System Limits and Timeouts
- **Targets:** Look in `backend/database.py`, `backend/services/job_worker.py`, and `backend/services/orchestrator.py` for hardcoded integers representing seconds (e.g., `600`, `300` for staleness or wall-clock limits), or hardcoded token limits (e.g., `max_tokens=4000`).
- **Fix:** Extract these into `tradingagents/default_config.py` or `.env` so they can be managed centrally via `build_ta_config()`.

### 2.4 Identify Hardcoded File Paths and URLs
- **Targets:** Search `backend/routers/*.py` and `backend/main.py` for hardcoded paths (like `/tmp/cache` or `sqlite:///stockapp.db`).
- **Fix:** Wrap these in `os.getenv("DATABASE_URL", "sqlite:///stockapp.db")` or use `pathlib` relative to the project root.

---

## 3. Execution Directives (AGENTS.md)
- Follow the **Sequential Subagent Pipeline**.
- **Builder Agent:** Perform a rigorous `grep_search` across `backend/services/` and `backend/routers/` for magic numbers, arrays, and strings. Refactor them into centralized configurations or environment variables.
- **Reviewer Agent:** Ensure no logic was broken during the extraction. Verify strict adherence to the "Explicit over implicit" and "Zero magic" rules in `AGENTS.md`.
- **Verifier Agent:** Run `pytest` or `python3 -m py_compile` to ensure the refactored imports and configurations load correctly without circular dependencies.
