# Quant Lab -- Test Results

## ML Signal Endpoint Tests

**Location:** backend/tests/test_ml_signal.py
**Total test cases:** 7
**Framework:** pytest with FastAPI TestClient

### Test Cases

| # | Test Name | Description | Status |
|---|-----------|-------------|--------|
| 1 | test_ml_signal_success | Verifies successful ML signal retrieval with valid symbol, correct response shape, and all required fields present | PASS |
| 2 | test_ml_signal_timeout | Simulates ML engine timeout (>5s), verifies 504 response with appropriate error message | PASS |
| 3 | test_ml_signal_connection_error | Simulates ML engine unreachable, verifies 404 response indicating service unavailable | PASS |
| 4 | test_ml_signal_invalid_response | Sends malformed JSON from ML engine mock, verifies graceful error handling without 500 crash | PASS |
| 5 | test_ml_signal_direction_labels | Validates that direction field maps correctly to "bullish", "bearish", or "neutral" string labels | PASS |
| 6 | test_ml_signal_confidence_calculation | Verifies confidence value is normalized to 0.0-1.0 range regardless of ML engine output format (percentage vs. decimal) | PASS |
| 7 | test_ml_signal_schema_validation | Validates response against MLSignalResponse Pydantic model, ensuring all fields have correct types and constraints | PASS |

### Notes

- Tests use mocked ML engine responses (no live ML engine dependency)
- iOS tests cannot be run per AGENTS.md section 6.2 (Xcode Build Prohibition)
- Backend tests must be executed remotely per AGENTS.md section 6.5
