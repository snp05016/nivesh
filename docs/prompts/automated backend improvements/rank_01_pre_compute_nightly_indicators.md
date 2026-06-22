# Prompt 01: Pre-compute Nightly Indicators

**Category:** Performance

**Goal:** Analyze the backend architecture to address this specific issue.

**Problem Statement / Description:**
Implement a nightly cron job to pre-compute `compute_indicators()` for the top 500 Nifty stocks and cache them in Redis. This reduces the runtime blocking during user requests.

**Why it will improve the system:**
It removes severe bottlenecks, blocking I/O, and sequential execution overhead, making the backend rendering extremely fast.

**What you have to do:**
1. Read the relevant source files.
2. Design the fix conceptually.
3. Implement the changes using proper architecture boundaries.
4. Write tests to verify correctness.
