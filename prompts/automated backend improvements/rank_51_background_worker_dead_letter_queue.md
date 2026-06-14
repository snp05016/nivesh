# Prompt 51: Background Worker Dead-Letter Queue

**Category:** Bugs/Issues

**Goal:** Analyze the backend architecture to address this specific issue.

**Problem Statement / Description:**
Build a dead-letter queue (DLQ) in SQLite/Redis to catch and auto-restart analyses that fail inside the detached `multiprocessing.Process` worker.

**Why it will improve the system:**
It hardens the system architecture, resolves brittle state handling, and ensures production-level fault tolerance.

**What you have to do:**
1. Read the relevant source files.
2. Design the fix conceptually.
3. Implement the changes using proper architecture boundaries.
4. Write tests to verify correctness.
