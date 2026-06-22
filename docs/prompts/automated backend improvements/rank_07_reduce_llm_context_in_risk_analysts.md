# Prompt 07: Reduce LLM Context in Risk Analysts

**Category:** Performance

**Goal:** Analyze the backend architecture to address this specific issue.

**Problem Statement / Description:**
Enforce strict length limits (e.g. 400 words) for the Aggressive, Neutral, and Conservative risk analysts to drastically reduce token consumption and generation time.

**Why it will improve the system:**
It removes severe bottlenecks, blocking I/O, and sequential execution overhead, making the backend rendering extremely fast.

**What you have to do:**
1. Read the relevant source files.
2. Design the fix conceptually.
3. Implement the changes using proper architecture boundaries.
4. Write tests to verify correctness.
