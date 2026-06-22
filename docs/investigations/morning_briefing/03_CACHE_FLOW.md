# Morning Briefing - Cache Flow

## Configuration
* **Namespace:** `morning_brief`
* **Key Format:** `str(user_id)`
* **File:** `backend/services/cache_service.py` sets base TTL to 86400s (24 hours) for this namespace. `routers/portfolio.py` specifies `_MORNING_CACHE_TTL = 7200` (2 hours) for live-generation overrides.

## Writers
1. **Batch Pre-Generation (Primary):**
   * **Function:** `pregen_morning_briefs_all_users` in `backend/services/portfolio_snapshot.py`.
   * **Behavior:** Runs every morning. Generates JSON briefs for all users and bulk writes to disk_cache.
2. **On-Demand Generation (Fallback):**
   * **Function:** `morning_summary_endpoint` in `backend/routers/portfolio.py`.
   * **Behavior:** If a user accesses the app and has no cache (or cache was purged), it generates the brief synchronously and writes to cache.

## Readers
* **Function:** `morning_summary_endpoint` in `backend/routers/portfolio.py`.

## Invalidation & Eviction
1. **Automatic Purge:** Nightly cache-purge task clears stale keys.
2. **Action-Driven Invalidation:** In `backend/routers/portfolio.py`, whenever a user updates their portfolio (e.g., executing a buy/sell trade, manually adding holdings, deleting holdings), the router triggers:
   * `_cache_invalidate("morning_brief", str(req.user_id))`
   * This ensures the next time they view the brief, it is regenerated with their latest holdings.
