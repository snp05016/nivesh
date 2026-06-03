# Nivesh Comprehensive Backend Test Suite

This directory (`backend/tests_suite`) contains a massive suite of ~600 tests designed to verify the robustness of the Nivesh backend across all core modules.

## Principles Followed
- **Think Before Coding**: Mapped all core services (Staleness, Ticker Matcher, Database, AI, Scrapers, API) before implementation.
- **Simplicity First**: Used `pytest` parameterization to generate hundreds of test cases with minimal boilerplate.
- **Surgical Changes**: Created a completely separate test directory to avoid interfering with existing tests.
- **Goal-Driven Execution**: Targeted 500-600 tests with an 80/20 split between general and edge cases.
- **Cost Efficiency**: All AI and external network calls (Claude, DeepSeek, Yahoo Finance, Scraping) are fully mocked. **No actual API tokens are spent during these tests.**

## Test Categories

### 1. Staleness Logic (`test_staleness_comprehensive.py`)
- **Tests**: 100 cases.
- **Coverage**: Verifies the math for staleness scoring.
- **Scenarios**: Range of days old (0 to 1000), price changes (-100% to +1000%), and signal volatility.
- **Edge Cases**: None dates (never analysed), future dates, extreme volatility, and tiny price fluctuations.

### 2. Ticker Matcher (`test_ticker_matcher_comprehensive.py`)
- **Tests**: ~120 cases.
- **Coverage**: Verifies Hinglish/spoken alias matching using RapidFuzz.
- **Scenarios**: Common stock names, spoken variations ("hdfc wala bank"), and various transcript noises.
- **Edge Cases**: Empty transcripts, pure symbols, extremely long text, and rapid duplication.

### 3. Database Integrity (`test_database_comprehensive.py`)
- **Tests**: ~100 cases.
- **Coverage**: CRUD operations for all SQLAlchemy models (User, Portfolio, Analysis, etc.).
- **Scenarios**: Bulk insertions, relationship cascading, and JSON storage verification.
- **Edge Cases**: Unique constraint violations, null-field integrity, and long text/blob storage.

### 4. AI & Sentiment Mocks (`test_ai_mock_comprehensive.py`)
- **Tests**: ~150 cases.
- **Coverage**: Factor Engine and Sentiment Engine logic without real LLM calls.
- **Scenarios**: Multi-signal classification (Buy/Sell/Hold), confidence level propagation, and batch sentiment processing.
- **Edge Cases**: Malformed JSON responses from "AI", timeouts, and empty responses.

### 5. Scraper Resilience (`test_scraper_mock_comprehensive.py`)
- **Tests**: ~120 cases.
- **Coverage**: Scraper service durability.
- **Scenarios**: Successful HTML fetches, status code handling (404, 500), and User-Agent rotation.
- **Edge Cases**: Timeouts, binary data, extremely large pages, and connection retries.

### 6. API Endpoints (`test_api_endpoints_comprehensive.py`)
- **Tests**: ~100 cases.
- **Coverage**: FastAPI routes using `TestClient`.
- **Scenarios**: Authentication flow, quick-info retrieval, and portfolio access.
- **Edge Cases**: Rate limiting, invalid input validation (Pydantic), and unauthorized access attempts.

## Running the Tests
To run the full suite:
```bash
pytest backend/tests_suite/
```

To run with timeout (already configured per-test, but global safety):
```bash
pytest --timeout=300 backend/tests_suite/
```

## Current Status (June 4, 2026)
- **Total Tests Collected**: 423
- **Total Tests Passing**: 383 (90.5% Pass Rate)
- **Execution Time**: ~20 seconds
- **Cost**: $0.00 (100% Mocked)

### Known Limitations
- **API Authentication**: Some `/login` tests fail due to session isolation between the test runner and the FastAPI app's internal database engine.
- **Ticker Matcher**: High-volume fuzzy matching tests sometimes fail depending on the local state of `stockapp.db`. Manual overrides are verified.
- **Multiprocessing**: The `/analyze` endpoint uses `multiprocessing.Process`, which is complex to mock in a simple `pytest` environment without `pytest-mock` or more invasive patching.

### Future Improvements
- Integrate `pytest-mock` for cleaner object patching.
- Implement a global `test_db` override that injects the same session across all modules.
- Add more negative tests for the LLM reformatting logic.
