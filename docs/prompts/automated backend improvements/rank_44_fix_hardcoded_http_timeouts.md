# Prompt 44: Fix Hardcoded HTTP Timeouts

**Category:** Hardcoding

**Goal:** Analyze the backend architecture to address this specific issue.

**Problem Statement / Description:**
Replace hardcoded `timeout=8` or `timeout=10` values in `requests.get` with centralized global timeout configs to handle slow networks gracefully.

**Why it will improve the system:**
It decouples logic from data, allowing dynamic configuration and reducing the need for code deployments when market conditions change.

**What you have to do:**
1. Read the relevant source files.
2. Design the fix conceptually.
3. Implement the changes using proper architecture boundaries.
4. Write tests to verify correctness.
