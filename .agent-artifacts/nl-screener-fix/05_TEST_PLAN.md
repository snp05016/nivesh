# Test Plan for NL Screener Fix

## Objective
Verify that natural language queries containing numeric filter constraints successfully return a response that the iOS app can decode without the `typeMismatch` error.

## 1. Local Backend Verification (cURL/HTTPie)
Before touching the iOS app, verify the backend outputs strictly string values in `parsed_filters`.

**Command:**
```bash
curl -X POST http://localhost:8000/api/v1/screener/natural-language \
  -H "Content-Type: application/json" \
  -d '{"query": "banks with PE less than 15"}'
```

**Expected JSON:**
```json
{
  "parsed_filters": {
    "sector": "Banks",
    "pe_max": "15"  // MUST BE A STRING "15", NOT A NUMBER 15
  },
  "results": [ ... ]
}
```

## 2. Unit Testing (Pytest)
Add a test case in `backend/tests/` to ensure `nl_screener` handles numeric filters without crashing and returns strings.

```python
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_nl_screener_numeric_stringification():
    response = client.post("/api/v1/screener/natural-language", json={
        "query": "tech companies with pe under 30"
    })
    assert response.status_code == 200
    data = response.json()
    
    # Verify the dictionary values are all strings
    parsed_filters = data.get("parsed_filters", {})
    for key, val in parsed_filters.items():
        assert isinstance(val, str), f"Filter {key} must be string, got {type(val)}"
```

## 3. End-to-End iOS Verification
1. Launch the Nivesh iOS App in the Simulator.
2. Navigate to the **Markets** tab -> **NL Screener**.
3. Enter the query: `"banks with PE less than 20"` and tap Search.
4. **Expected Outcome:** The skeleton loader completes and displays a list of cards (e.g. HDFC Bank, ICICI Bank) rather than flashing "Failed to load results".
5. Enter a query with no numeric filters: `"give me top IT companies"`.
6. **Expected Outcome:** Successfully loads results.
