# Prompt 02: Parallelize Calibration Block

**Category:** Performance

**Goal:** Analyze the backend architecture to address this specific issue.

**Problem Statement / Description:**
Refactor the 8 sequential HTTP calls in `orchestrator.py`'s calibration block to run concurrently using `concurrent.futures.ThreadPoolExecutor`, saving ~40s per analysis.

**Why it will improve the system:**
It removes severe bottlenecks, blocking I/O, and sequential execution overhead, making the backend rendering extremely fast.

**What you have to do:**
1. Read the relevant source files.
2. Design the fix conceptually.
3. Implement the changes using proper architecture boundaries.
4. Write tests to verify correctness.
