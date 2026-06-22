# Prompt 49: Fix OrderedDict Memory Leak

**Category:** Bugs/Issues

**Goal:** Analyze the backend architecture to address this specific issue.

**Problem Statement / Description:**
Fix the in-memory `_CACHE` implementation in `scraper.py` by implementing a proper thread-safe LRU Cache with automatic background TTL eviction.

**Why it will improve the system:**
It hardens the system architecture, resolves brittle state handling, and ensures production-level fault tolerance.

**What you have to do:**
1. Read the relevant source files.
2. Design the fix conceptually.
3. Implement the changes using proper architecture boundaries.
4. Write tests to verify correctness.
