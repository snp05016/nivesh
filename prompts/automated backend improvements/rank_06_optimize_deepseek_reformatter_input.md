# Prompt 06: Optimize DeepSeek Reformatter Input

**Category:** Performance

**Goal:** Analyze the backend architecture to address this specific issue.

**Problem Statement / Description:**
Create an `_extract_final_conclusion` function to truncate the 8000-character raw output sent to the DeepSeek reformatter, sending only the PM decision to save processing time.

**Why it will improve the system:**
It removes severe bottlenecks, blocking I/O, and sequential execution overhead, making the backend rendering extremely fast.

**What you have to do:**
1. Read the relevant source files.
2. Design the fix conceptually.
3. Implement the changes using proper architecture boundaries.
4. Write tests to verify correctness.
