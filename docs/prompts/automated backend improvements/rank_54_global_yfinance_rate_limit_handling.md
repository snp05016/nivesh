# Prompt 54: Global yfinance Rate Limit Handling

**Category:** Bugs/Issues

**Goal:** Analyze the backend architecture to address this specific issue.

**Problem Statement / Description:**
Implement a global Token Bucket rate limiter for `yfinance` to prevent HTTP 429 errors from crashing the backend during extreme volume scans.

**Why it will improve the system:**
It hardens the system architecture, resolves brittle state handling, and ensures production-level fault tolerance.

**What you have to do:**
1. Read the relevant source files.
2. Design the fix conceptually.
3. Implement the changes using proper architecture boundaries.
4. Write tests to verify correctness.
