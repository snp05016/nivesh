# Morning Briefing - System Map

## Frontend (iOS)
* **File:** `ios/StockApp/stockme/stockme/Views/HomeScreen.swift`
  * **Component:** `HomeScreen` & `MorningDecreeCard`
  * **Role:** Displays the Morning Briefing card to the user on the Home tab.
* **File:** `ios/StockApp/stockme/stockme/NetworkManager.swift`
  * **Function:** `getMorningSummary(userId: Int)`
  * **Role:** Fetches the morning summary from the backend.
  * **Function:** `sendMorningSummaryNotification()`
  * **Role:** Triggers push notifications.
* **File:** `ios/StockApp/stockme/stockme/Models/WatchlistModels.swift`
  * **Models:** `MorningSummaryResponse`, `MorningSummaryPriorityItem`
  * **Role:** Data structures for decoding the response.
* **File:** `ios/StockApp/stockme/stockme/Views/SettingsScreen.swift`
  * **Role:** Allows user configuration for morning brief notification time.

## Backend (FastAPI)
* **File:** `backend/routers/portfolio.py`
  * **Endpoint:** `GET /morning-summary/{user_id}`
  * **Function:** `morning_summary_endpoint`
  * **Role:** Serves the morning briefing payload. Checks cache, and falls back to live generation if needed.
* **File:** `backend/routers/user.py`
  * **Endpoint:** `POST /notifications/morning-summary-push`
  * **Function:** `notifications_morning_summary_push`
  * **Role:** Internal/system endpoint to trigger push notifications for morning brief.

## Background Services & Workers
* **File:** `backend/services/harvest_worker.py`
  * **Function:** `_run_pregen_morning_briefs`
  * **Role:** APScheduler cron job running daily to kick off bulk pre-generation.
* **File:** `backend/services/portfolio_snapshot.py`
  * **Function:** `pregen_morning_briefs_all_users`
  * **Role:** Core logic to generate briefs for all users with holdings and push them to cache.

## External Dependencies
* **LLM APIs:** DeepSeek Chat (pre-gen) and Anthropic (live generation fallback) to write the 4-6 bullet points based on portfolio data.
* **yfinance:** Used to pull live 2-day historical data for price changes.
