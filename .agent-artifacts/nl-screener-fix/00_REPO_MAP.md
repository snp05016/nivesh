# NL Screener Repository Map

## Frontend (iOS Swift)
* **View & ViewModel & Models:**
  `ios/StockApp/stockme/stockme/Views/NLScreenerScreen.swift`
  - `NLScreenerScreen` (SwiftUI View)
  - `NLScreenerViewModel` (ObservableObject handling network requests and state)
  - `NLScreenerRequest` (Codable request structure)
  - `NLScreenerResponse` (Codable response structure)
  - `NLScreenerResult` (Codable structure for individual stock results)

## Backend (FastAPI Python)
* **Router / Endpoint Definition:**
  `backend/routers/nl_screener.py`
  - Defines `NLScreenerRequest` Pydantic model
  - Maps `POST /api/v1/screener/natural-language` to `process_nl_query`

* **Service Layer / Logic:**
  `backend/services/nl_screener.py`
  - `process_nl_query(query: str)`: Coordinates caching, LLM parsing, SQL building, fetching stock info, and evaluating results.
  - `_evaluate_stock(info: dict, filters: dict)`: Checks `yf.Ticker` data against the extracted filters.

* **Dependencies / Integrations used by Service:**
  `backend/services/llm_utils.py` (DeepSeek interaction)
  `backend/helpers.py` (`_extract_json_from_text`)
  `backend/services/disk_cache.py` (Redis-like local caching)
  `database.py` (SQLAlchemy DB session for `stock_universe` query)
