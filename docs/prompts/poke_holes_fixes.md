# System Architecture Refactor: Poke Holes Vulnerability Fixes

This prompt outlines a series of critical architectural refactors based on the `poke_holes.md` vulnerability analysis. 

**AGENT INSTRUCTION:** 
You must execute this prompt using the `/goal` command framework to ensure exhaustiveness and prevent premature termination. Do not stop until every item in the checklist is complete. Once all code changes are made, **you must test everything in the end on the remote server** by executing the remote test commands (as dictated in `AGENTS.md`).

---

## 1. The Viable Issues to Fix

Based on the architectural review, the following three issues have been selected for immediate remediation because they provide the highest impact on system stability and output quality with the lowest risk of introducing breaking changes:

1. **Concurrency Isolation Failures (State Management):** 
   - *The Issue:* `orchestrator.py` and `analysis.py` currently use a global Python `set()` and `threading.Lock()` to track `_running_analyses`. In a production Gunicorn/Uvicorn multi-worker environment, memory is isolated per worker, causing race conditions and duplicate API billing.
   - *The Fix:* Refactor the state manager to use the existing SQLite database (or a robust file-based lock) to track active task IDs globally across all processes.

2. **Narrative Dissonance on Cache Hits:**
   - *The Issue:* When the Smart Cache Gate allows a cached report to be reused, it forcefully injects the live `current_price` into the old qualitative narrative. This creates cognitive dissonance (e.g., a lower injected price surrounded by text arguing for "violent bullish momentum").
   - *The Fix:* Introduce a "Harmonization Agent" pass. When live data is injected into a cached report, pass the updated payload through a fast Tier-1 LLM (DeepSeek Flash) specifically prompted to smooth out any contradictions between the new math and the old text.

3. **Brittle Additive Heuristics for Staleness:**
   - *The Issue:* `staleness.py` uses hard-coded integer penalties (e.g., +35 points for >10% movement). This ignores the asset's historical variance (a 10% move in a high-beta stock is normal; in a utility stock, it's a crisis).
   - *The Fix:* Refactor the price divergence penalty to be dynamic. Instead of a flat 10%, calculate the stock's rolling historical standard deviation (volatility) and penalize based on Z-scores (i.e., how many standard deviations the recent move represents).

---

## 2. Execution Checklist

Please complete the following checklist in order:

- [ ] **Task 1: Refactor Global State Management**
  - [ ] Remove `_running_analyses` set and `threading.Lock()` from `routers/analysis.py`.
  - [ ] Implement a distributed locking mechanism (e.g., an `ActiveAnalysis` table in `database.py` or a shared cross-process lock).
  - [ ] Ensure the lock is safely released/deleted upon job completion or failure.

- [ ] **Task 2: Dynamic Staleness Refactor**
  - [ ] Modify `services/staleness.py`.
  - [ ] Remove the hard-coded absolute percentage penalties for price movement.
  - [ ] Implement a dynamic Z-score or historical variance check (leveraging the math already present in `quant_engine.py`) to trigger staleness penalties only when the movement exceeds the asset's normal volatility.

- [ ] **Task 3: Narrative Harmonization Agent**
  - [ ] In `services/orchestrator.py`, locate the cache hit sequence where `_inject_live_data` occurs.
  - [ ] Implement a fast LLM call (e.g., `harmonize_narrative(old_text, new_data)`) that dynamically rewrites the cached commentary to match the injected live numbers.
  - [ ] Ensure the harmonization agent adheres to the Karpathy Principles (Zero Magic) and strictly outputs the normalized JSON schema.

- [ ] **Task 4: Server-Side Testing**
  - [ ] Deploy the changes to the remote server via the standard `AGENTS.md` deployment command.
  - [ ] Execute `pytest` or trigger an analysis request on the remote server to verify that the locks function correctly in a multi-worker environment and the cache harmonization works without crashing the `JSONDecoder`.

---
*End of Prompt*
