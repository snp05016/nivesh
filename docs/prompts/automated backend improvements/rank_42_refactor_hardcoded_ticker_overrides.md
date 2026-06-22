# Prompt 42: Refactor Hardcoded Ticker Overrides

**Category:** Hardcoding

**Goal:** Analyze the backend architecture to address this specific issue.

**Problem Statement / Description:**
Move the `_NSE_TICKER_OVERRIDES` dictionary (e.g. 'JITFINFRA') into the database so new oddball tickers can be fixed without a code deployment.

**Why it will improve the system:**
It decouples logic from data, allowing dynamic configuration and reducing the need for code deployments when market conditions change.

**What you have to do:**
1. Read the relevant source files.
2. Design the fix conceptually.
3. Implement the changes using proper architecture boundaries.
4. Write tests to verify correctness.
