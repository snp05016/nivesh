# Prompt 05: Batch RRG Quadrant Calculation

**Category:** Performance

**Goal:** Analyze the backend architecture to address this specific issue.

**Problem Statement / Description:**
Move the Relative Rotation Graph (RRG) calculations out of the request-response cycle and into a nightly batch job that writes to the database.

**Why it will improve the system:**
It removes severe bottlenecks, blocking I/O, and sequential execution overhead, making the backend rendering extremely fast.

**What you have to do:**
1. Read the relevant source files.
2. Design the fix conceptually.
3. Implement the changes using proper architecture boundaries.
4. Write tests to verify correctness.
