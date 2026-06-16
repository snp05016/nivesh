# Implementation Plan (For Claude)

## The Issue
The iOS app crashes out of the NL Screener with the error: *"The data couldn’t be read because it isn’t in the correct format."*
This occurs because the FastAPI backend returns `parsed_filters` with numeric values (e.g. `{"pe_max": 20}`), but the iOS `NLScreenerResponse` strongly types `parsedFilters` as `[String: String]?`. Swift's `JSONDecoder` immediately throws a `typeMismatch`.

## Action Plan

### Option A: Coerce strings on the Backend (Recommended)
This approach prevents having to write a custom type-erased `AnyCodable` wrapper in Swift, keeping the iOS models clean.

1. **Modify `backend/services/nl_screener.py`**
   Find where `response_data` is constructed at the end of the file:
   ```python
   # Convert all filter values to strings for iOS compatibility
   stringified_filters = {str(k): str(v) for k, v in filters.items()}
   
   response_data = {
       "parsed_filters": stringified_filters,
       "results": results
   }
   ```
   *Note: Ensure you stringify them AFTER the SQL query building block, because the SQL parameterized queries (`params["pe_max"] = filters["pe_max"]`) might require raw numbers for correct SQLite parameter binding.*

### Option B: Fix the iOS Model (Alternative)
If you prefer Swift to handle heterogenous dictionaries:

1. **Modify `ios/StockApp/stockme/stockme/Views/NLScreenerScreen.swift`**
   Change `[String: String]?` to `[String: AnyCodable]?` if your project has an `AnyCodable` library. Otherwise, you'll need to manually implement a custom `init(from decoder: Decoder)` to parse strings, ints, and doubles into string representations.
   
*(Given Option A is 2 lines of Python, it is the overwhelmingly preferred route.)*

## Additional Cleanup (Optional but Recommended)
- In `backend/routers/nl_screener.py`, explicitly define the response model in the router to catch these contract breaches in the OpenAPI docs:
  ```python
  from typing import Dict, List, Any
  
  class NLScreenerResultOut(BaseModel):
      ticker: str
      company: str
      score: float
      reason: str
      sector: str
      
  class NLScreenerResponseOut(BaseModel):
      parsed_filters: Dict[str, str]  # Enforces stringification
      results: List[NLScreenerResultOut]
      
  @router.post("/api/v1/screener/natural-language", response_model=NLScreenerResponseOut)
  ```
