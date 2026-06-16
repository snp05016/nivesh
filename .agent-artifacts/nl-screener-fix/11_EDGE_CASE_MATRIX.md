# Edge Case Matrix

This matrix documents the various edge cases explored in the exhaustive test suite and their expected vs actual behavior.

| ID | Edge Case Scenario | Test Input (Query / LLM Mock) | Expected Behavior | Actual Covered Result |
|----|--------------------|-------------------------------|-------------------|-----------------------|
| 1 | **Ambiguous Query** | `"good stocks"` / `{}` | Backend returns `parsed_filters: {}`, SQL ignores filters. | ✅ Returns 14 default fallback matching all criteria. |
| 2 | **Empty Results** | `"negative 100 PE"` / `{"pe_max": -100}` | DB yields 0 rows. Backend must return `results: []` instead of 14 default. | ✅ Returns `[]`, `db_failed` logic correctly separates empty arrays from DB crashes. |
| 3 | **Malformed LLM JSON** | `"banks"` / `"Here are some... wait"` | JSON parser exception swallowed. Falls back to `{}` filters. | ✅ Response safely completed. |
| 4 | **LLM Timeout** | `TimeoutError` injected into mock | Safe exception handling, defaulting to empty filters. | ✅ Response safely completed. |
| 5 | **Missing Sector (Null)** | `{"sector": "IT"}` but yf misses sector | Result `sector` mapped to JSON `null`. Swift maps to `Optional(nil)`. | ✅ iOS handles `null` gracefully. |
| 6 | **NaN Metric Serialization** | `math.nan` sent for `pe_max` | Cast to string `"nan"` instead of silently breaking JSON/Pydantic schemas. | ✅ `"nan"` correctly stringified. |
| 7 | **Multiple Combined Filters** | `"pe < 20 and roce > 15 in IT"` | Extracted correctly, combined `AND` SQL clauses successfully injected. | ✅ Filters parsed & serialized. |
| 8 | **Malformed Body to API** | `{ "not_query": "invalid" }` | FastAPI catches schema violation, returns structured JSON `422 Unprocessable Entity`. | ✅ Envelope safely decoded on iOS via `APIErrorResponse`. |
