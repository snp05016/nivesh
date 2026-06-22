# Prompt 59: Unify the Fragmentation of Caches

**Category:** Bugs/Issues

**Goal:** Analyze the backend architecture to address this specific issue.

**Problem Statement / Description:**
Consolidate `disk_cache.py`, the in-memory dicts in `scraper.py`, and DB caching into a single `CacheService` interface for predictability.

**Why it will improve the system:**
It hardens the system architecture, resolves brittle state handling, and ensures production-level fault tolerance.

**What you have to do:**
1. Read the relevant source files.
2. Design the fix conceptually.
3. Implement the changes using proper architecture boundaries.
4. Write tests to verify correctness.
