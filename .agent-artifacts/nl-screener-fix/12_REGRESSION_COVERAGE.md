# Regression Coverage

## The Original Bug
The NL Screener feature crashed upon returning results containing numerical values for constraints (e.g. `{"pe_max": 20}`). Swift's strongly-typed JSON Decoder expects `[String: String]` for `parsedFilters`, resulting in a `DecodingError.typeMismatch` exception, mapped to the generic UI error *"The data couldn’t be read because it isn’t in the correct format."*

## Testing Mechanism
The exhaustive test suite ensures regression prevention at both ends of the system boundary:

### 1. Backend Serialization Prevention (Pydantic)
In `backend/tests/test_nl_screener_exhaustive.py`, the `test_valuation_filter` artificially injects `{"pe_max": 15}` as a raw integer from the mock LLM.
**Assertion:**
```python
assert response.json()["parsed_filters"]["pe_max"] == "15"
```
If the backend logic ever regresses to returning an integer `15`, this test immediately fails. The Pydantic model (`Dict[str, str]`) physically enforces this schema at serialization time, preventing the bug at the foundation.

### 2. Frontend Strict Typing (Swift)
In `ios/StockApp/stockme/stockmeTests/NLScreenerTests.swift`, the `testFailGracefullyOnInvalidJSON` test loads the raw fixture `malformed_old_response.json` (which contains `pe_max: 20` as an Int).
**Assertion:**
```swift
XCTAssertThrowsError(try JSONDecoder().decode(NLScreenerResponse.self, from: json)) { error in
    ...
    // Asserts that the exact internal enum is typeMismatch, not something else
}
```
Furthermore, the `testDecodeSuccessfulNLScreenerFixture` explicitly verifies that stringified representations are correctly assigned, asserting `XCTAssertEqual(response.parsedFilters?["pe_max"], "20")`.

These combined layers guarantee that the exact conditions that caused the original crash are caught simultaneously by the backend unit tests, and correctly trapped by iOS's structured decoding pipeline.
