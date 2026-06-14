# Prompt 52: Migrate from Multiprocessing to Celery

**Category:** Bugs/Issues

**Goal:** Analyze the backend architecture to address this specific issue.

**Problem Statement / Description:**
Replace the fragile native `multiprocessing` spawn logic with Celery or RQ (Redis Queue) for production-grade task tracking and fault tolerance.

**Why it will improve the system:**
It hardens the system architecture, resolves brittle state handling, and ensures production-level fault tolerance.

**What you have to do:**
1. Read the relevant source files.
2. Design the fix conceptually.
3. Implement the changes using proper architecture boundaries.
4. Write tests to verify correctness.
