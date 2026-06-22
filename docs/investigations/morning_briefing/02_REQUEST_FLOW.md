# Morning Briefing - Request Flow

## Standard Retrieval Flow (App Open)
1. **Trigger:** User opens the iOS app, initializing the `HomeScreen`.
2. **Client Call:** `HomeScreen` identifies the section is `morning` and calls `NetworkManager.getMorningSummary(userId: userId)`.
3. **API Routing:** Request arrives at `GET /morning-summary/{user_id}` in `backend/routers/portfolio.py`.
4. **Cache Check:** `morning_summary_endpoint` calls `_dcache_get("morning_brief", str(user_id))`.
5. **Cache Hit:** If the pre-generated brief exists and has valid English content (checked via `contains_devanagari`), it is returned immediately.
6. **Cache Miss / Live Generation:** 
   * Fetches user's `Portfolio` from DB.
   * Fetches latest `AnalysisHistory` signals.
   * Calls `yfinance` for latest daily prices.
   * Compiles data into an LLM prompt.
   * Calls the LLM (Anthropic) to generate a brief (max 600 tokens).
   * Parses the JSON output.
   * Stores in cache via `_dcache_set("morning_brief", str(user_id), result, ttl=_MORNING_CACHE_TTL)`.
7. **Response:** Returns `MorningSummaryResponse` JSON back to the iOS app.
8. **Render:** App decodes JSON and renders `MorningDecreeCard`.

## Push Notification Flow
1. **Trigger:** User's scheduled notification time (configured in `SettingsScreen`) triggers locally or via external cron.
2. **Endpoint:** Hits `POST /notifications/morning-summary-push` in `backend/routers/user.py`.
3. **Execution:** Calls `morning_summary_endpoint` locally to fetch the summary.
4. **Dispatch:** Formats a summary string and triggers the push notification via Firebase/APNS.
