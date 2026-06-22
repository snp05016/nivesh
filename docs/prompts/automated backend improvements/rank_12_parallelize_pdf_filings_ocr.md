# Prompt 12: Parallelize PDF Filings OCR

**Category:** Performance

**Goal:** Analyze the backend architecture to address this specific issue.

**Problem Statement / Description:**
Use a multiprocessing pool in `filings_extractor.py` to concurrently OCR and process multiple pages/documents of SEBI filings instead of doing them sequentially.

**Why it will improve the system:**
It removes severe bottlenecks, blocking I/O, and sequential execution overhead, making the backend rendering extremely fast.

**What you have to do:**
1. Read the relevant source files.
2. Design the fix conceptually.
3. Implement the changes using proper architecture boundaries.
4. Write tests to verify correctness.
