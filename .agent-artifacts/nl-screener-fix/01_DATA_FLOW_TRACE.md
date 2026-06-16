# Data Flow Trace: NL Screener

## 1. User Interaction (Frontend)
- User enters a query (e.g., "banks with PE less than 20") in `NLScreenerScreen`.
- View triggers `viewModel.performSearch()`.
- `NLScreenerViewModel` constructs `NLScreenerRequest(query: "banks with PE less than 20")`.
- Encodes body to JSON and makes a `POST` request to `[BASE_URL]/api/v1/screener/natural-language`.
- *Note:* Request is sent *unauthenticated* (no Authorization header).

## 2. API Endpoint (Backend)
- FastAPI router `@router.post("/api/v1/screener/natural-language")` receives the request.
- Pydantic validates the body against `NLScreenerRequest` (just `{"query": str}`).
- Router passes `req.query` to `process_nl_query()`.

## 3. Natural Language Processing (Backend Service)
- `process_nl_query` checks local cache first.
- If not cached, sends the `query` + `SYSTEM_PROMPT` to DeepSeek LLM.
- LLM returns a raw text response, parsed via `_extract_json_from_text`.
- JSON string is loaded into a Python `dict`.
- The `"parsed_filters"` object is extracted. E.g., `{"sector": "Banks", "pe_max": 20}`.

## 4. Query Execution & Evaluation (Backend Service)
- Builds an SQL query dynamically to fetch tickers from `stock_universe` matching the filters.
- If DB returns no tickers (or fails), falls back to 14 hardcoded major NSE tickers.
- Uses `yfinance` in an `asyncio.to_thread` loop to concurrently fetch live stats for all candidates.
- Evaluates each stock's `yf.info` dict using `_evaluate_stock(info, filters)`.
- Calculates a match score, reasons, and maps the response into `results`.
- Constructs final dict: 
  ```python
  {
      "parsed_filters": filters,  # Contains mixed types (strings, ints, floats)
      "results": [...]
  }
  ```
- Endpoint directly returns this dictionary, allowing FastAPI to JSON-encode it.

## 5. Decoding (Frontend)
- iOS receives HTTP 200 JSON response.
- `JSONDecoder().decode(NLScreenerResponse.self, from: data)` attempts to parse the JSON.
- `NLScreenerResponse` defines `parsedFilters` as `[String: String]?`.
- When encountering numeric values (like `pe_max: 20`) in `parsedFilters`, `JSONDecoder` throws a `typeMismatch` error.
- Catch block maps the error to localized description: *"The data couldn’t be read because it isn’t in the correct format."*
