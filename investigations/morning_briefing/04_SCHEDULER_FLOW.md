# Morning Briefing - Scheduler Flow

## Configuration
* **File:** `backend/services/harvest_worker.py`
* **Trigger:** APScheduler `cron`
* **Schedule:** `hour=1, minute=0` (UTC) -> **6:30 AM IST**

## Execution Pipeline
1. **Trigger Activation:** At 6:30 AM IST, APScheduler triggers the `_run_pregen_morning_briefs` async job.
2. **Status Update:** Worker updates internal telemetry/dashboard using `_dash_update_harvest("morning_brief", "running")`.
3. **Task Delegation:** Calls `pregen_morning_briefs_all_users()` located in `backend/services/portfolio_snapshot.py`.
4. **Data Aggregation:** For each user with active holdings, gathers portfolio data and AI signals from the database.
5. **LLM Generation:** Dispatches the data to DeepSeek Chat (`deepseek-chat`) for fast, bulk summarization into 4-6 bullet points. DeepSeek is prioritized over Anthropic in the batch process to optimize LLM credit usage.
6. **Cache Seeding:** Generated briefs are directly written to the `morning_brief` cache namespace.
7. **Status Finalization:** On completion, updates the harvest dashboard to `"idle"` (or `"error"` if an exception occurred) and logs the total generated, skipped, and error counts.
