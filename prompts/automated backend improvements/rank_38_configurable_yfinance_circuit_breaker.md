# Prompt 38: Configurable yfinance Circuit Breaker

**Category:** Hardcoding

**Goal:** Analyze the backend architecture to address this specific issue.

**Problem Statement / Description:**
Remove the hardcoded `_YF_CIRCUIT_THRESHOLD = 3` and `_YF_CIRCUIT_TIMEOUT = 300` values, making them configurable environment variables.

**Why it will improve the system:**
It decouples logic from data, allowing dynamic configuration and reducing the need for code deployments when market conditions change.

**What you have to do:**
1. Read the relevant source files.
2. Design the fix conceptually.
3. Implement the changes using proper architecture boundaries.
4. Write tests to verify correctness.
