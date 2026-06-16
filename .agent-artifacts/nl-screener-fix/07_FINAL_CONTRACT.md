# Final Frontend-Backend Contract: NL Screener

## 1. Request
- **Endpoint:** `POST /api/v1/screener/natural-language`
- **Authentication:** None
- **Body Schema (JSON):**
  ```json
  {
    "query": "banks with PE less than 20"
  }
  ```

## 2. Successful Response (HTTP 200)
The backend enforces this exact schema via Pydantic `NLScreenerResponse`. All `parsed_filters` values are guaranteed to be strings.

```json
{
  "parsed_filters": {
    "sector": "Banks",
    "pe_max": "20"
  },
  "results": [
    {
      "ticker": "HDFCBANK.NS",
      "company": "HDFC Bank Limited",
      "score": 100.0,
      "reason": "PE 18.2 < 20, Sector matches Banks",
      "sector": "Financial Services"
    }
  ]
}
```

*Note: If no matches are found, `results` will be an empty array `[]`.*

## 3. Error Response (HTTP != 200)
If the backend encounters an unhandled exception or explicit HTTP exception, it returns a structured JSON payload:
```json
{
  "detail": "Descriptive error message from the server."
}
```
The iOS app uses `APIErrorResponse` to extract and display this exact `detail` string to the user.
