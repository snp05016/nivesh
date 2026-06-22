# Morning Briefing - Database Flow

Both the bulk pre-generation (`pregen_morning_briefs_all_users`) and the fallback on-demand generation (`morning_summary_endpoint`) interact with the database using the same query pattern.

## Models Queried
1. **`User` (models.db_models)**
   * Used to iterate over all active users during the bulk pre-generation cron job.
   * Used to validate the `user_id` matches the authenticated session in the on-demand endpoint.
2. **`Portfolio` (models.db_models)**
   * Queried to retrieve the user's active holdings.
   * **Filter:** `user_id = user.id` AND `group_name = "holdings"`
   * Used to extract the `ticker`, `shares`, and `buy_price` to calculate individual and aggregate P&L to feed into the LLM prompt.
3. **`AnalysisHistory` (models.db_models)**
   * Queried to fetch the most recent AI signals (Bullish/Bearish/Hold) for each holding.
   * **Filter Pattern:** Uses an `IN` clause (`AnalysisHistory.ticker.in_(tickers)`) combined with an `order_by(created_at.desc())` to fetch all necessary signals in a single bulk query, strictly preventing N+1 database queries during loop iteration.

## Transaction Boundary
* Read-only operations.
* Safely wrapped in `get_session()` context managers to ensure DB connections are cleanly released back to the pool.
