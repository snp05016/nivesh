# Root Cause Hypotheses

## 1. Type Mismatch in `parsed_filters` (Confirmed Root Cause 🎯)
**Hypothesis:** The Swift code expects `parsedFilters` to be a dictionary of type `[String: String]?`. However, the LLM is prompted to return numeric screening criteria (e.g., `pe_max`, `roce_min`), which it returns natively as JSON Numbers (`{"pe_max": 20}`).
**Evidence:** 
- The prompt explicitly lists filters like `pe_max`, `market_cap_min`.
- The python code uses these directly in mathematical SQL filters (`"AND pe <= :pe_max"`).
- The Python dict passes these integers/floats down to FastAPI.
- Swift's strongly-typed `JSONDecoder` will throw `DecodingError.typeMismatch` when trying to map `20` to `String`.
- The caught error in iOS uses `error.localizedDescription`, which exactly matches: *"The data couldn’t be read because it isn’t in the correct format."*

## 2. Invalid LLM JSON Formatting (Plausible but Handled)
**Hypothesis:** The DeepSeek LLM returns markdown or invalid JSON, causing FastAPI to return malformed output or a 500 error.
**Evidence:**
- The backend uses `_extract_json_from_text(raw_text)` to strip markdown.
- If `json.loads` fails, it falls back to `filters = {}`.
- If `filters` is empty, the response is `{ "parsed_filters": {}, "results": [...] }`.
- `[String: String]` cleanly decodes an empty `{}` JSON object. 
- *Conclusion:* This actually bypasses the error.

## 3. Empty Database Fallback (Plausible but Handled)
**Hypothesis:** The SQL query to `stock_universe` fails, causing an empty response or backend crash.
**Evidence:** 
- The Python code has an explicit fallback: `if not tickers: tickers = [...]` (14 hardcoded NSE tickers).
- This ensures `fetch_all(tickers)` still runs and valid JSON is produced.
- *Conclusion:* Not the root cause.

## 4. Asyncio Loop Collision (Plausible but Handled)
**Hypothesis:** The `asyncio.to_thread` usage inside a synchronous FastAPI router causes an event loop crash.
**Evidence:** 
- The developer used a very robust `try/except RuntimeError` and `nest_asyncio` to ensure it works whether an event loop is running (e.g. Uvicorn worker thread) or not.
- *Conclusion:* Not the root cause.

## 5. Missing Authorization Header (Plausible but Handled)
**Hypothesis:** The iOS network request omits the JWT token, resulting in a 401 Unauthorized HTML response.
**Evidence:**
- `NLScreenerScreen.swift` has no `Authorization` header logic.
- However, `backend/routers/nl_screener.py` explicitly omits the `Depends(require_auth)` decorator. It is an open, unauthenticated endpoint.
- *Conclusion:* Not the root cause.
